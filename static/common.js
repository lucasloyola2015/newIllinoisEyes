// /static/common.js - Funciones comunes unificadas
(function(){
  // Placeholder image helper
  function setPlaceholder(img){
    if(!img) return;
    img.onerror = null;
    img.src = 'data:image/svg+xml;utf8,' + encodeURIComponent(
      `<svg xmlns="http://www.w3.org/2000/svg" width="800" height="400">
         <rect width="100%" height="100%" fill="#0c0c0d"/>
         <rect x="1" y="1" width="798" height="398" fill="none" stroke="#242428"/>
         <text x="50%" y="50%" dominant-baseline="middle" text-anchor="middle"
               font-family="Segoe UI, Roboto, Arial" font-size="16" fill="#bdbdc4">
           Sin imagen
         </text>
       </svg>`
    );
  }

  // Fetch with timeout - configuraciones por defecto más altas para configWebCam
  async function fetchWithTimeout(url, opts={}, timeoutMs=15000){
    const ctrl = new AbortController();
    const id = setTimeout(()=>ctrl.abort(), timeoutMs);
    try{
      const res = await fetch(url, {...opts, signal: ctrl.signal});
      clearTimeout(id);
      return res;
    }catch(e){
      clearTimeout(id);
      throw e;
    }
  }

  // Status helpers para configuración
  function setStatusIndicator(elementId, isOn){
    const element = document.getElementById(elementId);
    if(element) {
      element.classList.toggle("on", !!isOn);
    }
  }

  // Camera helpers
  function showCamError(text){ 
    const el = document.getElementById("camStatus"); 
    if (el){ 
      el.textContent = text || "Error de cámara."; 
      el.style.display = "flex"; 
    } 
  }
  
  function hideCamError(){ 
    const el = document.getElementById("camStatus"); 
    if (el){ 
      el.textContent = ""; 
      el.style.display = "none"; 
    } 
  }

  // Terminal helpers
  async function logToTerminal(type, message) {
    try {
      await fetchWithTimeout('/api/terminal/log', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ type: type, message: message })
      });
    } catch (error) {
      console.error('Error enviando log al terminal:', error);
    }
  }

  async function clearTerminal() {
    try {
      const response = await fetchWithTimeout('/api/terminal/clear', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      });
      return await response.json();
    } catch (error) {
      console.error('Error limpiando terminal:', error);
      return { ok: false, error: error.message };
    }
  }

  async function getTerminalLogs(limit = 50, filter = null) {
    try {
      const params = new URLSearchParams();
      params.append('limit', limit.toString());
      if (filter) params.append('filter', filter);
      
      const response = await fetchWithTimeout(`/api/terminal/logs?${params}`);
      return await response.json();
    } catch (error) {
      console.error('Error obteniendo logs del terminal:', error);
      return { ok: false, error: error.message };
    }
  }

  // Auto connect camera (dashboard)
  async function autoConnectCamera(){
    try{
      const r = await fetchWithTimeout("/api/auto_connect");
      const j = await r.json();
      const img = document.getElementById("camStream");
      if (j.ok){ 
        if (img){ img.src = "/video_feed?t=" + Date.now(); } 
      } else { 
        showCamError(j.error || "No se pudo conectar automáticamente."); 
      }
    }catch(e){ 
      showCamError("No se pudo contactar el servidor de cámara."); 
    }
  }

  // Centralized drawOverlay (letterboxing aware, origin centroCilindros)
  function drawOverlay(img, canvas, j){
    if(!img || !canvas || !j) return;
    const ctx = canvas.getContext('2d');
    const W = canvas.clientWidth || img.clientWidth;
    const H = canvas.clientHeight || img.clientHeight;
    canvas.width = W; canvas.height = H;
    ctx.clearRect(0,0,W,H);

    const natW = img.naturalWidth || W, natH = img.naturalHeight || H;
    const s = Math.min(W / natW, H / natH);
    const scaledW = natW * s, scaledH = natH * s;
    const offX = (W - scaledW) / 2;
    const offY = (H - scaledH) / 2;

    const css = getComputedStyle(document.documentElement);
    const fontPx = parseInt(css.getPropertyValue('--overlay-font')||'12',10) || 12;
    const brand = (css.getPropertyValue('--brand-red') || '#d41414').trim();

    ctx.fillStyle = brand;
    ctx.strokeStyle = brand;
    ctx.font = `bold ${Math.round(fontPx * s)}px Segoe UI, Roboto, Arial`;
    ctx.textAlign = 'center'; ctx.textBaseline = 'middle';

    const cc = j.centroCilindros || {x: natW/2, y: natH/2};
    function T(pt){
      if(!pt) return null;
      const x = offX + (cc.x + (pt.x||0)) * s;
      const y = offY + (cc.y + (pt.y||0)) * s;
      const ang = ((pt.rotacion || 0) * Math.PI / 180);
      return {x, y, ang};
    }
    function drawLabel(text, obj){
      const p = T(obj);
      if(!p) return;
      ctx.save();
      ctx.translate(p.x, p.y);
      ctx.rotate(p.ang);
      ctx.fillText(text, 0, 0);
      ctx.restore();
    }

    drawLabel("LOTE",     j.Lote);
    drawLabel("ILLINOIS", j.Texto_Illinois);
    drawLabel("CODIGO",   j.Codigo);
    const m = j.Muescas || {};
    const n = Number(m.Cantidad || 0);
    if (n > 0) drawLabel('o'.repeat(Math.max(1, n)), m);
  }

  // Load modelo function for ordenTrabajo
  async function loadModelo(){
    const qs = new URLSearchParams(location.search);
    let modelo = (qs.get("modelo") || "").trim();
    if(!modelo){
      try{
        const r = await fetchWithTimeout("/api/config");
        const cfg = await r.json();
        modelo = cfg?.junta_actual?.modelo || "";
      }catch(e){}
    }
    
    const titleElement = document.getElementById("titleModelo");
    if(titleElement) titleElement.textContent = modelo || "—";
    
    const img = document.getElementById("preview");
    const overlay = document.getElementById("overlay");
    
    if(img) {
      img.onload = async ()=>{
        // buscar datos para overlay
        if(!modelo) return;
        try{
          const r = await fetchWithTimeout(`/api/db/get?modelo=${encodeURIComponent(modelo)}`);
          const j = await r.json();
          if(j.ok) drawOverlay(img, overlay, j.item);
        }catch(e){}
      };
      img.src = modelo ? `/imgDatabase/${encodeURIComponent(modelo)}.png?ts=${Date.now()}` : "";
    }
  }

  // Setup resize handler for overlay redraw
  function setupOverlayResize(modeloElementId = "titleModelo", imgElementId = "preview", overlayElementId = "overlay"){
    window.addEventListener("resize", ()=>{
      const titleElement = document.getElementById(modeloElementId);
      const img = document.getElementById(imgElementId);
      const overlay = document.getElementById(overlayElementId);
      
      if(!titleElement || !img || !overlay) return;
      
      const modelo = titleElement.textContent.trim();
      if(!modelo || modelo === "—" || !img.naturalWidth) return;
      
      fetchWithTimeout(`/api/db/get?modelo=${encodeURIComponent(modelo)}`)
        .then(r=>r.json())
        .then(j=>{
          if(j.ok) drawOverlay(img, overlay, j.item);
        })
        .catch(()=>{});
    });
  }

  // Setup live overlay updates for form inputs
  function setupLiveOverlay(inputIds, imgElementId = "preview", overlayElementId = "overlay", getFormFunction){
    if(!getFormFunction) return;
    
    const img = document.getElementById(imgElementId);
    const overlay = document.getElementById(overlayElementId);
    
    if(!img || !overlay) return;

    // Redibujar al cambiar valores (en vivo)
    window.addEventListener('resize', ()=> drawOverlay(img, overlay, getFormFunction()));
    
    document.addEventListener('input', (e)=>{
      if (!e.target || !e.target.id) return;
      if (inputIds.includes(e.target.id)) {
        drawOverlay(img, overlay, getFormFunction());
      }
    });
    
    // Redondeo a 1 decimal en change para campos numéricos
    document.addEventListener('change', (e)=>{
      if (!e.target || !e.target.id) return;
      if (inputIds.includes(e.target.id) && e.target.type === 'number') {
        const val = parseFloat(e.target.value);
        if (!isNaN(val)) {
          e.target.value = val.toFixed(1);
          drawOverlay(img, overlay, getFormFunction());
        }
      }
    });
  }

  // Message helper
  function setMessage(elementId, text, className = ""){
    const element = document.getElementById(elementId);
    if(element) {
      element.textContent = text || "";
      element.className = className || "";
    }
  }

  // Image loader with timestamp cache busting
  function loadImageForModel(name, imgElementId = "preview"){
    const img = document.getElementById(imgElementId);
    if(img) {
      img.src = `/imgDatabase/${encodeURIComponent(name||"")}.png?ts=${Date.now()}`;
    }
  }

  // Form helpers for number inputs
  function getNumericValue(elementId){
    const element = document.getElementById(elementId);
    if(!element) return null;
    const v = element.value;
    return v === "" ? null : Number(v);
  }

  function setNumericValue(elementId, value){
    const element = document.getElementById(elementId);
    if(element) {
      element.value = value ?? "";
    }
  }

  // expose all functions
  window.Common = { 
    setPlaceholder, 
    fetchWithTimeout, 
    drawOverlay, 
    loadModelo,
    setupOverlayResize,
    setupLiveOverlay,
    setMessage,
    loadImageForModel,
    getNumericValue,
    setNumericValue,
    setStatusIndicator,
    showCamError,
    hideCamError,
    autoConnectCamera,
    logToTerminal,
    clearTerminal,
    getTerminalLogs
  };
  
  // Compatibility - expose individual functions for backward compatibility
  window.setPlaceholder = setPlaceholder;
  window.fetchWithTimeout = fetchWithTimeout;
  window.drawOverlay = drawOverlay;
  window.loadModelo = loadModelo;
  window.showError = showCamError;
  window.hideError = hideCamError;
  window.autoConnect = autoConnectCamera;
})();