# Configurar el archivo `.env` con la URI de MongoDB Atlas

La API REST (`python -m api`) lee la conexión a la base desde un archivo `.env` ubicado en la raíz del repositorio. Ese archivo contiene la contraseña, por eso **cada integrante crea el suyo** y nunca se sube a GitHub (ya está en `.gitignore`).

> Los scripts de la carpeta `scripts/` no leen el `.env`: siguen usando la variable de entorno `MONGO_URI` o piden la URI al ejecutarse (ver el final de esta guía).

## 1. Obtener la URI en Atlas

1. Entrar a [cloud.mongodb.com](https://cloud.mongodb.com) y abrir el proyecto de QuickTrack.
2. Ir a **Database > Clusters**, botón **Connect** del clúster y elegir **Drivers** (Python).
3. Copiar la cadena de conexión. Tiene esta forma:

   ```
   mongodb+srv://<usuario>:<db_password>@cluster0.xxxxx.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0
   ```

4. Reemplazar `<db_password>` (con los signos `< >` incluidos) por la contraseña del **usuario de base de datos** (la de **Security > Database Access**, no la de la cuenta de Atlas). La entrega el equipo por un canal privado.
5. Si la contraseña tiene caracteres especiales, hay que codificarlos o la conexión falla:

   | Carácter | Se escribe |
   |---|---|
   | `@` | `%40` |
   | `:` | `%3A` |
   | `/` | `%2F` |
   | `#` | `%23` |
   | `?` | `%3F` |
   | `%` | `%25` |

   Para obtenerla ya codificada:

   ```
   python -c "from urllib.parse import quote; print(quote('LA_CONTRASEÑA', safe=''))"
   ```

## 2. Autorizar la IP del equipo

En **Security > Network Access > IP Access List**, botón **Add IP Address** y luego **Add Current IP Address**.

- Si cambias de red (otra casa, el celular, la sede) la IP cambia y hay que agregarla de nuevo.
- Evitar `0.0.0.0/0` (permite conexiones desde cualquier lugar). Si se usó, quitarla al terminar el proyecto.

## 3. Crear el `.env`

Abrir una terminal en la raíz del repositorio (la carpeta donde están `README.md` y `.env.example`) y copiar la plantilla:

| Sistema | Comando |
|---|---|
| Windows (PowerShell) | `Copy-Item .env.example .env` |
| Windows (cmd) | `copy .env.example .env` |
| Linux o macOS | `cp .env.example .env` |

Abrir `.env` con un editor (Windows: `notepad .env`) y reemplazar la línea de la URI por la real:

```
MONGO_URI=mongodb+srv://usuario:contraseña@cluster0.xxxxx.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0
MONGO_DB=QuickTrack
```

Reglas:
- Una variable por línea, sin espacios alrededor del `=`. No hacen falta comillas.
- `MONGO_DB` debe ser exactamente `QuickTrack`: MongoDB distingue mayúsculas (`quicktrack` es otra base, vacía).
- **Windows:** el Bloc de notas puede guardarlo como `.env.txt`. Al guardar, elegir *Tipo: Todos los archivos (\*.\*)* y como nombre `.env`. Para comprobarlo, en PowerShell `Get-ChildItem -Force .env*` debe mostrar `.env` y `.env.example`, nada más.

### Variables opcionales

Se agregan en el mismo `.env` solo si hace falta cambiar el valor por defecto. Las variables de entorno del sistema tienen prioridad sobre el `.env`.

| Variable | Por defecto | Para qué |
|---|---|---|
| `MONGO_TIMEOUT_MS` | `5000` | Tiempo máximo de espera para contactar a Atlas antes de responder 503 |
| `API_HOST` | `127.0.0.1` | Dirección donde escucha la API (`0.0.0.0` para aceptar conexiones de otros equipos de la red) |
| `API_PUERTO` | `8000` | Puerto de la API. Si se cambia, actualizar `baseUrl` en el entorno de Postman |
| `API_NIVEL_LOG` | `INFO` | Detalle del registro (`DEBUG`, `INFO`, `WARNING`) |
| `API_ARCHIVO_LOG` | `evidencias/api.log` | Archivo de registro |
| `API_CORS_ORIGENES` | `*` | Orígenes web permitidos, separados por comas |

## 4. Verificar la conexión

1. Instalar las dependencias (una sola vez):

   ```
   python -m pip install -r requirements.txt
   ```

2. Iniciar la API desde la raíz del repositorio:

   ```
   python -m api
   ```

   Si el `.env` está bien, la consola muestra:

   ```
   INFO | - | quicktrack_api | Conectado a MongoDB, base QuickTrack con sus 5 colecciones
   ```

3. Abrir en el navegador `http://127.0.0.1:8000/api/v1/salud`. Debe responder:

   ```json
   {"estado": "ok", "version": "1.0.0", "base_datos": {"estado": "conectada", "nombre": "QuickTrack", "latencia_ms": 80.0}}
   ```

4. Con eso ya se puede usar `http://127.0.0.1:8000/docs` y ejecutar la colección de Postman (ver la sección *Pruebas de la API con Postman* del README).

## 5. Problemas frecuentes

| Síntoma | Causa probable | Solución |
|---|---|---|
| La API pide la URI por teclado, o termina con `Falta la URI de MongoDB` | No encuentra el `.env` | Revisar que esté en la raíz del repo, que se llame `.env` (no `.env.txt`) y que la línea empiece con `MONGO_URI=` |
| Termina con `La URI de MongoDB no es válida` | URI mal copiada o contraseña con caracteres sin codificar | Volver a copiar la URI desde Atlas y codificar la contraseña (paso 1.5) |
| El log dice `MongoDB no responde al iniciar (ServerSelectionTimeoutError)` y `/salud` responde 503 | IP no autorizada, sin internet o clúster pausado | Agregar la IP actual en Network Access (paso 2) y revisar que el clúster esté activo |
| El log dice `MongoDB no responde al iniciar (OperationFailure)` o aparece `bad auth : authentication failed` | Usuario o contraseña incorrectos | Revisar el usuario en Database Access y la contraseña del `.env` |
| Advertencia `La base ... no tiene las colecciones` | `MONGO_DB` mal escrito | Usar exactamente `MONGO_DB=QuickTrack` |
| `Address already in use` al iniciar | El puerto 8000 ya está ocupado (otra API abierta) | Cerrar la otra terminal o usar `API_PUERTO=8001` y cambiar `baseUrl` en Postman |

Con la API funcionando, si una solicitud responde 503 `BASE_NO_DISPONIBLE`, la causa es la misma que la del tercer caso: la API sigue viva y vuelve a responder normal apenas la base esté accesible.

## 6. Seguridad

- No subir el `.env` al repositorio. Antes de cada commit, `git status` no debe mostrarlo; `git check-ignore -v .env` confirma que está ignorado.
- No compartir la URI en grupos, capturas de pantalla ni en el informe. La API nunca la muestra: la guarda como secreto y la oculta en los mensajes de error.
- Si la contraseña se filtra, cambiarla en **Security > Database Access** y avisar al equipo para que actualice su `.env`.

## Usar la misma URI con los scripts

Los scripts (`diagnostico_atlas.py`, `consultas_quicktrack.py`, etc.) piden la URI cada vez. Para no pegarla en cada ejecución, se puede definir solo para la terminal actual (se borra al cerrarla):

| Sistema | Comando |
|---|---|
| Windows (PowerShell) | `$env:MONGO_URI = "mongodb+srv://..."` |
| Windows (cmd) | `set MONGO_URI=mongodb+srv://...` |
| Linux o macOS | `export MONGO_URI="mongodb+srv://..."` |
