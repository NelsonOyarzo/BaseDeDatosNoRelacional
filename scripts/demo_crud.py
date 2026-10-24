"""Demostración de CRUD con validación sobre QuickTrack (IE7, IE8).

Simula la gestión de órdenes de entrega:
    1. Flujo completo: crear, leer, avanzar estados, corregir total, valorar.
    2. Cancelación y eliminación sin dejar documentos huérfanos.
    3. Errores provocados a propósito: el sistema debe rechazarlos.
    4. Integridad: detectar y corregir inconsistencias y huérfanos.

Todas las órdenes de prueba usan el prefijo `orden_test_` y se eliminan al
terminar, de modo que los resultados de las consultas C1 a C11 no cambian.

Uso:
    python scripts\\demo_crud.py
"""
import csv
import getpass
import logging
import os
import sys
from pathlib import Path

from pymongo.errors import PyMongoError

import quicktrack_crud as crud

BASE_DIR = Path(__file__).resolve().parent
SALIDA_DIR = BASE_DIR.parent / "evidencias"
SALIDA_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler(SALIDA_DIR / "crud.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger("demo_crud")

PREFIJO_PRUEBA = "orden_test_"
CLIENTE_PRUEBA = 1
RUTA_PRUEBA = "ruta_1"

resultados = []


# ---------------------------------------------------------------- utilidades
def titulo(texto):
    log.info("")
    log.info("=" * 70)
    log.info(texto)
    log.info("=" * 70)


def registrar(escenario, caso, ok, detalle=""):
    resultados.append(
        {"escenario": escenario, "caso": caso, "resultado": "OK" if ok else "FALLO", "detalle": detalle}
    )
    if ok:
        log.info("[OK]    %s | %s %s", escenario, caso, detalle)
    else:
        log.error("[FALLO] %s | %s %s", escenario, caso, detalle)


def comprobar(escenario, caso, condicion, detalle=""):
    registrar(escenario, caso, bool(condicion), detalle)


def esperar_error(escenario, caso, clase, funcion, *args, **kwargs):
    """La operación debe ser rechazada con la excepción indicada."""
    try:
        funcion(*args, **kwargs)
    except clase as error:
        registrar(escenario, caso, True, f"rechazado ({clase.__name__}): {error}")
    except Exception as error:
        registrar(escenario, caso, False, f"se esperaba {clase.__name__} y llegó {type(error).__name__}: {error}")
    else:
        registrar(escenario, caso, False, "la operación no fue rechazada")


def contar_pruebas(db):
    patron = {"$regex": "^" + PREFIJO_PRUEBA}
    return (
        db[crud.COL_ORDENES].count_documents({"_id": patron})
        + db[crud.COL_SEGUIMIENTO].count_documents({"orden_id": patron})
        + db[crud.COL_VALORACIONES].count_documents({"orden_id": patron})
    )


def limpiar_pruebas(db):
    """Elimina solo documentos de prueba (orden_test_*), nunca datos reales."""
    patron = {"$regex": "^" + PREFIJO_PRUEBA}
    eliminados = db[crud.COL_VALORACIONES].delete_many({"orden_id": patron}).deleted_count
    eliminados += db[crud.COL_SEGUIMIENTO].delete_many({"orden_id": patron}).deleted_count
    eliminados += db[crud.COL_ORDENES].delete_many({"_id": patron}).deleted_count
    return eliminados


def orden_de_prueba(db, numero, total=85000, medio_pago="Tarjeta"):
    return crud.crear_orden(
        db, CLIENTE_PRUEBA, RUTA_PRUEBA, total, medio_pago, orden_id=f"{PREFIJO_PRUEBA}{numero}"
    )["orden"]["_id"]


# --------------------------------------------------------------- escenarios
def escenario_flujo_completo(db):
    esc = "1 Flujo completo"
    titulo("ESCENARIO 1: ciclo de vida de una orden (crear, leer, actualizar, valorar)")
    oid = orden_de_prueba(db, "001")

    orden = crud.leer_orden(db, oid)
    comprobar(esc, "Crear: orden queda En preparación", orden["estado"] == "En preparación")
    comprobar(esc, "Crear: seguimiento inicial creado",
              orden["seguimiento"] is not None and orden["seguimiento"]["estado_actual"] == "En preparación")
    comprobar(esc, "Leer: datos de la orden coinciden",
              orden["cliente_id"] == CLIENTE_PRUEBA and orden["total"] == 85000.0)

    crud.avanzar_estado(db, oid, "En tránsito")
    orden = crud.leer_orden(db, oid)
    comprobar(esc, "Actualizar: orden pasa a En tránsito",
              orden["estado"] == "En tránsito" and orden["seguimiento"]["estado_actual"] == "En tránsito")

    cambio = crud.corregir_total(db, oid, 92500.5)
    comprobar(esc, "Actualizar: total corregido", cambio["modificado"] and
              crud.leer_orden(db, oid, detalle=False)["total"] == 92500.5,
              f"{cambio['total_anterior']} -> {cambio['total_nuevo']}")

    crud.avanzar_estado(db, oid, "Entregado")
    crud.registrar_valoracion(db, oid, 5, "Entrega puntual (prueba)")
    orden = crud.leer_orden(db, oid)
    secuencia = [e["estado"] for e in orden["seguimiento"]["historial"]]
    comprobar(esc, "Historial registra cada cambio",
              secuencia == ["En preparación", "En tránsito", "Entregado"], " -> ".join(secuencia))
    comprobar(esc, "Valoración registrada",
              orden["valoracion"] is not None and orden["valoracion"]["puntaje"] == 5)
    problemas = crud.verificar_consistencia(db, oid)
    comprobar(esc, "Orden consistente de punta a punta", not problemas, "; ".join(problemas))
    return oid


def escenario_cancelacion(db):
    esc = "2 Cancelar y eliminar"
    titulo("ESCENARIO 2: cancelación y eliminación sin dejar huérfanos")
    oid = orden_de_prueba(db, "002", total=45000, medio_pago="Efectivo")
    crud.avanzar_estado(db, oid, "Cancelado")
    comprobar(esc, "Orden cancelada",
              crud.leer_orden(db, oid, detalle=False)["estado"] == "Cancelado")

    resultado = crud.eliminar_orden(db, oid)
    comprobar(esc, "Eliminar: se borró el seguimiento asociado", resultado["seguimientos_eliminados"] == 1)
    restos = (
        db[crud.COL_ORDENES].count_documents({"_id": oid})
        + db[crud.COL_SEGUIMIENTO].count_documents({"orden_id": oid})
        + db[crud.COL_VALORACIONES].count_documents({"orden_id": oid})
    )
    comprobar(esc, "Eliminar: no quedan documentos huérfanos", restos == 0, f"documentos restantes: {restos}")


def escenario_errores(db, oid_entregada):
    esc = "3 Errores provocados"
    titulo("ESCENARIO 3: entradas inválidas y reglas de negocio (deben ser rechazadas)")
    antes = crud.leer_orden(db, oid_entregada, detalle=False)
    abierta = orden_de_prueba(db, "004")

    def nueva(numero, **cambios):
        datos = {"cliente_id": CLIENTE_PRUEBA, "ruta_id": RUTA_PRUEBA, "total": 50000,
                 "medio_pago": "Tarjeta", "orden_id": f"{PREFIJO_PRUEBA}{numero}"}
        datos.update(cambios)
        return crud.crear_orden(db, **datos)

    esperar_error(esc, "Cliente inexistente", crud.ValidacionError, nueva, "E01", cliente_id=99999)
    esperar_error(esc, "Ruta inexistente", crud.ValidacionError, nueva, "E02", ruta_id="ruta_99999")
    esperar_error(esc, "Total negativo", crud.ValidacionError, nueva, "E03", total=-500)
    esperar_error(esc, "Total no numérico", crud.ValidacionError, nueva, "E04", total="abc")
    esperar_error(esc, "Medio de pago inválido", crud.ValidacionError, nueva, "E05", medio_pago="Cheque")
    esperar_error(esc, "Id de orden duplicado", crud.ConflictoError, nueva, "001")
    esperar_error(esc, "Id con operador de MongoDB (inyección)", crud.ValidacionError,
                  crud.leer_orden, db, {"$ne": None})
    esperar_error(esc, "Leer orden inexistente", crud.NoEncontradoError,
                  crud.leer_orden, db, PREFIJO_PRUEBA + "404")
    esperar_error(esc, "Transición no permitida (Entregado -> En preparación)", crud.ConflictoError,
                  crud.avanzar_estado, db, oid_entregada, "En preparación")
    esperar_error(esc, "Saltar etapas (En preparación -> Entregado)", crud.ConflictoError,
                  crud.avanzar_estado, db, abierta, "Entregado")
    esperar_error(esc, "Corregir total de orden entregada", crud.ConflictoError,
                  crud.corregir_total, db, oid_entregada, 1000)
    esperar_error(esc, "Valoración duplicada (índice único)", crud.ConflictoError,
                  crud.registrar_valoracion, db, oid_entregada, 3, "Segundo intento")
    esperar_error(esc, "Puntaje fuera de rango", crud.ValidacionError,
                  crud.registrar_valoracion, db, abierta, 9, "Puntaje inválido")
    esperar_error(esc, "Valorar orden no entregada", crud.ConflictoError,
                  crud.registrar_valoracion, db, abierta, 4, "Aún no se entrega")
    esperar_error(esc, "Eliminar orden entregada sin autorización", crud.ConflictoError,
                  crud.eliminar_orden, db, oid_entregada)

    despues = crud.leer_orden(db, oid_entregada, detalle=False)
    comprobar(esc, "Los datos originales no cambiaron tras los rechazos", antes == despues)
    comprobar(esc, "La orden abierta sigue En preparación",
              crud.leer_orden(db, abierta, detalle=False)["estado"] == "En preparación")


def escenario_integridad(db, base):
    esc = "4 Integridad"
    titulo("ESCENARIO 4: detección y corrección de inconsistencias")
    log.info("Estado inicial de la base (antes de las pruebas): %s", crud.resumen_auditoria(base))

    # 4a. Seguimiento desalineado de su orden
    oid = orden_de_prueba(db, "005")
    db[crud.COL_SEGUIMIENTO].update_one({"orden_id": oid}, {"$set": {"estado_actual": "Entregado"}})
    problemas = crud.verificar_consistencia(db, oid)
    comprobar(esc, "Detecta seguimiento desalineado", len(problemas) > 0, "; ".join(problemas))
    comprobar(esc, "La auditoría global lo incluye",
              oid in crud.auditar_integridad(db)["seguimientos_inconsistentes"])
    crud.sincronizar_seguimiento(db, oid)
    comprobar(esc, "Corrige el seguimiento con sincronizar_seguimiento",
              not crud.verificar_consistencia(db, oid))

    # 4b. Valoración huérfana (sin orden)
    db[crud.COL_VALORACIONES].insert_one(
        {"_id": "val_test_huerfana", "orden_id": PREFIJO_PRUEBA + "999", "puntaje": 3, "comentario": "Huérfana de prueba"}
    )
    auditoria = crud.auditar_integridad(db)
    comprobar(esc, "Detecta valoración huérfana", "val_test_huerfana" in auditoria["valoraciones_huerfanas"])
    if not base["seguimientos_huerfanos"] and not base["valoraciones_huerfanas"]:
        crud.depurar_huerfanos(db, ejecutar=True)
    else:
        db[crud.COL_VALORACIONES].delete_one({"_id": "val_test_huerfana"})
    comprobar(esc, "Elimina la valoración huérfana",
              "val_test_huerfana" not in crud.auditar_integridad(db)["valoraciones_huerfanas"])

    # 4c. Las operaciones del CRUD no generan inconsistencias nuevas
    despues = crud.auditar_integridad(db)
    comprobar(esc, "El CRUD no introdujo inconsistencias",
              despues["seguimientos_inconsistentes"] == base["seguimientos_inconsistentes"]
              and despues["ordenes_sin_seguimiento"] == base["ordenes_sin_seguimiento"],
              f"inconsistentes: {len(base['seguimientos_inconsistentes'])} antes y {len(despues['seguimientos_inconsistentes'])} después")

    # 4d. Datos originales: se informan, no se modifican
    simulacion = crud.reparar_seguimientos(db, ejecutar=False)
    log.info("Datos originales: %d seguimientos desalineados de su orden. "
             "No se modifican (modo simulación) para no alterar los resultados de C11.", simulacion["detectados"])
    comprobar(esc, "Reparación en modo simulación no modifica datos",
              crud.auditar_integridad(db)["seguimientos_inconsistentes"] == base["seguimientos_inconsistentes"],
              f"detectados: {simulacion['detectados']}")


def guardar_resultados():
    with open(SALIDA_DIR / "crud_resultados.csv", "w", newline="", encoding="utf-8-sig") as archivo:
        escritor = csv.DictWriter(archivo, fieldnames=["escenario", "caso", "resultado", "detalle"])
        escritor.writeheader()
        escritor.writerows(resultados)


def main():
    uri = os.getenv("MONGO_URI") or getpass.getpass("URI de conexión de MongoDB Atlas: ")
    try:
        cliente, db = crud.conectar(uri)
    except (PyMongoError, RuntimeError) as error:
        log.error("No se pudo conectar con MongoDB: %s", error)
        raise SystemExit(1)
    log.info("Conexión exitosa con MongoDB (base %s)", db.name)

    base = None
    try:
        previos = limpiar_pruebas(db)
        if previos:
            log.warning("Se eliminaron %d documentos de prueba de una ejecución anterior", previos)
        base = crud.auditar_integridad(db)

        oid = escenario_flujo_completo(db)
        escenario_cancelacion(db)
        escenario_errores(db, oid)
        escenario_integridad(db, base)
    except Exception as error:  # noqa: BLE001 - se registra y se continúa con la limpieza
        log.exception("La demostración se interrumpió: %s", error)
        registrar("General", "Ejecución completa sin interrupciones", False, str(error))
    finally:
        titulo("CIERRE: limpieza de datos de prueba")
        eliminados = limpiar_pruebas(db)
        log.info("Documentos de prueba eliminados: %d", eliminados)
        final = crud.auditar_integridad(db)
        comprobar("Cierre", "No quedan datos de prueba", contar_pruebas(db) == 0)
        comprobar("Cierre", "La base volvió a su estado inicial", final == base,
                  f"totales: {final['totales']}")
        cliente.close()

    guardar_resultados()
    fallos = [r for r in resultados if r["resultado"] != "OK"]
    titulo("RESUMEN")
    log.info("Comprobaciones: %d | correctas: %d | con fallo: %d",
             len(resultados), len(resultados) - len(fallos), len(fallos))
    for fallo in fallos:
        log.error("FALLO: [%s] %s %s", fallo["escenario"], fallo["caso"], fallo["detalle"])
    log.info("Resultados guardados en %s", SALIDA_DIR / "crud_resultados.csv")
    if fallos:
        sys.exit(1)


if __name__ == "__main__":
    main()
