"""Operaciones CRUD de QuickTrack sobre MongoDB (IE7, IE8).

Módulo reutilizable: lo usan demo_crud.py y la API REST (carpeta api).
Todas las funciones reciben la base de datos de pymongo (`db`) como primer
parámetro y lanzan excepciones propias que la API puede traducir a HTTP:

    ValidacionError   -> 400  datos de entrada inválidos
    NoEncontradoError -> 404  el documento no existe
    ConflictoError    -> 409  duplicado o regla de negocio incumplida

Reglas de negocio:
    * Una orden nace "En preparación" y su seguimiento se crea con ella.
    * Flujo de estados: En preparación -> En tránsito -> Entregado.
      Se puede cancelar desde En preparación o En tránsito.
      Entregado y Cancelado son estados finales.
    * El estado de la orden y el de su seguimiento se mantienen sincronizados.
    * El total solo se corrige mientras la orden está abierta.
    * Solo las órdenes entregadas pueden valorarse, una vez cada una.
    * Por defecto solo se eliminan órdenes canceladas o en preparación.
"""
import logging
import math
import os
import re
from datetime import datetime, timezone

from pymongo import ASCENDING, DESCENDING, MongoClient
from pymongo.collation import Collation, CollationStrength
from pymongo.errors import DuplicateKeyError, PyMongoError

log = logging.getLogger("quicktrack_crud")

COL_ORDENES = "ordenes_entrega"
COL_CLIENTES = "clientes"
COL_RUTAS = "rutas"
COL_SEGUIMIENTO = "seguimiento"
COL_VALORACIONES = "valoraciones"

ESTADO_INICIAL = "En preparación"
ESTADOS_ORDEN = ("En preparación", "En tránsito", "Entregado", "Cancelado")
ESTADOS_ABIERTOS = ("En preparación", "En tránsito")
ESTADOS_ELIMINABLES = ("En preparación", "Cancelado")
TRANSICIONES = {
    "En preparación": ("En tránsito", "Cancelado"),
    "En tránsito": ("Entregado", "Cancelado"),
    "Entregado": (),
    "Cancelado": (),
}
MEDIOS_PAGO = ("Tarjeta", "Efectivo", "Transferencia")

RE_ORDEN = re.compile(r"orden_[A-Za-z0-9_]{1,40}")
RE_RUTA = re.compile(r"ruta_[A-Za-z0-9_]{1,40}")

# Filtros de texto sin distinguir mayúsculas ni tildes ("peru" = "Perú") y orden
# numérico de los ids de texto (ruta_2 antes que ruta_10).
COLACION_ES = Collation(locale="es", strength=CollationStrength.PRIMARY, numericOrdering=True)


class QuickTrackError(Exception):
    """Base de los errores controlados del CRUD."""


class ValidacionError(QuickTrackError):
    """Dato de entrada inválido (HTTP 400)."""


class NoEncontradoError(QuickTrackError):
    """El documento solicitado no existe (HTTP 404)."""


class ConflictoError(QuickTrackError):
    """Duplicado o regla de negocio incumplida (HTTP 409)."""


# ---------------------------------------------------------------- utilidades
def ahora():
    return datetime.now(timezone.utc)


def conectar(uri=None, nombre_db=None):
    """Abre la conexión y devuelve (cliente, db). La URI viene de MONGO_URI."""
    uri = uri or os.getenv("MONGO_URI")
    if not uri:
        raise RuntimeError("Falta la URI de conexión: defina la variable de entorno MONGO_URI")
    cliente = MongoClient(uri, serverSelectionTimeoutMS=8000)
    cliente.admin.command("ping")
    return cliente, cliente[nombre_db or os.getenv("MONGO_DB", "QuickTrack")]


def serializar(valor):
    """Convierte fechas a texto ISO para poder devolver los documentos como JSON."""
    if isinstance(valor, datetime):
        return valor.isoformat()
    if isinstance(valor, dict):
        return {clave: serializar(v) for clave, v in valor.items()}
    if isinstance(valor, (list, tuple)):
        return [serializar(v) for v in valor]
    return valor


# -------------------------------------------------------------- validaciones
def _validar_id_orden(orden_id):
    if not isinstance(orden_id, str) or not RE_ORDEN.fullmatch(orden_id):
        raise ValidacionError("El id de orden debe ser un texto con formato orden_<identificador>")
    return orden_id


def _validar_id_ruta(ruta_id):
    if not isinstance(ruta_id, str) or not RE_RUTA.fullmatch(ruta_id):
        raise ValidacionError("El id de ruta debe ser un texto con formato ruta_<identificador>")
    return ruta_id


def _validar_cliente_id(valor):
    if isinstance(valor, bool):
        raise ValidacionError("El id de cliente debe ser un entero positivo")
    if isinstance(valor, str):
        texto = valor.strip()
        texto = texto[4:] if texto.startswith("cli_") else texto
        if not texto.isdigit():
            raise ValidacionError("El id de cliente debe ser un entero positivo")
        valor = int(texto)
    if not isinstance(valor, int) or valor <= 0:
        raise ValidacionError("El id de cliente debe ser un entero positivo")
    return valor


def _validar_total(valor):
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        raise ValidacionError("El total debe ser un número")
    if not math.isfinite(valor):
        raise ValidacionError("El total debe ser un número finito")
    total = round(float(valor), 2)
    if total <= 0:
        raise ValidacionError("El total debe ser mayor que 0")
    return total


def _validar_medio_pago(valor):
    if valor not in MEDIOS_PAGO:
        raise ValidacionError(f"Medio de pago inválido. Opciones: {', '.join(MEDIOS_PAGO)}")
    return valor


def _validar_estado(valor):
    if valor not in ESTADOS_ORDEN:
        raise ValidacionError(f"Estado inválido. Opciones: {', '.join(ESTADOS_ORDEN)}")
    return valor


def _validar_fecha(valor):
    if valor is None:
        return ahora()
    if isinstance(valor, datetime):
        return valor
    if isinstance(valor, str):
        try:
            return datetime.fromisoformat(valor.strip())
        except ValueError:
            pass
    raise ValidacionError("La fecha debe ser un datetime o un texto ISO (por ejemplo 2024-05-31)")


def _validar_puntaje(valor):
    if isinstance(valor, bool) or not isinstance(valor, int) or not 1 <= valor <= 5:
        raise ValidacionError("El puntaje debe ser un entero entre 1 y 5")
    return valor


def _validar_comentario(valor):
    if not isinstance(valor, str) or not valor.strip():
        raise ValidacionError("El comentario no puede estar vacío")
    if len(valor.strip()) > 300:
        raise ValidacionError("El comentario no puede superar los 300 caracteres")
    return valor.strip()


def _validar_entero(valor, campo, minimo, maximo):
    if isinstance(valor, str) and valor.strip().isdigit():
        valor = int(valor)
    if isinstance(valor, bool) or not isinstance(valor, int) or not minimo <= valor <= maximo:
        raise ValidacionError(f"{campo} debe ser un entero entre {minimo} y {maximo}")
    return valor


def _id_seguimiento(orden_id):
    return "seg_" + orden_id[len("orden_"):]


def _id_valoracion(orden_id):
    return "val_" + orden_id[len("orden_"):]


def _siguiente_id_orden(db):
    maximo = 0
    for doc in db[COL_ORDENES].find({}, {"_id": 1}):
        coincidencia = re.fullmatch(r"orden_(\d+)", str(doc["_id"]))
        if coincidencia:
            maximo = max(maximo, int(coincidencia.group(1)))
    return f"orden_{maximo + 1}"


def _buscar_orden(db, orden_id, campos=None):
    orden = db[COL_ORDENES].find_one({"_id": orden_id}, campos)
    if orden is None:
        raise NoEncontradoError(f"La orden {orden_id} no existe")
    return orden


# -------------------------------------------------------------------- CREATE
def crear_orden(db, cliente_id, ruta_id, total, medio_pago, fecha_envio=None, orden_id=None):
    """Crea una orden y su seguimiento inicial. Si el seguimiento falla, revierte la orden."""
    cliente_id = _validar_cliente_id(cliente_id)
    ruta_id = _validar_id_ruta(ruta_id)
    total = _validar_total(total)
    medio_pago = _validar_medio_pago(medio_pago)
    fecha_envio = _validar_fecha(fecha_envio)
    if orden_id is not None:
        orden_id = _validar_id_orden(orden_id)

    if db[COL_CLIENTES].find_one({"_id": cliente_id}, {"_id": 1}) is None:
        raise ValidacionError(f"El cliente {cliente_id} no existe")
    if db[COL_RUTAS].find_one({"_id": ruta_id}, {"_id": 1}) is None:
        raise ValidacionError(f"La ruta {ruta_id} no existe")

    orden = None
    for _ in range(1 if orden_id else 3):
        nuevo_id = orden_id or _siguiente_id_orden(db)
        candidata = {
            "_id": nuevo_id,
            "cliente_id": cliente_id,
            "ruta_id": ruta_id,
            "fecha_envio": fecha_envio,
            "estado": ESTADO_INICIAL,
            "medio_pago": medio_pago,
            "total": total,
        }
        try:
            db[COL_ORDENES].insert_one(candidata)
            orden = candidata
            break
        except DuplicateKeyError:
            if orden_id:
                log.warning("crear_orden: la orden %s ya existe", nuevo_id)
                raise ConflictoError(f"Ya existe la orden {nuevo_id}")
            log.warning("crear_orden: el id %s se ocupó mientras se creaba, se reintenta", nuevo_id)
    if orden is None:
        raise ConflictoError("No se pudo asignar un id de orden único; reintente")

    seguimiento = {
        "_id": _id_seguimiento(orden["_id"]),
        "orden_id": orden["_id"],
        "estado_actual": ESTADO_INICIAL,
        "historial": [{"estado": ESTADO_INICIAL, "fecha": ahora()}],
    }
    try:
        db[COL_SEGUIMIENTO].insert_one(seguimiento)
    except PyMongoError as error:
        db[COL_ORDENES].delete_one({"_id": orden["_id"]})
        log.error("crear_orden: falló el seguimiento de %s, se revirtió la orden: %s", orden["_id"], error)
        if isinstance(error, DuplicateKeyError):
            raise ConflictoError(
                f"Ya existía un seguimiento para {orden['_id']}; se revirtió la creación de la orden"
            ) from error
        raise

    log.info("Orden %s creada (cliente %s, ruta %s, total %.2f, %s)",
             orden["_id"], cliente_id, ruta_id, total, medio_pago)
    return {"orden": orden, "seguimiento": seguimiento}


def registrar_valoracion(db, orden_id, puntaje, comentario):
    """Registra la valoración de una orden entregada (una por orden)."""
    orden_id = _validar_id_orden(orden_id)
    puntaje = _validar_puntaje(puntaje)
    comentario = _validar_comentario(comentario)
    orden = _buscar_orden(db, orden_id, {"estado": 1})
    if orden["estado"] != "Entregado":
        raise ConflictoError(f"Solo se pueden valorar órdenes entregadas (estado actual: {orden['estado']})")

    valoracion = {
        "_id": _id_valoracion(orden_id),
        "orden_id": orden_id,
        "puntaje": puntaje,
        "comentario": comentario,
    }
    try:
        db[COL_VALORACIONES].insert_one(valoracion)
    except DuplicateKeyError:
        log.warning("registrar_valoracion: la orden %s ya tiene valoración", orden_id)
        raise ConflictoError(f"La orden {orden_id} ya tiene una valoración")
    log.info("Valoración de %s registrada (puntaje %d)", orden_id, puntaje)
    return valoracion


# ---------------------------------------------------------------------- READ
def leer_orden(db, orden_id, detalle=True):
    """Devuelve la orden; con detalle=True incluye su seguimiento y su valoración."""
    orden_id = _validar_id_orden(orden_id)
    orden = _buscar_orden(db, orden_id)
    if detalle:
        orden["seguimiento"] = db[COL_SEGUIMIENTO].find_one({"orden_id": orden_id})
        orden["valoracion"] = db[COL_VALORACIONES].find_one({"orden_id": orden_id})
    return orden


def _filtro_ordenes(estado=None, cliente_id=None):
    filtro = {}
    if estado is not None:
        filtro["estado"] = _validar_estado(estado)
    if cliente_id is not None:
        filtro["cliente_id"] = _validar_cliente_id(cliente_id)
    return filtro


def listar_ordenes(db, estado=None, cliente_id=None, limite=20, salto=0):
    """Lista órdenes (más recientes primero) con filtros opcionales y paginación."""
    filtro = _filtro_ordenes(estado, cliente_id)
    limite = _validar_entero(limite, "limite", 1, 100)
    salto = _validar_entero(salto, "salto", 0, 100000)
    cursor = (
        db[COL_ORDENES]
        .find(filtro)
        .sort([("fecha_envio", DESCENDING), ("_id", DESCENDING)])
        .skip(salto)
        .limit(limite)
    )
    return list(cursor)


def contar_ordenes(db, estado=None, cliente_id=None):
    """Cantidad de órdenes que cumplen los mismos filtros de listar_ordenes."""
    return db[COL_ORDENES].count_documents(_filtro_ordenes(estado, cliente_id))


# ------------------------------------------------------ lectura de catálogos
def _validar_texto_filtro(valor, campo):
    if not isinstance(valor, str) or not 1 <= len(valor.strip()) <= 80:
        raise ValidacionError(f"{campo} debe ser un texto de 1 a 80 caracteres")
    return valor.strip()


def _filtro_por_campo(campo, valor):
    return {} if valor is None else {campo: _validar_texto_filtro(valor, campo)}


def _paginar(db, coleccion, filtro, limite, salto):
    limite = _validar_entero(limite, "limite", 1, 100)
    salto = _validar_entero(salto, "salto", 0, 100000)
    cursor = (
        db[coleccion]
        .find(filtro)
        .collation(COLACION_ES)
        .sort("_id", ASCENDING)
        .skip(salto)
        .limit(limite)
    )
    return list(cursor)


def leer_cliente(db, cliente_id):
    cliente_id = _validar_cliente_id(cliente_id)
    cliente = db[COL_CLIENTES].find_one({"_id": cliente_id})
    if cliente is None:
        raise NoEncontradoError(f"El cliente {cliente_id} no existe")
    return cliente


def listar_clientes(db, pais=None, limite=20, salto=0):
    """Lista clientes por id; el filtro de país no distingue mayúsculas ni tildes."""
    return _paginar(db, COL_CLIENTES, _filtro_por_campo("pais", pais), limite, salto)


def contar_clientes(db, pais=None):
    return db[COL_CLIENTES].count_documents(_filtro_por_campo("pais", pais), collation=COLACION_ES)


def leer_ruta(db, ruta_id):
    ruta_id = _validar_id_ruta(ruta_id)
    ruta = db[COL_RUTAS].find_one({"_id": ruta_id})
    if ruta is None:
        raise NoEncontradoError(f"La ruta {ruta_id} no existe")
    return ruta


def listar_rutas(db, zona=None, limite=20, salto=0):
    """Lista rutas por id (ruta_2 antes que ruta_10); el filtro de zona no distingue mayúsculas."""
    return _paginar(db, COL_RUTAS, _filtro_por_campo("zona", zona), limite, salto)


def contar_rutas(db, zona=None):
    return db[COL_RUTAS].count_documents(_filtro_por_campo("zona", zona), collation=COLACION_ES)


# -------------------------------------------------------------------- UPDATE
def avanzar_estado(db, orden_id, nuevo_estado):
    """Cambia el estado de la orden y lo registra en su seguimiento (orden e historial)."""
    orden_id = _validar_id_orden(orden_id)
    nuevo = _validar_estado(nuevo_estado)
    actual = _buscar_orden(db, orden_id, {"estado": 1})["estado"]

    permitidas = TRANSICIONES.get(actual, ())
    if nuevo not in permitidas:
        detalle = ", ".join(permitidas) if permitidas else "ninguna (estado final)"
        log.warning("avanzar_estado: %s no puede pasar de %s a %s", orden_id, actual, nuevo)
        raise ConflictoError(f"Transición no permitida: {actual} -> {nuevo}. Permitidas: {detalle}")

    # El filtro incluye el estado leído: si otro proceso lo cambió, no se pisa su cambio.
    resultado = db[COL_ORDENES].update_one({"_id": orden_id, "estado": actual}, {"$set": {"estado": nuevo}})
    if resultado.modified_count == 0:
        raise ConflictoError("La orden cambió de estado mientras se procesaba la solicitud; reintente")

    try:
        db[COL_SEGUIMIENTO].update_one(
            {"_id": _id_seguimiento(orden_id)},
            {
                "$set": {"estado_actual": nuevo},
                "$push": {"historial": {"estado": nuevo, "fecha": ahora()}},
                "$setOnInsert": {"orden_id": orden_id},
            },
            upsert=True,
        )
    except PyMongoError as error:
        db[COL_ORDENES].update_one({"_id": orden_id, "estado": nuevo}, {"$set": {"estado": actual}})
        log.error("avanzar_estado: falló el seguimiento de %s, se revirtió el estado: %s", orden_id, error)
        raise

    log.info("Orden %s: %s -> %s", orden_id, actual, nuevo)
    return {"orden_id": orden_id, "estado_anterior": actual, "estado_nuevo": nuevo}


def corregir_total(db, orden_id, nuevo_total):
    """Corrige el total de una orden abierta (En preparación o En tránsito)."""
    orden_id = _validar_id_orden(orden_id)
    nuevo_total = _validar_total(nuevo_total)
    orden = _buscar_orden(db, orden_id, {"estado": 1, "total": 1})
    if orden["estado"] not in ESTADOS_ABIERTOS:
        log.warning("corregir_total: %s está %s", orden_id, orden["estado"])
        raise ConflictoError(f"No se puede corregir el total de una orden {orden['estado']}")

    anterior = orden["total"]
    if anterior == nuevo_total:
        return {"orden_id": orden_id, "total_anterior": anterior, "total_nuevo": nuevo_total, "modificado": False}

    resultado = db[COL_ORDENES].update_one(
        {"_id": orden_id, "estado": {"$in": list(ESTADOS_ABIERTOS)}}, {"$set": {"total": nuevo_total}}
    )
    if resultado.matched_count == 0:
        raise ConflictoError("La orden se cerró mientras se corregía su total")
    log.info("Orden %s: total %.2f -> %.2f", orden_id, anterior, nuevo_total)
    return {"orden_id": orden_id, "total_anterior": anterior, "total_nuevo": nuevo_total, "modificado": True}


# -------------------------------------------------------------------- DELETE
def eliminar_orden(db, orden_id, forzar=False):
    """Elimina la orden junto con su seguimiento y su valoración (sin dejar huérfanos).

    Sin `forzar` solo se eliminan órdenes canceladas o en preparación. Se borran
    primero los dependientes y al final la orden: si algo falla a mitad de camino
    queda una orden visible y reparable, no documentos huérfanos.
    """
    orden_id = _validar_id_orden(orden_id)
    orden = _buscar_orden(db, orden_id, {"estado": 1})
    if not forzar and orden["estado"] not in ESTADOS_ELIMINABLES:
        log.warning("eliminar_orden: %s está %s y no se elimina", orden_id, orden["estado"])
        raise ConflictoError(
            f"No se puede eliminar una orden {orden['estado']}; solo canceladas o en preparación"
        )

    seguimientos = db[COL_SEGUIMIENTO].delete_many({"orden_id": orden_id}).deleted_count
    valoraciones = db[COL_VALORACIONES].delete_many({"orden_id": orden_id}).deleted_count
    db[COL_ORDENES].delete_one({"_id": orden_id})
    log.info("Orden %s eliminada (seguimientos: %d, valoraciones: %d)", orden_id, seguimientos, valoraciones)
    return {"orden_id": orden_id, "seguimientos_eliminados": seguimientos, "valoraciones_eliminadas": valoraciones}


# ------------------------------------------------- validación e integridad
def verificar_consistencia(db, orden_id):
    """Revisa una orden y devuelve la lista de problemas encontrados (vacía si está sana)."""
    orden_id = _validar_id_orden(orden_id)
    orden = db[COL_ORDENES].find_one({"_id": orden_id})
    if orden is None:
        return [f"La orden {orden_id} no existe"]

    problemas = []
    seguimiento = db[COL_SEGUIMIENTO].find_one({"orden_id": orden_id})
    if seguimiento is None:
        problemas.append("la orden no tiene seguimiento")
    else:
        if seguimiento.get("estado_actual") != orden["estado"]:
            problemas.append(
                f"estado_actual del seguimiento ({seguimiento.get('estado_actual')}) "
                f"distinto del estado de la orden ({orden['estado']})"
            )
        historial = seguimiento.get("historial") or []
        if not historial:
            problemas.append("el historial de seguimiento está vacío")
        elif historial[-1].get("estado") != orden["estado"]:
            problemas.append("el último evento del historial no coincide con el estado de la orden")
    if db[COL_CLIENTES].find_one({"_id": orden.get("cliente_id")}, {"_id": 1}) is None:
        problemas.append("el cliente de la orden no existe")
    if db[COL_RUTAS].find_one({"_id": orden.get("ruta_id")}, {"_id": 1}) is None:
        problemas.append("la ruta de la orden no existe")
    if db[COL_VALORACIONES].find_one({"orden_id": orden_id}, {"_id": 1}) and orden["estado"] != "Entregado":
        problemas.append("hay una valoración sobre una orden no entregada")
    return problemas


def auditar_integridad(db):
    """Audita toda la base. Pensada para el volumen del proyecto (cientos de documentos)."""
    ordenes = list(db[COL_ORDENES].find({}, {"cliente_id": 1, "ruta_id": 1, "estado": 1}))
    clientes = {d["_id"] for d in db[COL_CLIENTES].find({}, {"_id": 1})}
    rutas = {d["_id"] for d in db[COL_RUTAS].find({}, {"_id": 1})}
    seguimientos = list(db[COL_SEGUIMIENTO].find({}, {"orden_id": 1, "estado_actual": 1, "historial": 1}))
    valoraciones = list(db[COL_VALORACIONES].find({}, {"orden_id": 1}))

    estado_orden = {o["_id"]: o.get("estado") for o in ordenes}
    seguimiento_de = {s.get("orden_id"): s for s in seguimientos}

    inconsistentes = []
    for orden_id, estado in estado_orden.items():
        seg = seguimiento_de.get(orden_id)
        if seg is None:
            continue
        historial = seg.get("historial") or []
        ultimo = historial[-1].get("estado") if historial else None
        if seg.get("estado_actual") != estado or ultimo != estado:
            inconsistentes.append(orden_id)

    return {
        "totales": {
            "ordenes": len(ordenes),
            "seguimientos": len(seguimientos),
            "valoraciones": len(valoraciones),
        },
        "ordenes_sin_cliente": sorted(o["_id"] for o in ordenes if o.get("cliente_id") not in clientes),
        "ordenes_sin_ruta": sorted(o["_id"] for o in ordenes if o.get("ruta_id") not in rutas),
        "ordenes_sin_seguimiento": sorted(i for i in estado_orden if i not in seguimiento_de),
        "seguimientos_huerfanos": sorted(s["_id"] for s in seguimientos if s.get("orden_id") not in estado_orden),
        "valoraciones_huerfanas": sorted(v["_id"] for v in valoraciones if v.get("orden_id") not in estado_orden),
        "seguimientos_inconsistentes": sorted(inconsistentes),
    }


def resumen_auditoria(auditoria):
    """Cantidad de problemas por categoría (para comparar auditorías y mostrarlas)."""
    return {clave: len(valor) for clave, valor in auditoria.items() if isinstance(valor, list)}


def sincronizar_seguimiento(db, orden_id):
    """Alinea el seguimiento con el estado de la orden, que es la fuente de verdad."""
    orden_id = _validar_id_orden(orden_id)
    estado = _buscar_orden(db, orden_id, {"estado": 1})["estado"]
    seguimiento = db[COL_SEGUIMIENTO].find_one({"orden_id": orden_id}, {"estado_actual": 1, "historial": 1})

    if seguimiento is None:
        db[COL_SEGUIMIENTO].insert_one(
            {
                "_id": _id_seguimiento(orden_id),
                "orden_id": orden_id,
                "estado_actual": estado,
                "historial": [{"estado": estado, "fecha": ahora()}],
            }
        )
        log.info("Seguimiento de %s creado durante la sincronización", orden_id)
        return {"orden_id": orden_id, "corregido": True, "accion": "seguimiento creado"}

    cambios = {}
    if seguimiento.get("estado_actual") != estado:
        cambios["$set"] = {"estado_actual": estado}
    historial = seguimiento.get("historial") or []
    if not historial or historial[-1].get("estado") != estado:
        cambios["$push"] = {"historial": {"estado": estado, "fecha": ahora()}}
    if not cambios:
        return {"orden_id": orden_id, "corregido": False, "accion": "sin cambios"}

    db[COL_SEGUIMIENTO].update_one({"_id": seguimiento["_id"]}, cambios)
    log.info("Seguimiento de %s sincronizado con el estado %s", orden_id, estado)
    return {"orden_id": orden_id, "corregido": True, "accion": f"sincronizado con {estado}"}


def reparar_seguimientos(db, ejecutar=False):
    """Detecta (y con ejecutar=True corrige) seguimientos desalineados de su orden."""
    auditoria = auditar_integridad(db)
    pendientes = auditoria["seguimientos_inconsistentes"] + auditoria["ordenes_sin_seguimiento"]
    corregidos = 0
    if ejecutar:
        for orden_id in pendientes:
            if sincronizar_seguimiento(db, orden_id)["corregido"]:
                corregidos += 1
    return {"detectados": len(pendientes), "corregidos": corregidos, "ejecutado": ejecutar}


def depurar_huerfanos(db, ejecutar=False):
    """Detecta (y con ejecutar=True elimina) seguimientos y valoraciones sin orden."""
    auditoria = auditar_integridad(db)
    seguimientos = auditoria["seguimientos_huerfanos"]
    valoraciones = auditoria["valoraciones_huerfanas"]
    if ejecutar:
        if seguimientos:
            db[COL_SEGUIMIENTO].delete_many({"_id": {"$in": seguimientos}})
        if valoraciones:
            db[COL_VALORACIONES].delete_many({"_id": {"$in": valoraciones}})
        log.info("Huérfanos eliminados: %d seguimientos, %d valoraciones", len(seguimientos), len(valoraciones))
    return {
        "seguimientos_huerfanos": len(seguimientos),
        "valoraciones_huerfanas": len(valoraciones),
        "ejecutado": ejecutar,
    }
