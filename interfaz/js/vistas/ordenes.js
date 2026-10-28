// Órdenes: listado con filtros, detalle con seguimiento y valoración, y las
// operaciones de escritura (crear, cambiar estado, corregir total, valorar, eliminar).
// Los botones siguen las reglas del CRUD; igual, quien decide es la API.

import { api, catalogos } from "../api.js";
import * as f from "../formato.js";
import {
  aviso, avisoError, cargando, confirmar, dialogoFormulario, el, encabezado, errorVista,
  paginacion, panelLateral, tabla, tarjeta,
} from "../ui.js";

const LIMITE = 20;
const TRANSICIONES = {
  "En preparación": ["En tránsito", "Cancelado"],
  "En tránsito": ["Entregado", "Cancelado"],
};
const ABIERTOS = ["En preparación", "En tránsito"];
const ELIMINABLES = ["En preparación", "Cancelado"];
const MEDIOS_PAGO = ["Tarjeta", "Efectivo", "Transferencia"];
const TEXTO_TRANSICION = {
  "En tránsito": "Pasar a En tránsito",
  "Entregado": "Marcar como Entregado",
  "Cancelado": "Cancelar orden",
};

const filtros = { estado: "", cliente: "", salto: 0 };

export function columnasOrden({ clientes, rutas }, { conCliente = true } = {}) {
  return [
    { titulo: "Orden", valor: (o) => el("span", { class: "mono" }, o._id) },
    conCliente && {
      titulo: "Cliente",
      valor: (o) => el("div", { class: "celda-doble" }, f.nombreCliente(clientes, o.cliente_id), el("small", {}, `#${o.cliente_id}`)),
    },
    {
      titulo: "Ruta",
      valor: (o) => el("div", { class: "celda-doble" }, f.tramoRuta(rutas.get(o.ruta_id)), el("small", {}, o.ruta_id)),
    },
    { titulo: "Envío", valor: (o) => f.fecha(o.fecha_envio) },
    { titulo: "Pago", valor: (o) => o.medio_pago },
    { titulo: "Total", valor: (o) => f.dinero(o.total), num: true },
    { titulo: "Estado", valor: (o) => f.insigniaEstado(o.estado) },
  ].filter(Boolean);
}

export async function render(contenedor, parametro) {
  const nueva = el("button", { class: "boton boton-primario", type: "button" }, "Nueva orden");
  contenedor.replaceChildren(encabezado("Órdenes", "Órdenes de entrega con su seguimiento y valoración", nueva), cargando());

  let cat;
  try {
    cat = await catalogos();
  } catch (error) {
    contenedor.lastChild.replaceWith(errorVista(error, () => render(contenedor, parametro)));
    return;
  }

  const estado = el("select", { "aria-label": "Filtrar por estado" },
    el("option", { value: "" }, "Todos los estados"),
    f.ESTADOS.map((e) => el("option", { value: e, selected: filtros.estado === e }, e)));
  const cliente = el("select", { "aria-label": "Filtrar por cliente" },
    el("option", { value: "" }, "Todos los clientes"),
    [...cat.clientes.values()].sort((a, b) => a.nombre.localeCompare(b.nombre, "es"))
      .map((c) => el("option", { value: c._id, selected: String(filtros.cliente) === String(c._id) }, `${c.nombre} (#${c._id})`)));
  const resultado = el("div", {}, cargando());

  async function recargar() {
    resultado.classList.add("recargando");
    try {
      const pagina = await api("/ordenes", {
        consulta: { estado: filtros.estado, cliente_id: filtros.cliente, limite: LIMITE, salto: filtros.salto },
      });
      resultado.replaceChildren(
        tabla({
          columnas: columnasOrden(cat),
          filas: pagina.datos,
          alElegir: (o) => abrirOrden(o._id, { alCambiar: recargar }),
          vacio: "No hay órdenes con esos filtros",
        }),
        paginacion(pagina, (salto) => { filtros.salto = salto; recargar(); }));
    } catch (error) {
      resultado.replaceChildren(errorVista(error, recargar));
    } finally {
      resultado.classList.remove("recargando");
    }
  }

  for (const [control, clave] of [[estado, "estado"], [cliente, "cliente"]]) {
    control.addEventListener("change", () => { filtros[clave] = control.value; filtros.salto = 0; recargar(); });
  }
  nueva.addEventListener("click", () => nuevaOrden(cat, recargar));

  contenedor.replaceChildren(
    encabezado("Órdenes", "Órdenes de entrega con su seguimiento y valoración", nueva),
    tarjeta({},
      el("div", { class: "barra-filtros" },
        el("label", { class: "campo" }, "Estado", estado),
        el("label", { class: "campo" }, "Cliente", cliente)),
      resultado));
  await recargar();

  if (parametro) {
    abrirOrden(parametro, {
      alCambiar: recargar,
      // Si se cerró por navegar a otra vista, la dirección ya es otra y no se toca
      alCerrar: () => { if (location.hash.startsWith("#/ordenes/")) history.replaceState(null, "", "#/ordenes"); },
    });
  }
}

async function nuevaOrden(cat, alCrear) {
  const clientes = [...cat.clientes.values()].sort((a, b) => a.nombre.localeCompare(b.nombre, "es"));
  const rutas = [...cat.rutas.values()].sort((a, b) => a._id.localeCompare(b._id, "es", { numeric: true }));
  const creada = await dialogoFormulario({
    titulo: "Nueva orden",
    descripcion: "La orden nace En preparación y se crea con su seguimiento inicial.",
    boton: "Crear orden",
    campos: [
      { nombre: "cliente_id", etiqueta: "Cliente", tipo: "select", requerido: true,
        opciones: clientes.map((c) => ({ valor: String(c._id), texto: `${c.nombre} (#${c._id})` })) },
      { nombre: "ruta_id", etiqueta: "Ruta", tipo: "select", requerido: true,
        opciones: rutas.map((r) => ({ valor: r._id, texto: `${f.tramoRuta(r)} · ${r.zona} (${r._id})` })) },
      { nombre: "total", etiqueta: "Total ($)", tipo: "number", requerido: true, min: "0.01", paso: "0.01", ayuda: "Por ejemplo 85000" },
      { nombre: "medio_pago", etiqueta: "Medio de pago", tipo: "select", requerido: true,
        opciones: MEDIOS_PAGO.map((m) => ({ valor: m, texto: m })) },
      { nombre: "fecha_envio", etiqueta: "Fecha de envío (vacía = hoy)", tipo: "date" },
    ],
    alEnviar: (v) => api("/ordenes", {
      metodo: "POST",
      cuerpo: {
        cliente_id: Number(v.cliente_id), ruta_id: v.ruta_id, total: v.total, medio_pago: v.medio_pago,
        ...(v.fecha_envio ? { fecha_envio: v.fecha_envio } : {}),
      },
    }),
  });
  if (!creada) return;
  aviso(`Orden ${creada.orden._id} creada`, { detalle: `${f.dinero(creada.orden.total)} · ${creada.orden.medio_pago}` });
  await alCrear();
  abrirOrden(creada.orden._id, { alCambiar: alCrear });
}

/** Panel de detalle de una orden. alCambiar se llama después de cada modificación. */
export function abrirOrden(ordenId, { alCambiar, alCerrar } = {}) {
  const panel = panelLateral({ titulo: ordenId, alCerrar });

  async function cargar() {
    panel.cuerpo.replaceChildren(cargando());
    try {
      const [orden, cat] = await Promise.all([api(`/ordenes/${encodeURIComponent(ordenId)}`), catalogos()]);
      pintar(orden, cat);
    } catch (error) {
      panel.cuerpo.replaceChildren(errorVista(error, cargar));
    }
  }

  async function ejecutar(accion, mensaje) {
    try {
      const resultado = await accion();
      if (resultado === null) return; // diálogo cancelado
      aviso(mensaje(resultado));
      await alCambiar?.();
      await cargar();
    } catch (error) {
      avisoError(error);
    }
  }

  function pintar(orden, { clientes, rutas }) {
    panel.titulo.replaceChildren(el("span", { class: "mono" }, orden._id), f.insigniaEstado(orden.estado));
    const cliente = clientes.get(orden.cliente_id);
    const ruta = rutas.get(orden.ruta_id);

    const datos = el("dl", { class: "datos" },
      el("dt", {}, "Cliente"),
      el("dd", {}, cliente
        ? [el("a", { href: `#/clientes/${cliente._id}` }, cliente.nombre), el("div", { class: "muy-tenue" }, `#${cliente._id} · ${cliente.correo} · ${cliente.pais}`)]
        : `#${orden.cliente_id}`),
      el("dt", {}, "Ruta"),
      el("dd", {}, ruta
        ? [f.tramoRuta(ruta), el("div", { class: "muy-tenue" }, `${ruta._id} · zona ${ruta.zona} · ${f.km(ruta.distancia_km)}`)]
        : orden.ruta_id),
      el("dt", {}, "Fecha de envío"), el("dd", {}, f.fecha(orden.fecha_envio)),
      el("dt", {}, "Medio de pago"), el("dd", {}, orden.medio_pago),
      el("dt", {}, "Total"), el("dd", {}, el("strong", {}, f.dinero(orden.total))));

    panel.cuerpo.replaceChildren(
      el("section", {}, datos),
      el("section", {}, el("h3", {}, "Seguimiento"), seguimiento(orden)),
      el("section", {}, el("h3", {}, "Valoración"), valoracion(orden)),
      acciones(orden));
  }

  function acciones(orden) {
    const botones = [];
    for (const destino of TRANSICIONES[orden.estado] || []) {
      botones.push(el("button", {
        class: `boton ${destino === "Cancelado" ? "boton-peligro" : "boton-primario"}`, type: "button",
        onClick: () => ejecutar(async () => {
          const ok = await confirmar({
            titulo: `¿${TEXTO_TRANSICION[destino]}?`,
            texto: `La orden pasa de ${orden.estado} a ${destino}. El cambio se guarda en MongoDB y queda en el historial del seguimiento.`,
            boton: TEXTO_TRANSICION[destino], peligro: destino === "Cancelado",
          });
          return ok ? api(`/ordenes/${orden._id}/estado`, { metodo: "PATCH", cuerpo: { estado: destino } }) : null;
        }, (r) => `Orden ${r.orden_id}: ${r.estado_anterior} → ${r.estado_nuevo}`),
      }, TEXTO_TRANSICION[destino]));
    }
    if (ABIERTOS.includes(orden.estado)) {
      botones.push(el("button", {
        class: "boton", type: "button",
        onClick: () => ejecutar(() => dialogoFormulario({
          titulo: "Corregir el total",
          descripcion: `Total actual: ${f.dinero(orden.total)}. Solo se corrige mientras la orden está abierta.`,
          boton: "Guardar total",
          campos: [{ nombre: "total", etiqueta: "Nuevo total ($)", tipo: "number", requerido: true, min: "0.01", paso: "0.01", valor: orden.total }],
          alEnviar: (v) => api(`/ordenes/${orden._id}/total`, { metodo: "PATCH", cuerpo: { total: v.total } }),
        }), (r) => (r.modificado ? `Total corregido: ${f.dinero(r.total_anterior)} → ${f.dinero(r.total_nuevo)}` : "El total ya tenía ese valor")),
      }, "Corregir total"));
    }
    if (orden.estado === "Entregado" && !orden.valoracion) {
      botones.push(el("button", {
        class: "boton", type: "button",
        onClick: () => ejecutar(() => dialogoFormulario({
          titulo: "Registrar valoración",
          descripcion: "Una valoración por orden entregada.",
          boton: "Registrar",
          campos: [
            { nombre: "puntaje", etiqueta: "Puntaje", tipo: "select", requerido: true, valor: "5",
              opciones: [5, 4, 3, 2, 1].map((p) => ({ valor: String(p), texto: `${"★".repeat(p)}${"☆".repeat(5 - p)}  ${p} de 5` })) },
            { nombre: "comentario", etiqueta: "Comentario", tipo: "textarea", requerido: true, maximo: 300 },
          ],
          alEnviar: (v) => api(`/ordenes/${orden._id}/valoracion`, {
            metodo: "POST", cuerpo: { puntaje: Number(v.puntaje), comentario: v.comentario },
          }),
        }), (r) => `Valoración registrada (${r.puntaje} de 5)`),
      }, "Registrar valoración"));
    }
    if (ELIMINABLES.includes(orden.estado)) {
      botones.push(el("button", {
        class: "boton boton-peligro", type: "button",
        onClick: async () => {
          const ok = await confirmar({
            titulo: `¿Eliminar la orden ${orden._id}?`,
            texto: "Se elimina de MongoDB junto con su seguimiento y su valoración. No se puede deshacer.",
            boton: "Eliminar", peligro: true,
          });
          if (!ok) return;
          try {
            const r = await api(`/ordenes/${orden._id}`, { metodo: "DELETE" });
            aviso(`Orden ${r.orden_id} eliminada`, { detalle: `Seguimientos: ${r.seguimientos_eliminados} · valoraciones: ${r.valoraciones_eliminadas}` });
            panel.cerrar();
            await alCambiar?.();
          } catch (error) {
            avisoError(error);
          }
        },
      }, "Eliminar"));
    }
    if (!botones.length) {
      return el("section", {}, el("h3", {}, "Acciones"),
        el("p", { class: "tenue" }, `${orden.estado} es un estado final: la orden ya no admite cambios.`));
    }
    return el("section", {}, el("h3", {}, "Acciones"), el("div", { class: "acciones" }, botones));
  }

  cargar();
}

function seguimiento(orden) {
  const seg = orden.seguimiento;
  if (!seg) return el("div", { class: "nota aviso" }, el("span", { class: "nota-icono" }, "!"), "Esta orden no tiene seguimiento.");
  const historial = seg.historial || [];
  const lista = el("ol", { class: "linea-tiempo" }, historial.map((evento, i) =>
    el("li", { class: i === historial.length - 1 ? "actual" : null },
      evento.estado, el("small", {}, f.fecha(evento.fecha)))));
  const desalineado = seg.estado_actual !== orden.estado;
  return el("div", {},
    el("p", { class: "tenue", style: "margin:0 0 10px" }, "Estado actual del seguimiento: ", f.insigniaEstado(seg.estado_actual)),
    historial.length ? lista : el("p", { class: "tenue" }, "El historial está vacío."),
    desalineado && el("div", { class: "nota aviso", style: "margin-top:12px" },
      el("span", { class: "nota-icono" }, "!"),
      el("span", {}, `El seguimiento dice «${seg.estado_actual}», pero la orden está «${orden.estado}». `,
        "Es una inconsistencia de los datos originales; ver ", el("a", { href: "#/integridad" }, "Integridad"), ".")));
}

function valoracion(orden) {
  const v = orden.valoracion;
  if (!v) {
    return el("p", { class: "tenue", style: "margin:0" },
      orden.estado === "Entregado" ? "Aún no tiene valoración." : "Solo las órdenes entregadas se pueden valorar.");
  }
  return el("div", {},
    el("div", {}, f.estrellas(v.puntaje), el("span", { class: "tenue" }, `  ${v.puntaje} de 5`)),
    el("p", { style: "margin:6px 0 0" }, `“${v.comentario}”`));
}
