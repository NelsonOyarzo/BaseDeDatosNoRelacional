"""Trazabilidad de cada solicitud: id, tiempo de respuesta, registro y errores no previstos.

Es un middleware ASGI puro (no BaseHTTPMiddleware) y va por fuera del resto:
    * Asigna el id de solicitud: respeta X-Request-ID si el cliente lo envía
      con un formato seguro, si no genera uno. Lo devuelve en la respuesta.
    * Agrega X-Response-Time y registra una línea por solicitud en el log.
    * Si una excepción no fue atrapada por ningún manejador, la registra con
      su traza completa y responde 500 en formato Problem Details, sin
      exponer la traza al cliente.
"""
import logging
import re
import time
import uuid

from starlette.datastructures import Headers, MutableHeaders
from starlette.requests import Request

from api.errores import respuesta_problema
from api.registro import id_solicitud

log = logging.getLogger("quicktrack_api")

CABECERA_ID = "X-Request-ID"
RE_ID_EXTERNO = re.compile(r"[A-Za-z0-9._-]{1,64}")


class MiddlewareTrazabilidad:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        externo = Headers(scope=scope).get(CABECERA_ID, "")
        rid = externo if RE_ID_EXTERNO.fullmatch(externo) else uuid.uuid4().hex[:12]
        token = id_solicitud.set(rid)
        inicio = time.perf_counter()
        estado = 500
        iniciada = False

        async def enviar(mensaje):
            nonlocal estado, iniciada
            if mensaje["type"] == "http.response.start":
                iniciada = True
                estado = mensaje["status"]
                cabeceras = MutableHeaders(scope=mensaje)
                cabeceras[CABECERA_ID] = rid
                cabeceras["X-Response-Time"] = f"{(time.perf_counter() - inicio) * 1000:.1f}ms"
            await send(mensaje)

        try:
            await self.app(scope, receive, enviar)
        except Exception:
            log.exception("500 ERROR_INTERNO en %s %s", scope["method"], scope["path"])
            if iniciada:  # la respuesta ya empezó a enviarse: no se puede reemplazar
                raise
            respuesta = respuesta_problema(
                Request(scope), "ERROR_INTERNO",
                f"Error inesperado al procesar la solicitud. Informe el id {rid} para revisar el registro.",
            )
            await respuesta(scope, receive, enviar)
        finally:
            ruta = scope["path"] + (f"?{scope['query_string'].decode('latin-1')}" if scope["query_string"] else "")
            nivel = logging.ERROR if estado >= 500 else logging.WARNING if estado >= 400 else logging.INFO
            if nivel == logging.INFO and scope["path"].startswith("/interfaz/"):
                nivel = logging.DEBUG  # los archivos de la interfaz no llenan el log de evidencias
            cliente = scope["client"][0] if scope.get("client") else "-"
            log.log(nivel, "%s %s -> %d (%.1f ms) desde %s",
                    scope["method"], ruta, estado, (time.perf_counter() - inicio) * 1000, cliente)
            id_solicitud.reset(token)
