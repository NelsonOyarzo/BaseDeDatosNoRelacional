"""Aplicación FastAPI de QuickTrack.

Iniciar con `python -m api` (ver api/__main__.py). Documentación interactiva
en /docs (Swagger UI) y /redoc; especificación OpenAPI en /openapi.json, que
también se puede importar en Postman.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi

from api import PREFIJO, __version__
from api.config import obtener_ajustes
from api.db import ciclo_de_vida
from api.errores import registrar_manejadores
from api.esquemas import respuestas_error
from api.middleware import CABECERA_ID, MiddlewareTrazabilidad
from api.registro import configurar_registro
from api.routers import catalogos, consultas, general, integridad, ordenes

DESCRIPCION = """
API REST de **QuickTrack** sobre MongoDB Atlas: gestión de órdenes de entrega
(con su seguimiento y valoración), catálogos de clientes y rutas, consultas de
análisis C1 a C11 y auditoría de integridad.

## Errores

Todas las respuestas de error usan `application/problem+json` (RFC 9457) con
los campos `codigo` e `id_solicitud`. El catálogo completo está en
`GET /api/v1/errores`.

| HTTP | codigo | Cuándo |
|---|---|---|
| 400 | VALIDACION | Formato o regla de validación incumplida (`errores` detalla cada campo) |
| 404 | NO_ENCONTRADO | La orden, cliente, ruta o consulta no existe |
| 404 | RUTA_NO_ENCONTRADA | La URL no corresponde a ningún endpoint |
| 405 | METODO_NO_PERMITIDO | Método HTTP no admitido (ver cabecera Allow) |
| 409 | CONFLICTO | Duplicado o regla de negocio (transición, orden cerrada, valoración repetida) |
| 500 | ERROR_BASE_DATOS / ERROR_INTERNO | Error no previsto; el detalle queda en el log |
| 503 | BASE_NO_DISPONIBLE | MongoDB no responde (ver Retry-After) |

## Trazabilidad

Cada respuesta incluye `X-Request-ID` (se respeta el que envíe el cliente) y
`X-Response-Time`. El mismo id aparece en cada línea de `evidencias/api.log`.
"""

ETIQUETAS = [
    {"name": "General", "description": "Estado de la API y catálogo de errores"},
    {"name": "Órdenes", "description": "CRUD de órdenes de entrega, seguimiento y valoración"},
    {"name": "Clientes", "description": "Lectura de clientes y de sus órdenes"},
    {"name": "Rutas", "description": "Lectura de rutas"},
    {"name": "Consultas de análisis", "description": "Consultas C1 a C11 del informe"},
    {"name": "Integridad", "description": "Auditoría y corrección de inconsistencias"},
]


def _openapi_sin_422(app):
    """FastAPI documenta 422 para los errores de formato, pero esta API responde 400."""
    def generar():
        if app.openapi_schema is None:
            esquema = get_openapi(title=app.title, version=app.version, description=app.description,
                                  routes=app.routes, tags=app.openapi_tags)
            for operaciones in esquema.get("paths", {}).values():
                for operacion in operaciones.values():
                    operacion.get("responses", {}).pop("422", None)
            for nombre in ("HTTPValidationError", "ValidationError"):
                esquema.get("components", {}).get("schemas", {}).pop(nombre, None)
            app.openapi_schema = esquema
        return app.openapi_schema
    return generar


def crear_app() -> FastAPI:
    ajustes = obtener_ajustes()
    configurar_registro(ajustes.api_archivo_log, ajustes.api_nivel_log)

    app = FastAPI(
        title="QuickTrack API",
        version=__version__,
        description=DESCRIPCION,
        openapi_tags=ETIQUETAS,
        lifespan=ciclo_de_vida,
        responses=respuestas_error(400, 500, 503),
    )
    registrar_manejadores(app)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=ajustes.origenes_cors,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=[CABECERA_ID, "X-Response-Time", "Location"],
    )
    app.add_middleware(MiddlewareTrazabilidad)  # el último agregado queda por fuera de todos

    for router in (general.router, ordenes.router, catalogos.clientes, catalogos.rutas,
                   consultas.router, integridad.router):
        app.include_router(router, prefix=PREFIJO)

    @app.get("/", include_in_schema=False)
    def raiz():
        return {
            "nombre": app.title,
            "version": __version__,
            "documentacion": "/docs",
            "openapi": "/openapi.json",
            "salud": f"{PREFIJO}/salud",
        }

    app.openapi = _openapi_sin_422(app)
    return app


app = crear_app()
