"""Clientes y rutas: lectura, para que una aplicación externa pueda elegirlos al crear órdenes."""
from typing import Annotated

from fastapi import APIRouter, Query

import quicktrack_crud as crud
from api.db import BaseDatos
from api.esquemas import Cliente, Orden, Pagina, Ruta, respuestas_error

clientes = APIRouter(prefix="/clientes", tags=["Clientes"])
rutas = APIRouter(prefix="/rutas", tags=["Rutas"])

Limite = Annotated[int, Query(description="Documentos por página, de 1 a 100")]
Salto = Annotated[int, Query(description="Documentos que se omiten (paginación)")]


@clientes.get("", response_model=Pagina[Cliente], summary="Listar clientes", responses=respuestas_error(400))
def listar_clientes(
    db: BaseDatos,
    pais: Annotated[str | None, Query(description="País exacto, sin distinguir mayúsculas ni tildes")] = None,
    limite: Limite = 20,
    salto: Salto = 0,
):
    datos = crud.listar_clientes(db, pais, limite, salto)
    return {"total": crud.contar_clientes(db, pais), "limite": limite, "salto": salto, "datos": datos}


@clientes.get("/{cliente_id}", response_model=Cliente, summary="Leer un cliente",
              responses=respuestas_error(400, 404))
def leer_cliente(db: BaseDatos, cliente_id: str):
    """Acepta el id numérico (5) o con prefijo (cli_5)."""
    return crud.leer_cliente(db, cliente_id)


@clientes.get("/{cliente_id}/ordenes", response_model=Pagina[Orden], summary="Órdenes de un cliente",
              responses=respuestas_error(400, 404))
def ordenes_del_cliente(
    db: BaseDatos,
    cliente_id: str,
    estado: Annotated[str | None, Query(description="Filtra por estado de la orden")] = None,
    limite: Limite = 20,
    salto: Salto = 0,
):
    cliente = crud.leer_cliente(db, cliente_id)  # 404 si el cliente no existe
    datos = crud.listar_ordenes(db, estado, cliente["_id"], limite, salto)
    return {"total": crud.contar_ordenes(db, estado, cliente["_id"]), "limite": limite, "salto": salto, "datos": datos}


@rutas.get("", response_model=Pagina[Ruta], summary="Listar rutas", responses=respuestas_error(400))
def listar_rutas(
    db: BaseDatos,
    zona: Annotated[str | None, Query(description="Norte, Sur, Centro, Oriente o Poniente")] = None,
    limite: Limite = 20,
    salto: Salto = 0,
):
    datos = crud.listar_rutas(db, zona, limite, salto)
    return {"total": crud.contar_rutas(db, zona), "limite": limite, "salto": salto, "datos": datos}


@rutas.get("/{ruta_id}", response_model=Ruta, summary="Leer una ruta", responses=respuestas_error(400, 404))
def leer_ruta(db: BaseDatos, ruta_id: str):
    return crud.leer_ruta(db, ruta_id)
