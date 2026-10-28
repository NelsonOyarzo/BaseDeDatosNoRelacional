// Piezas de interfaz sin dependencias. Todo el texto que viene de la base se
// inserta como nodo de texto (nunca como HTML), así un comentario con etiquetas
// no puede inyectar código.

/** Crea un elemento: el("a", { href, class, onClick }, "texto", otroNodo, [lista]) */
export function el(etiqueta, props = {}, ...hijos) {
  const nodo = document.createElement(etiqueta);
  for (const [clave, valor] of Object.entries(props || {})) {
    if (valor == null || valor === false) continue;
    if (clave.startsWith("on") && typeof valor === "function") nodo.addEventListener(clave.slice(2).toLowerCase(), valor);
    else if (clave === "dataset") Object.assign(nodo.dataset, valor);
    else if (clave === "value") nodo.value = valor;
    else nodo.setAttribute(clave, valor === true ? "" : valor);
  }
  agregar(nodo, hijos);
  return nodo;
}

function agregar(nodo, hijos) {
  for (const hijo of hijos.flat(Infinity)) {
    if (hijo == null || hijo === false) continue;
    nodo.append(hijo instanceof Node ? hijo : document.createTextNode(String(hijo)));
  }
}

export function svg(etiqueta, atributos = {}, ...hijos) {
  const nodo = document.createElementNS("http://www.w3.org/2000/svg", etiqueta);
  for (const [clave, valor] of Object.entries(atributos)) if (valor != null) nodo.setAttribute(clave, valor);
  for (const hijo of hijos.flat()) if (hijo) nodo.append(hijo instanceof Node ? hijo : document.createTextNode(String(hijo)));
  return nodo;
}

export function encabezado(titulo, descripcion, ...acciones) {
  return el("div", { class: "encabezado" },
    el("div", {}, el("h1", {}, titulo), descripcion && el("p", {}, descripcion)),
    acciones.length ? el("div", { class: "acciones" }, acciones) : null);
}

export function tarjeta({ titulo, subtitulo, pie, clase = "" }, ...contenido) {
  return el("section", { class: `tarjeta ${clase}` },
    titulo && el("div", { class: "tarjeta-titulo" }, el("div", {}, el("h2", {}, titulo), subtitulo && el("p", {}, subtitulo))),
    contenido,
    pie && el("div", { class: "tarjeta-pie" }, [pie].flat().map((p) => (p instanceof Node ? p : el("span", {}, p)))));
}

export const cargando = (texto = "Cargando…") => el("div", { class: "cargando", role: "status" }, texto);

export function errorVista(error, reintentar) {
  return el("div", { class: "tarjeta error-vista", role: "alert" },
    el("h2", {}, "No se pudieron cargar los datos"),
    el("p", { class: "tenue" }, error.message),
    error.idSolicitud && el("p", { class: "muy-tenue" }, `Id de solicitud: ${error.idSolicitud}`),
    reintentar && el("button", { class: "boton", type: "button", onClick: reintentar }, "Reintentar"));
}

// ------------------------------------------------------------------ avisos
export function aviso(titulo, { detalle, error = false } = {}) {
  const nodo = el("div", { class: `aviso-flotante${error ? " error" : ""}`, role: error ? "alert" : "status" },
    el("div", {}, el("strong", {}, titulo), detalle && el("small", {}, detalle)));
  document.getElementById("avisos").append(nodo);
  setTimeout(() => nodo.remove(), error ? 9000 : 5000);
}

export function avisoError(error) {
  const detalle = [error.codigo && error.codigo !== "ERROR" ? error.codigo : null,
    error.idSolicitud ? `id ${error.idSolicitud}` : null].filter(Boolean).join(" · ");
  aviso(error.message, { detalle, error: true });
}

// ------------------------------------------------------------------ tooltip
const tooltip = () => document.getElementById("tooltip");

export function mostrarTooltip(x, y, ...contenido) {
  const nodo = tooltip();
  nodo.replaceChildren(...contenido.flat().filter(Boolean));
  nodo.hidden = false;
  const { width, height } = nodo.getBoundingClientRect();
  const izquierda = Math.min(x + 14, window.innerWidth - width - 8);
  const arriba = y - height - 12 < 8 ? y + 16 : y - height - 12;
  nodo.style.left = `${Math.max(8, izquierda)}px`;
  nodo.style.top = `${arriba}px`;
}

export const ocultarTooltip = () => { tooltip().hidden = true; };

// ------------------------------------------------------------------ tablas
/**
 * columnas: [{ titulo, valor: (fila) => texto | nodo, num: bool }]
 * alElegir(fila): hace la fila clicable (también con Enter).
 */
export function tabla({ columnas, filas, alElegir, vacio = "Sin resultados" }) {
  if (!filas.length) return el("div", { class: "vacio" }, vacio);
  const cuerpo = filas.map((fila) => el("tr", alElegir ? {
    class: "clicable", tabindex: 0,
    onClick: () => alElegir(fila),
    onKeydown: (e) => { if (e.key === "Enter") alElegir(fila); },
  } : {}, columnas.map((c) => el("td", { class: c.num ? "num" : null }, c.valor(fila)))));
  return el("div", { class: "tabla-contenedor" },
    el("table", {},
      el("thead", {}, el("tr", {}, columnas.map((c) => el("th", { class: c.num ? "num" : null, scope: "col" }, c.titulo)))),
      el("tbody", {}, cuerpo)));
}

export function paginacion({ total, limite, salto }, alCambiar) {
  const desde = total ? salto + 1 : 0;
  const hasta = Math.min(salto + limite, total);
  return el("div", { class: "paginacion" },
    el("span", {}, `${desde}–${hasta} de ${total}`),
    el("div", { class: "botones" },
      el("button", { class: "boton", type: "button", disabled: salto <= 0, onClick: () => alCambiar(Math.max(0, salto - limite)) }, "Anterior"),
      el("button", { class: "boton", type: "button", disabled: hasta >= total, onClick: () => alCambiar(salto + limite) }, "Siguiente")));
}

// ------------------------------------------------------------------ diálogos
function abrir(dialogo) {
  document.body.append(dialogo);
  dialogo.addEventListener("close", () => dialogo.remove());
  dialogo.showModal();
  return dialogo;
}

export function confirmar({ titulo, texto, boton = "Confirmar", peligro = false }) {
  return new Promise((resolver) => {
    let aceptado = false;
    const dialogo = el("dialog", { "aria-label": titulo },
      el("div", { class: "dialogo-cuerpo" }, el("h2", {}, titulo), texto && el("p", {}, texto)),
      el("div", { class: "dialogo-acciones" },
        el("button", { class: "boton", type: "button", onClick: () => dialogo.close() }, "Cancelar"),
        el("button", {
          class: `boton ${peligro ? "boton-peligro lleno" : "boton-primario"}`, type: "button",
          onClick: () => { aceptado = true; dialogo.close(); },
        }, boton)));
    dialogo.addEventListener("close", () => resolver(aceptado));
    abrir(dialogo);
  });
}

/**
 * Formulario en un diálogo. alEnviar(valores) hace la llamada a la API: si
 * falla, el error se muestra dentro del diálogo (marcando los campos que
 * informe la API) y el diálogo sigue abierto.
 * campos: [{ nombre, etiqueta, tipo: text|number|date|select|textarea, opciones: [{valor, texto}], requerido, ... }]
 */
export function dialogoFormulario({ titulo, descripcion, campos, boton = "Guardar", alEnviar }) {
  return new Promise((resolver) => {
    let resultado = null;
    const caja = el("div", { class: "dialogo-error", role: "alert", hidden: true });
    const controles = {};
    const filas = campos.map((c) => {
      const id = `campo-${c.nombre}`;
      const atributos = { id, name: c.nombre, required: c.requerido, min: c.min, max: c.max, step: c.paso, placeholder: c.ayuda };
      const control = c.tipo === "select"
        ? el("select", atributos, c.opciones.map((o) => el("option", { value: o.valor, selected: o.valor === c.valor }, o.texto)))
        : c.tipo === "textarea"
          ? el("textarea", { ...atributos, maxlength: c.maximo }, c.valor ?? "")
          : el("input", { ...atributos, type: c.tipo || "text", value: c.valor ?? "" });
      controles[c.nombre] = { control, mensaje: el("span", { class: "campo-error", hidden: true }) };
      return el("label", { class: "campo", for: id }, c.etiqueta, control, controles[c.nombre].mensaje);
    });
    const enviar = el("button", { class: "boton boton-primario", type: "submit" }, boton);
    const formulario = el("form", { method: "dialog", novalidate: false },
      el("div", { class: "dialogo-cuerpo" },
        el("h2", {}, titulo), descripcion && el("p", {}, descripcion), caja, el("div", { class: "campos" }, filas)),
      el("div", { class: "dialogo-acciones" },
        el("button", { class: "boton", type: "button", onClick: () => dialogo.close() }, "Cancelar"), enviar));

    formulario.addEventListener("submit", async (evento) => {
      evento.preventDefault();
      const valores = {};
      for (const c of campos) {
        const { control, mensaje } = controles[c.nombre];
        control.removeAttribute("aria-invalid");
        mensaje.hidden = true;
        const texto = control.value.trim();
        valores[c.nombre] = texto === "" ? null : c.tipo === "number" ? Number(texto) : texto;
      }
      caja.hidden = true;
      enviar.disabled = true;
      try {
        resultado = await alEnviar(valores);
        dialogo.close();
      } catch (error) {
        caja.replaceChildren(el("strong", {}, error.message || "No se pudo guardar"),
          error.idSolicitud ? el("div", { class: "muy-tenue" }, `${error.codigo} · id ${error.idSolicitud}`) : null);
        caja.hidden = false;
        for (const e of error.errores || []) {
          const campo = controles[e.campo];
          if (!campo) continue;
          campo.control.setAttribute("aria-invalid", "true");
          campo.mensaje.textContent = e.mensaje;
          campo.mensaje.hidden = false;
        }
      } finally {
        enviar.disabled = false;
      }
    });

    const dialogo = el("dialog", { "aria-label": titulo }, formulario);
    dialogo.addEventListener("close", () => resolver(resultado));
    abrir(dialogo);
    filas[0]?.querySelector("input, select, textarea")?.focus();
  });
}

/** Panel lateral (detalle de una orden o un cliente). Devuelve { cuerpo, titulo, cerrar }. */
export function panelLateral({ titulo, alCerrar }) {
  const encabezadoTitulo = el("h2", {}, titulo);
  const cuerpo = el("div", { class: "lateral-cuerpo" }, cargando());
  const dialogo = el("dialog", { class: "lateral", "aria-label": titulo },
    el("div", { class: "lateral-cabecera" }, encabezadoTitulo,
      el("button", { class: "boton boton-icono", type: "button", "aria-label": "Cerrar", onClick: () => dialogo.close() }, "✕")),
    cuerpo);
  dialogo.addEventListener("click", (e) => { if (e.target === dialogo) dialogo.close(); });
  if (alCerrar) dialogo.addEventListener("close", alCerrar);
  abrir(dialogo);
  return { cuerpo, titulo: encabezadoTitulo, cerrar: () => dialogo.close() };
}
