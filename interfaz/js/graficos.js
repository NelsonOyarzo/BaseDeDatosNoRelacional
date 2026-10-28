// Gráficos sin bibliotecas, con un solo color (el acento): cada gráfico tiene una
// sola serie, así que el título la nombra y no hace falta leyenda.
// Marcas finas (barras de 16 px con el extremo redondeado, línea de 2 px),
// rejilla tenue, valor directo en el extremo y tooltip en cada marca.

import { el, mostrarTooltip, ocultarTooltip, svg } from "./ui.js";

/** Escala "limpia" (1, 2, 2.5, 5 x 10^n) que cubre el máximo con ~n marcas. */
export function marcasEje(maximo, n = 4) {
  if (!maximo || maximo <= 0) return [0, 1];
  const bruto = maximo / n;
  const potencia = 10 ** Math.floor(Math.log10(bruto));
  const paso = [1, 2, 2.5, 5, 10].map((f) => f * potencia).find((p) => p >= bruto);
  const marcas = [];
  for (let v = 0; v <= maximo + paso * 0.999; v += paso) marcas.push(Number(v.toPrecision(12)));
  return marcas;
}

function filaTooltip(texto) {
  return el("div", { class: "fila-tooltip" }, el("span", { class: "clave-linea" }), texto);
}

/**
 * Barras horizontales.
 * datos: [{ etiqueta, valor, detalle: [texto, ...] }]
 * formato(valor) para el valor en el extremo; maximo fija la escala (p. ej. 5 para puntajes).
 */
export function barrasHorizontales({ datos, formato, formatoEje = formato, maximo, eje = true }) {
  const marcas = marcasEje(maximo ?? Math.max(...datos.map((d) => d.valor)), 4);
  const tope = maximo ?? marcas.at(-1);
  const filas = datos.flatMap((d) => {
    const pista = el("div", {
      class: "barras-pista", tabindex: 0, role: "img",
      "aria-label": `${d.etiqueta}: ${formato(d.valor)}`,
    }, el("div", { class: "barras-relleno", style: `width:${Math.max(0, (d.valor / tope) * 100)}%` }));
    const mostrar = (x, y) => mostrarTooltip(x, y, el("strong", {}, formato(d.valor)), filaTooltip(d.etiqueta),
      (d.detalle || []).map((t) => el("div", { class: "muy-tenue" }, t)));
    pista.addEventListener("pointermove", (e) => mostrar(e.clientX, e.clientY));
    pista.addEventListener("pointerleave", ocultarTooltip);
    pista.addEventListener("focus", () => { const r = pista.getBoundingClientRect(); mostrar(r.left + r.width / 2, r.top); });
    pista.addEventListener("blur", ocultarTooltip);
    return [el("div", { class: "barras-etiqueta" }, d.etiqueta), pista, el("div", { class: "barras-valor" }, formato(d.valor))];
  });
  const ejeX = eje && el("div", { class: "barras-eje", "aria-hidden": "true" },
    (maximo ? [0, maximo / 2, maximo] : [0, tope / 2, tope]).map((v) => el("span", {}, formatoEje(v))));
  return el("div", { class: "barras" }, filas, ejeX);
}

/**
 * Línea temporal de una serie, con área tenue, mira que se ajusta al punto más
 * cercano y navegación con flechas del teclado.
 * puntos: [{ x: "2023-04", y: 1234, detalle: [texto] }]
 */
export function lineaTemporal({ puntos, formatoY, formatoEjeY = formatoY, formatoX, alto = 240, descripcion }) {
  const contenedor = el("div", { class: "linea-grafico" });
  let indiceActivo = null;

  function dibujar() {
    const ancho = Math.max(320, contenedor.clientWidth || 640);
    const margen = { arriba: 16, derecha: 56, abajo: 28, izquierda: 56 };
    const anchoUtil = ancho - margen.izquierda - margen.derecha;
    const altoUtil = alto - margen.arriba - margen.abajo;
    const marcas = marcasEje(Math.max(...puntos.map((p) => p.y)), 4);
    const tope = marcas.at(-1);
    const x = (i) => margen.izquierda + (puntos.length === 1 ? anchoUtil / 2 : (i / (puntos.length - 1)) * anchoUtil);
    const y = (v) => margen.arriba + altoUtil - (v / tope) * altoUtil;

    const lienzo = svg("svg", {
      viewBox: `0 0 ${ancho} ${alto}`, height: alto, role: "img", tabindex: 0,
      "aria-label": descripcion || "Gráfico de línea",
    });
    for (const v of marcas) {
      lienzo.append(svg("line", { class: v === 0 ? "base" : "rejilla-h", x1: margen.izquierda, x2: ancho - margen.derecha, y1: y(v), y2: y(v) }));
      lienzo.append(svg("text", { x: margen.izquierda - 8, y: y(v) + 4, "text-anchor": "end" }, formatoEjeY(v)));
    }
    // Etiquetas del eje X: unas 6, espaciadas de forma pareja
    const pasoX = Math.max(1, Math.ceil(puntos.length / 6));
    puntos.forEach((p, i) => {
      if (i % pasoX === 0) lienzo.append(svg("text", { x: x(i), y: alto - 8, "text-anchor": "middle" }, formatoX(p.x)));
    });

    const recorrido = puntos.map((p, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(p.y).toFixed(1)}`).join("");
    const base = y(0);
    lienzo.append(svg("path", { class: "area", d: `${recorrido}L${x(puntos.length - 1)},${base}L${x(0)},${base}Z` }));
    lienzo.append(svg("path", { class: "trazo", d: recorrido }));

    // Valor directo solo en el último punto
    const ultimo = puntos.length - 1;
    lienzo.append(svg("circle", { class: "marcador", cx: x(ultimo), cy: y(puntos[ultimo].y), r: 4 }));
    lienzo.append(svg("text", { class: "etiqueta-final", x: x(ultimo) + 8, y: y(puntos[ultimo].y) + 4 }, formatoEjeY(puntos[ultimo].y)));

    const guia = svg("line", { class: "guia", y1: margen.arriba, y2: base, visibility: "hidden" });
    const punto = svg("circle", { class: "marcador", r: 4, visibility: "hidden" });
    const captura = svg("rect", { class: "captura", x: margen.izquierda, y: margen.arriba, width: anchoUtil, height: altoUtil });
    lienzo.append(guia, punto, captura);

    function activar(i) {
      indiceActivo = i;
      const p = puntos[i];
      for (const n of [guia, punto]) n.setAttribute("visibility", "visible");
      guia.setAttribute("x1", x(i)); guia.setAttribute("x2", x(i));
      punto.setAttribute("cx", x(i)); punto.setAttribute("cy", y(p.y));
      const caja = lienzo.getBoundingClientRect();
      const escala = caja.width / ancho;
      mostrarTooltip(caja.left + x(i) * escala, caja.top + y(p.y) * escala,
        el("strong", {}, formatoY(p.y)), filaTooltip(formatoX(p.x)),
        (p.detalle || []).map((t) => el("div", { class: "muy-tenue" }, t)));
    }
    function desactivar() {
      indiceActivo = null;
      for (const n of [guia, punto]) n.setAttribute("visibility", "hidden");
      ocultarTooltip();
    }
    captura.addEventListener("pointermove", (e) => {
      const caja = lienzo.getBoundingClientRect();
      const posicion = ((e.clientX - caja.left) / caja.width) * ancho;
      const i = Math.round(((posicion - margen.izquierda) / anchoUtil) * (puntos.length - 1));
      activar(Math.max(0, Math.min(puntos.length - 1, i)));
    });
    captura.addEventListener("pointerleave", desactivar);
    lienzo.addEventListener("keydown", (e) => {
      if (e.key !== "ArrowLeft" && e.key !== "ArrowRight") return;
      e.preventDefault();
      const i = indiceActivo ?? (e.key === "ArrowLeft" ? puntos.length : -1);
      activar(Math.max(0, Math.min(puntos.length - 1, i + (e.key === "ArrowRight" ? 1 : -1))));
    });
    lienzo.addEventListener("blur", desactivar);
    contenedor.replaceChildren(lienzo);
  }

  // Se vuelve a dibujar cuando cambia el ancho (texto nítido, sin deformar)
  let anchoPrevio = 0;
  new ResizeObserver(() => {
    if (Math.abs(contenedor.clientWidth - anchoPrevio) < 4) return;
    anchoPrevio = contenedor.clientWidth;
    dibujar();
  }).observe(contenedor);
  return contenedor;
}
