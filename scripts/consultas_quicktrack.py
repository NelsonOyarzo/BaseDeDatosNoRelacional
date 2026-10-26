import getpass
import logging
import os
import time
from datetime import datetime
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
from pymongo import MongoClient
from pymongo.errors import PyMongoError

BASE_DIR = Path(__file__).resolve().parent
SALIDA_DIR = BASE_DIR.parent / "evidencias"
if not SALIDA_DIR.exists():
    SALIDA_DIR = BASE_DIR

DB_NAME = os.getenv("MONGO_DB", "QuickTrack")
REPETICIONES = 5

log = logging.getLogger("consultas_quicktrack")


def configurar_registro():
    # Se configura al ejecutar el script, no al importarlo: la API reutiliza CONSULTAS
    # y lleva su propio registro.
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        handlers=[
            logging.FileHandler(SALIDA_DIR / "consultas.log", encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )

PROY_ORDEN = {"_id": 1, "cliente_id": 1, "estado": 1, "medio_pago": 1, "fecha_envio": 1, "total": 1}

CONSULTAS = [
    {
        "id": "C1",
        "titulo": "Entregas exitosas de mayor valor",
        "requerimiento": "Identificar las 10 órdenes entregadas con total igual o superior a 100000 para analizar clientes de alto valor.",
        "coleccion": "ordenes_entrega",
        "tipo": "find",
        "filtro": {"estado": "Entregado", "total": {"$gte": 100000}},
        "proyeccion": PROY_ORDEN,
        "orden": [("total", -1)],
        "limite": 10,
    },
    {
        "id": "C2",
        "titulo": "Cancelaciones pagadas con tarjeta en 2023",
        "requerimiento": "Revisar las cancelaciones de 2023 pagadas con tarjeta, que implican reembolsos, ordenadas por fecha.",
        "coleccion": "ordenes_entrega",
        "tipo": "find",
        "filtro": {
            "estado": "Cancelado",
            "medio_pago": "Tarjeta",
            "fecha_envio": {"$gte": datetime(2023, 1, 1), "$lt": datetime(2024, 1, 1)},
        },
        "proyeccion": PROY_ORDEN,
        "orden": [("fecha_envio", 1)],
        "limite": 0,
    },
    {
        "id": "C3",
        "titulo": "Pedidos pendientes de alto valor",
        "requerimiento": "Priorizar las órdenes aún en preparación o en tránsito con total igual o superior a 150000.",
        "coleccion": "ordenes_entrega",
        "tipo": "find",
        "filtro": {"estado": {"$in": ["En preparación", "En tránsito"]}, "total": {"$gte": 150000}},
        "proyeccion": PROY_ORDEN,
        "orden": [("total", -1)],
        "limite": 10,
    },
    {
        "id": "C4",
        "titulo": "Resumen de órdenes por estado",
        "requerimiento": "Medir cuántas órdenes hay por estado, su monto total y su ticket medio para evaluar el cumplimiento operativo.",
        "coleccion": "ordenes_entrega",
        "tipo": "aggregate",
        "pipeline": [
            {
                "$group": {
                    "_id": "$estado",
                    "ordenes": {"$sum": 1},
                    "total": {"$sum": "$total"},
                    "ticket_medio": {"$avg": "$total"},
                }
            },
            {
                "$project": {
                    "_id": 0,
                    "estado": "$_id",
                    "ordenes": 1,
                    "total": {"$round": ["$total", 1]},
                    "ticket_medio": {"$round": ["$ticket_medio", 1]},
                }
            },
            {"$sort": {"ordenes": -1}},
        ],
    },
    {
        "id": "C5",
        "titulo": "Ingresos y órdenes por zona",
        "requerimiento": "Comparar las zonas según cantidad de órdenes e ingresos para decidir dónde reforzar la operación logística.",
        "coleccion": "ordenes_entrega",
        "tipo": "aggregate",
        "pipeline": [
            {"$lookup": {"from": "rutas", "localField": "ruta_id", "foreignField": "_id", "as": "ruta"}},
            {"$unwind": "$ruta"},
            {
                "$group": {
                    "_id": "$ruta.zona",
                    "ordenes": {"$sum": 1},
                    "ingresos": {"$sum": "$total"},
                    "ticket_medio": {"$avg": "$total"},
                }
            },
            {
                "$project": {
                    "_id": 0,
                    "zona": "$_id",
                    "ordenes": 1,
                    "ingresos": {"$round": ["$ingresos", 1]},
                    "ticket_medio": {"$round": ["$ticket_medio", 1]},
                }
            },
            {"$sort": {"ingresos": -1}},
        ],
    },
    {
        "id": "C6",
        "titulo": "Clientes con mayor facturación",
        "requerimiento": "Identificar los 5 clientes que más gastan para diseñar acciones de fidelización.",
        "coleccion": "ordenes_entrega",
        "tipo": "aggregate",
        "pipeline": [
            {"$group": {"_id": "$cliente_id", "ordenes": {"$sum": 1}, "total": {"$sum": "$total"}}},
            {"$sort": {"total": -1}},
            {"$limit": 5},
            {"$lookup": {"from": "clientes", "localField": "_id", "foreignField": "_id", "as": "cliente"}},
            {"$unwind": "$cliente"},
            {
                "$project": {
                    "_id": 0,
                    "cliente_id": "$_id",
                    "nombre": "$cliente.nombre",
                    "pais": "$cliente.pais",
                    "ordenes": 1,
                    "total": {"$round": ["$total", 1]},
                }
            },
        ],
    },
    {
        "id": "C7",
        "titulo": "Rutas más utilizadas",
        "requerimiento": "Detectar las 5 rutas con más órdenes para priorizar su optimización.",
        "coleccion": "ordenes_entrega",
        "tipo": "aggregate",
        "pipeline": [
            {"$group": {"_id": "$ruta_id", "ordenes": {"$sum": 1}, "ingresos": {"$sum": "$total"}}},
            {"$sort": {"ordenes": -1, "ingresos": -1}},
            {"$limit": 5},
            {"$lookup": {"from": "rutas", "localField": "_id", "foreignField": "_id", "as": "ruta"}},
            {"$unwind": "$ruta"},
            {
                "$project": {
                    "_id": 0,
                    "ruta_id": "$_id",
                    "origen": "$ruta.ciudad_origen",
                    "destino": "$ruta.ciudad_destino",
                    "zona": "$ruta.zona",
                    "distancia_km": "$ruta.distancia_km",
                    "ordenes": 1,
                    "ingresos": {"$round": ["$ingresos", 1]},
                }
            },
        ],
    },
    {
        "id": "C8",
        "titulo": "Satisfacción según el estado de la orden",
        "requerimiento": "Medir el puntaje medio de las valoraciones por estado de la orden para relacionar el servicio con la satisfacción.",
        "coleccion": "valoraciones",
        "tipo": "aggregate",
        "pipeline": [
            {"$lookup": {"from": "ordenes_entrega", "localField": "orden_id", "foreignField": "_id", "as": "orden"}},
            {"$unwind": "$orden"},
            {"$group": {"_id": "$orden.estado", "valoraciones": {"$sum": 1}, "puntaje_medio": {"$avg": "$puntaje"}}},
            {
                "$project": {
                    "_id": 0,
                    "estado": "$_id",
                    "valoraciones": 1,
                    "puntaje_medio": {"$round": ["$puntaje_medio", 1]},
                }
            },
            {"$sort": {"puntaje_medio": -1}},
        ],
    },
    {
        "id": "C9",
        "titulo": "Motivos de valoraciones bajas",
        "requerimiento": "Agrupar los comentarios de las valoraciones con puntaje 2 o menos para detectar los reclamos más frecuentes.",
        "coleccion": "valoraciones",
        "tipo": "aggregate",
        "pipeline": [
            {"$match": {"puntaje": {"$lte": 2}}},
            {"$group": {"_id": "$comentario", "valoraciones": {"$sum": 1}, "puntaje_medio": {"$avg": "$puntaje"}}},
            {
                "$project": {
                    "_id": 0,
                    "comentario": "$_id",
                    "valoraciones": 1,
                    "puntaje_medio": {"$round": ["$puntaje_medio", 1]},
                }
            },
            {"$sort": {"valoraciones": -1}},
        ],
    },
    {
        "id": "C10",
        "titulo": "Evolución mensual de órdenes e ingresos",
        "requerimiento": "Seguir la evolución mensual de órdenes e ingresos para definir indicadores de seguimiento operativo.",
        "coleccion": "ordenes_entrega",
        "tipo": "aggregate",
        "pipeline": [
            {
                "$group": {
                    "_id": {"$dateToString": {"format": "%Y-%m", "date": "$fecha_envio"}},
                    "ordenes": {"$sum": 1},
                    "ingresos": {"$sum": "$total"},
                }
            },
            {"$project": {"_id": 0, "mes": "$_id", "ordenes": 1, "ingresos": {"$round": ["$ingresos", 1]}}},
            {"$sort": {"mes": 1}},
        ],
    },
    {
        "id": "C11",
        "titulo": "Seguimientos inconsistentes",
        "requerimiento": "Detectar seguimientos cuyo estado actual es En preparación aunque el historial ya registra En tránsito.",
        "coleccion": "seguimiento",
        "tipo": "find",
        "filtro": {"estado_actual": "En preparación", "historial.estado": "En tránsito"},
        "proyeccion": {"_id": 1, "orden_id": 1, "estado_actual": 1},
        "orden": [("orden_id", 1)],
        "limite": 10,
    },
]


def construir_cursor(db, consulta):
    cursor = db[consulta["coleccion"]].find(consulta["filtro"], consulta["proyeccion"])
    if consulta.get("orden"):
        cursor = cursor.sort(consulta["orden"])
    if consulta.get("limite"):
        cursor = cursor.limit(consulta["limite"])
    return cursor


def ejecutar_una_vez(db, consulta):
    if consulta["tipo"] == "find":
        return list(construir_cursor(db, consulta))
    return list(db[consulta["coleccion"]].aggregate(consulta["pipeline"]))


def medir(db, consulta, repeticiones=REPETICIONES):
    resultado = ejecutar_una_vez(db, consulta)
    tiempos = []
    for _ in range(repeticiones):
        inicio = time.perf_counter()
        ejecutar_una_vez(db, consulta)
        tiempos.append((time.perf_counter() - inicio) * 1000)
    return resultado, tiempos


def usa_indice(nodo):
    if isinstance(nodo, dict):
        if nodo.get("stage") == "IXSCAN":
            return True
        return any(usa_indice(v) for v in nodo.values())
    if isinstance(nodo, list):
        return any(usa_indice(v) for v in nodo)
    return False


def explicar(db, consulta):
    if consulta["tipo"] != "find":
        return None, None
    plan = construir_cursor(db, consulta).explain()
    stats = plan.get("executionStats", {})
    return stats.get("totalDocsExamined"), usa_indice(plan.get("queryPlanner", {}))


def comparar_indice(db, repeticiones=20):
    filtro = {"cliente_id": 99}
    resultados = {}
    for nombre, hint in (("con índice", [("cliente_id", 1)]), ("sin índice", [("$natural", 1)])):
        tiempos = []
        for _ in range(repeticiones):
            inicio = time.perf_counter()
            list(db["ordenes_entrega"].find(filtro).hint(hint))
            tiempos.append((time.perf_counter() - inicio) * 1000)
        resultados[nombre] = round(sum(tiempos) / len(tiempos), 1)
    return resultados


def mostrar(consulta, resultado, tiempos, examinados, indice):
    print("\n" + "=" * 78)
    print(f"{consulta['id']} - {consulta['titulo']}")
    print(f"Requerimiento: {consulta['requerimiento']}")
    print("-" * 78)
    if resultado:
        print(pd.DataFrame(resultado).head(10).to_string(index=False))
    else:
        print("Sin resultados")
    medio = sum(tiempos) / len(tiempos)
    print(f"\nDocumentos devueltos: {len(resultado)} | tiempo medio: {medio:.1f} ms ({len(tiempos)} repeticiones)")
    if examinados is not None:
        print(f"Documentos examinados: {examinados} | usa índice: {'sí' if indice else 'no'}")


def guardar_resumen(filas):
    tabla = pd.DataFrame(filas)
    tabla.to_csv(SALIDA_DIR / "tiempos_consultas.csv", index=False, encoding="utf-8-sig")

    sns.set_theme(style="whitegrid", context="notebook")
    plt.figure(figsize=(10, 6))
    grafico = sns.barplot(data=tabla, y="consulta", x="tiempo_medio_ms", hue="consulta", palette="deep", legend=False)
    for contenedor in grafico.containers:
        grafico.bar_label(contenedor, fmt="%.1f", padding=3)
    plt.title("Tiempo medio de respuesta por consulta (ms)")
    plt.xlabel("Tiempo medio (ms)")
    plt.ylabel("")
    plt.tight_layout()
    plt.savefig(SALIDA_DIR / "tiempos_consultas.png", dpi=150)
    plt.show()
    return tabla


def main():
    configurar_registro()
    uri = os.getenv("MONGO_URI") or getpass.getpass("URI de conexión de MongoDB Atlas: ")
    cliente = None
    try:
        cliente = MongoClient(uri, serverSelectionTimeoutMS=8000)
        cliente.admin.command("ping")
        log.info("Conexión exitosa con MongoDB")
        db = cliente[DB_NAME]

        filas = []
        for consulta in CONSULTAS:
            resultado, tiempos = medir(db, consulta)
            examinados, indice = explicar(db, consulta)
            mostrar(consulta, resultado, tiempos, examinados, indice)
            log.info("%s ejecutada: %d documentos, %.1f ms", consulta["id"], len(resultado), sum(tiempos) / len(tiempos))
            filas.append(
                {
                    "consulta": f"{consulta['id']} {consulta['titulo']}",
                    "documentos_devueltos": len(resultado),
                    "tiempo_medio_ms": round(sum(tiempos) / len(tiempos), 1),
                    "documentos_examinados": examinados,
                    "usa_indice": indice,
                }
            )

        print("\n" + "=" * 78)
        print("Comparación de tiempos con y sin índice (filtro por cliente_id, ms)")
        print(comparar_indice(db))

        tabla = guardar_resumen(filas)
        print("\nResumen de tiempos")
        print(tabla.to_string(index=False))
    except PyMongoError as error:
        log.error("Error de MongoDB: %s", error)
        raise SystemExit(1)
    finally:
        if cliente is not None:
            cliente.close()


if __name__ == "__main__":
    main()
