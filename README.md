# NewIllinoisEyes

Sistema de visión artificial para detección y análisis de objetos en tiempo real, desarrollado para aplicaciones industriales.

## Características

- **Detección de Objetos**: Sistema de detección basado en OpenCV con múltiples algoritmos (MOG2, KNN)
- **Filtros en Cascada**: Sistema de filtros de imagen configurables (grayscale, noise reduction, bilateral, gaussian, contrast enhance, edge enhance)
- **Gestión de Perfiles**: Sistema de perfiles de configuración para diferentes escenarios
- **Calibración de Cámara**: Herramientas de calibración automática
- **Interfaz Web**: Interfaz de usuario web moderna y responsiva
- **Integración PLC**: Comunicación con sistemas PLC industriales
- **Gestión de Red**: Configuración y monitoreo de dispositivos de red

## Tecnologías

- **Backend**: Python 3.11+
- **Visión Artificial**: OpenCV
- **Frontend**: HTML5, CSS3, JavaScript (ES6+)
- **Comunicación**: Modbus TCP/IP
- **Servidor Web**: Python HTTP Server

## Instalación

1. Clonar el repositorio:
```bash
git clone https://github.com/lucasloyola2015/newIllinoisEyes.git
cd newIllinoisEyes
```

2. Instalar dependencias:
```bash
pip install -r requirements.txt
```

3. Ejecutar el servidor:
```bash
python webserver.py
```

4. Abrir en el navegador:
```
http://localhost:8000
```

## Estructura del Proyecto

```
NewIllinoisEyes/
├── webserver.py              # Servidor web principal
├── image_analisis/           # Módulos de análisis de imagen
│   ├── camera_manager.py     # Gestión de cámara
│   ├── detection.py          # Detección de objetos
│   ├── filters.py            # Filtros de imagen
│   └── utils.py              # Utilidades
├── template/                 # Plantillas HTML
│   ├── main.html            # Página principal
│   ├── control.html         # Panel de control
│   ├── filter_config.html   # Configuración de filtros
│   └── ...
├── static/                   # Archivos estáticos
│   ├── styles.css           # Estilos CSS
│   ├── common.js            # JavaScript común
│   └── app.js               # JavaScript principal
├── imgDatabase/             # Base de datos de imágenes
├── config.json              # Configuración general
├── filter_config.json       # Configuración de filtros
└── database.json            # Base de datos de juntas
```

## Configuración

### Perfiles de Filtros

El sistema incluye tres perfiles predefinidos:

1. **Balanceado (Defecto)**: Configuración equilibrada entre sensibilidad y precisión
2. **Sensible**: Configuración para detectar objetos pequeños
3. **Estricto**: Configuración para detectar solo objetos bien definidos

### Configuración de Red

El sistema permite configurar:
- Interfaces de red
- Direcciones IP de dispositivos
- Ping automático a dispositivos

## Uso

### Panel de Control Principal

1. **Conexión de Cámara**: Configurar y conectar cámaras
2. **Detección**: Activar/desactivar detección de objetos
3. **Calibración**: Ejecutar calibración de cámara
4. **Configuración**: Acceder a configuración avanzada

### Configuración de Filtros

1. **Filtros de Imagen**: Configurar filtros en cascada
2. **Detección de Objetos**: Ajustar parámetros de detección
3. **Calibración de Cámara**: Configurar parámetros de calibración
4. **Gestión de Perfiles**: Crear, editar y eliminar perfiles

## API Endpoints

### Cámara
- `GET /api/scan_cams` - Escanear cámaras disponibles
- `GET /api/camera/config` - Obtener configuración de cámara
- `POST /api/camera/config` - Guardar configuración de cámara

### Filtros
- `GET /api/cascade_filters/config` - Obtener configuración de filtros
- `POST /api/cascade_filters/save` - Guardar configuración de filtros
- `GET /api/cascade_filters/preview` - Vista previa de filtros

### Perfiles
- `POST /api/profiles/create` - Crear nuevo perfil
- `POST /api/profiles/update` - Actualizar perfil
- `DELETE /api/profiles/delete/{id}` - Eliminar perfil

### Sistema
- `GET /api/system/status` - Estado del sistema
- `POST /api/system/restart` - Reiniciar sistema
- `GET /api/terminal/logs` - Obtener logs del terminal

## Contribución

1. Fork el proyecto
2. Crear una rama para tu feature (`git checkout -b feature/AmazingFeature`)
3. Commit tus cambios (`git commit -m 'Add some AmazingFeature'`)
4. Push a la rama (`git push origin feature/AmazingFeature`)
5. Abrir un Pull Request

## Licencia

Este proyecto está bajo la Licencia MIT. Ver el archivo `LICENSE` para más detalles.

## Autor

**Lucas Loyola**
- GitHub: [@lucasloyola2015](https://github.com/lucasloyola2015)

## Soporte

Para soporte técnico o preguntas, por favor abrir un issue en el repositorio de GitHub.
