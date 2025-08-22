# filters.py - Gestión de filtros de imagen
import json
import threading
from typing import List, Dict, Optional, Tuple
from .utils import _cv2_safe, _np_safe, load_config, save_config

# Variables globales para filtros en cascada
_cascade_filters_config = None
_config_mode = False
_preview_filter = 1
_preview_mode = False
_cascade_preview_filters = []

def _apply_smoothing_filters(frame, filter_type="default"):
    """
    Aplica filtros de suavizado para reducir ruido en contornos.
    
    Args:
        frame: Imagen de entrada
        filter_type: Tipo de filtro a aplicar
            - "default": Combinación optimizada de filtros
            - "bilateral": Solo filtro bilateral
            - "gaussian": Solo filtro gaussiano
            - "median": Solo filtro mediana
            - "morphological": Solo operaciones morfológicas
            - "aggressive": Filtros más agresivos para mucho ruido
            - "adaptive": Filtro adaptativo basado en análisis de ruido
            - "contour_optimized": Optimizado específicamente para contornos
    
    Returns:
        Imagen suavizada
    """
    cv2 = _cv2_safe()
    if cv2 is None:
        return frame
    
    try:
        # Detectar nivel de ruido para filtros adaptativos
        noise_level = _estimate_noise_level(frame) if filter_type in ["adaptive", "contour_optimized"] else None
        
        if filter_type == "default":
            # Combinación optimizada: Bilateral + Gaussiano suave + Morfológico
            # 1. Filtro bilateral para preservar bordes
            smoothed = cv2.bilateralFilter(frame, 9, 75, 75)
            
            # 2. Filtro gaussiano suave para reducir ruido
            smoothed = cv2.GaussianBlur(smoothed, (5, 5), 0.8)
            
            # 3. Operación morfológica para limpiar contornos
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
            smoothed = cv2.morphologyEx(smoothed, cv2.MORPH_CLOSE, kernel)
            
            return smoothed
            
        elif filter_type == "bilateral":
            # Solo filtro bilateral - preserva bordes
            return cv2.bilateralFilter(frame, 9, 75, 75)
            
        elif filter_type == "gaussian":
            # Solo filtro gaussiano
            return cv2.GaussianBlur(frame, (5, 5), 1.0)
            
        elif filter_type == "median":
            # Solo filtro de mediana - bueno para ruido sal y pimienta
            return cv2.medianBlur(frame, 5)
            
        elif filter_type == "morphological":
            # Solo operaciones morfológicas
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
            smoothed = cv2.morphologyEx(frame, cv2.MORPH_OPEN, kernel)
            smoothed = cv2.morphologyEx(smoothed, cv2.MORPH_CLOSE, kernel)
            return smoothed
            
        elif filter_type == "aggressive":
            # Filtros más agresivos para mucho ruido
            # 1. Filtro bilateral más fuerte
            smoothed = cv2.bilateralFilter(frame, 15, 100, 100)
            
            # 2. Filtro gaussiano más fuerte
            smoothed = cv2.GaussianBlur(smoothed, (7, 7), 1.5)
            
            # 3. Operaciones morfológicas más agresivas
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
            smoothed = cv2.morphologyEx(smoothed, cv2.MORPH_OPEN, kernel)
            smoothed = cv2.morphologyEx(smoothed, cv2.MORPH_CLOSE, kernel)
            
            return smoothed
            
        elif filter_type == "adaptive":
            # Filtro adaptativo basado en nivel de ruido detectado
            if noise_level < 0.1:  # Bajo ruido
                return cv2.bilateralFilter(frame, 5, 50, 50)
            elif noise_level < 0.3:  # Ruido medio
                smoothed = cv2.bilateralFilter(frame, 9, 75, 75)
                return cv2.GaussianBlur(smoothed, (3, 3), 0.5)
            else:  # Alto ruido
                smoothed = cv2.bilateralFilter(frame, 15, 100, 100)
                smoothed = cv2.GaussianBlur(smoothed, (5, 5), 1.0)
                kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
                return cv2.morphologyEx(smoothed, cv2.MORPH_CLOSE, kernel)
                
        elif filter_type == "contour_optimized":
            # Optimizado específicamente para mejorar contornos
            # 1. Reducción de ruido preservando bordes
            if noise_level and noise_level > 0.2:
                smoothed = cv2.bilateralFilter(frame, 11, 80, 80)
            else:
                smoothed = cv2.bilateralFilter(frame, 7, 60, 60)
            
            # 2. Mejora de contraste local para contornos
            lab = cv2.cvtColor(smoothed, cv2.COLOR_BGR2LAB)
            clahe = cv2.createCLAHE(clipLimit=1.5, tileGridSize=(8,8))
            lab[:,:,0] = clahe.apply(lab[:,:,0])
            smoothed = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
            
            # 3. Suavizado final muy suave para contornos más regulares
            return cv2.GaussianBlur(smoothed, (3, 3), 0.3)
            
        else:
            # Filtro por defecto si no se reconoce el tipo
            return cv2.bilateralFilter(frame, 9, 75, 75)
            
    except Exception as e:
        print(f"[smoothing] Error aplicando filtros de suavizado: {e}")
        return frame

def _estimate_noise_level(frame):
    """
    Estima el nivel de ruido en la imagen usando la varianza de Laplaciano.
    Returns: valor entre 0 y 1 (0 = sin ruido, 1 = muy ruidoso)
    """
    cv2 = _cv2_safe()
    if cv2 is None:
        return 0.5  # Valor por defecto
    
    try:
        # Convertir a escala de grises
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # Aplicar filtro Laplaciano
        laplacian = cv2.Laplacian(gray, cv2.CV_64F)
        
        # Calcular varianza (medida de ruido)
        variance = laplacian.var()
        
        # Normalizar a rango 0-1 (ajustar según experiencia)
        # Valores típicos: 0-50 = bajo ruido, 50-200 = medio, >200 = alto
        normalized = min(variance / 200.0, 1.0)
        
        return normalized
        
    except Exception as e:
        print(f"[noise] Error estimando ruido: {e}")
        return 0.5

def load_cascade_filters_config():
    """Carga la configuración de filtros en cascada desde filter_config.json."""
    global _cascade_filters_config
    try:
        with open('filter_config.json', 'r', encoding='utf-8') as f:
            _cascade_filters_config = json.load(f)
            print(f"[cascade_filters] Configuración cargada: {len(_cascade_filters_config.get('cascade_filters', []))} filtros, modo: {_cascade_filters_config.get('config_mode', False)}, preview: {_cascade_filters_config.get('preview_filter', 1)}")
            return _cascade_filters_config
    except FileNotFoundError:
        print("[cascade_filters] Archivo filter_config.json no encontrado, usando configuración por defecto")
        _cascade_filters_config = {
            "cascade_filters": [
                {"id": 1, "enabled": True, "type": "grayscale", "params": {}},
                {"id": 2, "enabled": True, "type": "bilateral", "params": {"d": 12, "sigma_color": 75, "sigma_space": 75}},
                {"id": 3, "enabled": True, "type": "gaussian", "params": {"kernel_size": 7, "sigma": 1.5}},
                {"id": 4, "enabled": True, "type": "median", "params": {"kernel_size": 5}},
                {"id": 5, "enabled": True, "type": "morphological", "params": {"operation": "close", "kernel_size": 3, "kernel_type": "ellipse"}},
                {"id": 6, "enabled": True, "type": "contour_clean", "params": {"threshold": 0.02}}
            ],
            "detection_params": {
                "learning_rate": 0.01,
                "threshold": 25,
                "min_area": 500,
                "solidity_threshold": 0.7,
                "contour_polish_enabled": True
            },
            "preview_filter": 1,
            "config_mode": True,
            "last_updated": "2025-01-27 15:35:00"
        }
        return _cascade_filters_config
    except Exception as e:
        print(f"[cascade_filters] Error cargando configuración: {e}")
        return None

def save_cascade_filters_config():
    """Guarda la configuración de filtros en cascada en filter_config.json."""
    global _cascade_filters_config
    try:
        if _cascade_filters_config is not None:
            with open('filter_config.json', 'w', encoding='utf-8') as f:
                json.dump(_cascade_filters_config, f, indent=2, ensure_ascii=False)
            print("[cascade_filters] Configuración guardada exitosamente")
            return True
    except Exception as e:
        print(f"[cascade_filters] Error guardando configuración: {e}")
        return False

def get_cascade_filters_config():
    """Obtiene la configuración actual de filtros en cascada."""
    global _cascade_filters_config
    if _cascade_filters_config is None:
        load_cascade_filters_config()
    return _cascade_filters_config

def update_cascade_filter(filter_id: int, filter_type: str, params: Dict = None):
    """Actualiza un filtro específico en la configuración en cascada."""
    global _cascade_filters_config
    try:
        if _cascade_filters_config is None:
            load_cascade_filters_config()
        
        for filter_config in _cascade_filters_config.get("cascade_filters", []):
            if filter_config.get("id") == filter_id:
                filter_config["type"] = filter_type
                if params is not None:
                    filter_config["params"] = params
                save_cascade_filters_config()
                print(f"[cascade_filters] Filtro {filter_id} actualizado: {filter_type}")
                return True
        
        print(f"[cascade_filters] Filtro {filter_id} no encontrado")
        return False
    except Exception as e:
        print(f"[cascade_filters] Error actualizando filtro: {e}")
        return False

def enable_cascade_filter(filter_id: int, enabled: bool):
    """Habilita o deshabilita un filtro específico en la configuración en cascada."""
    global _cascade_filters_config
    try:
        if _cascade_filters_config is None:
            load_cascade_filters_config()
        
        for filter_config in _cascade_filters_config.get("cascade_filters", []):
            if filter_config.get("id") == filter_id:
                filter_config["enabled"] = enabled
                save_cascade_filters_config()
                print(f"[cascade_filters] Filtro {filter_id} {'habilitado' if enabled else 'deshabilitado'}")
                return True
        
        print(f"[cascade_filters] Filtro {filter_id} no encontrado")
        return False
    except Exception as e:
        print(f"[cascade_filters] Error habilitando/deshabilitando filtro: {e}")
        return False

def set_config_mode(enabled: bool):
    """Establece el modo de configuración."""
    global _config_mode
    try:
        _config_mode = enabled
        print(f"[cascade_filters] Modo configuración: {'activado' if enabled else 'desactivado'}")
        return True
    except Exception as e:
        print(f"[cascade_filters] Error configurando modo: {e}")
        return False

def set_preview_filter(filter_id: int):
    """Establece el filtro de preview."""
    global _preview_filter
    try:
        _preview_filter = filter_id
        print(f"[cascade_filters] Filtro preview configurado: {filter_id}")
        return True
    except Exception as e:
        print(f"[cascade_filters] Error configurando filtro preview: {e}")
        return False

def set_preview_mode(enabled: bool):
    """Establece el modo preview para la vista Original."""
    global _preview_mode
    try:
        _preview_mode = enabled
        print(f"[cascade_filters] Modo preview: {'activado' if enabled else 'desactivado'}")
        return True
    except Exception as e:
        print(f"[cascade_filters] Error configurando modo preview: {e}")
        return False

def set_cascade_preview_filters(filter_ids: list):
    """Establece qué filtros aplicar en el preview de la vista Original."""
    global _cascade_preview_filters
    try:
        _cascade_preview_filters = filter_ids
        print(f"[cascade_filters] Preview filtros configurados: {filter_ids}")
        return True
    except Exception as e:
        print(f"[cascade_filters] Error configurando preview filtros: {e}")
        return False

def _apply_cascade_filter(frame, filter_config: Dict):
    """Aplica un filtro específico de la configuración en cascada."""
    cv2 = _cv2_safe()
    if cv2 is None or frame is None:
        return frame
    
    try:
        filter_type = filter_config.get("type", "none")
        params = filter_config.get("params", {})
        
        if filter_type == "none":
            return frame
        
        return _apply_cascade_filter_v2(frame, filter_type, params)
        
    except Exception as e:
        print(f"[cascade] Error aplicando filtro {filter_config.get('id', 'unknown')}: {e}")
        return frame

def _apply_cascade_filters(frame):
    """Aplica todos los filtros en cascada configurados."""
    cv2 = _cv2_safe()
    if cv2 is None or frame is None:
        return frame
    
    try:
        config = get_cascade_filters_config()
        if not config or "cascade_filters" not in config:
            return frame
        
        result = frame.copy()
        
        for filter_config in config["cascade_filters"]:
            if filter_config.get("enabled", False):
                result = _apply_cascade_filter(result, filter_config)
        
        return result
        
    except Exception as e:
        print(f"[cascade] Error aplicando filtros en cascada: {e}")
        return frame

def apply_cascade_filters_to_frame(frame):
    """
    Aplica filtros en cascada configurados en filter_config.json.
    Versión mejorada con validación y optimización.
    """
    cv2 = _cv2_safe()
    if cv2 is None or frame is None:
        return frame
    
    try:
        # Cargar configuración de filtros
        config = get_cascade_filters_config()
        if not config or "cascade_filters" not in config:
            return frame
        
        # Validar que cascade_filters sea una lista
        if not isinstance(config["cascade_filters"], list):
            print(f"[cascade] Error: cascade_filters debe ser una lista, recibido: {type(config['cascade_filters'])}")
            return frame
        
        result = frame.copy()
        applied_filters = []
        
        # Verificar si estamos en modo preview
        global _preview_mode, _cascade_preview_filters
        
        if _preview_mode and _cascade_preview_filters:
            # Modo preview: aplicar solo los filtros especificados
            print(f"[cascade] Modo preview activado, aplicando filtros: {_cascade_preview_filters}")
            
            for filter_id in _cascade_preview_filters:
                # Buscar el filtro por ID
                filter_config = None
                for fc in config["cascade_filters"]:
                    if fc.get("id") == filter_id and fc.get("enabled", False):
                        filter_config = fc
                        break
                
                if filter_config:
                    filter_type = filter_config.get("type", "none")
                    params = filter_config.get("params", {})
                    
                    if filter_type != "none":
                        result = _apply_cascade_filter_v2(result, filter_type, params)
                        applied_filters.append(filter_type)
        else:
            # Modo normal: aplicar todos los filtros habilitados
            for filter_config in config["cascade_filters"]:
                # Validar que filter_config sea un diccionario
                if not isinstance(filter_config, dict):
                    print(f"[cascade] Error: filter_config debe ser un diccionario, recibido: {type(filter_config)}")
                    continue
                    
                if not filter_config.get("enabled", False):
                    continue
                    
                filter_type = filter_config.get("type", "none")
                params = filter_config.get("params", {})
                
                # Validar parámetros
                if not isinstance(params, dict):
                    print(f"[cascade] Error: params debe ser un diccionario para filtro {filter_type}, recibido: {type(params)}")
                    params = {}
                
                if filter_type == "none":
                    continue
                    
                # Aplicar filtro específico
                result = _apply_cascade_filter_v2(result, filter_type, params)
                applied_filters.append(filter_type)
        
        # Debug: mostrar filtros aplicados
        if len(applied_filters) > 0:
            print(f"[cascade] Filtros aplicados: {' -> '.join(applied_filters)}")
        
        return result
        
    except Exception as e:
        print(f"[cascade] Error aplicando filtros en cascada: {e}")
        return frame

def _apply_cascade_filter_v2(frame, filter_type: str, params: dict):
    """
    Aplica un filtro específico con parámetros dados.
    
    Args:
        frame: Imagen de entrada (puede ser a color o escala de grises)
        filter_type: Tipo de filtro a aplicar
        params: Parámetros del filtro
    
    Returns:
        Imagen procesada
        
    Nota: Algunos filtros como 'grayscale' convierten la imagen a escala de grises.
    Los filtros posteriores en la cascada deben manejar correctamente tanto
    imágenes a color (3 canales) como en escala de grises (1 canal).
    """
    cv2 = _cv2_safe()
    np = _np_safe()
    if cv2 is None or frame is None:
        return frame
    
    try:
        if filter_type == "grayscale":
            return cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            
        elif filter_type == "bilateral":
            d = params.get("d", 12)
            sigma_color = params.get("sigma_color", 75)
            sigma_space = params.get("sigma_space", 75)
            return cv2.bilateralFilter(frame, d, sigma_color, sigma_space)
            
        elif filter_type == "gaussian":
            kernel_size = params.get("kernel_size", 7)
            sigma = params.get("sigma", 1.5)
            # Asegurar que kernel_size sea impar
            if kernel_size % 2 == 0:
                kernel_size += 1
            return cv2.GaussianBlur(frame, (kernel_size, kernel_size), sigma)
            
        elif filter_type == "median":
            kernel_size = params.get("kernel_size", 5)
            # Asegurar que kernel_size sea impar
            if kernel_size % 2 == 0:
                kernel_size += 1
            return cv2.medianBlur(frame, kernel_size)
            
        elif filter_type == "morphological":
            operation = params.get("operation", "close")
            kernel_size = params.get("kernel_size", 3)
            kernel_type = params.get("kernel_type", "ellipse")
            
            # Crear kernel
            if kernel_type == "ellipse":
                kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))
            elif kernel_type == "rect":
                kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (kernel_size, kernel_size))
            elif kernel_type == "cross":
                kernel = cv2.getStructuringElement(cv2.MORPH_CROSS, (kernel_size, kernel_size))
            else:
                kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))
            
            # Aplicar operación
            if operation == "open":
                return cv2.morphologyEx(frame, cv2.MORPH_OPEN, kernel)
            elif operation == "close":
                return cv2.morphologyEx(frame, cv2.MORPH_CLOSE, kernel)
            elif operation == "gradient":
                return cv2.morphologyEx(frame, cv2.MORPH_GRADIENT, kernel)
            elif operation == "tophat":
                return cv2.morphologyEx(frame, cv2.MORPH_TOPHAT, kernel)
            elif operation == "blackhat":
                return cv2.morphologyEx(frame, cv2.MORPH_BLACKHAT, kernel)
            else:
                return cv2.morphologyEx(frame, cv2.MORPH_CLOSE, kernel)
                
        elif filter_type == "contour_clean":
            threshold = params.get("threshold", 0.02)
            # Aproximar contornos para limpiar ruido
            if len(frame.shape) == 3:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            else:
                gray = frame
            
            # Encontrar contornos
            contours, _ = cv2.findContours(gray, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            # Crear máscara limpia
            mask = np.zeros_like(gray)
            for contour in contours:
                epsilon = threshold * cv2.arcLength(contour, True)
                approx = cv2.approxPolyDP(contour, epsilon, True)
                cv2.fillPoly(mask, [approx], 255)
            
            return mask
            
        elif filter_type == "noise_reduction":
            h = params.get("h", 10)
            # Filtro de reducción de ruido no local means
            # Verificar si la imagen es a color o escala de grises
            if len(frame.shape) == 3:
                # Imagen a color - usar fastNlMeansDenoisingColored
                return cv2.fastNlMeansDenoisingColored(frame, None, h, h, 7, 21)
            else:
                # Imagen en escala de grises - usar fastNlMeansDenoising
                return cv2.fastNlMeansDenoising(frame, None, h, 7, 21)
            
        elif filter_type == "contrast_enhance":
            alpha = params.get("alpha", 1.3)  # Contraste
            beta = params.get("beta", 20)     # Brillo
            # cv2.convertScaleAbs funciona tanto con imágenes a color como en escala de grises
            return cv2.convertScaleAbs(frame, alpha=alpha, beta=beta)
            
        elif filter_type == "edge_enhance":
            strength = params.get("strength", 0.5)
            
            # Verificar si la imagen ya es de escala de grises
            if len(frame.shape) == 3:
                # Imagen de color (3 canales)
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                edges = cv2.Laplacian(gray, cv2.CV_64F)
                edges = np.uint8(np.absolute(edges))
                
                # Convertir edges a 3 canales para poder mezclar con la imagen original
                edges_3channel = cv2.cvtColor(edges, cv2.COLOR_GRAY2BGR)
                
                # Mezclar con imagen original
                enhanced = cv2.addWeighted(frame, 1 - strength, edges_3channel, strength, 0)
                return enhanced
            else:
                # Imagen ya es de escala de grises (1 canal)
                edges = cv2.Laplacian(frame, cv2.CV_64F)
                edges = np.uint8(np.absolute(edges))
                
                # Mezclar directamente con la imagen de escala de grises
                enhanced = cv2.addWeighted(frame, 1 - strength, edges, strength, 0)
                return enhanced
            
        elif filter_type == "clahe":
            clip_limit = params.get("clip_limit", 2.0)
            tile_grid_size = params.get("tile_grid_size", 8)
            
            # Verificar si la imagen es a color o escala de grises
            if len(frame.shape) == 3:
                # Imagen a color - aplicar CLAHE en LAB
                lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
                clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=(tile_grid_size, tile_grid_size))
                lab[:,:,0] = clahe.apply(lab[:,:,0])
                return cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
            else:
                # Imagen en escala de grises - aplicar CLAHE directamente
                clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=(tile_grid_size, tile_grid_size))
                return clahe.apply(frame)
            
        elif filter_type == "sharpen":
            strength = params.get("strength", 0.5)
            # Kernel de agudizado
            kernel = np.array([[-1,-1,-1],
                              [-1, 9,-1],
                              [-1,-1,-1]])
            
            # Aplicar kernel (funciona tanto con imágenes a color como en escala de grises)
            sharpened = cv2.filter2D(frame, -1, kernel)
            
            # Mezclar con imagen original
            return cv2.addWeighted(frame, 1 - strength, sharpened, strength, 0)
            
        else:
            return frame
            
    except Exception as e:
        print(f"[cascade] Error aplicando filtro {filter_type}: {e}")
        return frame

def get_smoothing_filter_options() -> List[Dict]:
    """Retorna las opciones disponibles de filtros de suavizado."""
    return [
        {"value": "default", "label": "Por Defecto", "description": "Combinación optimizada de filtros"},
        {"value": "bilateral", "label": "Bilateral", "description": "Preserva bordes mientras reduce ruido"},
        {"value": "gaussian", "label": "Gaussiano", "description": "Suavizado gaussiano estándar"},
        {"value": "median", "label": "Mediana", "description": "Efectivo contra ruido sal y pimienta"},
        {"value": "morphological", "label": "Morphológico", "description": "Operaciones morfológicas"},
        {"value": "aggressive", "label": "Agresivo", "description": "Filtros más fuertes para mucho ruido"},
        {"value": "adaptive", "label": "Adaptativo", "description": "Se adapta al nivel de ruido detectado"},
        {"value": "contour_optimized", "label": "Optimizado para Contornos", "description": "Específico para mejorar contornos"}
    ]
