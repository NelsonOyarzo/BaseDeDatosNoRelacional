import getpass
import logging
import os
from datetime import datetime
from pathlib import Path

import pandas as pd
from pymongo import ASCENDING, MongoClient
from pymongo.errors import PyMongoError

BASE_DIR = Path(__file__).resolve().parent
SALIDA_DIR = BASE_DIR.parent / "evidencias"
if not SALIDA_DIR.exists():
    SALIDA_DIR = BASE_DIR
CSV_DIR = BASE_DIR.parent / "datos_bi"

DB_NAME = os.getenv("MONGO_DB", "QuickTrack")

COLECCIONES_BI = ["clientes_cosmos_etl", "fact_ordenes_bi", "bridge_seguimiento_historial", "rice_atributos"]

INDICES = {
    "fact_ordenes_bi": ["estado", "zona", "mes", "cliente_id"],
    "bridge_seguimiento_historial": ["orden_id", "estado_historial"],
    "rice_atributos": ["decision", "pregunta"],
}

POSITIVOS = {"Excelente atención", "Muy buen servicio", "Recomendaría", "Entrega a tiempo"}
NEGATIVOS = {"Tuvo retraso", "Producto en mal estado"}

CLIENTES_COSMOS = [
    (1, "Juan", "Lima", "2024-05-15"),
    (2, "María", "Bogotá", "2024-06-01"),
    (4, "Sofia", "Buenos Aires", "2024-07-02"),
    (5, "Luis", "Ciudad de México", "2024-07-20"),
]

PERSPECTIVAS = {1: "Negocio", 2: "Técnica", 3: "Operacional"}

RICE = [
    (1, "total", "ordenes_entrega", 1.0, 3.0, 1.0, 1, "Métrica financiera central: ingresos entregados, cancelados y pendientes."),
    (1, "estado", "ordenes_entrega", 1.0, 3.0, 1.0, 1, "Separa ingresos reales, pérdidas por cancelación y backlog en curso."),
    (1, "medio_pago", "ordenes_entrega", 1.0, 2.0, 1.0, 1, "Identifica la exposición a reembolsos por medio de pago."),
    (1, "zona", "rutas", 1.0, 3.0, 1.0, 2, "Revela las zonas con mayores pérdidas; exige unión con órdenes."),
    (1, "fecha_envio", "ordenes_entrega", 1.0, 3.0, 0.9, 2, "Base temporal de la evolución mensual; requiere derivar AAAA-MM."),
    (1, "ciudad", "clientes_cosmos_etl", 1.0, 2.0, 1.0, 2, "Segmenta la facturación de los clientes activos tras unir id con cliente_id."),
    (1, "puntaje", "valoraciones", 1.0, 2.0, 0.75, 2, "Vincula satisfacción con retención, pero la mayoría pertenece a órdenes no entregadas."),
    (1, "pais", "clientes", 1.0, 1.0, 0.5, 2, "Países sintéticos aleatorios sin coherencia con las rutas dentro de Chile."),
    (1, "comentario", "valoraciones", 1.0, 0.5, 0.6, 3, "Texto libre con contradicciones frente al puntaje; no aporta al cálculo financiero."),
    (2, "id / _id -> cliente_id", "clientes / todas", 1.0, 3.0, 1.0, 1, "Llave de relación; se normaliza a entero en el ETL."),
    (2, "activo", "clientes_cosmos", 1.0, 3.0, 1.0, 1, "Se filtra en la consulta de origen para leer menos documentos y ahorrar RU/s."),
    (2, "estado_actual", "seguimiento", 1.0, 3.0, 0.85, 1, "Atributo de auditoría: detecta seguimientos desalineados con la orden."),
    (2, "historial", "seguimiento", 1.0, 3.0, 0.85, 2, "Arreglo de eventos que se desanida para auditar el flujo operativo."),
    (2, "fecha_registro", "clientes_cosmos", 1.0, 2.0, 0.9, 2, "Útil para cohortes, con bandera temporal por órdenes previas al alta."),
    (2, "_rid, _self, _etag, _ts", "clientes_cosmos", 1.0, 0.25, 1.0, 1, "Metadatos internos del motor sin valor analítico."),
    (2, "correo", "clientes (todas)", 1.0, 0.25, 0.95, 1, "Dato personal identificable que no debe copiarse a la herramienta de BI."),
    (3, "ruta_id", "ordenes / rutas", 1.0, 3.0, 1.0, 1, "Identifica las rutas con mayor carga para asignar flota."),
    (3, "estado", "ordenes_entrega", 1.0, 3.0, 1.0, 1, "Filtra la carga operativa abierta y los pedidos críticos."),
    (3, "ciudad_origen / destino", "rutas", 1.0, 2.0, 0.95, 1, "Define el tramo físico de despacho para la hoja de ruta."),
    (3, "historial.estado / fecha", "seguimiento", 1.0, 3.0, 0.85, 2, "Audita en qué etapa del flujo se detuvo cada paquete."),
    (3, "distancia_km", "rutas", 1.0, 2.0, 0.65, 2, "Útil para estimar kilometraje, con baja confianza por distancias dispares."),
    (3, "comentario", "valoraciones", 1.0, 2.0, 0.65, 2, "Permite separar reclamos reales en puntajes bajos tras filtrar contradicciones."),
    (3, "medio_pago", "ordenes_entrega", 1.0, 0.5, 1.0, 1, "Secundario para el transporte; incide solo en cobro contra entrega."),
    (3, "nombre", "clientes", 1.0, 0.25, 1.0, 1, "No modifica la planificación agregada de rutas ni la capacidad por zona."),
]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler(SALIDA_DIR / "modelo_bi.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger("cargar_modelo_bi")


def a_fecha(valor):
    if isinstance(valor, datetime):
        return valor.replace(tzinfo=None)
    return datetime.fromisoformat(str(valor).replace("Z", "+00:00")).replace(tzinfo=None)


def a_dia(valor):
    fecha = a_fecha(valor)
    return datetime(fecha.year, fecha.month, fecha.day)


def a_entero(valor):
    return int(str(valor).replace("cli_", ""))


def decision(puntaje):
    if puntaje >= 1.0:
        return "Conservar"
    if puntaje >= 0.5:
        return "Evaluar"
    return "Descartar"


def construir_rice():
    docs = []
    for numero, (pregunta, atributo, coleccion, r, i, c, e, justificacion) in enumerate(RICE, start=1):
        puntaje = r * i * c / e
        docs.append(
            {
                "_id": f"rice_{numero}",
                "pregunta": pregunta,
                "perspectiva": PERSPECTIVAS[pregunta],
                "atributo": atributo,
                "coleccion": coleccion,
                "reach": r,
                "impact": i,
                "confidence": c,
                "effort": e,
                "puntaje_rice": round(puntaje, 2),
                "decision": decision(puntaje),
                "justificacion": justificacion,
            }
        )
    return docs


def construir_modelo(clientes, ordenes, rutas, seguimientos, valoraciones):
    activos = {c[0]: {"_id": c[0], "nombre": c[1], "ciudad": c[2], "fecha_registro": a_dia(c[3])} for c in CLIENTES_COSMOS}
    registro = {c["_id"]: a_fecha(c["fecha_registro"]) for c in clientes}
    zonas = {r["_id"]: r for r in rutas}
    seg_por_orden = {s["orden_id"]: s for s in seguimientos}
    val_por_orden = {v["orden_id"]: v for v in valoraciones}

    hechos = []
    for o in ordenes:
        cliente_id = a_entero(o["cliente_id"])
        ruta = zonas.get(o["ruta_id"], {})
        seg = seg_por_orden.get(o["_id"])
        val = val_por_orden.get(o["_id"])
        fecha_envio = a_fecha(o["fecha_envio"])
        historial = sorted(seg["historial"], key=lambda e: a_fecha(e["fecha"])) if seg else []
        estados_historial = [e["estado"] for e in historial]
        hechos.append(
            {
                "_id": o["_id"],
                "cliente_id": cliente_id,
                "ruta_id": o["ruta_id"],
                "fecha_envio": a_dia(fecha_envio),
                "mes": fecha_envio.strftime("%Y-%m"),
                "estado": o["estado"],
                "medio_pago": o["medio_pago"],
                "total": float(o["total"]),
                "zona": ruta.get("zona"),
                "ciudad_origen": ruta.get("ciudad_origen"),
                "ciudad_destino": ruta.get("ciudad_destino"),
                "cliente_activo_cosmos": cliente_id in activos,
                "cliente_ciudad_cosmos": activos[cliente_id]["ciudad"] if cliente_id in activos else None,
                "seguimiento_estado_actual": seg["estado_actual"] if seg else None,
                "puntaje_valoracion": val["puntaje"] if val else None,
                "flag_envio_previo_registro": bool(cliente_id in registro and fecha_envio < registro[cliente_id]),
                "flag_orden_vs_seguimiento": bool(seg and seg["estado_actual"] != o["estado"]),
                "flag_seguimiento_vs_historial": bool(historial and seg["estado_actual"] != estados_historial[-1]),
                "flag_c11": bool(seg and seg["estado_actual"] == "En preparación" and "En tránsito" in estados_historial),
                "flag_valoracion_contradictoria": bool(
                    val
                    and (
                        (val["comentario"] in POSITIVOS and val["puntaje"] <= 2)
                        or (val["comentario"] in NEGATIVOS and val["puntaje"] >= 4)
                    )
                ),
                "flag_valorada_no_entregada": bool(val and o["estado"] != "Entregado"),
            }
        )

    puente = []
    for s in seguimientos:
        for secuencia, evento in enumerate(sorted(s["historial"], key=lambda e: a_fecha(e["fecha"])), start=1):
            puente.append(
                {
                    "_id": f"{s['_id']}_{secuencia}",
                    "seguimiento_id": s["_id"],
                    "orden_id": s["orden_id"],
                    "secuencia": secuencia,
                    "estado_historial": evento["estado"],
                    "fecha_evento": a_dia(evento["fecha"]),
                }
            )

    return {
        "clientes_cosmos_etl": list(activos.values()),
        "fact_ordenes_bi": hechos,
        "bridge_seguimiento_historial": puente,
        "rice_atributos": construir_rice(),
    }


def resumen(modelo):
    hechos = pd.DataFrame(modelo["fact_ordenes_bi"])
    filas = {"órdenes": len(hechos), "eventos de historial": len(modelo["bridge_seguimiento_historial"]), "atributos RICE": len(modelo["rice_atributos"])}
    for bandera in [c for c in hechos.columns if c.startswith("flag_")]:
        filas[bandera] = int(hechos[bandera].sum())
    filas["total facturado"] = round(float(hechos["total"].sum()), 1)
    return filas


def exportar_csv(modelo):
    CSV_DIR.mkdir(exist_ok=True)
    for nombre, docs in modelo.items():
        pd.DataFrame(docs).to_csv(CSV_DIR / f"{nombre}.csv", index=False, encoding="utf-8-sig")
    log.info("CSV exportados en %s", CSV_DIR)


def main():
    uri = os.getenv("MONGO_URI") or getpass.getpass("URI de conexión de MongoDB Atlas: ")
    cliente = None
    try:
        cliente = MongoClient(uri, serverSelectionTimeoutMS=8000)
        cliente.admin.command("ping")
        log.info("Conexión exitosa con MongoDB")
        db = cliente[DB_NAME]

        origen = {nombre: list(db[nombre].find({})) for nombre in ["clientes", "ordenes_entrega", "rutas", "seguimiento", "valoraciones"]}
        for nombre, docs in origen.items():
            log.info("Origen %s: %d documentos", nombre, len(docs))
        if not all(origen.values()):
            raise SystemExit("Hay colecciones de origen vacías: revisa el nombre de la base (MONGO_DB) y la carga de datos.")

        modelo = construir_modelo(
            origen["clientes"], origen["ordenes_entrega"], origen["rutas"], origen["seguimiento"], origen["valoraciones"]
        )

        for nombre in COLECCIONES_BI:
            db[nombre].drop()
            for campo in INDICES.get(nombre, []):
                db[nombre].create_index([(campo, ASCENDING)])
            resultado = db[nombre].insert_many(modelo[nombre])
            log.info("%s: %d documentos insertados", nombre, len(resultado.inserted_ids))

        print("\nVerificación en MongoDB")
        for nombre in COLECCIONES_BI:
            print(f"{nombre}: {db[nombre].count_documents({})} documentos")
        print("\nResumen del modelo")
        for clave, valor in resumen(modelo).items():
            print(f"{clave}: {valor}")

        exportar_csv(modelo)
    except PyMongoError as error:
        log.error("Error de MongoDB: %s", error)
        raise SystemExit(1)
    finally:
        if cliente is not None:
            cliente.close()


if __name__ == "__main__":
    main()