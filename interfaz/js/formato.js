// Formato de cifras y fechas en español de Chile.
// Las fechas de la base están en UTC (la mayoría a medianoche): se muestran en UTC
// para que una fecha de envío no aparezca un día antes.

import { el } from "./ui.js";

const decimal = new Intl.NumberFormat("es-CL", { maximumFractionDigits: 2 });
const centavos = new Intl.NumberFormat("es-CL", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const entero = new Intl.NumberFormat("es-CL", { maximumFractionDigits: 0 });
const compacto = new Intl.NumberFormat("es-CL", { notation: "compact", maximumFractionDigits: 1 });
const uno = new Intl.NumberFormat("es-CL", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
const fechaCorta = new Intl.DateTimeFormat("es-CL", { day: "2-digit", month: "short", year: "numeric", timeZone: "UTC" });
const mesCorto = new Intl.DateTimeFormat("es-CL", { month: "short", year: "numeric", timeZone: "UTC" });

export const numero = (v) => (v == null ? "—" : entero.format(v));
export const decimal1 = (v) => (v == null ? "—" : uno.format(v));
export const dinero = (v) => (v == null ? "—" : `$${centavos.format(v)}`);
export const dineroEntero = (v) => (v == null ? "—" : `$${entero.format(v)}`);
export const dineroCompacto = (v) => (v == null ? "—" : `$${compacto.format(v)}`);
export const compactoNum = (v) => compacto.format(v);
export const porcentaje = (v) => `${uno.format(v * 100)} %`;
export const km = (v) => (v == null ? "—" : `${decimal.format(v)} km`);

export function fecha(valor) {
  if (!valor) return "—";
  const f = new Date(valor);
  return Number.isNaN(f.getTime()) ? String(valor) : fechaCorta.format(f).replace(".", "");
}

/** "2023-04" -> "abr 2023" */
export function mes(clave) {
  const [anio, m] = clave.split("-").map(Number);
  return mesCorto.format(new Date(Date.UTC(anio, m - 1, 1))).replace(".", "");
}

export const ESTADOS = ["En preparación", "En tránsito", "Entregado", "Cancelado"];
const CLASE_ESTADO = {
  "En preparación": "preparacion",
  "En tránsito": "transito",
  "Entregado": "entregado",
  "Cancelado": "cancelado",
};

export function insigniaEstado(estado) {
  return el("span", { class: `estado estado--${CLASE_ESTADO[estado] || "otro"}` }, estado || "—");
}

export function estrellas(puntaje) {
  const llenas = Math.max(0, Math.min(5, puntaje));
  return el("span", { class: "estrellas", "aria-label": `${puntaje} de 5` },
    "★".repeat(llenas), el("span", { class: "vacia" }, "★".repeat(5 - llenas)));
}

export const nombreCliente = (clientes, id) => clientes.get(id)?.nombre ?? `Cliente ${id}`;
export const tramoRuta = (ruta) => (ruta ? `${ruta.ciudad_origen} → ${ruta.ciudad_destino}` : "—");
