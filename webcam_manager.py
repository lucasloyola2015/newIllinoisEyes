# webcam_manager_new.py - Versión refactorizada usando image_analisis
"""
Gestor de webcam refactorizado que utiliza el paquete image_analisis.

Este archivo actúa como una capa de compatibilidad que importa todas las
funciones del paquete image_analisis para mantener la compatibilidad con
el código existente.
"""

# Importar todas las funciones del paquete image_analisis
from image_analisis import (
    # Camera management
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
    get_available_filters,
    
    # Filters
    apply_cascade_filters_to_frame,
    load_cascade_filters_config,
    save_cascade_filters_config,
    get_cascade_filters_config,
    update_cascade_filter,
    enable_cascade_filter,
    set_config_mode,
    set_preview_mode,
    set_cascade_preview_filters,
    get_smoothing_filter_options,
    
    # Detection
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
    get_detection_method,
    
    # Autotune
    run_filter_autotune,
    get_default_target_metrics,
    validate_filter_params,
    AutoTuneOptimizer
)

# Importar funciones de configuración desde utils
from image_analisis.utils import load_config, save_config

# Importar funciones adicionales desde filters
from image_analisis.filters import set_preview_filter

# FUNCIONES DE COMPATIBILIDAD OPTIMIZADAS
def set_contour_cleanup_params(var_threshold: int = 25, min_area: int = 500, solidity_threshold: float = 0.7):
    """Configura parámetros para limpieza de contornos."""
    return set_detection_method("MOG2", {
        "var_threshold": var_threshold,
        "min_contour_area": min_area,
        "solidity_threshold": solidity_threshold
    })

def check_background_model_status():
    """Verifica el estado del modelo de fondo."""
    return get_background_learning_status()





# Variables globales para compatibilidad (si son necesarias)
# Estas variables ahora están en los módulos correspondientes
# pero se pueden exponer aquí si es necesario para compatibilidad

# FUNCIONES DEL SISTEMA OPTIMIZADAS
def get_system_status():
    """Obtiene el estado actual del sistema de visión."""
    return {
        "camera_connected": get_jpeg() is not None,
        "current_filter": get_current_filter(),
        "background_learning": get_background_learning_status(),
        "area_status": get_area_status(),
        "cascade_filters": get_cascade_filters_config()
    }

def initialize_system():
    """Inicializa el sistema de visión."""
    success, error = auto_connect_from_config()
    config = load_cascade_filters_config()
    return success, error

def cleanup_system():
    """Limpia los recursos del sistema."""
    stop_webcam()

# Si este archivo se ejecuta directamente, inicializar el sistema
if __name__ == "__main__":
    initialize_system()
    try:
        # Mantener el sistema corriendo
        import time
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[system] Cerrando sistema...")
        cleanup_system()
