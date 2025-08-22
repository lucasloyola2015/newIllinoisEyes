// Ajusta altura de iframes
const fit = () => {
  document.querySelectorAll(".pane-frame").forEach(f => {
    f.style.height = (window.innerHeight - 64) + "px";
  });
};
window.addEventListener("resize", fit);
window.addEventListener("load", fit);

// Navegación: derecho fijo (dashboard). Izquierdo cambia.
const leftFrame = document.getElementById("leftFrame");
const navButtons = document.querySelectorAll(".navbtn");
let currentPage = null;

const PAGE_MAP = {
  control: "/template/control.html",
  configuracion: "/template/configuracion.html",
  plc_logo: "/template/plc_logo.html",
  filter_config: "/template/filter_config.html",
  filter_specific_config: "/template/filter_specific_config.html",
};

function setLeftPane(page) {
  const target = PAGE_MAP[page] || PAGE_MAP.control;
  if (!leftFrame) return;

  // Solo cambiar la página si es diferente, pero permitir parámetros en la URL
  const currentIframePath = leftFrame.contentWindow.location.pathname;
  const needsNav = currentIframePath !== target;

  if (needsNav) {
    leftFrame.src = target;
  }

  currentPage = page;

  // Estado visual botones
  navButtons.forEach(btn => {
    const active = btn.dataset.page === page;
    btn.classList.toggle("active", active);
    // Para el botón único, siempre estará 'activo'
    btn.setAttribute("aria-current", "page");
  });

  // Mantener deep-link
  if (location.hash.replace("#","") !== page) {
    history.replaceState(null, "", "#" + page);
  }
}

// Eventos de los botones
navButtons.forEach(btn => btn.addEventListener("click", () => setLeftPane(btn.dataset.page)));

// Inicialización según hash
window.addEventListener("load", () => {
  const page = (location.hash || "#control").slice(1);
  setLeftPane(page);
});
window.addEventListener("hashchange", () => {
  const page = (location.hash || "#control").slice(1);
  setLeftPane(page);
});

// Captura de errores menor
window.addEventListener("error", (e) => console.warn("Error:", e.message));