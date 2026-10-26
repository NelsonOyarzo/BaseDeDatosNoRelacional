"""Estado de la API y catálogo de errores."""
import logging
import time

from fastapi import APIRouter, Request, Response
from pymongo.errors import PyMongoError

import quicktrack_crud as crud
from api import __version__
from api.errores import CATALOGO
from api.esquemas import Salud, TipoErrorInfo, respuestas_error

log = logging.getLogger("quicktrack_api")

router = APIRouter(tags=["General"])


@router.get("/salud", response_model=Salud, summary="Estado de la API y de la base",
            responses={503: {"model": Salud, "description": "La base de datos no responde"}})
def salud(request: Request, response: Response):
    """200 si MongoDB responde al ping; 503 (estado degradado) si no."""
    db = request.app.state.db
    inicio = time.perf_counter()
    try:
        db.client.admin.command("ping")
    except PyMongoError as error:
        log.error("Salud: MongoDB no responde (%s)", type(error).__name__)
        response.status_code = 503
        response.headers["Retry-After"] = "30"
        base = {"estado": "sin conexión", "nombre": db.name, "latencia_ms": None}
        return {"estado": "degradado", "version": __version__, "base_datos": base}
    base = {"estado": "conectada", "nombre": db.name, "latencia_ms": round((time.perf_counter() - inicio) * 1000, 1)}
    return {"estado": "ok", "version": __version__, "base_datos": base}


def _tipo(codigo):
    tipo = CATALOGO[codigo]
    return {"codigo": codigo, "estado_http": tipo.estado, "titulo": tipo.titulo, "descripcion": tipo.descripcion}


@router.get("/errores", response_model=list[TipoErrorInfo], summary="Catálogo de errores")
def listar_errores():
    """Códigos de error que puede responder la API (campo `codigo` de cada error)."""
    return [_tipo(codigo) for codigo in CATALOGO]


@router.get("/errores/{codigo}", response_model=TipoErrorInfo, summary="Detalle de un código de error",
            responses=respuestas_error(404))
def leer_error(codigo: str):
    """Destino del campo `type` de cada respuesta de error."""
    if codigo.upper() not in CATALOGO:
        raise crud.NoEncontradoError(f"El código de error {codigo} no existe")
    return _tipo(codigo.upper())
