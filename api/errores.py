"""Control de errores de la API.

Todas las respuestas de error usan el formato Problem Details (RFC 9457,
`application/problem+json`) con dos campos propios: `codigo`, estable y pensado
para que el cliente decida qué hacer, e `id_solicitud`, que permite encontrar
la solicitud en evidencias/api.log.

Las excepciones del CRUD se traducen así:
    ValidacionError   -> 400 VALIDACION
    NoEncontradoError -> 404 NO_ENCONTRADO
    ConflictoError    -> 409 CONFLICTO
Los errores de MongoDB nunca muestran detalles internos (hosts, topología)
al cliente: se registran completos en el log y se responde un mensaje genérico.
"""
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from http import HTTPStatus

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pymongo.errors import ConnectionFailure, DuplicateKeyError, PyMongoError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.routing import Match

import quicktrack_crud as crud
from api import PREFIJO
from api.registro import id_solicitud

log = logging.getLogger("quicktrack_api")

TIPO_CONTENIDO = "application/problem+json"
RUTA_CATALOGO = f"{PREFIJO}/errores"


@dataclass(frozen=True)
class TipoError:
    estado: int
    titulo: str
    descripcion: str


CATALOGO = {
    "VALIDACION": TipoError(
        400, "Datos de entrada inválidos",
        "El cuerpo, la ruta o los parámetros no cumplen el formato o las reglas de validación. "
        "Si el error es de formato, `errores` indica cada campo con problemas.",
    ),
    "NO_ENCONTRADO": TipoError(
        404, "Recurso no encontrado", "La orden, cliente, ruta, seguimiento o consulta solicitada no existe.",
    ),
    "RUTA_NO_ENCONTRADA": TipoError(
        404, "Endpoint inexistente", "La URL no corresponde a ningún endpoint de la API.",
    ),
    "METODO_NO_PERMITIDO": TipoError(
        405, "Método no permitido",
        "El endpoint existe pero no admite ese método HTTP. La cabecera Allow indica los permitidos.",
    ),
    "CONFLICTO": TipoError(
        409, "Conflicto con el estado actual",
        "Duplicado o regla de negocio incumplida: transición de estado no permitida, orden cerrada, "
        "valoración repetida o eliminación no autorizada.",
    ),
    "ERROR_BASE_DATOS": TipoError(
        500, "Error de la base de datos", "MongoDB rechazó la operación. El detalle queda en el log.",
    ),
    "ERROR_INTERNO": TipoError(
        500, "Error interno", "Error inesperado. Use id_solicitud para buscar el detalle en evidencias/api.log.",
    ),
    "BASE_NO_DISPONIBLE": TipoError(
        503, "Base de datos no disponible",
        "No se pudo contactar a MongoDB (red, IP no autorizada en Atlas o clúster detenido). "
        "Reintente después de los segundos indicados en Retry-After.",
    ),
}


def respuesta_problema(request: Request, codigo, detalle, *, errores=None, cabeceras=None, tipo=None):
    tipo = tipo or CATALOGO[codigo]
    cuerpo = {
        "type": f"{RUTA_CATALOGO}/{codigo.lower()}",
        "title": tipo.titulo,
        "status": tipo.estado,
        "detail": detalle,
        "instance": request.url.path,
        "codigo": codigo,
        "id_solicitud": id_solicitud.get(),
        "fecha": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    if errores:
        cuerpo["errores"] = errores
    return JSONResponse(cuerpo, status_code=tipo.estado, media_type=TIPO_CONTENIDO, headers=cabeceras)


# ------------------------------------------ errores de formato (Pydantic)
UBICACIONES = {"body": "cuerpo", "query": "parametro", "path": "ruta", "header": "cabecera"}

# Errores de tipo: se agrupan por campo ("Debe ser un número entero o un texto").
TIPOS_ESPERADOS = {
    "int_type": "un número entero",
    "int_parsing": "un número entero",
    "int_from_float": "un número entero",
    "float_type": "un número",
    "float_parsing": "un número",
    "string_type": "un texto",
    "bool_type": "true o false",
    "bool_parsing": "true o false",
}

MENSAJES = {
    "missing": "Campo obligatorio",
    "extra_forbidden": "Campo no permitido",
    "model_attributes_type": "El cuerpo debe ser un objeto JSON",
    "dict_type": "El cuerpo debe ser un objeto JSON",
    "model_type": "El cuerpo debe ser un objeto JSON",
}


def traducir_errores(errores):
    """Convierte los errores de Pydantic en una lista en español, uno por campo."""
    agrupados = {}
    for error in errores:
        loc = [str(parte) for parte in error.get("loc", ())]
        ubicacion = UBICACIONES.get(loc[0], loc[0]) if loc else "solicitud"
        campo = loc[1] if len(loc) > 1 else None
        tipo = error.get("type")

        if tipo == "json_invalid":
            # loc trae la posición del error dentro del texto, no un campo
            mensaje, campo = f"El cuerpo no es un JSON válido (revise cerca del carácter {campo})", None
        elif tipo == "missing" and campo is None:
            mensaje = "Falta el cuerpo JSON de la solicitud"
        else:
            mensaje = MENSAJES.get(tipo, error.get("msg", "Valor inválido"))

        grupo = agrupados.setdefault((ubicacion, campo), {"tipos": [], "mensajes": []})
        if tipo in TIPOS_ESPERADOS:
            if TIPOS_ESPERADOS[tipo] not in grupo["tipos"]:
                grupo["tipos"].append(TIPOS_ESPERADOS[tipo])
        elif mensaje not in grupo["mensajes"]:
            grupo["mensajes"].append(mensaje)

    resultado = []
    for (ubicacion, campo), grupo in agrupados.items():
        mensajes = grupo["mensajes"] + (["Debe ser " + " o ".join(grupo["tipos"])] if grupo["tipos"] else [])
        resultado.append({"ubicacion": ubicacion, "campo": campo, "mensaje": "; ".join(mensajes)})
    return resultado


# ------------------------------------------------------------ manejadores
async def _validacion_crud(request, error):
    log.warning("400 VALIDACION: %s", error)
    return respuesta_problema(request, "VALIDACION", str(error))


async def _no_encontrado(request, error):
    log.warning("404 NO_ENCONTRADO: %s", error)
    return respuesta_problema(request, "NO_ENCONTRADO", str(error))


async def _conflicto(request, error):
    log.warning("409 CONFLICTO: %s", error)
    return respuesta_problema(request, "CONFLICTO", str(error))


async def _validacion_solicitud(request, error: RequestValidationError):
    errores = traducir_errores(error.errors())
    detalle = "; ".join(f"{e['campo']}: {e['mensaje']}" if e["campo"] else e["mensaje"] for e in errores)
    log.warning("400 VALIDACION de formato: %s", detalle)
    return respuesta_problema(request, "VALIDACION", detalle, errores=errores)


async def _http(request, error: StarletteHTTPException):
    if error.status_code == 404:
        detalle = f"No existe el endpoint {request.method} {request.url.path}"
        log.warning("404 RUTA_NO_ENCONTRADA: %s", detalle)
        return respuesta_problema(request, "RUTA_NO_ENCONTRADA", detalle)
    if error.status_code == 405:
        # Starlette solo informa los métodos de la primera ruta que coincide con la URL
        # (/ordenes/{id} tiene GET y DELETE en rutas distintas): se juntan todos.
        permitidos = ", ".join(sorted({
            metodo
            for ruta in request.app.router.routes
            if ruta.matches(request.scope)[0] != Match.NONE
            for metodo in getattr(ruta, "methods", None) or ()
        }))
        detalle = f"El método {request.method} no está permitido en {request.url.path}. Permitidos: {permitidos}"
        log.warning("405 METODO_NO_PERMITIDO: %s", detalle)
        return respuesta_problema(request, "METODO_NO_PERMITIDO", detalle, cabeceras={"Allow": permitidos})
    # Cualquier otro HTTPException conserva su código con el mismo formato de respuesta.
    frase = HTTPStatus(error.status_code).phrase
    tipo = TipoError(error.status_code, frase, "")
    log.warning("%d HTTP: %s", error.status_code, error.detail)
    return respuesta_problema(request, f"HTTP_{error.status_code}", str(error.detail), cabeceras=error.headers, tipo=tipo)


async def _base_no_disponible(request, error: ConnectionFailure):
    log.error("503 BASE_NO_DISPONIBLE: %s: %s", type(error).__name__, error)
    return respuesta_problema(
        request, "BASE_NO_DISPONIBLE",
        "No se pudo contactar a MongoDB. Revise la conexión y que la IP esté autorizada en Atlas.",
        cabeceras={"Retry-After": "30"},
    )


async def _duplicado(request, error: DuplicateKeyError):
    log.warning("409 CONFLICTO por índice único: %s", error.details)
    return respuesta_problema(request, "CONFLICTO", "Ya existe un documento con ese identificador o valor único")


async def _error_mongo(request, error: PyMongoError):
    log.error("500 ERROR_BASE_DATOS: %s: %s", type(error).__name__, error)
    return respuesta_problema(request, "ERROR_BASE_DATOS", "MongoDB rechazó la operación")


def registrar_manejadores(app: FastAPI):
    """Los errores no previstos (500) los atrapa MiddlewareTrazabilidad, ver middleware.py."""
    app.add_exception_handler(crud.ValidacionError, _validacion_crud)
    app.add_exception_handler(crud.NoEncontradoError, _no_encontrado)
    app.add_exception_handler(crud.ConflictoError, _conflicto)
    app.add_exception_handler(RequestValidationError, _validacion_solicitud)
    app.add_exception_handler(StarletteHTTPException, _http)
    app.add_exception_handler(ConnectionFailure, _base_no_disponible)
    app.add_exception_handler(DuplicateKeyError, _duplicado)
    app.add_exception_handler(PyMongoError, _error_mongo)
