"""Configuración de la API, leída de variables de entorno o del archivo .env de la raíz.

Las variables de entorno tienen prioridad sobre el .env. Los nombres son los
mismos que usan los scripts (MONGO_URI, MONGO_DB) más los propios de la API.
"""
from functools import lru_cache
from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from api import RAIZ


class Ajustes(BaseSettings):
    model_config = SettingsConfigDict(env_file=RAIZ / ".env", env_file_encoding="utf-8", extra="ignore")

    mongo_uri: SecretStr | None = None  # SecretStr: la contraseña no aparece en logs ni en repr()
    mongo_db: str = "QuickTrack"
    mongo_timeout_ms: int = 5000

    api_host: str = "127.0.0.1"
    api_puerto: int = 8000
    api_nivel_log: str = "INFO"
    api_archivo_log: Path = RAIZ / "evidencias" / "api.log"
    api_cors_origenes: str = "*"  # lista separada por comas

    @property
    def origenes_cors(self) -> list[str]:
        return [origen.strip() for origen in self.api_cors_origenes.split(",") if origen.strip()]


@lru_cache
def obtener_ajustes() -> Ajustes:
    return Ajustes()
