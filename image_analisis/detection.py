# detection.py - Detección de objetos y áreas
import json
import threading
from typing import List, Dict, Optional, Tuple
from .utils import _cv2_safe, _np_safe, _get_frame_dimensions, create_polygon_mask

# Variables para detección de objetos
_background_subtractor = None
_is_learning_background = False
_background_model_saved = False  # Indica si hay un modelo de fondo guardado
_detection_method = "MOG2"  # Método de detección por defecto
_background_suppression_enabled = True  # Estado de habilitación de la supresión de fondo
_detection_params = {
    "var_threshold": 25,
    "detect_shadows": False
}

# Variables para detección de movimiento en área específica
_area_mask = None
_area_points = []
_is_drawing_area = False
_area_detection_active = False

# Variables para snapshoot y procesamiento de objetos
_detected_objects = []  # Lista de objetos detectados en el último frame
_snapshot_mask = None   # Máscara del objeto más grande para snapshoot
_snapshot_image = None  # Imagen del objeto capturado para snapshoot
_snapshot_mode = False  # Modo para mostrar la imagen en lugar del video

# Variables para resolución dual
_high_res_capture = None  # Captura de alta resolución para snapshoot
_dual_resolution_mode = True  # Activar modo resolución dual (detección baja, snapshoot alta)
_detection_resolution = (640, 480)  # Resolución para detección (baja) - solo para procesamiento
_snapshot_resolution = (1280, 720)  # Resolución para snapshoot (alta) - solo para procesamiento
_original_resolution = None  # Resolución original de la cámara (para mantener FOV)

def unified_detection_pipeline(frame, params):
    """
    PIPELINE UNIFICADO Y LINEAL para detección de objetos.
    Esta función maneja TODO el flujo de procesamiento de forma secuencial.
    
    PASOS:
    1. Inicializar máscara de polígono (si no existe)
    2. Reducir resolución para detección
    3. Aplicar filtros en cascada
    4. Aplicar máscara de polígono (si habilitada)
    5. Aplicar supresión de fondo
    6. Encontrar y filtrar contornos
    7. Validar contornos contra polígono
    8. Dibujar resultados
    """
    global _area_mask, _area_points, _background_subtractor, _detected_objects
    
    cv2 = _cv2_safe()
    if cv2 is None:
        return frame
    
    import numpy as np
    
    try:
        # PASO 1: INICIALIZAR MÁSCARA DE POLÍGONO
        if len(_area_points) >= 3 and _area_mask is None:
            _area_mask = create_polygon_mask()
        
        # PASO 2: PREPARAR RESOLUCIÓN Y APLICAR FILTROS
        original_height, original_width = frame.shape[:2]
        
        if _dual_resolution_mode and _detection_resolution:
            detection_width, detection_height = _detection_resolution
            detection_frame = cv2.resize(frame, (detection_width, detection_height))
        else:
            detection_frame = frame
            detection_width, detection_height = original_width, original_height
        
        # PASO 3: APLICAR FILTROS Y MÁSCARA
        from .filters import apply_cascade_filters_to_frame
        filtered_frame = apply_cascade_filters_to_frame(detection_frame)
        
        polygon_restriction_enabled = params.get("polygon_restriction_enabled", True)
        if polygon_restriction_enabled and _area_mask is not None:
            area_mask_resized = cv2.resize(_area_mask, (detection_width, detection_height))
            final_detection_frame = cv2.bitwise_and(filtered_frame, filtered_frame, mask=area_mask_resized)
        else:
            final_detection_frame = filtered_frame
        
        # PASO 4: APLICAR SUPRESIÓN DE FONDO
        if _background_subtractor is None:
            _background_subtractor = _create_background_subtractor()
        
        learning_rate = params.get("learning_rate", 0.01) if _is_learning_background else 0.0
        fg_mask = _background_subtractor.apply(final_detection_frame, learningRate=learning_rate)
        
        # Debug para KNN
        if _detection_method == "KNN":
            print(f"[KNN] Método: {_detection_method}, Learning rate: {learning_rate}")
            print(f"[KNN] Máscara generada - Valores únicos: {np.unique(fg_mask)}")
            print(f"[KNN] Forma de máscara: {fg_mask.shape}")
        
        # PASO 5: PROCESAR CONTORNOS
        contours, _ = cv2.findContours(fg_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # Parámetros de filtrado
        min_area = params.get("min_contour_area", 500)
        solidity_threshold = params.get("solidity_threshold", 0.7)
        margin_pixels = params.get("polygon_margin", 5)
        
        _detected_objects = []  # Limpiar lista
        scale_x = original_width / detection_width
        scale_y = original_height / detection_height
        
        for contour in contours:
            area = cv2.contourArea(contour)
            
            # Filtros básicos
            if area <= min_area:
                continue
                
            hull = cv2.convexHull(contour)
            hull_area = cv2.contourArea(hull)
            solidity = float(area) / hull_area if hull_area > 0 else 0
            
            if solidity <= solidity_threshold:
                continue
            
            # Validar posición en polígono
            if polygon_restriction_enabled and _area_mask is not None:
                if not _validate_contour_inside_polygon_unified(contour, (detection_height, detection_width), margin_pixels):
                    continue
            
            # Objeto válido - almacenar información
            x, y, w, h = cv2.boundingRect(contour)
            
            orig_x = int(x * scale_x)
            orig_y = int(y * scale_y)
            orig_w = int(w * scale_x)
            orig_h = int(h * scale_y)
            
            _detected_objects.append({
                'contour': contour,
                'area': area,
                'bbox': (orig_x, orig_y, orig_w, orig_h),
                'bbox_norm': (orig_x / original_width, orig_y / original_height, 
                             orig_w / original_width, orig_h / original_height),
                'mask': fg_mask[y:y+h, x:x+w]
            })
        
        # PASO 6: RENDERIZAR RESULTADOS
        result = _render_detection_results(frame, _detected_objects, scale_x, scale_y, 
                                         original_width, original_height)
        return result
        
    except Exception as e:
        print(f"[unified_pipeline] ❌ Error en pipeline: {e}")
        return frame

def _render_detection_results(frame, detected_objects, scale_x, scale_y, frame_width, frame_height):
    """Renderiza los resultados de detección en el frame."""
    global _area_points, _area_mask, _is_learning_background, _is_drawing_area
    
    cv2 = _cv2_safe()
    if cv2 is None:
        return frame
    
    import numpy as np
    result = frame.copy()
    
    # Dibujar polígono si existe y no está en modo dibujo
    if len(_area_points) >= 3 and not _is_drawing_area:
        if _area_mask is not None:
            masked_frame = cv2.bitwise_and(frame, frame, mask=_area_mask)
            result = cv2.addWeighted(result, 0.3, masked_frame, 0.7, 0)
        
        # Dibujar contorno del polígono
        pixel_points = []
        for norm_x, norm_y in _area_points:
            x = int(norm_x * frame_width)
            y = int(norm_y * frame_height)
            pixel_points.append([x, y])
        cv2.polylines(result, [np.array(pixel_points, dtype=np.int32)], True, (0, 255, 0), 2)
    
    # Dibujar objetos detectados
    for obj in detected_objects:
        orig_x, orig_y, orig_w, orig_h = obj['bbox']
        
        # Suavizar contorno
        contour = obj['contour']
        epsilon = 0.02 * cv2.arcLength(contour, True)
        approx_contour = cv2.approxPolyDP(contour, epsilon, True)
        
        # Convertir contorno al frame original
        contour_orig = approx_contour.copy()
        contour_orig[:, :, 0] = (contour_orig[:, :, 0] * scale_x).astype(int)
        contour_orig[:, :, 1] = (contour_orig[:, :, 1] * scale_y).astype(int)
        
        cv2.drawContours(result, [contour_orig], -1, (0, 255, 0), 2)
        cv2.rectangle(result, (orig_x, orig_y), (orig_x + orig_w, orig_y + orig_h), (255, 0, 0), 2)
        cv2.putText(result, f"Area: {int(obj['area'])}", (orig_x, orig_y - 10), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
    
    # Indicadores de estado
    if _is_learning_background:
        cv2.putText(result, "CONFIGURANDO...", (10, 30), 
                   cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
    elif len(detected_objects) > 0:
        cv2.putText(result, "DETECCION ACTIVA", (10, 30), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
    
    return result

# FUNCIÓN ELIMINADA: _prepare_frame_for_detection()
# Funcionalidad integrada en unified_detection_pipeline()

def _apply_detection(frame, params):
    """Aplica detección de objetos solo dentro del área del polígono."""
    global _background_subtractor, _is_learning_background, _area_mask, _area_points, _area_detection_active, _is_drawing_area
    
    cv2 = _cv2_safe()
    if cv2 is None:
        return frame
    
    # Importar numpy
    import numpy as np
    
    try:
        # USAR EL PIPELINE UNIFICADO
        return unified_detection_pipeline(frame, params)
        
    except Exception as e:
        print(f"[detection] Error en detección: {e}")
        return frame

# FUNCIÓN ELIMINADA: _apply_object_detection()
# Funcionalidad integrada en unified_detection_pipeline()

# FUNCIÓN ELIMINADA: _apply_area_detection()
# Funcionalidad integrada en unified_detection_pipeline()

def toggle_background_learning():
    """Alterna el modo de aprendizaje del fondo para detección de objetos."""
    global _is_learning_background, _background_subtractor, _background_model_saved
    
    cv2 = _cv2_safe()
    if cv2 is None:
        return False
    
    _is_learning_background = not _is_learning_background
    
    if _is_learning_background:
        # Inicializar el subtractor de fondo con el método configurado
        _background_subtractor = _create_background_subtractor()
        print(f"[object_detection] ✅ Iniciando aprendizaje del fondo (learningRate=0.01) - Método: {_detection_method}")
    else:
        # Al detener el aprendizaje, marcar que hay un modelo guardado
        if _background_subtractor is not None:
            _background_model_saved = True
            print(f"[object_detection] 🛑 Deteniendo aprendizaje del fondo (learningRate=0.0) - Modelo guardado")
        else:
            print(f"[object_detection] 🛑 Deteniendo aprendizaje del fondo (learningRate=0.0)")
    
    return _is_learning_background

def get_background_learning_status():
    """Obtiene el estado actual del aprendizaje del fondo."""
    return {
        "is_learning": _is_learning_background,
        "has_model": _background_model_saved
    }

def start_background_learning():
    """Inicia el aprendizaje del fondo de forma controlada."""
    global _is_learning_background, _background_subtractor
    
    cv2 = _cv2_safe()
    if cv2 is None:
        return False
    
    if _is_learning_background:
        print(f"[object_detection] El aprendizaje ya está activo")
        return True
    
    # Inicializar el subtractor de fondo con el método configurado
    _background_subtractor = _create_background_subtractor()
    _is_learning_background = True
    
    print(f"[object_detection] ✅ Iniciando aprendizaje automático del fondo - Método: {_detection_method}")
    return True

def stop_background_learning():
    """Detiene el aprendizaje del fondo de forma controlada."""
    global _is_learning_background, _background_model_saved
    
    if not _is_learning_background:
        print(f"[object_detection] El aprendizaje no está activo")
        return True
    
    # Al detener el aprendizaje, marcar que hay un modelo guardado
    if _background_subtractor is not None:
        _background_model_saved = True
    
    _is_learning_background = False
    print(f"[object_detection] 🛑 Aprendizaje automático del fondo detenido - Modelo guardado")
    return True

def start_area_drawing():
    """Inicia el modo de dibujo de área para detección de movimiento."""
    global _is_drawing_area, _area_points
    _is_drawing_area = True
    _area_points = []
    print(f"[area_detection] Iniciando dibujo de área")
    return True

def stop_area_drawing():
    """Detiene el modo de dibujo de área."""
    global _is_drawing_area
    _is_drawing_area = False
    print(f"[area_detection] Deteniendo dibujo de área")
    return False

def start_area_detection():
    """Activa la detección de objetos en el área (mantenido por compatibilidad)."""
    global _area_detection_active
    _area_detection_active = True
    print(f"[area_detection] ✅ Activando detección manual de objetos")
    return True

def stop_area_detection():
    """Desactiva la detección de objetos en el área (mantenido por compatibilidad)."""
    global _area_detection_active
    _area_detection_active = False
    print(f"[area_detection] Desactivando detección manual de objetos")
    return False

def add_area_point(x: int, y: int):
    """Agrega un punto al área de detección."""
    global _area_points
    if _is_drawing_area:
        # Convertir coordenadas de píxeles a normalizadas (0-1)
        frame_width, frame_height = _get_frame_dimensions()
        norm_x = x / frame_width
        norm_y = y / frame_height
        
        # Guardar coordenadas normalizadas
        _area_points.append((norm_x, norm_y))
        print(f"[area_detection] Punto agregado: ({x}, {y}) -> normalizado: ({norm_x:.3f}, {norm_y:.3f})")
        return True
    return False

def close_area():
    """Cierra el área y genera la máscara."""
    global _area_points, _area_mask, _is_drawing_area, _area_detection_active
    
    if len(_area_points) < 3:
        print(f"[area_detection] Se necesitan al menos 3 puntos para cerrar el área")
        return False
    
    # Crear la máscara
    _area_mask = create_polygon_mask()
    if _area_mask is not None:
        _is_drawing_area = False
        # NO activar automáticamente la detección - el usuario debe activarla manualmente
        _area_detection_active = False
        print(f"[area_detection] Área cerrada con {len(_area_points)} puntos (detección inactiva)")
        return True
    else:
        print(f"[area_detection] Error creando máscara")
        return False

def get_area_status():
    """Obtiene el estado actual del área de detección."""
    return {
        "is_drawing": _is_drawing_area,
        "is_active": _area_detection_active,
        "points": _area_points.copy(),
        "has_mask": _area_mask is not None
    }

def _polish_contours(contours, frame_shape, params=None):
    """Aplica pulido a los contornos para mejorar su calidad."""
    cv2 = _cv2_safe()
    np = _np_safe()
    if cv2 is None or np is None:
        return contours
    
    try:
        polished_contours = []
        
        for contour in contours:
            # Suavizar contorno con spline
            smoothed_contour = _smooth_contour_spline(contour, params)
            
            # Remover puntos redundantes
            cleaned_contour = _remove_redundant_points(smoothed_contour, params)
            
            # Validar calidad del contorno
            if _validate_contour_quality(cleaned_contour, frame_shape, params):
                polished_contours.append(cleaned_contour)
        
        return polished_contours
        
    except Exception as e:
        print(f"[contour_polish] Error puliendo contornos: {e}")
        return contours

def _smooth_contour_spline(contour, params):
    """Suaviza un contorno usando interpolación spline."""
    np = _np_safe()
    if np is None:
        return contour
    
    try:
        # Intentar importar scipy para spline
        try:
            from scipy.interpolate import splprep, splev
        except ImportError:
            return contour
        
        # Extraer puntos del contorno
        points = contour.reshape(-1, 2)
        
        if len(points) < 4:
            return contour
        
        # Preparar puntos para spline (necesita ser cerrado)
        x = points[:, 0]
        y = points[:, 1]
        
        # Cerrar el contorno si no está cerrado
        if not (x[0] == x[-1] and y[0] == y[-1]):
            x = np.append(x, x[0])
            y = np.append(y, y[0])
        
        # Ajustar spline
        tck, u = splprep([x, y], s=0, per=True)
        
        # Generar puntos suavizados
        new_points = splev(u, tck)
        
        # Convertir de vuelta a formato de contorno
        smoothed_points = np.column_stack(new_points).astype(np.int32)
        smoothed_contour = smoothed_points.reshape(-1, 1, 2)
        
        return smoothed_contour
        
    except Exception as e:
        print(f"[contour_polish] Error suavizando contorno: {e}")
        return contour

def _remove_redundant_points(contour, params):
    """Remueve puntos redundantes del contorno."""
    cv2 = _cv2_safe()
    np = _np_safe()
    if cv2 is None or np is None:
        return contour
    
    try:
        # Usar aproximación de Douglas-Peucker
        epsilon = params.get("epsilon", 0.02) if params else 0.02
        arc_length = cv2.arcLength(contour, True)
        epsilon_value = epsilon * arc_length
        
        approx_contour = cv2.approxPolyDP(contour, epsilon_value, True)
        
        return approx_contour
        
    except Exception as e:
        print(f"[contour_polish] Error removiendo puntos redundantes: {e}")
        return contour

def _validate_contour_quality(contour, frame_shape, params):
    """Valida la calidad de un contorno."""
    cv2 = _cv2_safe()
    if cv2 is None:
        return True
    
    try:
        # Calcular área
        area = cv2.contourArea(contour)
        
        # Área mínima
        min_area = params.get("min_area", 100) if params else 100
        if area < min_area:
            return False
        
        # Calcular perímetro
        perimeter = cv2.arcLength(contour, True)
        
        # Evitar contornos muy pequeños o muy grandes
        frame_area = frame_shape[0] * frame_shape[1]
        if area > frame_area * 0.8:  # No más del 80% del frame
            return False
        
        # Verificar que el contorno tenga suficientes puntos
        if len(contour) < 3:
            return False
        
        return True
        
    except Exception as e:
        print(f"[contour_polish] Error validando contorno: {e}")
        return False

def normalize_coordinates(x, y, width, height):
    """
    Convierte coordenadas de píxeles a coordenadas normalizadas (0-1).
    
    Args:
        x, y: Coordenadas en píxeles
        width, height: Dimensiones del frame
    
    Returns:
        tuple: (norm_x, norm_y) coordenadas normalizadas
    """
    return (x / width, y / height)

def denormalize_coordinates(norm_x, norm_y, width, height):
    """
    Convierte coordenadas normalizadas (0-1) a coordenadas de píxeles.
    
    Args:
        norm_x, norm_y: Coordenadas normalizadas (0-1)
        width, height: Dimensiones del frame
    
    Returns:
        tuple: (x, y) coordenadas en píxeles
    """
    return (int(norm_x * width), int(norm_y * height))

# FUNCIÓN ELIMINADA: _validate_contour_inside_polygon()
# Reemplazada por _validate_contour_inside_polygon_unified()

def _validate_contour_inside_polygon_unified(contour, frame_shape, margin_pixels=5):
    """
    Versión unificada de validación de contorno dentro del polígono.
    """
    global _area_mask, _area_points
    
    cv2 = _cv2_safe()
    if cv2 is None:
        return True
    
    try:
        if _area_mask is None or len(_area_points) < 3:
            return True
        
        frame_height, frame_width = frame_shape
        x, y, w, h = cv2.boundingRect(contour)
        
        # Verificar margen del frame
        if x < margin_pixels or y < margin_pixels or x + w > frame_width - margin_pixels or y + h > frame_height - margin_pixels:
            return False
        
        # Redimensionar máscara al frame de detección
        detection_mask = cv2.resize(_area_mask, (frame_width, frame_height))
        
        # Crear máscara con margen
        margin_mask = detection_mask.copy()
        if margin_pixels > 0:
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (margin_pixels * 2 + 1, margin_pixels * 2 + 1))
            margin_mask = cv2.erode(detection_mask, kernel, iterations=1)
        
        # Verificar todos los puntos del contorno
        for point in contour:
            px, py = point[0]
            if px >= 0 and py >= 0 and px < frame_width and py < frame_height:
                if margin_mask[py, px] == 0:
                    return False
        
        return True
        
    except Exception as e:
        print(f"[polygon_validation] Error: {e}")
        return False

def save_polygon_to_config():
    """Guarda el polígono actual en la configuración."""
    global _area_points
    
    try:
        from .utils import load_config, save_config
        
        # Cargar configuración actual
        config = load_config()
        
        # Guardar puntos del polígono
        config.setdefault("detection", {})["area_points"] = _area_points
        
        # Guardar configuración
        save_config(config)
        
        print(f"[area] Polígono guardado en configuración: {len(_area_points)} puntos")
        return True
        
    except Exception as e:
        print(f"[area] Error guardando polígono: {e}")
        return False

def load_polygon_from_config():
    """Carga el polígono desde la configuración."""
    global _area_points, _area_mask
    
    try:
        from .utils import load_config
        
        # Cargar configuración
        config = load_config()
        
        # Obtener puntos del polígono
        area_points = config.get("detection", {}).get("area_points", [])
        
        if len(area_points) >= 3:
            _area_points = area_points
            _area_mask = None  # Forzar recreación de máscara
            print(f"[area] Polígono cargado desde configuración: {len(_area_points)} puntos")
            return True
        else:
            print("[area] No hay polígono válido en configuración")
            return False
        
    except Exception as e:
        print(f"[area] Error cargando polígono: {e}")
        return False

def take_snapshot_with_mask():
    """
    Toma un snapshot del objeto más grande detectado usando coordenadas normalizadas.
    Usa el stream original de alta resolución para máxima calidad.
    """
    global _snapshot_mode, _snapshot_image, _snapshot_mask, _detected_objects
    
    try:
        from .camera_manager import get_jpeg
        
        # Obtener frame actual de alta resolución
        jpeg_data = get_jpeg()
        if jpeg_data is None:
            return False, "No hay imagen disponible"
        
        # Decodificar imagen
        import cv2
        import numpy as np
        
        # Convertir bytes a array numpy
        nparr = np.frombuffer(jpeg_data, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if frame is None:
            return False, "Error decodificando imagen"
        
        # Si hay objetos detectados, tomar snapshot del más grande
        if _detected_objects:
            # Encontrar el objeto con mayor área
            largest_object = max(_detected_objects, key=lambda obj: obj['area'])
            
            # Obtener coordenadas normalizadas del objeto
            norm_x, norm_y, norm_w, norm_h = largest_object['bbox_norm']
            
            # Obtener dimensiones del frame original
            frame_height, frame_width = frame.shape[:2]
            
            # Convertir coordenadas normalizadas a píxeles en el frame original
            x = int(norm_x * frame_width)
            y = int(norm_y * frame_height)
            w = int(norm_w * frame_width)
            h = int(norm_h * frame_height)
            
            # Asegurar que las coordenadas estén dentro del frame
            x = max(0, min(x, frame_width - 1))
            y = max(0, min(y, frame_height - 1))
            w = min(w, frame_width - x)
            h = min(h, frame_height - y)
            
            # Extraer el objeto del frame original (alta resolución)
            object_snapshot = frame[y:y+h, x:x+w]
            
            # Si hay máscara de polígono, aplicarla al snapshot
            if len(_area_points) >= 3:
                mask = create_polygon_mask()
                if mask is not None:
                    # Redimensionar máscara al tamaño del objeto
                    object_mask = mask[y:y+h, x:x+w]
                    object_snapshot = cv2.bitwise_and(object_snapshot, object_snapshot, mask=object_mask)
            
            _snapshot_image = object_snapshot
            _snapshot_mode = True
            print(f"[snapshot] ✅ Snapshot de objeto tomado: {w}x{h} píxeles (área: {largest_object['area']})")
            return True, f"Snapshot tomado exitosamente - Objeto: {w}x{h} píxeles"
        
        # Si no hay objetos detectados, tomar snapshot completo
        _snapshot_image = frame
        _snapshot_mode = True
        print("[snapshot] Snapshot completo tomado (sin objetos detectados)")
        return True, "Snapshot completo tomado exitosamente"
        
    except Exception as e:
        print(f"[snapshot] Error tomando snapshot: {e}")
        return False, f"Error: {str(e)}"

def clear_snapshot_mode():
    """Limpia el modo snapshot."""
    global _snapshot_mode, _snapshot_image, _snapshot_mask
    
    _snapshot_mode = False
    _snapshot_image = None
    _snapshot_mask = None
    print("[snapshot] Modo snapshot limpiado")

def get_snapshot_status():
    """Obtiene el estado del snapshot."""
    global _snapshot_mode, _snapshot_image
    
    return {
        "mode": _snapshot_mode,
        "has_image": _snapshot_image is not None
    }

def set_detection_method(method: str, params: dict = None, enabled: bool = True):
    """Configura el método de detección de objetos."""
    global _detection_method, _detection_params, _background_subtractor, _background_suppression_enabled
    
    cv2 = _cv2_safe()
    if cv2 is None:
        return False, "OpenCV no disponible"
    
    valid_methods = ["MOG2", "KNN"]
    if method not in valid_methods:
        return False, f"Método no válido. Opciones: {', '.join(valid_methods)}"
    
    try:
        # Actualizar método, parámetros y estado de habilitación
        _detection_method = method
        _background_suppression_enabled = enabled
        if params:
            _detection_params.update(params)
        
        # Reinicializar el subtractor con el nuevo método solo si está habilitado
        if enabled:
            _background_subtractor = _create_background_subtractor()
        else:
            _background_subtractor = None
        
        status = "habilitado" if enabled else "deshabilitado"
        print(f"[detection] Método de detección {method} {status}")
        return True, f"Método {method} {status}"
        
    except Exception as e:
        print(f"[detection] Error configurando método de detección: {e}")
        return False, f"Error: {str(e)}"

def get_detection_method():
    """Obtiene el método de detección actual y sus parámetros."""
    global _detection_method, _detection_params, _background_suppression_enabled
    
    return {
        "method": _detection_method,
        "enabled": _background_suppression_enabled,
        "params": _detection_params.copy()
    }

def _create_background_subtractor():
    """Crea un subtractor de fondo según el método y configuración actual."""
    global _detection_method, _detection_params, _algorithm_configs
    
    cv2 = _cv2_safe()
    if cv2 is None:
        return None
    
    try:
        # Usar configuración específica del algoritmo o fallback a parámetros globales
        config = _algorithm_configs.get(_detection_method, {})
        
        if _detection_method == "MOG2":
            return cv2.createBackgroundSubtractorMOG2(
                history=config.get("history", 500),
                varThreshold=config.get("varThreshold", _detection_params.get("var_threshold", 25)),
                detectShadows=config.get("detectShadows", _detection_params.get("detect_shadows", False))
            )
        elif _detection_method == "KNN":
            knn_config = {
                "history": config.get("history", 500),
                "dist2Threshold": config.get("dist2Threshold", 1000.0),
                "detectShadows": config.get("detectShadows", False)
            }
            print(f"[detection] Creando KNN con configuración: {knn_config}")
            return cv2.createBackgroundSubtractorKNN(**knn_config)
        else:
            # Fallback a MOG2
            return cv2.createBackgroundSubtractorMOG2(
                history=500,
                varThreshold=_detection_params.get("var_threshold", 25),
                detectShadows=_detection_params.get("detect_shadows", False)
            )
            
    except Exception as e:
        print(f"[detection] Error creando subtractor de fondo: {e}")
        return None

# Configuraciones específicas por algoritmo
_algorithm_configs = {
    "MOG2": {
        "history": 500,
        "varThreshold": 16,
        "detectShadows": True,
        "shadowValue": 127
    },

    "KNN": {
        "history": 500,
        "dist2Threshold": 1000,  # Umbral más alto para detectar más objetos
        "detectShadows": False,  # Deshabilitar sombras para KNN
        "shadowValue": 127
    }
}

# Configuración de aprendizaje del modelo
_learning_config = {
    "learning_rate": 0.01,
    "epochs": 100,
    "batch_size": 16,
    "validation_split": 0.2,
    "early_stopping": True,
    "data_augmentation": True,
    "normalization": "standard"
}

def get_algorithm_config(algorithm: str):
    """Obtiene la configuración específica de un algoritmo."""
    global _algorithm_configs
    
    if algorithm not in _algorithm_configs:
        return {}
    
    return _algorithm_configs[algorithm].copy()

def set_algorithm_config(algorithm: str, config: dict):
    """Configura los parámetros específicos de un algoritmo."""
    global _algorithm_configs, _background_subtractor, _detection_method
    
    cv2 = _cv2_safe()
    if cv2 is None:
        return False, "OpenCV no disponible"
    
    if algorithm not in _algorithm_configs:
        return False, f"Algoritmo no válido: {algorithm}"
    
    try:
        # Actualizar configuración
        _algorithm_configs[algorithm].update(config)
        
        # Si es el algoritmo actual, reinicializar el subtractor
        if algorithm == _detection_method:
            _background_subtractor = _create_background_subtractor()
        
        print(f"[detection] Configuración de {algorithm} actualizada")
        return True, f"Configuración de {algorithm} guardada"
        
    except Exception as e:
        print(f"[detection] Error configurando {algorithm}: {e}")
        return False, f"Error: {str(e)}"

def get_learning_config():
    """Obtiene la configuración de aprendizaje del modelo."""
    global _learning_config
    return _learning_config.copy()

def set_learning_config(config: dict):
    """Configura los parámetros de aprendizaje del modelo."""
    global _learning_config
    
    try:
        # Actualizar configuración
        _learning_config.update(config)
        
        print(f"[detection] Configuración de aprendizaje actualizada")
        return True, "Configuración de aprendizaje guardada"
        
    except Exception as e:
        print(f"[detection] Error configurando aprendizaje: {e}")
        return False, f"Error: {str(e)}"

def debug_knn_detection():
    """Función de diagnóstico para KNN."""
    global _detection_method, _background_subtractor, _algorithm_configs
    
    print(f"[KNN_DEBUG] Método actual: {_detection_method}")
    print(f"[KNN_DEBUG] Configuración KNN: {_algorithm_configs.get('KNN', {})}")
    print(f"[KNN_DEBUG] Subtractors activos: {_background_subtractor is not None}")
    
    if _detection_method == "KNN":
        print(f"[KNN_DEBUG] ✅ KNN está configurado como método activo")
        if _background_subtractor is not None:
            print(f"[KNN_DEBUG] ✅ Subtractors KNN creado correctamente")
        else:
            print(f"[KNN_DEBUG] ❌ Subtractors KNN no está creado")
    else:
        print(f"[KNN_DEBUG] ⚠️ KNN no es el método activo (actual: {_detection_method})")
    
    return {
        "method": _detection_method,
        "knn_config": _algorithm_configs.get('KNN', {}),
        "subtractor_active": _background_subtractor is not None
    }

# FUNCIÓN ELIMINADA: _create_background_subtractor_with_config()
# Funcionalidad consolidada en _create_background_subtractor()
