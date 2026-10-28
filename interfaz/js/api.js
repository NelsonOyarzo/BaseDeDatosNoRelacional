// Cliente de la API REST de QuickTrack (mismo origen, prefijo /api/v1).

const BASE = "/api/v1";

/** Error devuelto por la API en formato Problem Details (RFC 9457). */
export class ErrorApi extends Error {
  constructor(problema, estado) {
    super(problema?.detail || `La API respondió ${estado}`);
    this.estado = estado;
    this.codigo = problema?.codigo || "ERROR";
    this.idSolicitud = problema?.id_solicitud || null;
    this.errores = problema?.errores || [];
  }
}

export async function api(ruta, { metodo = "GET", cuerpo, consulta } = {}) {
  const url = new URL(BASE + ruta, location.origin);
  for (const [clave, valor] of Object.entries(consulta || {})) {
    if (valor !== undefined && valor !== null && valor !== "") url.searchParams.set(clave, valor);
  }
  let respuesta;
  try {
    respuesta = await fetch(url, {
      method: metodo,
      headers: cuerpo ? { "Content-Type": "application/json" } : {},
      body: cuerpo ? JSON.stringify(cuerpo) : undefined,
    });
  } catch {
    throw new ErrorApi({ detail: "No se pudo contactar la API. Revise que esté corriendo (python -m api).", codigo: "SIN_CONEXION" }, 0);
  }
  const datos = await respuesta.json().catch(() => null);
  if (!respuesta.ok) throw new ErrorApi(datos, respuesta.status);
  return datos;
}

/** Recorre todas las páginas de un listado (la API entrega hasta 100 por página). */
export async function traerTodos(ruta, consulta = {}) {
  const todos = [];
  for (let salto = 0; ; salto += 100) {
    const pagina = await api(ruta, { consulta: { ...consulta, limite: 100, salto } });
    todos.push(...pagina.datos);
    if (!pagina.datos.length || todos.length >= pagina.total) return todos;
  }
}

let catalogosEnCurso = null;

/** Clientes y rutas indexados por id, para mostrar nombres en lugar de ids. Se cargan una vez. */
export function catalogos() {
  catalogosEnCurso ??= Promise.all([traerTodos("/clientes"), traerTodos("/rutas")])
    .then(([clientes, rutas]) => ({
      clientes: new Map(clientes.map((c) => [c._id, c])),
      rutas: new Map(rutas.map((r) => [r._id, r])),
    }))
    .catch((error) => { catalogosEnCurso = null; throw error; });
  return catalogosEnCurso;
}

export const consulta = (id) => api(`/consultas/${id}`);
