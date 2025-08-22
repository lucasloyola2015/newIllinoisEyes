# junta_detector.py
import threading
import time
import json
import numpy as np
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List
from datetime import datetime

# Import perezoso de OpenCV
_cv2_mod = None
_cv2_err: Optional[str] = None

def _cv2_safe():
    """Import perezoso de OpenCV."""
    global _cv2_mod, _cv2_err
    if _cv2_mod is not None:
        return _cv2_mod
    try:
        import cv2
        _cv2_mod = cv2
        _cv2_err = None
        return _cv2_mod
    except Exception as e:
        _cv2_err = f"OpenCV no disponible: {e}"
        print(f"[junta_detector] {_cv2_err}")
        return None

# ============================================================
# Estado global del sistema
# ============================================================
_lock = threading.Lock()
_background_model = None
_background_mean = None
_background_std = None
_polygon_changed = False
_current_model = None
_model_template = None
_model_contours = None
_model_hu_moments = None

# ============================================================
# Configuración
# ============================================================
ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "config.json"
IMG_DB_DIR = ROOT / "imgDatabase"
IMG_FAILS_DIR = ROOT / "imgFails"
FAILURES_DB_PATH = ROOT / "failures.json"

# Crear directorio de fallos si no existe
IMG_FAILS_DIR.mkdir(exist_ok=True)

def load_config() -> Dict:
    """Carga configuración desde config.json."""
    if CONFIG_PATH.exists():
        try:
            return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}

def save_config(cfg: Dict) -> None:
    """Guarda configuración en config.json."""
    try:
        CONFIG_PATH.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception as e:
        print(f"[junta_detector] Error guardando config.json: {e}")

def get_vision_config() -> Dict:
    """Obtiene configuración específica de visión."""
    cfg = load_config()
    vision_cfg = cfg.get("vision", {})
    
    # Valores por defecto
    defaults = {
        "similarity_threshold": 0.97,
        "training_frames": 30,
        "gaussian_kernel_size": 5,
        "median_kernel_size": 3,
        "anomaly_threshold": 0.10,
        "polygon_changed": False,
        "background_variance_threshold": 0.20,
        "min_contrast": 30,
        "max_object_area_percent": 0.05
    }
    
    # Combinar configuración existente con defaults
    for key, default_value in defaults.items():
        if key not in vision_cfg:
            vision_cfg[key] = default_value
    
    return vision_cfg

def save_vision_config(vision_cfg: Dict) -> None:
    """Guarda configuración específica de visión."""
    cfg = load_config()
    cfg["vision"] = vision_cfg
    save_config(cfg)

# ============================================================
# Sistema de logging de fallos
# ============================================================
def log_failure(reason: str, similarity_score: float = 0.0, model_searched: str = "") -> None:
    """Registra un fallo en la base de datos."""
    try:
        # Cargar base de datos existente
        failures = []
        if FAILURES_DB_PATH.exists():
            try:
                failures = json.loads(FAILURES_DB_PATH.read_text(encoding="utf-8"))
            except Exception:
                failures = []
        
        # Crear entrada de fallo
        timestamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        image_filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        
        failure_entry = {
            "timestamp": timestamp,
            "image_filename": image_filename,
            "failure_reason": reason,
            "similarity_score": similarity_score,
            "model_searched": model_searched
        }
        
        failures.append(failure_entry)
        
        # Guardar base de datos
        FAILURES_DB_PATH.write_text(json.dumps(failures, indent=2, ensure_ascii=False), encoding="utf-8")
        
        print(f"[junta_detector] Fallo registrado: {reason} (score: {similarity_score:.3f})")
        
    except Exception as e:
        print(f"[junta_detector] Error registrando fallo: {e}")

def save_failure_image(image: np.ndarray, filename: str) -> bool:
    """Guarda imagen de fallo."""
    try:
        cv2 = _cv2_safe()
        if cv2 is None:
            return False
        
        image_path = IMG_FAILS_DIR / filename
        return cv2.imwrite(str(image_path), image)
    except Exception as e:
        print(f"[junta_detector] Error guardando imagen de fallo: {e}")
        return False

# ============================================================
# Sistema de entrenamiento de fondo
# ============================================================
def train_background(frames: List[np.ndarray]) -> Dict[str, Any]:
    """Entrena modelo de fondo con frames capturados."""
    global _background_model, _background_mean, _background_std
    
    cv2 = _cv2_safe()
    if cv2 is None:
        return {"ok": False, "message": "OpenCV no disponible"}
    
    try:
        if not frames:
            return {"ok": False, "message": "No hay frames para entrenar"}
        
        # Convertir a escala de grises
        gray_frames = []
        for frame in frames:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            gray_frames.append(gray)
        
        # Apilar frames
        stacked = np.stack(gray_frames, axis=0)
        
        # Calcular estadísticas
        _background_mean = np.mean(stacked, axis=0).astype(np.float32)
        _background_std = np.std(stacked, axis=0).astype(np.float32)
        
        # Validar calidad del entrenamiento
        validation = validate_background_quality(_background_mean, _background_std)
        
        if not validation["ok"]:
            return validation
        
        _background_model = {
            "mean": _background_mean,
            "std": _background_std,
            "frames_used": len(frames),
            "timestamp": time.time()
        }
        
        # Marcar que el polígono no ha cambiado
        vision_cfg = get_vision_config()
        vision_cfg["polygon_changed"] = False
        save_vision_config(vision_cfg)
        
        return {
            "ok": True,
            "message": f"Fondo entrenado con {len(frames)} frames",
            "validation": validation
        }
        
    except Exception as e:
        return {"ok": False, "message": f"Error entrenando fondo: {e}"}

def validate_background_quality(mean: np.ndarray, std: np.ndarray) -> Dict[str, Any]:
    """Valida la calidad del modelo de fondo entrenado."""
    vision_cfg = get_vision_config()
    
    try:
        # Calcular varianza promedio
        variance = np.mean(std ** 2)
        variance_percent = variance / 255.0
        
        # Calcular contraste
        contrast = np.max(mean) - np.min(mean)
        
        # Verificar umbrales
        variance_ok = variance_percent < vision_cfg["background_variance_threshold"]
        contrast_ok = contrast > vision_cfg["min_contrast"]
        
        return {
            "ok": variance_ok and contrast_ok,
            "variance_percent": variance_percent,
            "contrast": contrast,
            "variance_ok": variance_ok,
            "contrast_ok": contrast_ok,
            "message": f"Varianza: {variance_percent:.3f}, Contraste: {contrast:.1f}"
        }
        
    except Exception as e:
        return {"ok": False, "message": f"Error validando fondo: {e}"}

# ============================================================
# Sistema de detección de anomalías
# ============================================================
def check_anomalies(current_frame: np.ndarray) -> Dict[str, Any]:
    """Detecta anomalías respecto al fondo entrenado."""
    global _background_mean, _background_std
    
    cv2 = _cv2_safe()
    if cv2 is None:
        return {"ok": False, "message": "OpenCV no disponible"}
    
    if _background_mean is None or _background_std is None:
        return {"ok": False, "message": "Fondo no entrenado"}
    
    try:
        # Convertir a escala de grises
        gray = cv2.cvtColor(current_frame, cv2.COLOR_BGR2GRAY)
        
        # Calcular diferencia
        diff = np.abs(gray.astype(np.float32) - _background_mean)
        
        # Normalizar por desviación estándar
        normalized_diff = diff / (_background_std + 1e-6)
        
        # Calcular porcentaje de píxeles anómalos
        anomaly_mask = normalized_diff > 2.0  # 2 desviaciones estándar
        anomaly_percent = np.mean(anomaly_mask)
        
        vision_cfg = get_vision_config()
        threshold = vision_cfg["anomaly_threshold"]
        
        return {
            "ok": True,
            "anomaly_percent": anomaly_percent,
            "has_anomaly": anomaly_percent > threshold,
            "threshold": threshold,
            "message": f"Anomalía: {anomaly_percent:.3f} ({'SÍ' if anomaly_percent > threshold else 'NO'})"
        }
        
    except Exception as e:
        return {"ok": False, "message": f"Error detectando anomalías: {e}"}

# ============================================================
# Sistema de precarga de modelos
# ============================================================
def preload_model(modelo: str) -> Dict[str, Any]:
    """Precarga un modelo de junta para detección."""
    global _current_model, _model_template, _model_contours, _model_hu_moments
    
    cv2 = _cv2_safe()
    if cv2 is None:
        return {"ok": False, "message": "OpenCV no disponible"}
    
    try:
        # Verificar que el modelo existe
        template_path = IMG_DB_DIR / f"{modelo}.png"
        if not template_path.exists():
            return {"ok": False, "message": f"Modelo no encontrado: {modelo}"}
        
        # Cargar imagen del modelo
        template = cv2.imread(str(template_path), cv2.IMREAD_GRAYSCALE)
        if template is None:
            return {"ok": False, "message": f"No se pudo cargar modelo: {modelo}"}
        
        # Encontrar contornos
        _, binary = cv2.threshold(template, 127, 255, cv2.THRESH_BINARY)
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if not contours:
            return {"ok": False, "message": f"No se encontraron contornos en modelo: {modelo}"}
        
        # Calcular momentos de Hu
        main_contour = max(contours, key=cv2.contourArea)
        hu_moments = cv2.HuMoments(cv2.moments(main_contour)).flatten()
        
        # Guardar modelo precargado
        _current_model = modelo
        _model_template = template
        _model_contours = contours
        _model_hu_moments = hu_moments
        
        return {
            "ok": True,
            "message": f"Modelo precargado: {modelo}",
            "contour_count": len(contours),
            "template_size": template.shape
        }
        
    except Exception as e:
        return {"ok": False, "message": f"Error precargando modelo: {e}"}

# ============================================================
# Sistema de detección de juntas
# ============================================================
def detect_junta(frame: np.ndarray, modelo: str) -> Dict[str, Any]:
    """Detecta una junta específica en el frame."""
    global _current_model, _model_template, _model_contours, _model_hu_moments
    
    cv2 = _cv2_safe()
    if cv2 is None:
        return {"ok": False, "message": "OpenCV no disponible"}
    
    # Verificar que el modelo esté precargado
    if _current_model != modelo:
        preload_result = preload_model(modelo)
        if not preload_result["ok"]:
            return preload_result
    
    try:
        # Convertir a escala de grises
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # Aplicar filtros de preprocesamiento
        processed = apply_preprocessing_filters(gray)
        
        # Template matching
        match_result = template_matching(processed, _model_template)
        if not match_result["ok"]:
            return match_result
        
        # Validar contornos
        contour_result = validate_contours(processed, _model_contours, _model_hu_moments)
        if not contour_result["ok"]:
            return contour_result
        
        # Calcular pose
        pose_result = calculate_pose(match_result["location"], _model_template.shape)
        
        return {
            "ok": True,
            "message": "Junta detectada exitosamente",
            "similarity_score": match_result["similarity_score"],
            "location": match_result["location"],
            "pose": pose_result,
            "contour_validation": contour_result
        }
        
    except Exception as e:
        return {"ok": False, "message": f"Error detectando junta: {e}"}

def apply_preprocessing_filters(gray: np.ndarray) -> np.ndarray:
    """Aplica filtros de preprocesamiento."""
    cv2 = _cv2_safe()
    vision_cfg = get_vision_config()
    
    # Filtro Gaussiano bilateral
    kernel_size = vision_cfg["gaussian_kernel_size"]
    if kernel_size % 2 == 0:
        kernel_size += 1
    
    filtered = cv2.bilateralFilter(gray, kernel_size, 75, 75)
    
    # Filtro de mediana
    median_kernel = vision_cfg["median_kernel_size"]
    if median_kernel % 2 == 0:
        median_kernel += 1
    
    filtered = cv2.medianBlur(filtered, median_kernel)
    
    return filtered

def template_matching(processed: np.ndarray, template: np.ndarray) -> Dict[str, Any]:
    """Realiza template matching."""
    cv2 = _cv2_safe()
    vision_cfg = get_vision_config()
    
    # Template matching
    result = cv2.matchTemplate(processed, template, cv2.TM_CCOEFF_NORMED)
    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
    
    similarity_score = max_val
    threshold = vision_cfg["similarity_threshold"]
    
    if similarity_score < threshold:
        return {
            "ok": False,
            "message": f"Similitud insuficiente: {similarity_score:.3f} < {threshold}",
            "similarity_score": similarity_score
        }
    
    return {
        "ok": True,
        "similarity_score": similarity_score,
        "location": max_loc,
        "template_size": template.shape
    }

def validate_contours(processed: np.ndarray, model_contours: List, model_hu_moments: np.ndarray) -> Dict[str, Any]:
    """Valida contornos usando momentos de Hu."""
    cv2 = _cv2_safe()
    
    # Encontrar contornos en imagen procesada
    _, binary = cv2.threshold(processed, 127, 255, cv2.THRESH_BINARY)
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    if not contours:
        return {"ok": False, "message": "No se encontraron contornos"}
    
    # Encontrar el contorno más similar
    best_score = 0
    best_contour = None
    
    for contour in contours:
        area = cv2.contourArea(contour)
        if area < 100:  # Filtrar contornos muy pequeños
            continue
        
        # Calcular momentos de Hu
        moments = cv2.moments(contour)
        hu_moments = cv2.HuMoments(moments).flatten()
        
        # Calcular similitud (distancia euclidiana en log space)
        log_hu = np.log(np.abs(hu_moments) + 1e-10)
        log_model_hu = np.log(np.abs(model_hu_moments) + 1e-10)
        
        distance = np.linalg.norm(log_hu - log_model_hu)
        similarity = 1.0 / (1.0 + distance)
        
        if similarity > best_score:
            best_score = similarity
            best_contour = contour
    
    if best_contour is None:
        return {"ok": False, "message": "No se encontró contorno válido"}
    
    return {
        "ok": True,
        "contour_similarity": best_score,
        "contour_area": cv2.contourArea(best_contour),
        "contour_center": tuple(map(int, cv2.minEnclosingCircle(best_contour)[0]))
    }

def calculate_pose(location: Tuple[int, int], template_size: Tuple[int, int]) -> Dict[str, Any]:
    """Calcula la pose de la junta detectada."""
    # Por ahora, calculamos posición relativa
    # En el futuro, esto se integrará con la calibración ArUco
    
    x, y = location
    width, height = template_size
    
    center_x = x + width // 2
    center_y = y + height // 2
    
    return {
        "center": (center_x, center_y),
        "bbox": (x, y, width, height),
        "rotation": 0.0,  # TODO: calcular rotación real
        "translation": (center_x, center_y)  # TODO: convertir a mm usando calibración
    }

# ============================================================
# Funciones de debug visual
# ============================================================
def get_debug_stages(frame: np.ndarray, modelo: str) -> Dict[str, Any]:
    """Obtiene imágenes de debug para cada etapa del procesamiento."""
    cv2 = _cv2_safe()
    if cv2 is None:
        return {"ok": False, "message": "OpenCV no disponible"}
    
    try:
        # Convertir a escala de grises
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # Etapa 1: Preprocesamiento
        processed = apply_preprocessing_filters(gray)
        
        # Etapa 2: Template matching (si hay modelo)
        match_overlay = frame.copy()
        if _current_model == modelo and _model_template is not None:
            result = cv2.matchTemplate(processed, _model_template, cv2.TM_CCOEFF_NORMED)
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
            
            # Dibujar rectángulo de match
            h, w = _model_template.shape
            cv2.rectangle(match_overlay, max_loc, (max_loc[0] + w, max_loc[1] + h), (0, 255, 0), 2)
            cv2.putText(match_overlay, f"Score: {max_val:.3f}", 
                       (max_loc[0], max_loc[1] - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        
        # Etapa 3: Contornos
        contour_overlay = frame.copy()
        _, binary = cv2.threshold(processed, 127, 255, cv2.THRESH_BINARY)
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        for contour in contours:
            area = cv2.contourArea(contour)
            if area > 100:
                cv2.drawContours(contour_overlay, [contour], -1, (0, 0, 255), 2)
        
        # Convertir a JPEG para web
        def to_jpeg(img):
            ok, buf = cv2.imencode(".jpg", img, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
            return buf.tobytes() if ok else None
        
        return {
            "ok": True,
            "stages": {
                "original": to_jpeg(frame),
                "grayscale": to_jpeg(gray),
                "preprocessed": to_jpeg(processed),
                "template_matching": to_jpeg(match_overlay),
                "contours": to_jpeg(contour_overlay)
            }
        }
        
    except Exception as e:
        return {"ok": False, "message": f"Error generando debug: {e}"}

# ============================================================
# Funciones de gestión del polígono
# ============================================================
def set_polygon_changed():
    """Marca que el polígono ha cambiado."""
    global _polygon_changed
    _polygon_changed = True
    
    vision_cfg = get_vision_config()
    vision_cfg["polygon_changed"] = True
    save_vision_config(vision_cfg)
    
    print("[junta_detector] Polígono marcado como cambiado")

def check_polygon_changed() -> bool:
    """Verifica si el polígono ha cambiado."""
    vision_cfg = get_vision_config()
    return vision_cfg.get("polygon_changed", False)

def get_status() -> Dict[str, Any]:
    """Obtiene el estado actual del sistema."""
    return {
        "background_trained": _background_model is not None,
        "current_model": _current_model,
        "polygon_changed": check_polygon_changed(),
        "config": get_vision_config()
    }
