// Clientes: listado con filtro por país y detalle con sus órdenes.

import { api, catalogos } from "../api.js";
import * as f from "../formato.js";
import { cargando, el, encabezado, errorVista, paginacion, panelLateral, tabla, tarjeta } from "../ui.js";
import { abrirOrden, columnasOrden } from "./ordenes.js";

const LIMITE = 20;
const filtros = { pais: "", salto: 0 };

export async function render(contenedor, parametro) {
  const pais = el("input", { type: "search", value: filtros.pais, placeholder: "Por ejemplo Chile", "aria-label": "Filtrar por país" });
  const resultado = el("div", {}, cargando());

  async function recargar() {
    resultado.classList.add("recargando");
    try {
      const pagina = await api("/clientes", { consulta: { pais: filtros.pais, limite: LIMITE, salto: filtros.salto } });
      resultado.replaceChildren(
        tabla({
          columnas: [
            { titulo: "ID", valor: (c) => el("span", { class: "mono" }, `#${c._id}`) },
            { titulo: "Cliente", valor: (c) => el("div", { class: "celda-doble" }, c.nombre, el("small", {}, c.correo)) },
            { titulo: "País", valor: (c) => c.pais },
            { titulo: "Registro", valor: (c) => f.fecha(c.fecha_registro) },
          ],
          filas: pagina.datos,
          alElegir: (c) => abrirCliente(c._id),
          vacio: "Ningún cliente coincide con ese país",
        }),
        paginacion(pagina, (salto) => { filtros.salto = salto; recargar(); }));
    } catch (error) {
      resultado.replaceChildren(errorVista(error, recargar));
    } finally {
      resultado.classList.remove("recargando");
    }
  }

  let espera;
  pais.addEventListener("input", () => {
    clearTimeout(espera);
    espera = setTimeout(() => { filtros.pais = pais.value.trim(); filtros.salto = 0; recargar(); }, 300);
  });

  contenedor.replaceChildren(
    encabezado("Clientes", "El filtro de país no distingue mayúsculas ni tildes"),
    tarjeta({}, el("div", { class: "barra-filtros" }, el("label", { class: "campo" }, "País", pais)), resultado));
  await recargar();
  if (parametro) {
    abrirCliente(parametro, () => { if (location.hash.startsWith("#/clientes/")) history.replaceState(null, "", "#/clientes"); });
  }
}

function abrirCliente(clienteId, alCerrar) {
  const panel = panelLateral({ titulo: `Cliente #${clienteId}`, alCerrar });

  async function cargar() {
    panel.cuerpo.replaceChildren(cargando());
    try {
      const [cliente, ordenes, cat] = await Promise.all([
        api(`/clientes/${encodeURIComponent(clienteId)}`),
        api(`/clientes/${encodeURIComponent(clienteId)}/ordenes`, { consulta: { limite: 100 } }),
        catalogos(),
      ]);
      const total = ordenes.datos.reduce((s, o) => s + o.total, 0);
      panel.titulo.replaceChildren(cliente.nombre);
      panel.cuerpo.replaceChildren(
        el("dl", { class: "datos" },
          el("dt", {}, "Id"), el("dd", { class: "mono" }, `#${cliente._id}`),
          el("dt", {}, "Correo"), el("dd", {}, cliente.correo),
          el("dt", {}, "País"), el("dd", {}, cliente.pais),
          el("dt", {}, "Registro"), el("dd", {}, f.fecha(cliente.fecha_registro))),
        el("section", {},
          el("h3", {}, `Órdenes · ${f.numero(ordenes.total)} por ${f.dinero(total)}`),
          tabla({
            columnas: columnasOrden(cat, { conCliente: false }).filter((c) => c.titulo !== "Pago"),
            filas: ordenes.datos,
            alElegir: (o) => abrirOrden(o._id, { alCambiar: cargar }),
            vacio: "Este cliente no tiene órdenes",
          })));
    } catch (error) {
      panel.cuerpo.replaceChildren(errorVista(error, cargar));
    }
  }
  cargar();
}
