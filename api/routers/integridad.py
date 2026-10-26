"""Auditoría y corrección de integridad de toda la base.

Las correcciones funcionan en modo simulación salvo que se pida ejecutar=true:
los datos originales tienen 96 seguimientos desalineados que se informan en
C11, y corregirlos cambiaría esos resultados.
"""
import logging
from typing import Annotated

from fastapi import APIRouter, Query

import quicktrack_crud as crud
from api.db import BaseDatos
from api.esquemas import Auditoria, Depuracion, Reparacion

log = logging.getLogger("quicktrack_api")

router = APIRouter(prefix="/integridad", tags=["Integridad"])

Ejecutar = Annotated[bool, Query(description="false: solo informa (simulación). true: modifica la base")]


@router.get("/auditoria", response_model=Auditoria, summary="Auditar la integridad de la base")
def auditar(db: BaseDatos):
    """Órdenes sin cliente, ruta o seguimiento, documentos huérfanos y seguimientos desalineados."""
    auditoria = crud.auditar_integridad(db)
    detalle = {clave: valor for clave, valor in auditoria.items() if isinstance(valor, list)}
    return {"totales": auditoria["totales"], "resumen": crud.resumen_auditoria(auditoria), "detalle": detalle}


@router.post("/seguimientos/reparar", response_model=Reparacion, summary="Reparar seguimientos desalineados")
def reparar_seguimientos(db: BaseDatos, ejecutar: Ejecutar = False):
    if ejecutar:
        log.warning("Reparación de seguimientos en modo ejecución: se modificará la base")
    return crud.reparar_seguimientos(db, ejecutar)


@router.post("/huerfanos/depurar", response_model=Depuracion, summary="Eliminar documentos huérfanos")
def depurar_huerfanos(db: BaseDatos, ejecutar: Ejecutar = False):
    if ejecutar:
        log.warning("Depuración de huérfanos en modo ejecución: se eliminarán documentos")
    return crud.depurar_huerfanos(db, ejecutar)
