"""Consultas de análisis C1 a C11 (sección 4 del informe), expuestas como endpoints de lectura.

Usa exactamente las definiciones de scripts/consultas_quicktrack.py, así los
resultados de la API coinciden con los del informe.
"""
import logging
import time

from fastapi import APIRouter

import consultas_quicktrack as consultas
import quicktrack_crud as crud
from api.db import BaseDatos
from api.esquemas import ConsultaInfo, ConsultaResultado, respuestas_error

log = logging.getLogger("quicktrack_api")

router = APIRouter(prefix="/consultas", tags=["Consultas de análisis"])

POR_ID = {consulta["id"]: consulta for consulta in consultas.CONSULTAS}


def _info(consulta):
    return {campo: consulta[campo] for campo in ("id", "titulo", "requerimiento", "coleccion", "tipo")}


@router.get("", response_model=list[ConsultaInfo], summary="Listar las consultas disponibles")
def listar_consultas():
    return [_info(consulta) for consulta in consultas.CONSULTAS]


@router.get("/{consulta_id}", response_model=ConsultaResultado, summary="Ejecutar una consulta",
            responses=respuestas_error(404))
def ejecutar_consulta(db: BaseDatos, consulta_id: str):
    """Ejecuta la consulta (C1 a C11, sin distinguir mayúsculas) y mide su tiempo de respuesta."""
    consulta = POR_ID.get(consulta_id.strip().upper())
    if consulta is None:
        raise crud.NoEncontradoError(f"La consulta {consulta_id} no existe. Disponibles: {', '.join(POR_ID)}")
    inicio = time.perf_counter()
    resultados = consultas.ejecutar_una_vez(db, consulta)
    tiempo_ms = round((time.perf_counter() - inicio) * 1000, 1)
    log.info("Consulta %s: %d documentos en %.1f ms", consulta["id"], len(resultados), tiempo_ms)
    return {**_info(consulta), "documentos": len(resultados), "tiempo_ms": tiempo_ms, "resultados": resultados}
