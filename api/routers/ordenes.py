"""Órdenes de entrega: CRUD completo con su seguimiento y valoración.

Cada endpoint delega en quicktrack_crud.py; los errores que este lanza se
convierten en respuestas HTTP en api/errores.py.
"""
from typing import Annotated

from fastapi import APIRouter, Query, Request, Response

import quicktrack_crud as crud
from api.db import BaseDatos
from api.esquemas import (
    CambioEstado, CambioEstadoResultado, Consistencia, CorreccionTotal, CorreccionTotalResultado,
    EliminacionResultado, Orden, OrdenCreada, OrdenDetalle, OrdenNueva, Pagina, Seguimiento,
    Sincronizacion, Valoracion, ValoracionNueva, respuestas_error,
)

router = APIRouter(prefix="/ordenes", tags=["Órdenes"])

Limite = Annotated[int, Query(description="Documentos por página, de 1 a 100")]
Salto = Annotated[int, Query(description="Documentos que se omiten (paginación)")]


@router.get("", response_model=Pagina[Orden], summary="Listar órdenes", responses=respuestas_error(400))
def listar_ordenes(
    db: BaseDatos,
    estado: Annotated[str | None, Query(description="En preparación, En tránsito, Entregado o Cancelado")] = None,
    cliente_id: Annotated[str | None, Query(description="Id del cliente (5 o cli_5)")] = None,
    limite: Limite = 20,
    salto: Salto = 0,
):
    """Órdenes más recientes primero, con filtros opcionales y paginación."""
    datos = crud.listar_ordenes(db, estado, cliente_id, limite, salto)
    return {"total": crud.contar_ordenes(db, estado, cliente_id), "limite": limite, "salto": salto, "datos": datos}


@router.post("", status_code=201, response_model=OrdenCreada, summary="Crear una orden",
             responses=respuestas_error(400, 409))
def crear_orden(db: BaseDatos, datos: OrdenNueva, request: Request, response: Response):
    """Crea la orden en estado En preparación junto con su seguimiento inicial.

    Valida que el cliente y la ruta existan. Si falla el seguimiento, la orden se revierte.
    """
    creada = crud.crear_orden(db, **datos.model_dump())
    response.headers["Location"] = str(request.url_for("leer_orden", orden_id=creada["orden"]["_id"]))
    return creada


@router.get("/{orden_id}", name="leer_orden", response_model=OrdenDetalle, response_model_exclude_unset=True,
            summary="Leer una orden", responses=respuestas_error(400, 404))
def leer_orden(
    db: BaseDatos,
    orden_id: str,
    detalle: Annotated[bool, Query(description="Incluir seguimiento y valoración")] = True,
):
    return crud.leer_orden(db, orden_id, detalle)


@router.delete("/{orden_id}", response_model=EliminacionResultado, summary="Eliminar una orden",
               responses=respuestas_error(400, 404, 409))
def eliminar_orden(
    db: BaseDatos,
    orden_id: str,
    forzar: Annotated[bool, Query(description="Permite eliminar órdenes en tránsito o entregadas")] = False,
):
    """Elimina la orden con su seguimiento y su valoración, sin dejar documentos huérfanos.

    Sin `forzar` solo se eliminan órdenes canceladas o en preparación (409 en otro caso).
    """
    return crud.eliminar_orden(db, orden_id, forzar)


@router.patch("/{orden_id}/estado", response_model=CambioEstadoResultado, summary="Cambiar el estado",
              responses=respuestas_error(400, 404, 409))
def cambiar_estado(db: BaseDatos, orden_id: str, cambio: CambioEstado):
    """Avanza el estado respetando el flujo y lo registra en el historial del seguimiento.

    Transiciones no permitidas (saltar etapas, salir de un estado final) responden 409.
    """
    return crud.avanzar_estado(db, orden_id, cambio.estado)


@router.patch("/{orden_id}/total", response_model=CorreccionTotalResultado, summary="Corregir el total",
              responses=respuestas_error(400, 404, 409))
def corregir_total(db: BaseDatos, orden_id: str, correccion: CorreccionTotal):
    """Solo en órdenes abiertas (En preparación o En tránsito). Repetir el mismo total no lo modifica."""
    return crud.corregir_total(db, orden_id, correccion.total)


@router.post("/{orden_id}/valoracion", status_code=201, response_model=Valoracion, summary="Valorar una orden",
             responses=respuestas_error(400, 404, 409))
def valorar_orden(db: BaseDatos, orden_id: str, datos: ValoracionNueva, request: Request, response: Response):
    """Solo órdenes entregadas, una valoración por orden (409 si se repite)."""
    valoracion = crud.registrar_valoracion(db, orden_id, datos.puntaje, datos.comentario)
    response.headers["Location"] = str(request.url_for("leer_orden", orden_id=orden_id))
    return valoracion


@router.get("/{orden_id}/seguimiento", response_model=Seguimiento, summary="Seguimiento de una orden",
            responses=respuestas_error(400, 404))
def leer_seguimiento(db: BaseDatos, orden_id: str):
    """Estado actual e historial de cambios de la orden."""
    seguimiento = crud.leer_orden(db, orden_id)["seguimiento"]
    if seguimiento is None:
        raise crud.NoEncontradoError(f"La orden {orden_id} no tiene seguimiento")
    return seguimiento


@router.get("/{orden_id}/consistencia", response_model=Consistencia, summary="Verificar la consistencia",
            responses=respuestas_error(400, 404))
def verificar_consistencia(db: BaseDatos, orden_id: str):
    """Revisa cliente, ruta, seguimiento y valoración de la orden."""
    crud.leer_orden(db, orden_id, detalle=False)  # 404 si no existe
    problemas = crud.verificar_consistencia(db, orden_id)
    return {"orden_id": orden_id, "consistente": not problemas, "problemas": problemas}


@router.post("/{orden_id}/sincronizar", response_model=Sincronizacion, summary="Sincronizar el seguimiento",
             responses=respuestas_error(400, 404))
def sincronizar_seguimiento(db: BaseDatos, orden_id: str):
    """Alinea el seguimiento con el estado de la orden, que es la fuente de verdad."""
    return crud.sincronizar_seguimiento(db, orden_id)
