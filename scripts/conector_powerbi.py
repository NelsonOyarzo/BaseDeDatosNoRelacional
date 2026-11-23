r"""Script conector para Power BI Desktop (Entorno de pruebas db3).
Ruta: C:/Users/nelca/Desktop/db3/BaseDeDatosNoRelacional/scripts/conector_powerbi.py

Permite cargar las tablas del modelo analitico de QuickTrack directamente en Power BI.
Si existe conexion a MongoDB Atlas, consulta la base de datos en la nube.
Si no hay conexion o no esta configurada la URI, carga automaticamente los datos
transformados locales desde 'datos_bi' de este clon o los JSON de 'db3'.
"""
import os
import json
from pathlib import Path
import pandas as pd

# 1. Configuracion de conexion (puedes pegar tu URI de Atlas entre las comillas si deseas)
MONGO_URI = os.getenv("MONGO_URI", "")
MONGO_DB = os.getenv("MONGO_DB", "QuickTrack")

# Buscar .env en la raiz del repo clonado
BASE_CLON = Path(r"C:\Users\nelca\Desktop\db3\BaseDeDatosNoRelacional")
ENV_FILE = BASE_CLON / ".env"
if not MONGO_URI and ENV_FILE.exists():
    with open(ENV_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith("MONGO_URI="):
                MONGO_URI = line.split("=", 1)[1].strip().strip('"').strip("'")
            elif line.startswith("MONGO_DB="):
                MONGO_DB = line.split("=", 1)[1].strip().strip('"').strip("'")

# Rutas de datos locales dentro de db3
DIR_CSV = BASE_CLON / "datos_bi"
DIR_JSON = Path(r"C:\Users\nelca\Desktop\db3")

def obtener_datos(coleccion_nombre, csv_nombre, json_nombre):
    # Intentar conexion a MongoDB Atlas si hay URI configurada
    if MONGO_URI:
        try:
            from pymongo import MongoClient
            client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=4000)
            db = client[MONGO_DB]
            docs = list(db[coleccion_nombre].find({}))
            if docs:
                df = pd.DataFrame(docs)
                if "_id" in df.columns:
                    df["_id"] = df["_id"].astype(str)
                return df
        except Exception as e:
            print(f"Aviso: No se pudo conectar a MongoDB Atlas ({e}). Cargando datos locales.")

    # Respaldo 1: Leer desde CSV en datos_bi
    csv_path = DIR_CSV / f"{csv_nombre}.csv"
    if csv_path.exists():
        return pd.read_csv(csv_path, encoding="utf-8-sig")

    # Respaldo 2: Leer desde JSON en db3
    json_path = DIR_JSON / f"QuickTrack.{json_nombre}.json"
    if json_path.exists():
        with open(json_path, "r", encoding="utf-8") as jf:
            data = json.load(jf)
        df = pd.DataFrame(data)
        if "_id" in df.columns:
            df["_id"] = df["_id"].astype(str)
        return df

    return pd.DataFrame()

# Cargar las tablas analiticas (estas variables seran reconocidas como tablas en Power BI)
fact_ordenes_bi = obtener_datos("fact_ordenes_bi", "fact_ordenes_bi", "fact_ordenes_bi")
bridge_seguimiento_historial = obtener_datos("bridge_seguimiento_historial", "bridge_seguimiento_historial", "bridge_seguimiento_historial")
clientes_cosmos_etl = obtener_datos("clientes_cosmos_etl", "clientes_cosmos_etl", "clientes_cosmos_etl")
rice_atributos = obtener_datos("rice_atributos", "rice_atributos", "rice_atributos")

# Formateo y tipado para Power BI
if not fact_ordenes_bi.empty:
    fact_ordenes_bi["_id"] = fact_ordenes_bi["_id"].astype(str)
    fact_ordenes_bi["total"] = pd.to_numeric(fact_ordenes_bi["total"], errors="coerce")
    fact_ordenes_bi["fecha_envio"] = pd.to_datetime(fact_ordenes_bi["fecha_envio"], errors="coerce")

if not bridge_seguimiento_historial.empty:
    bridge_seguimiento_historial["orden_id"] = bridge_seguimiento_historial["orden_id"].astype(str)

print("Datos cargados correctamente en Power BI desde entorno db3:")
print(f" - fact_ordenes_bi: {len(fact_ordenes_bi)} filas")
print(f" - bridge_seguimiento_historial: {len(bridge_seguimiento_historial)} filas")
print(f" - clientes_cosmos_etl: {len(clientes_cosmos_etl)} filas")
print(f" - rice_atributos: {len(rice_atributos)} filas")
