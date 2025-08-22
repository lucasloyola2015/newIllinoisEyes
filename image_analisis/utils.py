# utils.py - Funciones auxiliares y utilidades
import threading
import time
import json
from pathlib import Path
from typing import List, Dict, Optional, Tuple

def _cv2_safe():
    """Importa cv2 de forma segura, retorna None si no está disponible."""
    try:
        import cv2
        return cv2
    except ImportError:
        print("[utils] OpenCV no está disponible")
        return None

def _cv2_or_raise():
    """Importa cv2 o lanza una excepción si no está disponible."""
    cv2 = _cv2_safe()
    if cv2 is None:
        raise ImportError("OpenCV (cv2) no está instalado")
    return cv2

def _np_safe():
    """Importa numpy de forma segura, retorna None si no está disponible."""
    try:
        import numpy as np
        return np
    except ImportError:
        print("[utils] NumPy no está disponible")
        return None

def load_config() -> Dict:
    """Carga la configuración desde config.json."""
    try:
        with open('config.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except Exception as e:
        print(f"[utils] Error cargando configuración: {e}")
        return {}

def save_config(cfg: Dict) -> None:
    """Guarda la configuración en config.json."""
    try:
        with open('config.json', 'w', encoding='utf-8') as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[utils] Error guardando configuración: {e}")

def _get_frame_dimensions():
    """Obtiene las dimensiones del frame actual."""
    cv2 = _cv2_safe()
    if cv2 is None:
        return (640, 480)
    
    try:
        # Intentar obtener dimensiones de la cámara activa
        from .camera_manager import _cap
        if _cap is not None and _cap.isOpened():
            width = int(_cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(_cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            return (width, height)
    except:
        pass
    
    return (640, 480)

def _convert_to_normalized_coordinates(pixel_points):
    """Convierte coordenadas de píxeles a coordenadas normalizadas."""
    width, height = _get_frame_dimensions()
    normalized_points = []
    
    for point in pixel_points:
        x_norm = point[0] / width
        y_norm = point[1] / height
        normalized_points.append((x_norm, y_norm))
    
    return normalized_points

def _convert_to_pixel_coordinates(normalized_points):
    """Convierte coordenadas normalizadas a coordenadas de píxeles."""
    width, height = _get_frame_dimensions()
    pixel_points = []
    
    for point in normalized_points:
        x_pixel = int(point[0] * width)
        y_pixel = int(point[1] * height)
        pixel_points.append((x_pixel, y_pixel))
    
    return pixel_points

def create_polygon_mask():
    """Crea una máscara de polígono para detección de área."""
    cv2 = _cv2_safe()
    np = _np_safe()
    if cv2 is None or np is None:
        return None
    
    try:
        from .detection import _area_points
        
        if len(_area_points) < 3:
            print(f"[utils] Se necesitan al menos 3 puntos para crear máscara, actuales: {len(_area_points)}")
            return None
        
        # Obtener dimensiones del frame
        width, height = _get_frame_dimensions()
        
        # Crear máscara vacía
        mask = np.zeros((height, width), dtype=np.uint8)
        
        # Convertir coordenadas normalizadas a píxeles
        pixel_points = []
        for norm_x, norm_y in _area_points:
            x = int(norm_x * width)
            y = int(norm_y * height)
            pixel_points.append([x, y])
        
        # Convertir puntos a array de numpy
        points = np.array(pixel_points, dtype=np.int32)
        
        # Dibujar polígono en la máscara
        cv2.fillPoly(mask, [points], 255)
        
        print(f"[utils] Máscara de polígono creada con {len(_area_points)} puntos, dimensiones: {width}x{height}")
        return mask
        
    except Exception as e:
        print(f"[utils] Error creando máscara de polígono: {e}")
        return None
