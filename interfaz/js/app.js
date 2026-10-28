// Punto de entrada: navegación por hash (#/vista/parámetro), estado de la conexión y tema.

import * as clientes from "./vistas/clientes.js";
import * as consultas from "./vistas/consultas.js";
import * as integridad from "./vistas/integridad.js";
import * as ordenes from "./vistas/ordenes.js";
import * as resumen from "./vistas/resumen.js";
import * as rutas from "./vistas/rutas.js";
import { ocultarTooltip } from "./ui.js";

const VISTAS = {
  resumen: { modulo: resumen, titulo: "Resumen" },
  ordenes: { modulo: ordenes, titulo: "Órdenes" },
  clientes: { modulo: clientes, titulo: "Clientes" },
  rutas: { modulo: rutas, titulo: "Rutas" },
  consultas: { modulo: consultas, titulo: "Consultas" },
  integridad: { modulo: integridad, titulo: "Integridad" },
};

function rutaActual() {
  const [, vista, ...resto] = location.hash.split("/");
  return { vista: VISTAS[vista] ? vista : "resumen", parametro: resto.length ? decodeURIComponent(resto.join("/")) : null };
}

let primeraVez = true;

function navegar() {
  const { vista, parametro } = rutaActual();
  document.querySelectorAll("dialog[open]").forEach((d) => d.close());
  ocultarTooltip();
  for (const enlace of document.querySelectorAll(".navegacion a[data-vista]")) {
    if (enlace.dataset.vista === vista) enlace.setAttribute("aria-current", "page");
    else enlace.removeAttribute("aria-current");
  }
  document.title = `${VISTAS[vista].titulo} · QuickTrack`;

  // Cada navegación dibuja en un contenedor nuevo: si una vista anterior termina
  // de cargar tarde, escribe en un nodo que ya no está en la página.
  const main = document.getElementById("contenido");
  const contenedor = document.createElement("div");
  main.replaceChildren(contenedor);
  if (!primeraVez) { window.scrollTo(0, 0); main.focus({ preventScroll: true }); }
  primeraVez = false;
  VISTAS[vista].modulo.render(contenedor, parametro);
}

async function revisarConexion() {
  const nodo = document.getElementById("estado-conexion");
  const texto = nodo.querySelector(".texto");
  try {
    const respuesta = await fetch("/api/v1/salud");
    const salud = await respuesta.json();
    const ok = respuesta.ok && salud.estado === "ok";
    nodo.className = `conexion ${ok ? "ok" : "error"}`;
    texto.textContent = ok ? `MongoDB conectado · ${Math.round(salud.base_datos.latencia_ms)} ms` : "Base de datos no disponible";
    nodo.title = `Base ${salud.base_datos.nombre} · API ${salud.version}`;
  } catch {
    nodo.className = "conexion error";
    texto.textContent = "API sin conexión";
    nodo.title = "";
  }
}

function alternarTema() {
  const raiz = document.documentElement;
  const oscuro = raiz.dataset.theme
    ? raiz.dataset.theme === "dark"
    : matchMedia("(prefers-color-scheme: dark)").matches;
  raiz.dataset.theme = oscuro ? "light" : "dark";
  try { localStorage.setItem("qt-tema", raiz.dataset.theme); } catch { /* sin almacenamiento: el tema dura la sesión */ }
}

document.getElementById("cambiar-tema").addEventListener("click", alternarTema);
window.addEventListener("hashchange", navegar);
navegar();
revisarConexion();
setInterval(revisarConexion, 60_000);
