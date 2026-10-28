// Resumen: indicadores y gráficos a partir de las consultas C4 a C10 del informe.

import { api, consulta } from "../api.js";
import * as f from "../formato.js";
import { barrasHorizontales, lineaTemporal } from "../graficos.js";
import { cargando, el, encabezado, errorVista, tabla, tarjeta } from "../ui.js";

function kpi(etiqueta, valor, detalle) {
  return el("div", { class: "tarjeta kpi" },
    el("div", { class: "kpi-etiqueta" }, etiqueta),
    el("div", { class: "kpi-valor" }, valor),
    detalle && el("div", { class: "kpi-detalle" }, detalle));
}

const pie = (c) => [el("a", { href: `#/consultas/${c.id}` }, `Ver tabla · ${c.id}`), `${f.numero(c.documentos)} filas · ${f.decimal1(c.tiempo_ms)} ms`];

/** Completa con cero los meses sin órdenes, para que la línea no salte huecos. */
function mesesContinuos(filas) {
  if (!filas.length) return [];
  const porMes = new Map(filas.map((r) => [r.mes, r]));
  const [a0, m0] = filas[0].mes.split("-").map(Number);
  const [a1, m1] = filas.at(-1).mes.split("-").map(Number);
  const meses = [];
  for (let a = a0, m = m0; a < a1 || (a === a1 && m <= m1); m === 12 ? (a++, m = 1) : m++) {
    const clave = `${a}-${String(m).padStart(2, "0")}`;
    meses.push(porMes.get(clave) || { mes: clave, ordenes: 0, ingresos: 0 });
  }
  return meses;
}

export async function render(contenedor) {
  contenedor.replaceChildren(encabezado("Resumen", "Datos en vivo desde MongoDB Atlas, base QuickTrack"), cargando());
  let c4, c5, c6, c7, c8, c10, clientes, rutas;
  try {
    [c4, c5, c6, c7, c8, c10, clientes, rutas] = await Promise.all([
      consulta("C4"), consulta("C5"), consulta("C6"), consulta("C7"), consulta("C8"), consulta("C10"),
      api("/clientes", { consulta: { limite: 1 } }), api("/rutas", { consulta: { limite: 1 } }),
    ]);
  } catch (error) {
    contenedor.lastChild.replaceWith(errorVista(error, () => render(contenedor)));
    return;
  }

  const porEstado = c4.resultados;
  const totalOrdenes = porEstado.reduce((s, r) => s + r.ordenes, 0);
  const montoTotal = porEstado.reduce((s, r) => s + r.total, 0);
  const entregado = porEstado.find((r) => r.estado === "Entregado") ?? { ordenes: 0, total: 0 };
  const valoraciones = c8.resultados.reduce((s, r) => s + r.valoraciones, 0);
  const puntajeMedio = valoraciones ? c8.resultados.reduce((s, r) => s + r.puntaje_medio * r.valoraciones, 0) / valoraciones : null;

  const indicadores = el("div", { class: "rejilla rejilla-kpi" },
    kpi("Órdenes", f.numero(totalOrdenes), `${f.numero(entregado.ordenes)} entregadas`),
    kpi("Monto total", f.dineroCompacto(montoTotal), `Ticket medio ${f.dineroEntero(totalOrdenes ? montoTotal / totalOrdenes : 0)}`),
    kpi("Monto entregado", f.dineroCompacto(entregado.total), `${f.porcentaje(montoTotal ? entregado.total / montoTotal : 0)} del total`),
    kpi("Satisfacción media", puntajeMedio == null ? "—" : `${f.decimal1(puntajeMedio)} / 5`, `${f.numero(valoraciones)} valoraciones`),
    kpi("Clientes", f.numero(clientes.total), "registrados"),
    kpi("Rutas", f.numero(rutas.total), "en el catálogo"));

  const estados = tarjeta({ titulo: "Órdenes por estado", subtitulo: "Cantidad de órdenes en cada etapa", pie: pie(c4) },
    barrasHorizontales({
      datos: porEstado.map((r) => ({
        etiqueta: r.estado, valor: r.ordenes,
        detalle: [`Monto ${f.dineroEntero(r.total)}`, `Ticket medio ${f.dineroEntero(r.ticket_medio)}`],
      })),
      formato: f.numero,
    }));

  const zonas = tarjeta({ titulo: "Monto por zona", subtitulo: "Suma del total de las órdenes, por zona de la ruta", pie: pie(c5) },
    barrasHorizontales({
      datos: c5.resultados.map((r) => ({
        etiqueta: r.zona, valor: r.ingresos,
        detalle: [`${f.numero(r.ordenes)} órdenes`, `Ticket medio ${f.dineroEntero(r.ticket_medio)}`],
      })),
      formato: f.dineroCompacto,
    }));

  const meses = mesesContinuos(c10.resultados);
  const evolucion = tarjeta({ titulo: "Evolución mensual del monto", subtitulo: `Monto de las órdenes según su mes de envío · ${f.mes(meses[0].mes)} a ${f.mes(meses.at(-1).mes)}`, pie: pie(c10) },
    lineaTemporal({
      puntos: meses.map((r) => ({ x: r.mes, y: r.ingresos, detalle: [`${f.numero(r.ordenes)} ${r.ordenes === 1 ? "orden" : "órdenes"}`] })),
      formatoY: f.dineroEntero, formatoEjeY: f.dineroCompacto, formatoX: f.mes,
      descripcion: "Monto mensual de las órdenes; use las flechas para recorrer los meses",
    }));

  const satisfaccion = tarjeta({ titulo: "Satisfacción según el estado", subtitulo: "Puntaje medio de las valoraciones (1 a 5)", pie: pie(c8) },
    barrasHorizontales({
      datos: c8.resultados.map((r) => ({ etiqueta: r.estado, valor: r.puntaje_medio, detalle: [`${f.numero(r.valoraciones)} valoraciones`] })),
      formato: f.decimal1, maximo: 5,
    }));

  const topClientes = tarjeta({ titulo: "Clientes con mayor facturación", subtitulo: "Los 5 que más suman en órdenes", pie: pie(c6) },
    tabla({
      columnas: [
        { titulo: "Cliente", valor: (r) => el("div", { class: "celda-doble" }, r.nombre, el("small", {}, `#${r.cliente_id} · ${r.pais}`)) },
        { titulo: "Órdenes", valor: (r) => f.numero(r.ordenes), num: true },
        { titulo: "Total", valor: (r) => f.dineroEntero(r.total), num: true },
      ],
      filas: c6.resultados,
      alElegir: (r) => { location.hash = `#/clientes/${r.cliente_id}`; },
    }));

  const topRutas = tarjeta({ titulo: "Rutas más utilizadas", subtitulo: "Las 5 rutas con más órdenes", pie: pie(c7) },
    tabla({
      columnas: [
        { titulo: "Ruta", valor: (r) => el("div", { class: "celda-doble" }, `${r.origen} → ${r.destino}`, el("small", {}, `${r.ruta_id} · ${r.zona} · ${f.km(r.distancia_km)}`)) },
        { titulo: "Órdenes", valor: (r) => f.numero(r.ordenes), num: true },
        { titulo: "Monto", valor: (r) => f.dineroEntero(r.ingresos), num: true },
      ],
      filas: c7.resultados,
    }));

  contenedor.replaceChildren(
    encabezado("Resumen", "Datos en vivo desde MongoDB Atlas, base QuickTrack"),
    indicadores,
    el("div", { class: "rejilla rejilla-3 seccion" }, estados, zonas, satisfaccion),
    el("div", { class: "seccion" }, evolucion),
    el("div", { class: "rejilla rejilla-2 seccion" }, topClientes, topRutas));
}
