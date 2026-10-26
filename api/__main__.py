"""Inicia la API:  python -m api   (desde la raíz del repositorio).

Igual que los scripts, toma la URI de MONGO_URI (o del archivo .env) y, si no
está, la pide por teclado sin mostrarla.
"""
import getpass
import os

import uvicorn

from api.config import obtener_ajustes


def main():
    ajustes = obtener_ajustes()
    if ajustes.mongo_uri is None:
        os.environ["MONGO_URI"] = getpass.getpass("URI de conexión de MongoDB Atlas: ")
        obtener_ajustes.cache_clear()
        ajustes = obtener_ajustes()

    from api.main import app  # después de tener la URI: la app lee los ajustes al importarse

    print(f"QuickTrack API en http://{ajustes.api_host}:{ajustes.api_puerto}  (documentación en /docs)")
    # log_config=None: uvicorn usa el registro de la API (consola + evidencias/api.log)
    uvicorn.run(app, host=ajustes.api_host, port=ajustes.api_puerto,
                log_config=None, access_log=False, server_header=False)


if __name__ == "__main__":
    main()
