// Consultas C1 a C11 del informe: se ejecutan en la API y se muestran como tabla.

import { api, consulta } from "../api.js";
import * as f from "../formato.js";
import { cargando, el, encabezado, errorVista, tabla, tarjeta } from "../ui.js";
import { abrirOrden } from "./ordenes.js";

const TITULOS = {
  _id: "ID", cliente_id: "Cliente", ruta_id: "Ruta", orden_id: "Orden", fecha_envio: "Fecha de envío",
  medio_pago: "Medio de pago", ticket_medio: "Ticket medio", puntaje_medio: "Puntaje medio",
  distancia_km: "Distancia", estado_actual: "Estado actual", ingresos: "Monto", ordenes: "Órdenes", pais: "País",
};
const DINERO = new Set(["total", "ingresos", "ticket_medio"]);

const titulo = (clave) => TITULOS[clave] ?? clave.charAt(0).toUpperCase() + clave.slice(1).replaceAll("_", " ");

function valor(clave, v) {
  if (v == null) return "—";
  if (clave === "estado" || clave === "estado_actual") return f.insigniaEstado(v);
  if (clave === "fecha_envio") return f.fecha(v);
  if (clave === "mes") return f.mes(v);
  if (DINERO.has(clave)) return f.dinero(v);
  if (clave === "puntaje_medio") return f.decimal1(v);
  if (clave === "distancia_km") return f.km(v);
  if (clave.endsWith("_id") || clave === "_id") return el("span", { class: "mono" }, String(v));
  if (typeof v === "number") return f.numero(v);
  if (typeof v === "object") return JSON.stringify(v);
  return String(v);
}

let listado = null;

export async function render(contenedor, parametro) {
  const id = (parametro || "C1").toUpperCase();
  contenedor.replaceChildren(encabezado("Consultas", "Las 11 consultas de lectura del informe, ejecutadas en vivo sobre MongoDB"), cargando());
  try {
    listado ??= await api("/consultas");
  } catch (error) {
    contenedor.lastChild.replaceWith(errorVista(error, () => render(contenedor, parametro)));
    return;
  }

  const lista = tarjeta({ clase: "lista-consultas" },
    listado.map((c) => el("a", { href: `#/consultas/${c.id}`, "aria-current": c.id === id ? "true" : null },
      el("span", { class: "id" }, c.id), el("span", {}, c.titulo))));
  const detalle = el("div", {}, cargando("Ejecutando consulta…"));
  contenedor.replaceChildren(
    encabezado("Consultas", "Las 11 consultas de lectura del informe, ejecutadas en vivo sobre MongoDB"),
    el("div", { class: "consultas" }, lista, detalle));

  try {
    const r = await consulta(id);
    // Primero las columnas de texto (qué es cada fila) y después las cifras, en su orden original
    const claves = [...new Set(r.resultados.flatMap((fila) => Object.keys(fila)))];
    const esCifra = (clave) => r.resultados.some((fila) => typeof fila[clave] === "number") && !clave.endsWith("_id");
    const columnas = [...claves.filter((c) => !esCifra(c)), ...claves.filter(esCifra)].map((clave) => ({
      titulo: titulo(clave),
      valor: (fila) => valor(clave, fila[clave]),
      num: esCifra(clave),
    }));
    const idOrden = (fila) => fila.orden_id ?? (String(fila._id).startsWith("orden_") ? fila._id : null);
    detalle.replaceChildren(tarjeta(
      { titulo: `${r.id} · ${r.titulo}`, subtitulo: r.requerimiento,
        pie: [`Colección ${r.coleccion} · ${r.tipo}`, `${f.numero(r.documentos)} documentos · ${f.decimal1(r.tiempo_ms)} ms`] },
      tabla({
        columnas, filas: r.resultados,
        alElegir: r.resultados.some(idOrden) ? (fila) => idOrden(fila) && abrirOrden(idOrden(fila)) : null,
        vacio: "La consulta no devolvió documentos",
      })));
  } catch (error) {
    detalle.replaceChildren(errorVista(error, () => render(contenedor, parametro)));
  }
}
