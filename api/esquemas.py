"""Modelos de entrada y salida de la API (Pydantic).

Entrada: los modelos solo revisan la forma del JSON (campos obligatorios, tipos
y campos no permitidos). Las reglas de negocio (total positivo, medio de pago,
cliente existente, etc.) las aplica quicktrack_crud.py, que es la única fuente
de verdad; las listas de valores permitidos se toman de ahí para documentarlas.

Los tipos son estrictos para no aceptar en silencio lo que el CRUD rechaza:
"85000" (texto) no es un total válido, y true no es un puntaje.

Salida: definen lo que devuelve cada endpoint y aparecen en /docs.
"""
from datetime import datetime
from typing import Annotated, Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field, Strict, StrictInt, StrictStr

import quicktrack_crud as crud

Numero = Annotated[float, Strict()]  # acepta enteros y decimales JSON, no textos ni booleanos


class Entrada(BaseModel):
    model_config = ConfigDict(extra="forbid")


class OrdenNueva(Entrada):
    model_config = ConfigDict(json_schema_extra={"examples": [
        {"cliente_id": 1, "ruta_id": "ruta_1", "total": 85000, "medio_pago": "Tarjeta"},
    ]})

    cliente_id: StrictInt | StrictStr = Field(description="Id numérico del cliente; también acepta el formato cli_1")
    ruta_id: StrictStr = Field(description="Id de la ruta, con formato ruta_<id>")
    total: Numero = Field(description="Monto de la orden, mayor que 0")
    medio_pago: StrictStr = Field(json_schema_extra={"enum": list(crud.MEDIOS_PAGO)})
    fecha_envio: StrictStr | None = Field(None, description="Fecha ISO 8601 (2024-05-31). Por defecto, ahora")
    orden_id: StrictStr | None = Field(
        None, description="Id propio con formato orden_<id>. Si se omite se asigna el siguiente número libre",
    )


class CambioEstado(Entrada):
    model_config = ConfigDict(json_schema_extra={"examples": [{"estado": "En tránsito"}]})

    estado: StrictStr = Field(
        description="En preparación -> En tránsito -> Entregado; se puede cancelar mientras está abierta",
        json_schema_extra={"enum": list(crud.ESTADOS_ORDEN)},
    )


class CorreccionTotal(Entrada):
    model_config = ConfigDict(json_schema_extra={"examples": [{"total": 92500.5}]})

    total: Numero = Field(description="Nuevo total, mayor que 0. Solo en órdenes abiertas")


class ValoracionNueva(Entrada):
    model_config = ConfigDict(json_schema_extra={"examples": [{"puntaje": 5, "comentario": "Entrega puntual"}]})

    puntaje: StrictInt = Field(description="Entero de 1 a 5")
    comentario: StrictStr = Field(description="Texto de 1 a 300 caracteres")


# ------------------------------------------------------------------ salida
class EventoSeguimiento(BaseModel):
    estado: str
    fecha: datetime


class Seguimiento(BaseModel):
    id: str = Field(alias="_id")
    orden_id: str
    estado_actual: str
    historial: list[EventoSeguimiento]


class Valoracion(BaseModel):
    id: str = Field(alias="_id")
    orden_id: str
    puntaje: int
    comentario: str


class Orden(BaseModel):
    id: str = Field(alias="_id")
    cliente_id: int
    ruta_id: str
    fecha_envio: datetime
    estado: str
    medio_pago: str
    total: float


class OrdenDetalle(Orden):
    seguimiento: Seguimiento | None = None
    valoracion: Valoracion | None = None


class OrdenCreada(BaseModel):
    orden: Orden
    seguimiento: Seguimiento


class Cliente(BaseModel):
    id: int = Field(alias="_id")
    nombre: str
    correo: str
    pais: str
    fecha_registro: datetime


class Ruta(BaseModel):
    id: str = Field(alias="_id")
    zona: str
    ciudad_origen: str
    ciudad_destino: str
    distancia_km: float


T = TypeVar("T")


class Pagina(BaseModel, Generic[T]):
    total: int = Field(description="Documentos que cumplen el filtro, sin contar la paginación")
    limite: int
    salto: int
    datos: list[T]


class CambioEstadoResultado(BaseModel):
    orden_id: str
    estado_anterior: str
    estado_nuevo: str


class CorreccionTotalResultado(BaseModel):
    orden_id: str
    total_anterior: float
    total_nuevo: float
    modificado: bool


class EliminacionResultado(BaseModel):
    orden_id: str
    seguimientos_eliminados: int
    valoraciones_eliminadas: int


class Consistencia(BaseModel):
    orden_id: str
    consistente: bool
    problemas: list[str]


class Sincronizacion(BaseModel):
    orden_id: str
    corregido: bool
    accion: str


class Auditoria(BaseModel):
    totales: dict[str, int]
    resumen: dict[str, int] = Field(description="Cantidad de problemas por categoría")
    detalle: dict[str, list[Any]] = Field(description="Ids afectados por categoría")


class Reparacion(BaseModel):
    detectados: int
    corregidos: int
    ejecutado: bool


class Depuracion(BaseModel):
    seguimientos_huerfanos: int
    valoraciones_huerfanas: int
    ejecutado: bool


class ConsultaInfo(BaseModel):
    id: str
    titulo: str
    requerimiento: str
    coleccion: str
    tipo: str


class ConsultaResultado(ConsultaInfo):
    documentos: int
    tiempo_ms: float
    resultados: list[dict[str, Any]]


class EstadoBase(BaseModel):
    estado: str
    nombre: str
    latencia_ms: float | None


class Salud(BaseModel):
    estado: str = Field(description="ok o degradado")
    version: str
    base_datos: EstadoBase


class TipoErrorInfo(BaseModel):
    codigo: str
    estado_http: int
    titulo: str
    descripcion: str


class ErrorCampo(BaseModel):
    ubicacion: str = Field(description="cuerpo, parametro, ruta o cabecera")
    campo: str | None
    mensaje: str


class Problema(BaseModel):
    """Respuesta de error (RFC 9457, application/problem+json)."""

    type: str
    title: str
    status: int
    detail: str
    instance: str
    codigo: str
    id_solicitud: str
    fecha: datetime
    errores: list[ErrorCampo] | None = None


def respuestas_error(*estados):
    """Documenta en /docs las respuestas de error de un endpoint."""
    return {estado: {"model": Problema, "description": "Error (ver codigo)"} for estado in estados}
