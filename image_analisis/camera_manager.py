# camera_manager.py - Gestión de cámara y captura
import threading
import time
import subprocess
import sys
import json
import re
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from .utils import _cv2_safe, _cv2_or_raise, load_config, save_config

# Estado global de captura
_lock = threading.Lock()
_cap = None              # type: Optional[object]  # cv2.VideoCapture
_cam_id: Optional[int] = None
_last_jpeg: Optional[bytes] = None
_running = False

# Variables para resolución dual
_high_res_capture = None  # Captura de alta resolución para snapshoot
_dual_resolution_mode = True  # Activar modo resolución dual (detección baja, snapshoot alta)
_detection_resolution = (640, 480)  # Resolución para detección (baja) - solo para procesamiento
_snapshot_resolution = (1280, 720)  # Resolución para snapshoot (alta) - solo para procesamiento
_original_resolution = None  # Resolución original de la cámara (para mantener FOV)

# Sistema de filtros
_current_filter = "original"
_filter_params = {
    "original": {},
    "detection": {"learning_rate": 0.01, "threshold": 25, "smoothing_filter": "default"},
    "object_detection": {"learning_rate": 0.01, "threshold": 25, "smoothing_filter": "default"},
    "area_detection": {"smoothing_filter": "default"},
    "junta_detection": {"modelo": "TC-124-15", "smoothing_filter": "default"},
    "background_training": {"frames": 30},
    "debug_stages": {"modelo": "TC-124-15"}
}

def _reader_loop():
    """Lee frames de la cámara y guarda el último JPEG en memoria."""
    global _cap, _last_jpeg, _running
    cv2 = _cv2_safe()
    if cv2 is None:
        print("[cam] No se puede iniciar reader_loop: OpenCV no disponible.")
        return
    while _running:
        ok, frame = (_cap.read() if _cap is not None else (False, None))
        if not ok:
            time.sleep(0.05)
            continue
        try:
            # Aplicar filtro activo
            filtered_frame = _apply_filter(frame, _current_filter, _filter_params[_current_filter])
            
            # Convertir a JPEG con mayor calidad
            ok, buf = cv2.imencode(".jpg", filtered_frame, [int(cv2.IMWRITE_JPEG_QUALITY), 95])
            if ok:
                with _lock:
                    _last_jpeg = buf.tobytes()
        except Exception as e:
            print(f"[cam] imencode error: {e}")
        time.sleep(0.03)  # ~30 fps

def _apply_filter(frame, filter_name: str, params: Dict):
    """Aplica un filtro a un frame usando OpenCV."""
    cv2 = _cv2_safe()
    if cv2 is None or frame is None:
        return frame
    
    try:
        # Solo aplicar mejora de calidad si NO estamos dibujando el polígono
        # para preservar la nitidez de las líneas
        from .detection import _is_drawing_area
        if not _is_drawing_area:
            frame = _enhance_image_quality(frame)
        
        if filter_name == "original":
            return frame
        elif filter_name == "detection":
            # NO aplicar filtros aquí - _apply_detection maneja su propio pipeline
            from .detection import _apply_detection
            return _apply_detection(frame, params)
        elif filter_name == "object_detection":
            from .detection import _apply_detection
            return _apply_detection(frame, params)
        elif filter_name == "area_detection":
            from .detection import _apply_detection
            return _apply_detection(frame, params)
        elif filter_name == "junta_detection":
            return _apply_junta_detection(frame, params)
        elif filter_name == "background_training":
            return _apply_background_training(frame, params)
        elif filter_name == "debug_stages":
            return _apply_debug_stages(frame, params)
        else:
            return frame
    except Exception as e:
        print(f"[filter] Error aplicando filtro {filter_name}: {e}")
        return frame

def _enhance_image_quality(frame):
    """Aplica mejoras de calidad a la imagen."""
    cv2 = _cv2_safe()
    if cv2 is None:
        return frame
    
    try:
        # Aplicar un ligero ajuste de contraste y brillo
        # Convertir a LAB para ajustar solo la luminancia
        lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
        
        # Aplicar CLAHE (Contrast Limited Adaptive Histogram Equalization)
        clahe = cv2.createCLAHE(clipLimit=1.5, tileGridSize=(8,8))
        lab[:,:,0] = clahe.apply(lab[:,:,0])
        
        # Convertir de vuelta a BGR
        enhanced = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
        
        return enhanced
        
    except Exception as e:
        print(f"[enhance] Error mejorando calidad: {e}")
        return frame

def _stop_capture():
    """Detiene la captura si está activa."""
    global _cap, _running
    _running = False
    time.sleep(0.1)
    if _cap is not None:
        try:
            _cap.release()
        except Exception:
            pass
        _cap = None

def stop_webcam():
    """Detiene la webcam y su thread de forma ordenada."""
    global _cap, _running, _last_jpeg
    
    print("[webcam] Deteniendo webcam...")
    
    # Detener el thread de lectura
    _running = False
    
    # Esperar un poco para que el thread termine
    time.sleep(0.2)
    
    # Cerrar la captura
    if _cap is not None:
        try:
            _cap.release()
        except Exception as e:
            print(f"[webcam] Error cerrando captura: {e}")
        _cap = None
    
    # Limpiar el último JPEG
    with _lock:
        _last_jpeg = None
    
    print("[webcam] Webcam detenida correctamente")

def get_jpeg() -> Optional[bytes]:
    """Devuelve el último JPEG disponible."""
    with _lock:
        return _last_jpeg

def change_camera_resolution(width: int, height: int) -> bool:
    """Cambia la resolución de la cámara dinámicamente."""
    global _cap
    cv2 = _cv2_safe()
    if cv2 is None or _cap is None:
        return False
    
    try:
        # Detener temporalmente la captura
        _cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        _cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        
        # Verificar que el cambio fue exitoso
        actual_width = int(_cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_height = int(_cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        # Tolerancia de ±8 píxeles
        if abs(actual_width - width) <= 8 and abs(actual_height - height) <= 8:
            print(f"[camera] Resolución cambiada a {actual_width}x{actual_height}")
            return True
        else:
            print(f"[camera] Error: resolución solicitada {width}x{height}, obtenida {actual_width}x{actual_height}")
            return False
            
    except Exception as e:
        print(f"[camera] Error cambiando resolución: {e}")
        return False

def capture_high_res_snapshot() -> Optional[bytes]:
    """Captura un frame de alta resolución para snapshoot."""
    global _cap, _high_res_capture, _original_resolution
    cv2 = _cv2_safe()
    if cv2 is None or _cap is None:
        return None
    
    try:
        # Usar el frame actual de alta resolución (sin cambiar la resolución de la cámara)
        ok, frame = _cap.read()
        if ok:
            # Si la resolución original es menor que la deseada, redimensionar
            global _snapshot_resolution
            if _original_resolution and (_original_resolution[0] < _snapshot_resolution[0] or _original_resolution[1] < _snapshot_resolution[1]):
                # Redimensionar a la resolución deseada
                frame = cv2.resize(frame, (_snapshot_resolution[0], _snapshot_resolution[1]))
                print(f"[snapshot] Frame redimensionado para snapshoot: {_original_resolution} -> {_snapshot_resolution}")
            
            # Convertir a JPEG de alta calidad
            ok, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 95])
            if ok:
                high_res_jpeg = buf.tobytes()
                print(f"[snapshot] Captura de alta resolución exitosa: {len(high_res_jpeg)} bytes")
                return high_res_jpeg
        
        return None
        
    except Exception as e:
        print(f"[snapshot] Error en captura de alta resolución: {e}")
        return None

def _apply_junta_detection(frame, params):
    """Aplica detección de juntas."""
    try:
        import junta_detector as jd
        
        modelo = params.get("modelo", "TC-124-15")
        result = jd.detect_junta(frame, modelo)
        
        # Crear overlay con resultado
        overlay = frame.copy()
        
        if result["ok"]:
            # Dibujar rectángulo de detección
            location = result["location"]
            template_size = result["pose"]["bbox"][2:]
            x, y = location
            w, h = template_size
            
            cv2 = _cv2_safe()
            if cv2 is not None:
                cv2.rectangle(overlay, (x, y), (x + w, y + h), (0, 255, 0), 2)
                cv2.putText(overlay, f"JUNTA DETECTADA", (x, y - 10), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                cv2.putText(overlay, f"Score: {result['similarity_score']:.3f}", 
                           (x, y + h + 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
        else:
            # Mostrar error
            cv2 = _cv2_safe()
            if cv2 is not None:
                cv2.putText(overlay, f"ERROR: {result['message']}", (10, 30), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
        
        return overlay
        
    except Exception as e:
        print(f"[junta_detection] Error: {e}")
        return frame

def _apply_background_training(frame, params):
    """Aplica entrenamiento de fondo."""
    try:
        import junta_detector as jd
        
        # Capturar frames para entrenamiento
        frames_needed = params.get("frames", 30)
        
        # Por ahora, usamos el frame actual (en el futuro, capturaremos múltiples)
        result = jd.train_background([frame])
        
        # Crear overlay con resultado
        overlay = frame.copy()
        
        cv2 = _cv2_safe()
        if cv2 is not None:
            if result["ok"]:
                cv2.putText(overlay, "CALIBRANDO...", (10, 30), 
                           cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
                cv2.putText(overlay, result["message"], (10, 60), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
            else:
                cv2.putText(overlay, f"ERROR: {result['message']}", (10, 30), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
        
        return overlay
        
    except Exception as e:
        print(f"[background_training] Error: {e}")
        return frame

def _apply_debug_stages(frame, params):
    """Aplica debug de etapas de procesamiento."""
    try:
        import junta_detector as jd
        
        modelo = params.get("modelo", "TC-124-15")
        result = jd.get_debug_stages(frame, modelo)
        
        if result["ok"]:
            # Por ahora, mostramos la etapa de preprocesamiento
            # En el futuro, esto se integrará con el sistema de filtros
            stages = result["stages"]
            if "preprocessed" in stages:
                # Convertir bytes a imagen
                import numpy as np
                arr = np.frombuffer(stages["preprocessed"], dtype=np.uint8)
                cv2 = _cv2_safe()
                if cv2 is not None:
                    debug_img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
                    if debug_img is not None:
                        return debug_img
        
        return frame
        
    except Exception as e:
        print(f"[debug_stages] Error: {e}")
        return frame

def _windows_cam_infos() -> List[Dict]:
    """
    Devuelve [{name, pnp, vid, pid}] usando PowerShell.
    name: Nombre amigable
    pnp:  PNPDeviceID completo
    vid/pid: si se encuentran dentro del PNPDeviceID
    """
    try:
        ps = (
            r"(Get-CimInstance Win32_PnPEntity | Where-Object {$_.PNPClass -eq 'Camera'})"
            r" | Select-Object Name,PNPDeviceID | ConvertTo-Json"
        )
        out = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                             capture_output=True, text=True, timeout=5)
        data = json.loads(out.stdout) if out.stdout.strip() else []
        if isinstance(data, dict):
            data = [data]
        infos = []
        for d in data:
            name = (d.get("Name") or "").strip()
            pnp = (d.get("PNPDeviceID") or "").strip()
            vid = pid = None
            if "VID_" in pnp and "PID_" in pnp:
                mvid = re.search(r"VID_([0-9A-Fa-f]{4})", pnp)
                mpid = re.search(r"PID_([0-9A-Fa-f]{4})", pnp)
                vid = mvid.group(1) if mvid else None
                pid = mpid.group(1) if mpid else None
            infos.append({"name": name, "pnp": pnp, "vid": vid, "pid": pid})
        return infos
    except Exception as e:
        print(f"[scan] PowerShell error: {e}")
        return []

def _backend_order() -> List[Optional[int]]:
    """Orden de backends a probar según SO."""
    cv2 = _cv2_safe()
    if sys.platform.startswith("win"):
        # Usa getattr por si el backend no existe en esta versión
        dshow = getattr(cv2, "CAP_DSHOW", 700) if cv2 else 700
        msmf  = getattr(cv2, "CAP_MSMF", 1400) if cv2 else 1400
        return [dshow, msmf]
    return [None]  # backend por defecto en otros SO

def _try_open(index: int, backend: Optional[int]) -> bool:
    """Intenta abrir un índice con un backend y lo cierra."""
    cv2 = _cv2_safe()
    if cv2 is None:
        return False
    try:
        cap = cv2.VideoCapture(index, backend) if backend else cv2.VideoCapture(index)
        ok = cap.isOpened()
        cap.release()
        return ok
    except Exception:
        return False

def scanWebCams(max_index: int = 20) -> List[Dict]:
    """
    Escanea índices 0..max_index-1 con distintos backends.
    Devuelve lista de dispositivos abribles: [{id, name, uid}]
    - uid: estable preferentemente basado en VID/PID (Windows). Fallback: name#n
    """
    print("🔎 Escaneando webcams con OpenCV…")
    cv2 = _cv2_safe()
    if cv2 is None:
        print("[scan] OpenCV no disponible; devolviendo lista vacía.")
        # Igual damos info de Windows para diagnóstico
        win_infos = _windows_cam_infos() if sys.platform.startswith("win") else []
        if win_infos:
            print(f"[scan] Windows ve cámaras: {[w['name'] for w in win_infos]}")
        return []

    openable: List[int] = []
    for i in range(max_index):
        if any(_try_open(i, be) for be in _backend_order()):
            openable.append(i)

    win_infos = _windows_cam_infos() if sys.platform.startswith("win") else []
    name_counts: Dict[str, int] = {}
    devices: List[Dict] = []

    for idx, cam_id in enumerate(openable):
        name = f"Webcam {cam_id}"
        uid = None
        if idx < len(win_infos):
            name = win_infos[idx]["name"] or name
            pnp = (win_infos[idx].get("pnp") or "").strip()
            vid = win_infos[idx].get("vid")
            pid = win_infos[idx].get("pid")
            if vid and pid:
                uid = f"VID_{vid}&PID_{pid}"
            elif pnp:
                uid = pnp  # menos ideal, pero estable

        # fallback si no hay uid estable
        n = name_counts.get(name, 0) + 1
        name_counts[name] = n
        if not uid:
            uid = f"{name}#{n}"

        devices.append({"id": cam_id, "name": name, "uid": uid})
        print(f"🎥 id={cam_id}  name={name}  uid={uid}")

    if sys.platform.startswith("win") and win_infos and len(devices) < len(win_infos):
        print(f"⚠️ Windows reporta {len(win_infos)} cámara(s), OpenCV abre {len(devices)}.")
    if not devices:
        print("⚠️ No se detectaron cámaras abribles.")
    return devices

# Resoluciones soportadas (rápido + caché)
_PRIORITY_RES: List[Tuple[int, int]] = [
    (1280, 720), (1920, 1080), (640, 480), (640, 360),
    (800, 600), (320, 240), (960, 540), (1024, 576),
]

def _cfg_get_caps() -> Dict[str, List[List[int]]]:
    cfg = load_config()
    return cfg.get("camera_caps", {}) if isinstance(cfg, dict) else {}

def _cfg_set_caps(uid: str, res_list: List[Tuple[int, int]]) -> None:
    cfg = load_config()
    caps = cfg.get("camera_caps") or {}
    caps[uid] = [[int(w), int(h)] for (w, h) in res_list]
    cfg["camera_caps"] = caps
    save_config(cfg)

def _safe_test_set(index: int, be: Optional[int], w: int, h: int) -> bool:
    """Abre, setea WxH, verifica, cierra. Siempre protegido."""
    cv2 = _cv2_safe()
    if cv2 is None:
        return False
    try:
        cap = cv2.VideoCapture(index, be) if be else cv2.VideoCapture(index)
        if not cap.isOpened():
            return False
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, w)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, h)
        rw = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        rh = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
        cap.release()
        return abs(rw - w) <= 8 and abs(rh - h) <= 8
    except Exception:
        return False

def _index_in_use(index: int) -> bool:
    """True si ese índice está siendo usado por el stream actual."""
    return (_cam_id == index and _running)

def get_supported_resolutions(uid: str, max_index: int = 20) -> List[Tuple[int, int]]:
    """
    Devuelve resoluciones soportadas para la cámara UID:
    - Usa caché en config.json (camera_caps[uid])
    - Si la cámara está en uso, no la toca: devuelve caché o lista prioritaria
    - Sonda rápida (pocas resoluciones) + guarda caché
    """
    try:
        # 1) Caché
        caps = _cfg_get_caps()
        if uid in caps and isinstance(caps[uid], list) and caps[uid]:
            try:
                return [(int(w), int(h)) for (w, h) in caps[uid]]
            except Exception:
                pass

        # 2) Mapear uid -> índice
        index = map_uid_to_index(uid, max_index=max_index)
        if index is None:
            return []

        # 3) Si está en uso (stream) no tocar el dispositivo
        if _index_in_use(index):
            return _PRIORITY_RES[:]

        # 4) Sonda rápida por backend
        ok_list: List[Tuple[int, int]] = []
        seen = set()
        for be in _backend_order():
            for (w, h) in _PRIORITY_RES:
                if (w, h) in seen:
                    continue
                if _safe_test_set(index, be, w, h):
                    ok_list.append((w, h))
                    seen.add((w, h))
            if len(ok_list) >= 5:
                break

        # 5) Guardar caché
        if ok_list:
            _cfg_set_caps(uid, ok_list)

        return ok_list
    except Exception as e:
        print(f"[res] Error listando resoluciones: {e}")
        # fallback seguro para no romper el server
        return [(640, 480), (1280, 720)]

def connectWebCam(cam_id: int,
                  width: Optional[int] = None,
                  height: Optional[int] = None) -> bool:
    """
    Conecta a una cámara por índice. Intenta backends en orden.
    Si width/height vienen, trata de aplicarlos.
    """
    global _cap, _cam_id, _running, _last_jpeg
    print(f"🔌 Conectando a la webcam id={cam_id}…")

    cv2 = _cv2_safe()
    if cv2 is None:
        print(f"❌ No se pudo abrir la cámara: OpenCV no disponible")
        return False

    _stop_capture()
    _last_jpeg = None

    cap = None
    for be in _backend_order():
        try:
            c = cv2.VideoCapture(cam_id, be) if be else cv2.VideoCapture(cam_id)
            if not c.isOpened():
                continue
            if width and height:
                c.set(cv2.CAP_PROP_FRAME_WIDTH, width)
                c.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
            ok, _ = c.read()
            if ok:
                cap = c
                break
            c.release()
        except Exception:
            continue

    if not cap:
        print("❌ No se pudo abrir la cámara.")
        return False

    _cap = cap
    _cam_id = cam_id
    _running = True
    
    # Guardar la resolución original de la cámara para mantener el FOV
    global _original_resolution
    _original_resolution = (
        int(_cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
        int(_cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    )
    print(f"[camera] Resolución original de la cámara: {_original_resolution[0]}x{_original_resolution[1]}")
    
    if _dual_resolution_mode:
        print(f"[camera] ✅ Modo resolución dual activado:")
        print(f"[camera]   - Detección: {_detection_resolution[0]}x{_detection_resolution[1]} (procesamiento)")
        print(f"[camera]   - Snapshoot: {_snapshot_resolution[0]}x{_snapshot_resolution[1]} (procesamiento)")
        print(f"[camera]   - Campo visual: {_original_resolution[0]}x{_original_resolution[1]} (mantenido)")
    
    threading.Thread(target=_reader_loop, daemon=True).start()
    print("✅ Webcam conectada.")
    return True

def map_uid_to_index(uid: str, max_index: int = 20) -> Optional[int]:
    """
    Busca el índice actual de la cámara a partir del UID (o por nombre si es name#n).
    """
    devs = scanWebCams(max_index=max_index)

    # Match exacto por uid
    for d in devs:
        if d["uid"] == uid:
            return d["id"]

    # Fallback: si uid tenía formato "name#n", matchear por name
    if "#" in uid:
        base = uid.split("#")[0]
        for d in devs:
            if d["name"] == base:
                return d["id"]

    # Último recurso: substring en name/uid
    for d in devs:
        if uid in d["name"] or uid in d["uid"]:
            return d["id"]

    return None

def connect_by_uid(uid: str,
                   width: Optional[int] = None,
                   height: Optional[int] = None) -> Tuple[bool, str]:
    """Conecta por UID estable y devuelve (ok, error_msg)."""
    try:
        idx = map_uid_to_index(uid)
        if idx is None:
            return False, "Cámara no encontrada (UID no mapeable)."
        ok = connectWebCam(idx, width, height)
        if not ok:
            return False, "No se pudo abrir la cámara seleccionada."
        return True, ""
    except RuntimeError as e:
        return False, str(e)
    except Exception as e:
        return False, f"Error al conectar: {e}"

def auto_connect_from_config() -> Tuple[bool, str]:
    """
    Lee config.json -> camera.uid y preferred_resolution.
    Intenta conectar automáticamente al iniciar el sistema.
    """
    cfg = load_config()
    cam_cfg = cfg.get("camera") or {}
    uid = cam_cfg.get("uid")
    if not uid:
        return False, "No hay cámara configurada."

    w = cam_cfg.get("preferred_resolution", {}).get("width")
    h = cam_cfg.get("preferred_resolution", {}).get("height")
    
    # Si no hay resolución configurada, intentar usar la más alta disponible
    if not w or not h:
        resolutions = get_supported_resolutions(uid)
        if resolutions:
            # Usar la resolución más alta disponible
            w, h = max(resolutions, key=lambda x: x[0] * x[1])
            print(f"[auto_connect] Usando resolución automática: {w}x{h}")
    
    ok, err = connect_by_uid(uid, w, h)
    return ok, err

def snapshot(save_path: Optional[str] = None, timeout_s: float = 2.5) -> Tuple[bool, Optional[str], str]:
    """
    Toma una foto del stream actual y opcionalmente la guarda.
    Returns: (success, file_path, error_message)
    """
    global _last_jpeg
    
    if _last_jpeg is None:
        return False, None, "No hay frame disponible"
    
    try:
        if save_path:
            # Guardar en archivo
            with open(save_path, 'wb') as f:
                f.write(_last_jpeg)
            return True, save_path, ""
        else:
            # Solo retornar el JPEG en memoria
            return True, None, ""
            
    except Exception as e:
        return False, None, f"Error guardando snapshot: {e}"

def set_filter(filter_name: str, params: Optional[Dict] = None):
    """Establece el filtro activo y sus parámetros."""
    global _current_filter, _filter_params
    if filter_name in _filter_params:
        _current_filter = filter_name
        if params:
            _filter_params[filter_name].update(params)
        print(f"[filter] Filtro cambiado a: {filter_name}")
        return True
    return False

def get_current_filter() -> Dict:
    """Obtiene el filtro activo y sus parámetros."""
    return {
        "name": _current_filter,
        "params": _filter_params[_current_filter].copy()
    }

def get_available_filters() -> List[Dict]:
    """Obtiene la lista de filtros disponibles con sus parámetros por defecto."""
    return [
        {"name": "original", "display_name": "Original", "params": {}},
        {"name": "detection", "display_name": "Detección", "params": {"learning_rate": 0.01, "threshold": 25, "smoothing_filter": "default"}},
        {"name": "object_detection", "display_name": "Detección de Objetos", "params": {"learning_rate": 0.01, "threshold": 25, "smoothing_filter": "default"}},
        {"name": "area_detection", "display_name": "Detección en Área", "params": {"smoothing_filter": "default"}},
        {"name": "junta_detection", "display_name": "Detección de Junta", "params": {"modelo": "TC-124-15", "smoothing_filter": "default"}},
        {"name": "background_training", "display_name": "Entrenar Fondo", "params": {"frames": 30}},
        {"name": "debug_stages", "display_name": "Debug Etapas", "params": {"modelo": "TC-124-15"}}
    ]
