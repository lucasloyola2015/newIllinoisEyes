# image_analisis/__init__.py
"""
Paquete de análisis de imagen para el sistema de visión.

Este paquete contiene módulos especializados para diferentes aspectos
del procesamiento de imagen y detección de objetos.

Módulos:
- utils: Funciones auxiliares y utilidades
- filters: Gestión de filtros de imagen
- detection: Detección de objetos y áreas
- camera_manager: Gestión de cámara y captura
- autotune: Optimización automática de parámetros
"""

from . import utils
from . import filters
from . import detection
from . import camera_manager
from . import autotune

# Exportar funciones principales para facilitar el uso
from .camera_manager import (
    connectWebCam,
    connect_by_uid,
    auto_connect_from_config,
    scanWebCams,
    get_supported_resolutions,
    stop_webcam,
    get_jpeg,
    change_camera_resolution,
    snapshot,
    set_filter,
    get_current_filter,
    get_available_filters
)

from .filters import (
    apply_cascade_filters_to_frame,
    load_cascade_filters_config,
    save_cascade_filters_config,
    get_cascade_filters_config,
    update_cascade_filter,
    enable_cascade_filter,
    set_config_mode,
    set_preview_mode,
    set_cascade_preview_filters,
    get_smoothing_filter_options
)

from .detection import (
    toggle_background_learning,
    get_background_learning_status,
    start_background_learning,
    stop_background_learning,
    start_area_drawing,
    stop_area_drawing,
    start_area_detection,
    stop_area_detection,
    add_area_point,
    close_area,
    get_area_status,
    save_polygon_to_config,
    load_polygon_from_config,
    take_snapshot_with_mask,
    clear_snapshot_mode,
    get_snapshot_status,
    set_detection_method,
    get_detection_method
)

from .autotune import (
    run_filter_autotune,
    get_default_target_metrics,
    validate_filter_params,
    AutoTuneOptimizer
)

__version__ = "1.0.0"
__author__ = "Illinois Automation"
__description__ = "Sistema de análisis de imagen para detección de objetos"

# Lista de todas las funciones exportadas
__all__ = [
    # Camera management
    'connectWebCam',
    'connect_by_uid', 
    'auto_connect_from_config',
    'scanWebCams',
    'get_supported_resolutions',
    'stop_webcam',
    'get_jpeg',
    'change_camera_resolution',
    'snapshot',
    'set_filter',
    'get_current_filter',
    'get_available_filters',
    
    # Filters
    'apply_cascade_filters_to_frame',
    'load_cascade_filters_config',
    'save_cascade_filters_config', 
    'get_cascade_filters_config',
    'update_cascade_filter',
    'enable_cascade_filter',
    'set_config_mode',
    'set_preview_mode',
    'set_cascade_preview_filters',
    'get_smoothing_filter_options',
    
    # Detection
    'toggle_background_learning',
    'get_background_learning_status',
    'start_background_learning',
    'stop_background_learning',
    'start_area_drawing',
    'stop_area_drawing',
    'start_area_detection',
    'stop_area_detection',
    'add_area_point',
    'close_area',
    'get_area_status',
    'save_polygon_to_config',
    'load_polygon_from_config',
    'take_snapshot_with_mask',
    'clear_snapshot_mode',
    'get_snapshot_status',
    'set_detection_method',
    'get_detection_method',
    
    # Autotune
    'run_filter_autotune',
    'get_default_target_metrics',
    'validate_filter_params',
    'AutoTuneOptimizer'
]
