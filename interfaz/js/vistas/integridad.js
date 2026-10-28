// Integridad: auditoría completa de la base, con los problemas por categoría.
// La reparación solo se ofrece en modo simulación: los datos originales se informan, no se tocan.

import { api } from "../api.js";
import * as f from "../formato.js";
import { aviso, avisoError, cargando, el, encabezado, errorVista, tarjeta } from "../ui.js";

const CHEQUEOS = [
  ["ordenes_sin_cliente", "Órdenes sin cliente", "Órdenes cuyo cliente_id no existe en la colección clientes."],
  ["ordenes_sin_ruta", "Órdenes sin ruta", "Órdenes cuya ruta_id no existe en la colección rutas."],
  ["ordenes_sin_seguimiento", "Órdenes sin seguimiento", "Toda orden debe tener su documento de seguimiento."],
  ["seguimientos_huerfanos", "Seguimientos huérfanos", "Seguimientos cuya orden ya no existe."],
  ["valoraciones_huerfanas", "Valoraciones huérfanas", "Valoraciones cuya orden ya no existe."],
  ["seguimientos_inconsistentes", "Seguimientos desalineados",
    "El estado actual o el último evento del historial no coincide con el estado de la orden. Viene de los datos originales (ver consulta C11)."],
];

export async function render(contenedor) {
  const simular = el("button", { class: "boton", type: "button" }, "Simular reparación");
  contenedor.replaceChildren(encabezado("Integridad", "Auditoría de las relaciones entre colecciones", simular), cargando("Auditando la base…"));

  let auditoria;
  try {
    auditoria = await api("/integridad/auditoria");
  } catch (error) {
    contenedor.lastChild.replaceWith(errorVista(error, () => render(contenedor)));
    return;
  }

  simular.addEventListener("click", async () => {
    simular.disabled = true;
    try {
      const r = await api("/integridad/seguimientos/reparar", { metodo: "POST" });
      aviso(`Se corregirían ${f.numero(r.detectados)} seguimientos`, { detalle: "Simulación: no se modificó ningún documento" });
    } catch (error) {
      avisoError(error);
    } finally {
      simular.disabled = false;
    }
  });

  const { totales, resumen, detalle } = auditoria;
  const problemas = Object.values(resumen).reduce((s, n) => s + n, 0);
  const kpi = (etiqueta, valor) => el("div", { class: "tarjeta kpi" },
    el("div", { class: "kpi-etiqueta" }, etiqueta), el("div", { class: "kpi-valor" }, f.numero(valor)));

  const chequeos = CHEQUEOS.map(([clave, nombre, explicacion]) => {
    const ids = detalle[clave] || [];
    const ok = ids.length === 0;
    return el("div", { class: "chequeo" },
      el("span", { class: `chequeo-icono ${ok ? "bien" : "aviso"}`, "aria-hidden": "true" }, ok ? "✓" : "!"),
      el("div", {},
        el("h3", {}, nombre),
        el("p", {}, explicacion),
        !ok && el("details", {},
          el("summary", {}, `Ver los ${f.numero(ids.length)} afectados`),
          el("div", { class: "ids" }, ids.map((id) => String(id).startsWith("orden_")
            ? el("a", { href: `#/ordenes/${id}` }, el("span", {}, id))
            : el("span", {}, String(id)))))),
      el("div", { class: "num" }, el("strong", {}, ok ? "Sin problemas" : f.numero(ids.length))));
  });

  contenedor.replaceChildren(
    encabezado("Integridad", "Auditoría de las relaciones entre colecciones", simular),
    el("div", { class: "rejilla rejilla-kpi" },
      kpi("Órdenes", totales.ordenes), kpi("Seguimientos", totales.seguimientos), kpi("Valoraciones", totales.valoraciones),
      kpi("Problemas detectados", problemas)),
    tarjeta({ clase: "seccion", titulo: "Chequeos", subtitulo: "La orden es la fuente de verdad; los seguimientos y valoraciones dependen de ella" },
      el("div", { class: "chequeos" }, chequeos)));
}
