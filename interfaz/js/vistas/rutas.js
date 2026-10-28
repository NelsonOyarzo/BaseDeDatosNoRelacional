// Rutas: catálogo con filtro por zona, en orden numérico (ruta_2 antes que ruta_10).

import { api } from "../api.js";
import * as f from "../formato.js";
import { cargando, el, encabezado, errorVista, paginacion, tabla, tarjeta } from "../ui.js";

const LIMITE = 20;
const ZONAS = ["Centro", "Norte", "Oriente", "Poniente", "Sur"];
const filtros = { zona: "", salto: 0 };

export async function render(contenedor) {
  const zona = el("select", { "aria-label": "Filtrar por zona" },
    el("option", { value: "" }, "Todas las zonas"),
    ZONAS.map((z) => el("option", { value: z, selected: filtros.zona === z }, z)));
  const resultado = el("div", {}, cargando());

  async function recargar() {
    resultado.classList.add("recargando");
    try {
      const pagina = await api("/rutas", { consulta: { zona: filtros.zona, limite: LIMITE, salto: filtros.salto } });
      resultado.replaceChildren(
        tabla({
          columnas: [
            { titulo: "Ruta", valor: (r) => el("span", { class: "mono" }, r._id) },
            { titulo: "Tramo", valor: (r) => f.tramoRuta(r) },
            { titulo: "Zona", valor: (r) => r.zona },
            { titulo: "Distancia", valor: (r) => f.km(r.distancia_km), num: true },
          ],
          filas: pagina.datos,
        }),
        paginacion(pagina, (salto) => { filtros.salto = salto; recargar(); }));
    } catch (error) {
      resultado.replaceChildren(errorVista(error, recargar));
    } finally {
      resultado.classList.remove("recargando");
    }
  }

  zona.addEventListener("change", () => { filtros.zona = zona.value; filtros.salto = 0; recargar(); });
  contenedor.replaceChildren(
    encabezado("Rutas", "Catálogo de rutas con su zona y distancia"),
    tarjeta({}, el("div", { class: "barra-filtros" }, el("label", { class: "campo" }, "Zona", zona)), resultado));
  await recargar();
}
