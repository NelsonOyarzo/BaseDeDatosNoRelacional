# QuickTrack: análisis logístico con MongoDB Atlas

Evaluación Parcial 2 de **Base de Datos No Relacionales (BDY0101)**, Forma B. El proyecto implementa una base de datos NoSQL para QuickTrack, una empresa de logística de entregas express, y desarrolla consultas, operaciones CRUD e integración con una aplicación externa.

## Objetivo del proyecto

Configurar una base de datos MongoDB, cargar los datos operativos de QuickTrack y analizarlos para apoyar decisiones sobre rutas, zonas, satisfacción del cliente y cumplimiento de órdenes. Luego, integrar la base con una aplicación externa que lea y escriba datos.

## Tecnología

| Elemento | Detalle |
|---|---|
| Base de datos | MongoDB Atlas (clúster gratuito M0) |
| Nombre de la base | `QuickTrack` (respeta mayúsculas: MongoDB distingue entre `QuickTrack` y `quicktrack`) |
| Lenguaje | Python 3.11 |
| Librerías | `pymongo`, `pandas`, `seaborn`, `matplotlib` |

## Estructura del repositorio

```
BaseDeDatosNoRelacional/
├─ README.md
├─ .gitignore
├─ datos/          archivos JSON originales
├─ scripts/        carga_quicktrack.py, consultas_quicktrack.py, diagnostico_atlas.py
├─ evidencias/     capturas, tiempos_consultas.csv/.png y registros (.log)
└─ informe/        informe técnico final en PDF
```

## Colecciones

Cada colección tiene 100 documentos.

| Colección | Campos |
|---|---|
| `clientes` | `_id` (número), `nombre`, `correo`, `pais`, `fecha_registro` |
| `ordenes_entrega` | `_id`, `cliente_id` (número), `ruta_id`, `fecha_envio`, `estado`, `medio_pago`, `total` |
| `rutas` | `_id`, `zona`, `ciudad_origen`, `ciudad_destino`, `distancia_km` |
| `seguimiento` | `_id`, `orden_id`, `estado_actual`, `historial` (lista de `estado` y `fecha`) |
| `valoraciones` | `_id`, `orden_id`, `puntaje` (1 a 5), `comentario` |

Relaciones: `ordenes_entrega.cliente_id` apunta a `clientes._id`, `ordenes_entrega.ruta_id` a `rutas._id`, y `seguimiento.orden_id` y `valoraciones.orden_id` a `ordenes_entrega._id`.

Valores de `estado` en las órdenes: `En preparación`, `En tránsito`, `Entregado` y `Cancelado`. Valores de `medio_pago`: `Tarjeta`, `Efectivo` y `Transferencia`.

Índices creados por el script de carga: `clientes.correo` (único), `ordenes_entrega` (`cliente_id`, `ruta_id`, `estado`, `fecha_envio`), `rutas.zona`, `seguimiento.orden_id` (único) y `valoraciones` (`orden_id` único, `puntaje`).

## Cómo trabajar con el proyecto

### 1. Requisitos
- Python 3.11 o superior.
- Acceso al proyecto de MongoDB Atlas (invitación aceptada) y la IP del equipo autorizada en **Security > Database & Network Access > IP Access List**.
- La URI de conexión con la contraseña, entregada por el equipo por un canal privado.

### 2. Instalar y clonar

```
git clone https://github.com/NelsonOyarzo/BaseDeDatosNoRelacional.git
cd BaseDeDatosNoRelacional
python -m pip install pymongo pandas seaborn matplotlib
```

### 3. Ejecutar los scripts
Cada script pide la URI al ejecutarse (no se ve al pegarla). También se puede definir la variable de entorno `MONGO_URI`. El nombre de la base se puede cambiar con `MONGO_DB`, y por defecto es `QuickTrack`.

| Script | Qué hace |
|---|---|
| `scripts/diagnostico_atlas.py` | Comprueba la conexión y lista las bases con sus colecciones y cantidad de documentos |
| `scripts/consultas_quicktrack.py` | Ejecuta las 11 consultas de lectura, mide tiempos y guarda `tiempos_consultas.csv` y `tiempos_consultas.png` en `evidencias` |
| `scripts/carga_quicktrack.py` | Carga inicial de datos. Borra y recrea las colecciones |

```
python scripts\diagnostico_atlas.py
python scripts\consultas_quicktrack.py
```

**No ejecutar `carga_quicktrack.py`**: los datos ya están cargados y el script elimina las colecciones antes de insertar. Solo debe correrlo una persona, y solo si hay que reconstruir la base.

### 4. Seguridad
- No subir la URI, la contraseña de Atlas ni archivos `.env` al repositorio.
- Al terminar el proyecto, eliminar `0.0.0.0/0` de la lista de IP de Atlas, si se usó, y dejar solo las IP del equipo.

## Preparación de los datos

La carga transforma los datos antes de insertarlos:
- `cliente_id` pasa del texto `cli_99` al número `99`, para que coincida con `clientes._id`.
- Las fechas se convierten a tipo fecha, incluidas las del historial de seguimiento.
- Se validan campos obligatorios, puntaje entre 1 y 5 y total positivo. Los documentos inválidos se descartan y se registran en `carga.log`.

## Consultas de lectura (sección 4 del informe)

| Id | Consulta |
|---|---|
| C1 | Entregas exitosas de mayor valor |
| C2 | Cancelaciones pagadas con tarjeta en 2023 |
| C3 | Pedidos pendientes de alto valor |
| C4 | Resumen de órdenes por estado |
| C5 | Ingresos y órdenes por zona |
| C6 | Clientes con mayor facturación |
| C7 | Rutas más utilizadas |
| C8 | Satisfacción según el estado de la orden |
| C9 | Motivos de valoraciones bajas |
| C10 | Evolución mensual de órdenes e ingresos |
| C11 | Seguimientos inconsistentes |

Resultados destacados:
- Órdenes por estado: 29 en preparación, 27 entregadas, 23 canceladas y 21 en tránsito.
- Las órdenes canceladas suman 2 672 017.4 en monto, con el ticket medio más alto (116 174.7).
- Zonas con más ingresos: Poniente (2 751 194.2) y Norte (2 698 098.7). La más baja es Sur (1 228 343.6).
- Puntaje medio de valoraciones: entre 2.8 (en preparación) y 3.3 (entregado).
- Los tiempos de respuesta rondan los 74 a 80 ms en todas las consultas. Con 100 documentos por colección, la medición refleja sobre todo la latencia de red, y la comparación con y sin índice no muestra diferencia.

## Limitaciones de los datos

- Los tiempos de entrega no se pueden calcular de forma confiable: no existe `fecha_entrega`, el historial de seguimiento no coincide con `fecha_envio` y el `estado_actual` difiere del último estado del historial en la mayoría de los casos.
- Muchas órdenes tienen fecha de envío anterior a la fecha de registro del cliente.
- Las rutas no funcionan como catálogo: un mismo par origen-destino aparece con distancias muy distintas (por ejemplo, Valparaíso–Arica con 113.73 km).
- Las valoraciones tienen puntajes que contradicen su comentario (por ejemplo, "Muy buen servicio" con puntaje 2 o menos).
- Los clientes provienen de países muy variados, con datos claramente sintéticos.

## Estado del proyecto

| Sección del informe | Tarea | Estado | Responsable |
|---|---|---|---|
| 1 | Objetivos del proyecto | Pendiente | |
| 2 | Configuración de Atlas (clúster, usuario, red, base y colecciones) | Hecho | |
| 3 | Carga de datos de prueba y verificación | Hecho | |
| 4 | Consultas de lectura y medición de tiempos | Hecho | |
| 4 | Índices compuestos y nueva medición de documentos examinados (IE6) | Pendiente | |
| 5 | CRUD completo (inserciones, actualizaciones y eliminaciones) con validación | Pendiente | |
| 6 | Integración con una aplicación externa (API REST o Postman) | Pendiente | |
| 7 | Control de errores y trazabilidad | Pendiente | |
| Entrega | Informe técnico en PDF y enlace al repositorio en AVA | Pendiente | |

## Entregables

- Informe técnico en PDF con las siete secciones.
- Scripts de creación, inserción, consultas y CRUD (carpeta `scripts`).
- Capturas de consultas y resultados (carpeta `evidencias`).
- Código o capturas de la integración con la aplicación externa.
- Enlace a este repositorio, entregado por AVA.
