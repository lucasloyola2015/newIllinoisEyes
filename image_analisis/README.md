# Image Analisis - Sistema de Análisis de Imagen

Este paquete contiene módulos especializados para el procesamiento de imagen y detección de objetos, refactorizado desde el archivo `webcam_manager.py` original de más de 2500 líneas.

## Estructura del Paquete

```
image_analisis/
├── __init__.py          # Archivo principal del paquete
├── utils.py             # Funciones auxiliares y utilidades
├── filters.py           # Gestión de filtros de imagen
├── detection.py         # Detección de objetos y áreas
├── camera_manager.py    # Gestión de cámara y captura
├── autotune.py          # Optimización automática de parámetros
└── README.md           # Este archivo
```

## Módulos

### utils.py
Funciones auxiliares y utilidades del sistema:
- Importación segura de OpenCV y NumPy
- Gestión de configuración (carga/guardado)
- Conversión de coordenadas (píxeles ↔ normalizadas)
- Creación de máscaras de polígonos

### filters.py
Gestión completa de filtros de imagen:
- Filtros en cascada configurables
- Filtros de suavizado (bilateral, gaussiano, mediana, morfológico)
- Filtros de mejora (contraste, nitidez, reducción de ruido)
- Configuración y persistencia de parámetros
- Modo preview para configuración

### detection.py
Sistema de detección de objetos:
- Background subtraction con MOG2
- Detección en áreas específicas
- Dibujo y gestión de polígonos de detección
- Pulido y validación de contornos
- Aprendizaje de fondo

### camera_manager.py
Gestión completa de cámara:
- Conexión automática y manual
- Escaneo de cámaras disponibles
- Gestión de resoluciones
- Captura de frames y snapshots
- Aplicación de filtros en tiempo real

### autotune.py
Optimización automática de parámetros:
- Optimización de parámetros de filtros
- Evaluación de métricas de calidad
- Búsqueda inteligente de mejores configuraciones
- Reportes de optimización

## Uso Básico

```python
# Importar el paquete
from image_analisis import *

# Conectar cámara
success, error = auto_connect_from_config()
if success:
    print("Cámara conectada")

# Configurar filtros en cascada
config = get_cascade_filters_config()
print(f"Filtros configurados: {len(config['cascade_filters'])}")

# Aplicar detección
set_filter("detection")
status = get_background_learning_status()
print(f"Estado de aprendizaje: {status}")

# Optimizar parámetros automáticamente
best_params = run_filter_autotune("bilateral", frame, {
    "noise_reduction": 0.8,
    "detail_preservation": 0.7
})
```

## Migración desde webcam_manager.py

Para migrar desde el archivo original:

1. **Reemplazar importaciones**:
   ```python
   # Antes
   import webcam_manager as wm
   
   # Después
   from image_analisis import *
   ```

2. **Usar funciones directamente**:
   ```python
   # Las funciones mantienen la misma interfaz
   connectWebCam(0)
   set_filter("detection")
   get_jpeg()
   ```

3. **Archivo de compatibilidad**:
   - Se incluye `webcam_manager_new.py` como capa de compatibilidad
   - Importa todas las funciones del paquete
   - Mantiene la misma interfaz pública

## Funciones Principales

### Gestión de Cámara
- `connectWebCam(cam_id, width, height)` - Conectar por índice
- `connect_by_uid(uid, width, height)` - Conectar por UID
- `auto_connect_from_config()` - Conexión automática
- `scanWebCams()` - Escanear cámaras disponibles
- `stop_webcam()` - Detener cámara

### Filtros
- `apply_cascade_filters_to_frame(frame)` - Aplicar filtros en cascada
- `load_cascade_filters_config()` - Cargar configuración
- `update_cascade_filter(filter_id, type, params)` - Actualizar filtro
- `enable_cascade_filter(filter_id, enabled)` - Habilitar/deshabilitar

### Detección
- `toggle_background_learning()` - Alternar aprendizaje
- `start_area_drawing()` - Iniciar dibujo de área
- `add_area_point(x, y)` - Agregar punto al área
- `close_area()` - Cerrar área de detección

### Autotune
- `run_filter_autotune(filter_type, frame, metrics)` - Optimizar filtro
- `get_default_target_metrics(filter_type)` - Métricas por defecto
- `AutoTuneOptimizer` - Clase para optimización avanzada

## Configuración

El sistema utiliza los mismos archivos de configuración:
- `config.json` - Configuración general
- `filter_config.json` - Configuración de filtros en cascada

## Ventajas de la Refactorización

1. **Modularidad**: Código organizado por funcionalidad
2. **Mantenibilidad**: Más fácil de mantener y debuggear
3. **Reutilización**: Módulos independientes reutilizables
4. **Testabilidad**: Cada módulo puede ser testeado por separado
5. **Escalabilidad**: Fácil agregar nuevas funcionalidades
6. **Documentación**: Cada módulo tiene su propia documentación

## Compatibilidad

- ✅ Mantiene todas las funciones públicas del archivo original
- ✅ Misma interfaz de API
- ✅ Mismos archivos de configuración
- ✅ Misma funcionalidad completa

## Próximos Pasos

1. **Testing**: Crear tests unitarios para cada módulo
2. **Documentación**: Documentación detallada de cada función
3. **Optimización**: Mejorar rendimiento de funciones críticas
4. **Nuevas Funcionalidades**: Agregar nuevos filtros y algoritmos
