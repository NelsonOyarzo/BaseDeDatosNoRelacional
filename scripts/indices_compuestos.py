"""IE6: evaluación de eficiencia con índices compuestos.

Mide, para las consultas C1, C2 y C3 de consultas_quicktrack.py, cuántos
documentos y claves examina MongoDB ANTES (índice simple sobre `estado`) y
DESPUÉS de crear índices compuestos. Verifica que los resultados no cambien
y guarda la evidencia en la carpeta `evidencias`.

Uso:
    python scripts\\indices_compuestos.py              # mide, crea índices y vuelve a medir
    python scripts\\indices_compuestos.py --eliminar   # elimina los índices compuestos
"""
import argparse
import getpass
import logging
import os
import time
from datetime import datetime
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # solo guarda el gráfico, no abre ventana
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
from pymongo import ASCENDING, DESCENDING, MongoClient
from pymongo.errors import PyMongoError

BASE_DIR = Path(__file__).resolve().parent
SALIDA_DIR = BASE_DIR.parent / "evidencias"
if not SALIDA_DIR.exists():
    SALIDA_DIR = BASE_DIR

DB_NAME = os.getenv("MONGO_DB", "QuickTrack")
COLECCION = "ordenes_entrega"
REPETICIONES = 20

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler(SALIDA_DIR / "indices.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger("indices_compuestos")

# Índice simple que usan hoy las tres consultas (creado por carga_quicktrack.py).
INDICE_BASE = [("estado", ASCENDING)]

# Índices compuestos propuestos: igualdad primero (estado, medio_pago),
# luego el campo de orden/rango (total o fecha_envio).
INDICES_NUEVOS = {
    "idx_estado_total_desc": [("estado", ASCENDING), ("total", DESCENDING)],
    "idx_estado_pago_fecha": [("estado", ASCENDING), ("medio_pago", ASCENDING), ("fecha_envio", ASCENDING)],
}

PROY_ORDEN = {"_id": 1, "cliente_id": 1, "estado": 1, "medio_pago": 1, "fecha_envio": 1, "total": 1}

# Mismos filtros, orden y límite que C1, C2 y C3 de consultas_quicktrack.py.
CONSULTAS = [
    {
        "id": "C1",
        "titulo": "Entregas exitosas de mayor valor",
        "filtro": {"estado": "Entregado", "total": {"$gte": 100000}},
        "orden": [("total", -1)],
        "limite": 10,
        "indice_nuevo": "idx_estado_total_desc",
    },
    {
        "id": "C2",
        "titulo": "Cancelaciones pagadas con tarjeta en 2023",
        "filtro": {
            "estado": "Cancelado",
            "medio_pago": "Tarjeta",
            "fecha_envio": {"$gte": datetime(2023, 1, 1), "$lt": datetime(2024, 1, 1)},
        },
        "orden": [("fecha_envio", 1)],
        "limite": 0,
        "indice_nuevo": "idx_estado_pago_fecha",
    },
    {
        "id": "C3",
        "titulo": "Pedidos pendientes de alto valor",
        "filtro": {"estado": {"$in": ["En preparación", "En tránsito"]}, "total": {"$gte": 150000}},
        "orden": [("total", -1)],
        "limite": 10,
        "indice_nuevo": "idx_estado_total_desc",
    },
]


def construir_cursor(db, consulta, hint):
    cursor = db[COLECCION].find(consulta["filtro"], PROY_ORDEN).hint(hint)
    if consulta.get("orden"):
        cursor = cursor.sort(consulta["orden"])
    if consulta.get("limite"):
        cursor = cursor.limit(consulta["limite"])
    return cursor


def hay_etapa(nodo, etapa):
    """Busca de forma recursiva una etapa (por ejemplo SORT) en el plan ganador."""
    if isinstance(nodo, dict):
        if nodo.get("stage") == etapa:
            return True
        return any(hay_etapa(v, etapa) for v in nodo.values())
    if isinstance(nodo, list):
        return any(hay_etapa(v, etapa) for v in nodo)
    return False


def medir(db, consulta, hint, escenario, nombre_indice):
    plan = construir_cursor(db, consulta, hint).explain()
    stats = plan.get("executionStats", {})
    ids = [doc["_id"] for doc in construir_cursor(db, consulta, hint)]

    tiempos = []
    for _ in range(REPETICIONES):
        inicio = time.perf_counter()
        list(construir_cursor(db, consulta, hint))
        tiempos.append((time.perf_counter() - inicio) * 1000)

    return {
        "id": consulta["id"],
        "consulta": f"{consulta['id']} {consulta['titulo']}",
        "escenario": escenario,
        "indice": nombre_indice,
        "documentos_devueltos": stats.get("nReturned", len(ids)),
        "claves_examinadas": stats.get("totalKeysExamined"),
        "documentos_examinados": stats.get("totalDocsExamined"),
        "orden_en_memoria": hay_etapa(plan.get("queryPlanner", {}).get("winningPlan", {}), "SORT"),
        "tiempo_servidor_ms": stats.get("executionTimeMillis"),
        "tiempo_cliente_ms": round(sum(tiempos) / len(tiempos), 1),
        "_ids": ids,
    }


def medir_todas(db, escenario):
    filas = []
    for consulta in CONSULTAS:
        if escenario == "antes":
            hint, nombre = INDICE_BASE, "estado_1"
        else:
            hint = nombre = consulta["indice_nuevo"]
        fila = medir(db, consulta, hint, escenario, nombre)
        log.info(
            "%s %s [%s]: %s devueltos, %s claves, %s documentos examinados, orden en memoria: %s",
            consulta["id"], escenario, nombre, fila["documentos_devueltos"], fila["claves_examinadas"],
            fila["documentos_examinados"], "sí" if fila["orden_en_memoria"] else "no",
        )
        filas.append(fila)
    return filas


def crear_indices(db):
    for nombre, claves in INDICES_NUEVOS.items():
        db[COLECCION].create_index(claves, name=nombre)
        log.info("Índice %s creado o ya existente: %s", nombre, claves)


def eliminar_indices(db):
    existentes = db[COLECCION].index_information()
    for nombre in INDICES_NUEVOS:
        if nombre in existentes:
            db[COLECCION].drop_index(nombre)
            log.info("Índice %s eliminado", nombre)
        else:
            log.info("Índice %s no existe, no se elimina", nombre)


def validar_resultados(antes, despues):
    """Un índice debe cambiar el costo de la consulta, no su resultado."""
    ok_total = True
    for a, d in zip(antes, despues):
        iguales = a["_ids"] == d["_ids"]
        ok_total = ok_total and iguales
        nivel = logging.INFO if iguales else logging.ERROR
        log.log(nivel, "%s: resultados %s antes y después del índice", a["id"], "idénticos" if iguales else "DISTINTOS")
    return ok_total


def resumen_mejora(antes, despues):
    filas = []
    for a, d in zip(antes, despues):
        ex_a, ex_d = a["documentos_examinados"], d["documentos_examinados"]
        reduccion = round(100 * (ex_a - ex_d) / ex_a, 1) if ex_a else None
        filas.append(
            {
                "consulta": a["consulta"],
                "docs_examinados_antes": ex_a,
                "docs_examinados_despues": ex_d,
                "reduccion_pct": reduccion,
                "orden_en_memoria_antes": a["orden_en_memoria"],
                "orden_en_memoria_despues": d["orden_en_memoria"],
                "indice_nuevo": d["indice"],
            }
        )
    return pd.DataFrame(filas)


def guardar_evidencias(antes, despues):
    columnas = [
        "consulta", "escenario", "indice", "documentos_devueltos", "claves_examinadas",
        "documentos_examinados", "orden_en_memoria", "tiempo_servidor_ms", "tiempo_cliente_ms",
    ]
    detalle = pd.DataFrame(antes + despues)[columnas + ["id"]]
    detalle[columnas].to_csv(SALIDA_DIR / "indices_antes_despues.csv", index=False, encoding="utf-8-sig")

    sns.set_theme(style="whitegrid", context="notebook")
    plt.figure(figsize=(9, 5))
    grafico = sns.barplot(
        data=detalle, x="id", y="documentos_examinados", hue="escenario",
        hue_order=["antes", "despues"], palette=["#c44e52", "#4c72b0"],
    )
    for contenedor in grafico.containers:
        grafico.bar_label(contenedor, fmt="%d", padding=3)
    plt.title("Documentos examinados: índice simple vs índices compuestos")
    plt.xlabel("Consulta")
    plt.ylabel("Documentos examinados")
    plt.tight_layout()
    plt.savefig(SALIDA_DIR / "indices_antes_despues.png", dpi=150)
    plt.close()


def main():
    parser = argparse.ArgumentParser(description="Evaluación de índices compuestos (IE6)")
    parser.add_argument("--eliminar", action="store_true", help="elimina los índices compuestos y termina")
    args = parser.parse_args()

    uri = os.getenv("MONGO_URI") or getpass.getpass("URI de conexión de MongoDB Atlas: ")
    cliente = None
    try:
        cliente = MongoClient(uri, serverSelectionTimeoutMS=8000)
        cliente.admin.command("ping")
        log.info("Conexión exitosa con MongoDB (base %s)", DB_NAME)
        db = cliente[DB_NAME]

        if args.eliminar:
            eliminar_indices(db)
            return

        log.info("Midiendo ANTES (índice simple sobre estado)")
        antes = medir_todas(db, "antes")

        crear_indices(db)

        log.info("Midiendo DESPUÉS (índices compuestos)")
        despues = medir_todas(db, "despues")

        resultados_ok = validar_resultados(antes, despues)
        resumen = resumen_mejora(antes, despues)
        guardar_evidencias(antes, despues)

        print("\n" + "=" * 78)
        print("Comparación de documentos examinados (antes vs después)")
        print(resumen.to_string(index=False))
        print(f"\nResultados idénticos antes y después: {'sí' if resultados_ok else 'NO, revisar'}")
        print("\nÍndices actuales de ordenes_entrega:")
        for nombre, info in db[COLECCION].index_information().items():
            print(f"  {nombre}: {info['key']}")
        print(f"\nEvidencias guardadas en: {SALIDA_DIR}")
    except PyMongoError as error:
        log.error("Error de MongoDB: %s", error)
        raise SystemExit(1)
    finally:
        if cliente is not None:
            cliente.close()


if __name__ == "__main__":
    main()
