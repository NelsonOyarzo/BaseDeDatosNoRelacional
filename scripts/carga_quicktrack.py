import getpass
import json
import logging
import os
from datetime import datetime
from pathlib import Path

from pymongo import ASCENDING, MongoClient
from pymongo.errors import PyMongoError

BASE_DIR = Path(__file__).resolve().parent
DATOS_DIR = BASE_DIR.parent / "datos"
SALIDA_DIR = BASE_DIR.parent / "evidencias"
SALIDA_DIR.mkdir(exist_ok=True)
DB_NAME = os.getenv("MONGO_DB", "QuickTrack")

ARCHIVOS = {
    "clientes": "clientes.json",
    "ordenes_entrega": "ordenes_entrega.json",
    "rutas": "rutas.json",
    "seguimiento": "seguimiento.json",
    "valoraciones": "valoraciones.json",
}

CAMPOS_REQUERIDOS = {
    "clientes": ["_id", "nombre", "correo", "pais", "fecha_registro"],
    "ordenes_entrega": ["_id", "cliente_id", "ruta_id", "fecha_envio", "estado", "medio_pago", "total"],
    "rutas": ["_id", "zona", "ciudad_origen", "ciudad_destino", "distancia_km"],
    "seguimiento": ["_id", "orden_id", "estado_actual", "historial"],
    "valoraciones": ["_id", "orden_id", "puntaje", "comentario"],
}

INDICES = {
    "clientes": [("correo", True)],
    "ordenes_entrega": [("cliente_id", False), ("ruta_id", False), ("estado", False), ("fecha_envio", False)],
    "rutas": [("zona", False)],
    "seguimiento": [("orden_id", True)],
    "valoraciones": [("orden_id", True), ("puntaje", False)],
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler(SALIDA_DIR / "carga.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger("carga_quicktrack")


def leer_json(nombre_archivo):
    ruta = DATOS_DIR / nombre_archivo
    if not ruta.exists():
        raise FileNotFoundError(f"No se encontró {ruta}")
    texto = ruta.read_text(encoding="utf-8").strip()
    if texto.startswith("["):
        return json.loads(texto)
    return [json.loads(linea) for linea in texto.splitlines() if linea.strip()]


def a_fecha(valor):
    return datetime.fromisoformat(valor)


def transformar(coleccion, doc):
    if coleccion == "clientes":
        doc["fecha_registro"] = a_fecha(doc["fecha_registro"])
    elif coleccion == "ordenes_entrega":
        doc["cliente_id"] = int(str(doc["cliente_id"]).replace("cli_", ""))
        doc["fecha_envio"] = a_fecha(doc["fecha_envio"])
    elif coleccion == "seguimiento":
        for evento in doc["historial"]:
            evento["fecha"] = a_fecha(evento["fecha"])
    elif coleccion == "valoraciones":
        doc["puntaje"] = int(doc["puntaje"])
    return doc


def validar(coleccion, doc):
    faltantes = [c for c in CAMPOS_REQUERIDOS[coleccion] if c not in doc or doc[c] in (None, "")]
    if faltantes:
        return f"campos faltantes {faltantes}"
    if coleccion == "valoraciones" and not 1 <= int(doc["puntaje"]) <= 5:
        return "puntaje fuera del rango 1-5"
    if coleccion == "ordenes_entrega" and float(doc["total"]) <= 0:
        return "total no positivo"
    return None


def preparar_documentos():
    preparados = {}
    for coleccion, archivo in ARCHIVOS.items():
        validos = []
        descartados = 0
        for doc in leer_json(archivo):
            motivo = validar(coleccion, doc)
            if motivo:
                descartados += 1
                log.warning("%s: documento %s descartado (%s)", coleccion, doc.get("_id"), motivo)
                continue
            validos.append(transformar(coleccion, doc))
        preparados[coleccion] = validos
        log.info("%s: %d documentos listos, %d descartados", coleccion, len(validos), descartados)
    return preparados


def main():
    uri = os.getenv("MONGO_URI") or getpass.getpass("URI de conexión de MongoDB Atlas: ")
    documentos = preparar_documentos()

    try:
        cliente = MongoClient(uri, serverSelectionTimeoutMS=8000)
        cliente.admin.command("ping")
        log.info("Conexión exitosa con MongoDB")
        db = cliente[DB_NAME]

        for coleccion, docs in documentos.items():
            db[coleccion].drop()
            for campo, unico in INDICES[coleccion]:
                db[coleccion].create_index([(campo, ASCENDING)], unique=unico)
            resultado = db[coleccion].insert_many(docs)
            log.info("%s: %d documentos insertados", coleccion, len(resultado.inserted_ids))

        print("\nVerificación de la carga")
        for coleccion in ARCHIVOS:
            print(f"{coleccion}: {db[coleccion].count_documents({})} documentos")
        print("\nEjemplo de orden:")
        print(db["ordenes_entrega"].find_one({}, {"_id": 1, "cliente_id": 1, "fecha_envio": 1, "estado": 1, "total": 1}))
    except PyMongoError as error:
        log.error("Error de MongoDB: %s", error)
        raise SystemExit(1)
    finally:
        try:
            cliente.close()
        except NameError:
            pass


if __name__ == "__main__":
    main()