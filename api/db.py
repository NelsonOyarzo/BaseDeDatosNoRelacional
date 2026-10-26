"""Conexión a MongoDB: un solo MongoClient por proceso, creado al iniciar la API.

MongoClient mantiene un pool de conexiones y es seguro entre hilos, así que los
endpoints (que FastAPI ejecuta en un pool de hilos) lo comparten.

Si la URI falta o es inválida la API no arranca, porque es un error de
configuración. Si la base no responde al iniciar, la API arranca igual: /salud
informa el problema y cada endpoint responde 503 hasta que la base vuelva.
"""
import logging
from contextlib import asynccontextmanager
from typing import Annotated
from urllib.parse import unquote, urlsplit

from fastapi import Depends, FastAPI, Request
from pymongo import MongoClient
from pymongo.database import Database
from pymongo.errors import ConfigurationError, PyMongoError
from starlette.concurrency import run_in_threadpool

import quicktrack_crud as crud
from api.config import obtener_ajustes

log = logging.getLogger("quicktrack_api")

COLECCIONES = (crud.COL_CLIENTES, crud.COL_ORDENES, crud.COL_RUTAS, crud.COL_SEGUIMIENTO, crud.COL_VALORACIONES)


def _ocultar_secreto(texto, uri):
    """Quita la contraseña de un mensaje de error antes de registrarlo."""
    try:
        clave = urlsplit(uri).password
    except ValueError:
        clave = None
    for secreto in filter(None, (uri, clave, clave and unquote(clave))):
        texto = texto.replace(secreto, "***")
    return texto


def crear_cliente(ajustes):
    uri = ajustes.mongo_uri.get_secret_value().strip() if ajustes.mongo_uri else ""
    if not uri:
        raise RuntimeError("Falta la URI de MongoDB: defina MONGO_URI en el entorno o en el archivo .env")
    try:
        return MongoClient(uri, serverSelectionTimeoutMS=ajustes.mongo_timeout_ms, appname="quicktrack-api", tz_aware=True)
    except ConfigurationError as error:
        raise RuntimeError(f"La URI de MongoDB no es válida: {_ocultar_secreto(str(error), uri)}") from None


def _revisar_base(cliente, db):
    cliente.admin.command("ping")
    faltantes = sorted(set(COLECCIONES) - set(db.list_collection_names()))
    if faltantes:
        log.warning("La base %s no tiene las colecciones %s (¿MONGO_DB mal escrito?)", db.name, faltantes)
    else:
        log.info("Conectado a MongoDB, base %s con sus %d colecciones", db.name, len(COLECCIONES))


@asynccontextmanager
async def ciclo_de_vida(app: FastAPI):
    ajustes = obtener_ajustes()
    cliente = crear_cliente(ajustes)
    db = cliente[ajustes.mongo_db]
    try:
        await run_in_threadpool(_revisar_base, cliente, db)
    except PyMongoError as error:
        log.error("MongoDB no responde al iniciar (%s); la API responderá 503 hasta que vuelva",
                  type(error).__name__)
    app.state.db = db
    try:
        yield
    finally:
        cliente.close()
        log.info("Conexión con MongoDB cerrada")


def obtener_db(request: Request) -> Database:
    return request.app.state.db


BaseDatos = Annotated[Database, Depends(obtener_db)]
