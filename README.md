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
| API REST | FastAPI + Uvicorn, validación con Pydantic, configuración con `pydantic-settings` |
| Pruebas de la API | Postman (colección y entorno en `postman/`) y Newman para ejecutarla por consola |
| Interfaz web | HTML, CSS y JavaScript sin dependencias ni compilación, servida por la misma API |

## Estructura del repositorio

```
BaseDeDatosNoRelacional/
├─ README.md
├─ .gitignore
├─ requirements.txt
├─ .env.example    plantilla de configuración de la API (copiar como .env)
├─ datos/          archivos JSON originales
├─ scripts/        carga, consultas, índices, CRUD y diagnóstico
├─ api/            API REST (FastAPI) que reutiliza el CRUD y las consultas
├─ interfaz/       interfaz web (aplicación externa) que consume la API
├─ postman/        colección y entorno de Postman con las pruebas de la API
├─ documentacion/  guías de configuración (archivo .env con la URI de Atlas)
├─ evidencias/     capturas, tiempos, índices, resultados del CRUD y registros (.log)
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
python -m pip install -r requirements.txt
```

### 3. Ejecutar los scripts
Cada script pide la URI al ejecutarse (no se ve al pegarla). También se puede definir la variable de entorno `MONGO_URI`. El nombre de la base se puede cambiar con `MONGO_DB`, y por defecto es `QuickTrack`.

| Script | Qué hace |
|---|---|
| `scripts/diagnostico_atlas.py` | Comprueba la conexión y lista las bases con sus colecciones y cantidad de documentos |
| `scripts/consultas_quicktrack.py` | Ejecuta las 11 consultas de lectura, mide tiempos y guarda `tiempos_consultas.csv` y `tiempos_consultas.png` en `evidencias` |
| `scripts/indices_compuestos.py` | Mide documentos examinados antes y después de crear índices compuestos (IE6) y guarda `indices_antes_despues.csv` y `.png`. Con `--eliminar` borra los índices compuestos |
| `scripts/quicktrack_crud.py` | Módulo con las operaciones CRUD, las lecturas de clientes y rutas y las validaciones. No se ejecuta solo: lo importan el demo y la API |
| `scripts/demo_crud.py` | Demostración del CRUD (casos de negocio, errores provocados e integridad). Guarda `crud.log` y `crud_resultados.csv` en `evidencias` |
| `scripts/carga_quicktrack.py` | Carga inicial de datos. Borra y recrea las colecciones |

```
python scripts\diagnostico_atlas.py
python scripts\consultas_quicktrack.py
python scripts\indices_compuestos.py
python scripts\demo_crud.py
```

**No ejecutar `carga_quicktrack.py`**: los datos ya están cargados y el script elimina las colecciones antes de insertar. Solo debe correrlo una persona, y solo si hay que reconstruir la base.

`demo_crud.py` es seguro de repetir: usa órdenes con prefijo `orden_test_` y las elimina al terminar, de modo que la base queda igual que antes (100 órdenes, 100 seguimientos, 100 valoraciones).

### 4. Iniciar la API y la interfaz web
Desde la raíz del repositorio:

```
python -m api
```

Toma la URI de `MONGO_URI` o del archivo `.env` (copiar `.env.example` como `.env` y completar; el paso a paso está en [`documentacion/configurar_env.md`](documentacion/configurar_env.md)); si no la encuentra, la pide igual que los scripts. Queda escuchando en `http://127.0.0.1:8000`:

- Interfaz web: `http://127.0.0.1:8000/` (ver [Interfaz web](#interfaz-web)).
- Documentación interactiva (Swagger UI): `http://127.0.0.1:8000/docs`, y ReDoc en `/redoc`.
- Especificación OpenAPI: `http://127.0.0.1:8000/openapi.json` (se puede importar en Postman).
- Registro de cada solicitud: `evidencias/api.log`.

El detalle está en las secciones [API REST](#api-rest-sección-6-del-informe) y [Control de errores](#control-de-errores-y-trazabilidad-sección-7-del-informe).

### 5. Seguridad
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
- Los tiempos de respuesta rondan los 74 a 80 ms en todas las consultas. Con 100 documentos por colección, la medición de tiempo refleja sobre todo la latencia de red, por lo que la eficiencia se evalúa con los documentos examinados.

### Eficiencia con índices compuestos (IE6)

Con `scripts/indices_compuestos.py` se compara, para C1, C2 y C3, cuántos documentos examina MongoDB con el índice simple sobre `estado` y con índices compuestos:

| Consulta | Documentos examinados antes | Después | Ordenamiento en memoria |
|---|---|---|---|
| C1 Entregas exitosas de mayor valor | 27 | 10 | sí, luego no |
| C2 Cancelaciones pagadas con tarjeta en 2023 | 23 | 4 | sí, luego no |
| C3 Pedidos pendientes de alto valor | 50 | 10 | sí, luego no |

Los resultados de las consultas no cambian; el índice compuesto evita revisar documentos de más y el ordenamiento en memoria.

## CRUD con validación (sección 5 del informe)

El módulo `scripts/quicktrack_crud.py` implementa la gestión de órdenes de entrega. Es reutilizable: la API REST llamará a estas mismas funciones.

| Operación | Función | Qué hace |
|---|---|---|
| Create | `crear_orden` | Crea la orden en `En preparación` y su seguimiento inicial; si falla algo, deshace lo creado |
| Create | `registrar_valoracion` | Registra la valoración de una orden entregada (una por orden) |
| Read | `leer_orden`, `listar_ordenes` | Lee una orden con su detalle o lista con filtros por estado y cliente, y paginación |
| Update | `avanzar_estado` | Cambia el estado respetando el flujo y sincroniza el seguimiento |
| Update | `corregir_total` | Corrige el total mientras la orden está abierta |
| Delete | `eliminar_orden` | Elimina la orden junto con su seguimiento y valoración, sin dejar huérfanos |
| Integridad | `verificar_consistencia`, `auditar_integridad` | Detectan órdenes sin cliente, ruta o seguimiento, huérfanos y seguimientos desalineados |
| Integridad | `sincronizar_seguimiento`, `reparar_seguimientos`, `depurar_huerfanos` | Corrigen las inconsistencias (con modo simulación por defecto) |

Reglas de negocio:
- Flujo de estados: `En preparación` → `En tránsito` → `Entregado`. Se puede cancelar desde `En preparación` o `En tránsito`. `Entregado` y `Cancelado` son estados finales.
- El total solo se corrige en órdenes abiertas.
- Solo se valoran órdenes entregadas, una vez cada una.
- Por defecto solo se eliminan órdenes canceladas o en preparación.
- Se validan cliente y ruta existentes, total positivo y numérico, medio de pago, puntaje de 1 a 5 y el formato de los identificadores (se rechazan operadores de MongoDB en los ids).

Errores controlados, pensados para traducirse a códigos HTTP en la API:

| Excepción | Significado | HTTP |
|---|---|---|
| `ValidacionError` | Dato de entrada inválido | 400 |
| `NoEncontradoError` | El documento no existe | 404 |
| `ConflictoError` | Duplicado o regla de negocio incumplida | 409 |

`scripts/demo_crud.py` ejecuta cuatro escenarios y comprueba 37 casos (resultado: 37 correctos, 0 con fallo):
1. Ciclo de vida de una orden: crear, leer, avanzar estados, corregir el total y valorar.
2. Cancelación y eliminación sin dejar documentos huérfanos.
3. Errores provocados a propósito (cliente o ruta inexistente, total inválido, id duplicado, transiciones no permitidas, valoración duplicada), que el sistema debe rechazar.
4. Detección y corrección de inconsistencias. En los datos originales se detectaron **96 seguimientos cuyo `estado_actual` no coincide con el estado de su orden**; el demo los reporta pero no los modifica (modo simulación) para no alterar los resultados de C11.

Evidencias: `evidencias/crud.log` y `evidencias/crud_resultados.csv`.

## Interfaz web

La carpeta `interfaz/` es la aplicación externa que lee y escribe en MongoDB a través de la API. Son archivos estáticos (HTML, CSS y JavaScript, sin bibliotecas ni paso de compilación) que la misma API sirve en `http://127.0.0.1:8000/`, así que basta con `python -m api` para tener todo funcionando.

| Sección | Qué muestra o permite |
|---|---|
| Resumen | Indicadores (órdenes, monto total y entregado, satisfacción, clientes, rutas) y gráficos de órdenes por estado, monto por zona, satisfacción por estado y evolución mensual, más los clientes y rutas principales. Sale de las consultas C4 a C10 |
| Órdenes | Listado con filtros por estado y cliente, y paginación. Al abrir una orden se ve su cliente, ruta, seguimiento (historial) y valoración, con las acciones que permite su estado: avanzar, cancelar, corregir el total, valorar y eliminar. Botón **Nueva orden** |
| Clientes | Listado con filtro por país; al abrir un cliente se ven sus órdenes y lo que suman |
| Rutas | Catálogo con filtro por zona |
| Consultas | Las 11 consultas del informe, ejecutadas en vivo, con su tiempo de respuesta |
| Integridad | Auditoría de la base (huérfanos, órdenes sin cliente, ruta o seguimiento, y seguimientos desalineados) y una reparación en modo simulación |

Detalles de presentación:
- Montos en pesos con formato chileno (`$165.509,20`); en los indicadores y ejes, compactos (`$10,9 M`). Fechas en UTC, para que la fecha de envío no aparezca un día antes.
- Cada orden se muestra con el nombre del cliente y el tramo de la ruta, no solo con sus ids.
- Los gráficos usan un solo color de acento, rejilla tenue y un tooltip en cada barra o mes (también con el teclado). Cada gráfico enlaza a la consulta de la que sale, para ver los números en tabla.
- Tema claro y oscuro (sigue al sistema; el botón de la barra superior lo cambia) y diseño adaptable a móvil.
- Los errores de la API se muestran con su mensaje y su id de solicitud; en los formularios se marcan los campos con problemas.

Los cambios hechos desde la interfaz se guardan en Atlas. Para demostraciones conviene crear una orden nueva y trabajar sobre ella; se puede eliminar al final mientras esté en preparación o cancelada.

## API REST (sección 6 del informe)

La carpeta `api/` integra la base con una aplicación externa mediante una API REST hecha con **FastAPI**. La API no repite reglas de negocio: cada endpoint llama a las funciones de `scripts/quicktrack_crud.py` (y a las consultas de `scripts/consultas_quicktrack.py`), así que se comporta igual que el demo del CRUD.

| Archivo | Responsabilidad |
|---|---|
| `api/main.py` | Crea la aplicación, registra middlewares, manejadores de errores y endpoints |
| `api/config.py` | Lee la configuración de variables de entorno o `.env` (la URI se guarda como secreto) |
| `api/db.py` | Un único `MongoClient` (pool de conexiones) abierto al iniciar y cerrado al detener la API |
| `api/esquemas.py` | Modelos Pydantic de entrada (forma del JSON) y de salida (documentación en `/docs`) |
| `api/errores.py` | Traduce cada excepción a una respuesta HTTP con formato estándar |
| `api/middleware.py` | Id de solicitud, tiempo de respuesta, registro de accesos y errores no previstos |
| `api/routers/` | Endpoints agrupados por recurso |

Todas las rutas empiezan con `/api/v1`.

| Método | Ruta | Qué hace | Éxito |
|---|---|---|---|
| GET | `/salud` | Estado de la API y ping a MongoDB (503 si la base no responde) | 200 |
| GET | `/errores` | Catálogo de códigos de error | 200 |
| GET | `/ordenes` | Lista órdenes; filtros `estado`, `cliente_id`; paginación `limite`, `salto` | 200 |
| POST | `/ordenes` | Crea una orden y su seguimiento (cabecera `Location`) | 201 |
| GET | `/ordenes/{orden_id}` | Lee la orden con seguimiento y valoración (`detalle=false` para omitirlos) | 200 |
| DELETE | `/ordenes/{orden_id}` | Elimina la orden con sus dependientes (`forzar=true` para entregadas o en tránsito) | 200 |
| PATCH | `/ordenes/{orden_id}/estado` | Cambia el estado respetando el flujo | 200 |
| PATCH | `/ordenes/{orden_id}/total` | Corrige el total de una orden abierta | 200 |
| POST | `/ordenes/{orden_id}/valoracion` | Valora una orden entregada | 201 |
| GET | `/ordenes/{orden_id}/seguimiento` | Estado actual e historial | 200 |
| GET | `/ordenes/{orden_id}/consistencia` | Verifica cliente, ruta, seguimiento y valoración | 200 |
| POST | `/ordenes/{orden_id}/sincronizar` | Alinea el seguimiento con el estado de la orden | 200 |
| GET | `/clientes`, `/clientes/{id}` | Clientes (filtro `pais` sin distinguir mayúsculas ni tildes) | 200 |
| GET | `/clientes/{id}/ordenes` | Órdenes de un cliente | 200 |
| GET | `/rutas`, `/rutas/{id}` | Rutas (filtro `zona`), en orden numérico | 200 |
| GET | `/consultas`, `/consultas/{id}` | Lista y ejecuta las consultas C1 a C11, con su tiempo | 200 |
| GET | `/integridad/auditoria` | Auditoría completa de la base | 200 |
| POST | `/integridad/seguimientos/reparar` | Repara seguimientos desalineados (simulación salvo `ejecutar=true`) | 200 |
| POST | `/integridad/huerfanos/depurar` | Elimina huérfanos (simulación salvo `ejecutar=true`) | 200 |

Ejemplo, crear una orden:

```
POST /api/v1/ordenes
Content-Type: application/json

{"cliente_id": 1, "ruta_id": "ruta_1", "total": 85000, "medio_pago": "Tarjeta"}
```

Responde `201 Created` con la orden (`orden_101`, en estado `En preparación`) y su seguimiento inicial. `cliente_id` también acepta el formato `cli_1`; `orden_id` y `fecha_envio` son opcionales.

Decisiones de diseño:
- Los modelos de entrada son estrictos y rechazan campos desconocidos: `"total": "85000"` (texto) o enviar `"estado"` al crear una orden responden 400 en vez de aceptarse en silencio.
- Las correcciones masivas de integridad funcionan en modo simulación por defecto, para no alterar los resultados de C11.
- Las fechas se devuelven en ISO 8601 con zona horaria UTC (`2024-05-31T00:00:00Z`).

## Control de errores y trazabilidad (sección 7 del informe)

Todos los errores tienen el mismo formato, el estándar **Problem Details** (RFC 9457, `Content-Type: application/problem+json`), con dos campos propios: `codigo` (estable, para que el cliente decida qué hacer) e `id_solicitud`.

```json
{
  "type": "/api/v1/errores/conflicto",
  "title": "Conflicto con el estado actual",
  "status": 409,
  "detail": "Transición no permitida: Entregado -> En preparación. Permitidas: ninguna (estado final)",
  "instance": "/api/v1/ordenes/orden_2/estado",
  "codigo": "CONFLICTO",
  "id_solicitud": "3f2a9c1e8b7d",
  "fecha": "2026-10-26T16:02:50+00:00"
}
```

| HTTP | `codigo` | Origen | Ejemplo |
|---|---|---|---|
| 400 | `VALIDACION` | `ValidacionError` del CRUD o JSON con forma incorrecta | Cliente inexistente, total negativo, campo faltante, JSON mal formado, id con operadores de MongoDB |
| 404 | `NO_ENCONTRADO` | `NoEncontradoError` del CRUD | Orden, cliente, ruta o consulta inexistente |
| 404 | `RUTA_NO_ENCONTRADA` | URL desconocida | `GET /api/v1/no-existe` |
| 405 | `METODO_NO_PERMITIDO` | Método no admitido; la cabecera `Allow` indica los válidos | `PUT /api/v1/ordenes/orden_1` |
| 409 | `CONFLICTO` | `ConflictoError` del CRUD o índice único de MongoDB | Id duplicado, transición no permitida, valoración repetida |
| 500 | `ERROR_BASE_DATOS` | MongoDB rechazó la operación | |
| 500 | `ERROR_INTERNO` | Cualquier error no previsto | |
| 503 | `BASE_NO_DISPONIBLE` | MongoDB no responde (red, IP no autorizada en Atlas); incluye `Retry-After` | Clúster detenido |

Cuando el error es de formato, el campo `errores` indica cada problema por campo y en español:

```json
"errores": [
  {"ubicacion": "cuerpo", "campo": "total", "mensaje": "Debe ser un número"},
  {"ubicacion": "cuerpo", "campo": "estado", "mensaje": "Campo no permitido"}
]
```

Trazabilidad:
- Cada respuesta lleva `X-Request-ID` (si el cliente envía uno, se respeta) y `X-Response-Time`.
- `evidencias/api.log` registra una línea por solicitud (método, ruta, código, duración) y el motivo de cada error. El mismo id aparece en las líneas del CRUD (por ejemplo `Orden orden_101 creada`), así que con el `id_solicitud` de un error se encuentra todo lo que pasó en esa solicitud. El archivo rota al llegar a 1 MB.
- Los errores 500 y 503 se registran completos en el log, pero al cliente solo se le entrega un mensaje genérico: no se exponen trazas, hosts del clúster ni la URI.
- Si MongoDB no responde al iniciar, la API arranca igual: `/salud` informa el problema y cada endpoint responde 503 hasta que la base vuelva. Si falta la URI o es inválida, la API no arranca y lo indica (sin mostrar la contraseña).

## Pruebas de la API con Postman

`postman/QuickTrack.postman_collection.json` tiene 81 solicitudes con pruebas automáticas, en ocho carpetas que se ejecutan en orden:

| Carpeta | Qué prueba |
|---|---|
| 00 Preparación | Salud de la API y auditoría inicial, que se guarda para compararla al final |
| 01 Catálogos | Clientes y rutas: lectura, filtros, orden y paginación |
| 02 Consultas de análisis | C1 a C11 y que cada resultado cumpla su requerimiento |
| 03 Ciclo de vida de una orden | Crear, leer, avanzar estados, corregir total, valorar y verificar consistencia |
| 04 Cancelación y eliminación | Cancelar y eliminar sin dejar huérfanos |
| 05 Control de errores | 30 errores provocados (400, 404, 405, 409) y que no modifiquen los datos |
| 06 Integridad | Auditoría y correcciones en modo simulación |
| 07 Limpieza | Elimina las órdenes de prueba y comprueba que la base quedó igual que al inicio |

Además, después de cada solicitud se comprueba que la respuesta traiga `X-Request-ID` y `X-Response-Time`, y que todo error use el formato Problem Details sin exponer trazas.

En Postman:
1. Iniciar la API (`python -m api`).
2. **Import** de `postman/QuickTrack.postman_collection.json` y `postman/QuickTrack-local.postman_environment.json`.
3. Elegir el entorno **QuickTrack local** y ejecutar la colección completa con **Run collection**, sin cambiar el orden.

Por consola, con Newman (requiere Node.js):

```
npm install -g newman newman-reporter-htmlextra
newman run postman\QuickTrack.postman_collection.json -e postman\QuickTrack-local.postman_environment.json -r cli,htmlextra,junit --reporter-htmlextra-export evidencias\postman\reporte_newman.html --reporter-junit-export evidencias\postman\resultados_newman.xml
```

**Resultado sobre Atlas (27-10-2026):** 81 solicitudes, 431 aserciones, 0 fallas, en 28.7 s (tiempo medio de respuesta 202 ms). Al terminar, la base quedó igual que al inicio. Evidencias: `evidencias/postman/reporte_newman.html` (reporte navegable), `evidencias/postman/resultados_newman.xml` (JUnit) y `evidencias/api.log` (registro de cada solicitud con su id).

La colección es segura de repetir sobre Atlas: crea órdenes con prefijo `orden_test_api_` y las elimina al terminar. Si una ejecución se interrumpe a mitad, `python scripts\demo_crud.py` borra los restos (limpia todo lo que empiece con `orden_test_`).

## Limitaciones de los datos

- Los tiempos de entrega no se pueden calcular de forma confiable: no existe `fecha_entrega`, el historial de seguimiento no coincide con `fecha_envio` y el `estado_actual` difiere del último estado del historial en la mayoría de los casos.
- 96 de los 100 seguimientos tienen un estado distinto al de su orden (detectado por el CRUD y por C11).
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
| 4 | Índices compuestos y nueva medición de documentos examinados (IE6) | Hecho | |
| 5 | CRUD completo (inserciones, actualizaciones y eliminaciones) con validación | Hecho | |
| 6 | Integración con una aplicación externa (API REST y pruebas en Postman) | Hecho | |
| 7 | Control de errores y trazabilidad (CRUD y API) | Hecho | |
| Entrega | Informe técnico en PDF y enlace al repositorio en AVA | Pendiente | |

## Entregables

- Informe técnico en PDF con las siete secciones.
- Scripts de creación, inserción, consultas y CRUD (carpeta `scripts`).
- Capturas de consultas y resultados (carpeta `evidencias`).
- Código o capturas de la integración con la aplicación externa.
- Enlace a este repositorio, entregado por AVA.
