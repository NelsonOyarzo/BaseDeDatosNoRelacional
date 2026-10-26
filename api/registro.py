"""Registro de eventos (logs) con el id de la solicitud en cada línea.

El id se guarda en una variable de contexto: así también lo llevan los
mensajes del módulo CRUD, sin que este sepa nada de la API.
"""
import logging
from contextvars import ContextVar
from logging.handlers import RotatingFileHandler

id_solicitud: ContextVar[str] = ContextVar("id_solicitud", default="-")

FORMATO = "%(asctime)s | %(levelname)s | %(id_solicitud)s | %(name)s | %(message)s"


class _FiltroIdSolicitud(logging.Filter):
    def filter(self, registro):
        registro.id_solicitud = id_solicitud.get()
        return True


def configurar_registro(archivo, nivel="INFO"):
    """Consola y archivo rotativo (1 MB x 3). No duplica handlers si se llama dos veces."""
    raiz = logging.getLogger()
    if any(getattr(handler, "quicktrack", False) for handler in raiz.handlers):
        return
    archivo.parent.mkdir(parents=True, exist_ok=True)
    formato = logging.Formatter(FORMATO)
    for handler in (
        logging.StreamHandler(),
        RotatingFileHandler(archivo, maxBytes=1_000_000, backupCount=3, encoding="utf-8"),
    ):
        handler.setFormatter(formato)
        handler.addFilter(_FiltroIdSolicitud())
        handler.quicktrack = True
        raiz.addHandler(handler)
    raiz.setLevel(nivel.upper())
