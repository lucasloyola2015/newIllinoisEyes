# webserver.py (CRUD + cámara + calibración + control de sistema + terminal)
# ============================================================
# ESTRUCTURA DEL WEBSERVER:
# ============================================================
# 1. do_GET() - Maneja todas las peticiones GET
#    - Endpoints de lectura/consulta
#    - Streams de video y eventos
#    - Archivos estáticos
#
# 2. do_POST() - Maneja todas las peticiones POST  
#    - Endpoints de escritura/acción
#    - Configuraciones
#    - Comandos del sistema
#
# IMPORTANTE: Cada endpoint debe estar en UNA SOLA SECCIÓN
# NO duplicar endpoints entre GET y POST
# ============================================================

import argparse
import json
import os
import time
import urllib.parse as up
import subprocess
from http.server import SimpleHTTPRequestHandler
from socketserver import TCPServer
import threading
import signal
import sys
import socket
import traceback
from pathlib import Path

try:
    from http.server import ThreadingHTTPServer
except ImportError:
    from socketserver import ThreadingMixIn
    class ThreadingHTTPServer(ThreadingMixIn, TCPServer):
        daemon_threads = True

# --- Rutas del proyecto ---
ROOT = os.path.abspath(os.path.dirname(__file__))
os.chdir(ROOT)
print(f"[static root] {ROOT}")

CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
DEFAULT_PORT = 8000

DB_PATH = os.path.join(ROOT, "database.json")
IMG_DB_DIR = os.path.join(ROOT, "imgDatabase")
os.makedirs(IMG_DB_DIR, exist_ok=True)

# Módulos locales
import webcam_manager as cam
import aruco_manager as aruco
import contour_manager as contour
import system
import network_manager
import procesos
import global_flags

# Instancia global del PLC Manager (automático)
try:
    from PLC_LOGO_manager import get_plc_manager
    plc_manager = get_plc_manager()
    print("[webserver] PLC Manager automático inicializado")
except ImportError as e:
    plc_manager = None
    print(f"[webserver] Error importando PLC Manager: {e}")

try:
    import logger
    from logger import printTerminal
    LOGGER_AVAILABLE = True
    print("[webserver] Sistema de logging cargado correctamente")
except ImportError as e:
    LOGGER_AVAILABLE = False
    def printTerminal(log_type, message):
        timestamp = __import__('datetime').datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] [{log_type.upper()}] {message}")

# ---------------- DB helpers ----------------
def _db_load():
    if not os.path.exists(DB_PATH):
        return {"Juntas": []}
    try:
        with open(DB_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"Juntas": []}

def _db_save(db):
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    tmp = DB_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)
    os.replace(tmp, DB_PATH)

def _db_find(db, modelo):
    for i, j in enumerate(db.get("Juntas", [])):
        if (j.get("modelo") or "").strip().lower() == (modelo or "").strip().lower():
            return i, j
    return -1, None

# ============================================================
# Verificación de instancia única
# ============================================================
LOCK_FILE = os.path.join(ROOT, ".newillinoiseyes.lock")

def check_single_instance(port: int) -> bool:
    """
    Verifica que no haya otra instancia del servidor ejecutándose.
    Retorna True si es seguro continuar, False si ya hay una instancia.
    """
    try:
        # Verificar si el archivo de lock existe
        if os.path.exists(LOCK_FILE):
            # Leer información del lock
            try:
                with open(LOCK_FILE, 'r') as f:
                    lock_info = json.load(f)
                
                # Verificar si el proceso aún está ejecutándose
                pid = lock_info.get('pid')
                lock_port = lock_info.get('port')
                
                if pid and lock_port == port:
                    # Verificar si el proceso existe
                    try:
                        os.kill(pid, 0)  # No envía señal, solo verifica si existe
                        print(f"❌ Ya hay una instancia ejecutándose en el puerto {port} (PID: {pid})")
                        print(f"   Lock file: {LOCK_FILE}")
                        return False
                    except OSError:
                        # Proceso no existe, eliminar lock obsoleto
                        print(f"⚠️ Encontrado lock obsoleto, eliminando...")
                        os.remove(LOCK_FILE)
                
            except (json.JSONDecodeError, KeyError):
                # Lock file corrupto, eliminarlo
                print(f"⚠️ Lock file corrupto, eliminando...")
                os.remove(LOCK_FILE)
        
        # Verificar si el puerto está en uso
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(1)
                result = s.connect_ex(('localhost', port))
                if result == 0:
                    print(f"❌ Puerto {port} ya está en uso")
                    return False
        except Exception as e:
            print(f"⚠️ Error verificando puerto: {e}")
        
        return True
        
    except Exception as e:
        print(f"⚠️ Error verificando instancia única: {e}")
        return True  # En caso de error, permitir continuar

def create_lock_file(port: int):
    """Crea el archivo de lock con información del proceso actual."""
    try:
        lock_info = {
            'pid': os.getpid(),
            'port': port,
            'start_time': time.time(),
            'command_line': ' '.join(sys.argv)
        }
        
        with open(LOCK_FILE, 'w') as f:
            json.dump(lock_info, f, indent=2)
        
        print(f"🔒 Lock file creado: {LOCK_FILE}")
        
    except Exception as e:
        print(f"⚠️ Error creando lock file: {e}")

def remove_lock_file():
    """Elimina el archivo de lock."""
    try:
        if os.path.exists(LOCK_FILE):
            os.remove(LOCK_FILE)
            print(f"🔓 Lock file eliminado: {LOCK_FILE}")
    except Exception as e:
        print(f"⚠️ Error eliminando lock file: {e}")

# ---------------- HTTP Handler ----------------
class AppHandler(SimpleHTTPRequestHandler):
    def _send_json(self, obj, status=200):
        data = json.dumps(obj).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)



    def do_GET(self):
        """
        ============================================================
        SECCIÓN GET - ENDPOINTS DE LECTURA/CONSULTA
        ============================================================
        Aquí van TODOS los endpoints que solo leen datos:
        - Consultas de estado
        - Obtener configuraciones  
        - Streams de video
        - Archivos estáticos
        ============================================================
        """
        try:
            if self.path in ("/", "/index.html"):
                self.send_response(302)
                self.send_header("Location", "/template/main.html")
                self.end_headers()
                return

            # ============================================================
            # ENDPOINTS DE CÁMARA (GET)
            # ============================================================
            
            if self.path.startswith("/api/scan_cams"):
                devices = cam.scanWebCams()
                return self._send_json({"devices": devices})

            if self.path.startswith("/api/cam_resolutions"):
                q = up.urlparse(self.path).query
                uid = dict(up.parse_qsl(q)).get("uid")
                res = cam.get_supported_resolutions(uid) if uid else []
                return self._send_json({"resolutions": res})

            if self.path.startswith("/api/camera/config"):
                return self._send_json(cam.load_config() or {})

            if self.path.startswith("/api/auto_connect"):
                ok, err = cam.auto_connect_from_config()
                return self._send_json({"ok": ok, "error": err})

            if self.path.startswith("/api/filters/smoothing_options"):
                options = cam.get_smoothing_filter_options()
                return self._send_json({"ok": True, "options": options})

            if self.path.startswith("/api/filters/current"):
                current_filter = cam.get_current_filter()
                return self._send_json({"ok": True, "filter": current_filter})

            # ============================================================
            # Endpoints para Filtros en Cascada
            # ============================================================
            
            if self.path.startswith("/api/cascade_filters/config"):
                print("[webserver] Recibida petición GET config")
                try:
                    print("[webserver] Cargando filter_config.json...")
                    
                    # Cargar configuración desde filter_config.json
                    if os.path.exists("filter_config.json"):
                        print("[webserver] Archivo filter_config.json encontrado")
                        with open("filter_config.json", "r", encoding="utf-8") as f:
                            config = json.load(f)
                        print(f"[webserver] Configuración cargada: {len(config.get('profiles', {}))} perfiles")
                        return self._send_json({"ok": True, "config": config})
                    else:
                        # Si no existe, crear configuración por defecto
                        default_config = {
                            "active_profile": "default-balanced",
                            "profiles": {
                                "default-balanced": {
                                    "id": "default-balanced",
                                    "name": "Equilibrado",
                                    "description": "Configuración equilibrada para detección general",
                                    "is_default": True,
                                    "config": {
                                        "cascade_filters": [],
                                        "detection": {
                                            "detection_method": "MOG2",
                                            "var_threshold": 25,
                                            "detect_shadows": False,
                                            "training_time": 5000,
                                            "show_progress": True,
                                            "min_contour_area": 500,
                                            "max_contour_area": 20000
                                        }
                                    }
                                }
                            }
                        }
                        return self._send_json({"ok": True, "config": default_config})
                        
                except Exception as e:
                    error_msg = f"Error cargando configuración: {str(e)}"
                    printTerminal("error", error_msg)
                    return self._send_json({"ok": False, "message": error_msg}, 500)
            
            if self.path.startswith("/api/cascade_filters/preview"):
                q = up.urlparse(self.path).query
                params = dict(up.parse_qsl(q))
                filter_id = int(params.get("filter_id", 1))
                cam.set_preview_filter(filter_id)
                return self._send_json({"ok": True, "preview_filter": filter_id})
            
            if self.path.startswith("/api/cascade_filters/config_mode"):
                q = up.urlparse(self.path).query
                params = dict(up.parse_qsl(q))
                enabled = params.get("enabled", "false").lower() == "true"
                cam.set_config_mode(enabled)
                return self._send_json({"ok": True, "config_mode": enabled})
            
            if self.path.startswith("/api/webcam/filter_preview"):
                q = up.urlparse(self.path).query
                params = dict(up.parse_qsl(q))
                preview_mode = params.get("preview", "false").lower() == "true"
                original_mode = params.get("original", "false").lower() == "true"
                
                if preview_mode:
                    # Activar modo preview con filtros en cascada
                    cam.set_preview_mode(True)
                elif original_mode:
                    # Mostrar cámara cruda
                    cam.set_preview_mode(False)
                
                return self._send_json({"ok": True, "preview_mode": preview_mode, "original_mode": original_mode})

            # Endpoints GET para webcam
            if self.path.startswith("/api/webcam/filter"):
                # Obtener filtro actual
                current_filter = cam.get_current_filter()
                available_filters = cam.get_available_filters()
                return self._send_json({
                    "ok": True, 
                    "current_filter": current_filter,
                    "available_filters": available_filters
                })
            
            if self.path.startswith("/api/webcam/detection_method"):
                # Obtener método de detección actual
                method_info = cam.get_detection_method()
                return self._send_json({
                    "ok": True,
                    "method": method_info["method"],
                    "enabled": method_info["enabled"],
                    "params": method_info["params"]
                })
            



            




            if self.path.startswith("/api/status"):
                return self._send_json(system.get_status())

            if self.path.startswith("/api/system/network_interfaces"):
                interfaces = network_manager.get_network_interfaces()
                return self._send_json(interfaces)

            if self.path.startswith("/api/terminal/logs"):
                if not LOGGER_AVAILABLE:
                    return self._send_json({"ok": False, "error": "Sistema de logging no disponible"})
                q = up.urlparse(self.path).query
                params = dict(up.parse_qsl(q))
                limit = int(params.get("limit", 100))
                log_filter = params.get("filter")
                logs = logger.get_terminal_logs(limit=limit, log_filter=log_filter)
                return self._send_json({"ok": True, "logs": logs})

            if self.path.startswith("/api/terminal/stats"):
                if not LOGGER_AVAILABLE:
                    return self._send_json({"ok": False, "error": "Sistema de logging no disponible"})
                stats = logger.get_terminal_stats()
                return self._send_json({"ok": True, "stats": stats})

            if self.path.startswith("/api/db/list"):
                db = _db_load()
                items = sorted(db.get("Juntas", []), key=lambda x: (x.get("modelo") or "").lower())
                return self._send_json({"ok": True, "items": items})

            if self.path.startswith("/api/db/get"):
                q = up.urlparse(self.path).query
                modelo = dict(up.parse_qsl(q)).get("modelo")
                db = _db_load()
                _, item = _db_find(db, modelo)
                if item:
                    return self._send_json({"ok": True, "item": item})
                return self._send_json({"ok": False, "error": "No encontrado"}, 404)

            if self.path.startswith("/video_feed"):
                boundary = "frame"
                self.send_response(200)
                self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
                self.send_header("Pragma", "no-cache")
                self.send_header("Expires", "0")
                self.send_header("Connection", "close")
                self.send_header("Content-Type", f"multipart/x-mixed-replace; boundary={boundary}")
                self.end_headers()
                try:
                    while True:
                        buf = cam.get_jpeg()
                        if buf is None:
                            time.sleep(0.05)
                            continue
                        self.wfile.write(b"--" + boundary.encode() + b"\r\n")
                        self.wfile.write(b"Content-Type: image/jpeg\r\n")
                        self.wfile.write(f"Content-Length: {len(buf)}\r\n\r\n".encode())
                        self.wfile.write(buf)
                        self.wfile.write(b"\r\n")
                        time.sleep(0.03)
                except (BrokenPipeError, ConnectionResetError):
                    pass
                except Exception:
                    pass
                return

            if self.path.startswith("/api/process/status"):
                status = procesos.get_process_status()
                return self._send_json({"ok": True, "status": status})
            
            if self.path.startswith("/api/process/config"):
                config = procesos.get_process_config()
                return self._send_json({"ok": True, "config": config})

            if self.path.startswith("/api/webcam/area_detection"):
                print(f"[webserver] Recibida petición GET estado área de detección")
                try:
                    area_status = cam.get_area_status()
                    return self._send_json({
                        "ok": True,
                        "area_status": area_status
                    })
                except Exception as e:
                    error_msg = f"Error obteniendo estado del área: {str(e)}"
                    printTerminal("error", error_msg)
                    return self._send_json({"ok": False, "message": error_msg}, 500)

            if self.path.startswith("/api/process/stream"):
                print("[webserver] Iniciando stream SSE")
                try:
                    self.send_response(200)
                    self.send_header('Content-Type', 'text/event-stream')
                    self.send_header('Cache-Control', 'no-cache')
                    self.send_header('Connection', 'keep-alive')
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    
                    # Registrar callback para notificaciones
                    def sse_callback():
                        try:
                            status = procesos.get_process_status()
                            data = f"data: {json.dumps(status)}\n\n"
                            self.wfile.write(data.encode('utf-8'))
                            self.wfile.flush()
                        except (BrokenPipeError, ConnectionResetError, OSError) as e:
                            # Conexión cerrada por el cliente - esto es normal
                            print(f"[webserver] Cliente desconectado del SSE: {e}")
                            procesos.unregister_update_callback(sse_callback)
                            return
                        except Exception as e:
                            print(f"[webserver] Error en SSE callback: {e}")
                    
                    procesos.register_update_callback(sse_callback)
                    
                    # Mantener conexión activa
                    while True:
                        try:
                            time.sleep(1)
                            # Verificar si la conexión sigue activa
                            self.wfile.write(b": keepalive\n\n")
                            self.wfile.flush()
                        except (BrokenPipeError, ConnectionResetError, OSError) as e:
                            # Conexión cerrada - esto es normal
                            print(f"[webserver] Conexión SSE cerrada: {e}")
                            break
                        except Exception as e:
                            print(f"[webserver] Error en SSE: {e}")
                            break
                    
                    # Limpiar callback al salir
                    procesos.unregister_update_callback(sse_callback)
                    print("[webserver] Stream SSE terminado")
                    
                except (BrokenPipeError, ConnectionResetError, OSError) as e:
                    # Conexión cerrada por el cliente - esto es normal, no es un error
                    print(f"[webserver] Cliente desconectado del SSE (normal): {e}")
                except Exception as e:
                    print(f"[webserver] Error en GET /api/process/stream: {e}")
                    import traceback
                    traceback.print_exc()
                return

            if self.path.startswith("/api/plc/status"):
                print("[webserver] Recibida petición estado PLC")
                try:
                    if plc_manager is None:
                        return self._send_json({"ok": False, "message": "PLC Manager no disponible"}, 500)
                    
                    status = plc_manager.get_connection_status()
                    return self._send_json({"ok": True, "status": status})
                        
                except Exception as e:
                    error_msg = f"Error obteniendo estado PLC: {str(e)}"
                    printTerminal("error", error_msg)
                    return self._send_json({"ok": False, "message": error_msg}, 500)



            # ============================================================
            # ENDPOINTS DE FILTROS (GET)
            # ============================================================
            
            # NOTA: Los endpoints de webcam se manejan en la sección POST
            # para evitar duplicación y confusión

            # ============================================================
            # ENDPOINTS DE DETECCIÓN DE OBJETOS (GET)
            # ============================================================
            
            # NOTA: Los endpoints de webcam se manejan en la sección POST
            # para evitar duplicación y confusión

            # ============================================================
            # ENDPOINTS DE ÁREA DE DETECCIÓN (GET)
            # ============================================================
            
            # NOTA: Los endpoints de webcam se manejan en la sección POST
            # para evitar duplicación y confusión

            if self.path.startswith("/api/plc/events"):
                print("[webserver] Recibida petición eventos PLC (SSE)")
                try:
                    if plc_manager is None:
                        return self._send_json({"ok": False, "message": "PLC Manager no disponible"}, 500)
                    
                    # Configurar headers para Server-Sent Events
                    self.send_response(200)
                    self.send_header('Content-Type', 'text/event-stream')
                    self.send_header('Cache-Control', 'no-cache')
                    self.send_header('Connection', 'keep-alive')
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    
                    # Función para enviar eventos
                    def send_event(event_type, data):
                        try:
                            event_data = f"data: {json.dumps(data)}\n\n"
                            self.wfile.write(event_data.encode('utf-8'))
                            self.wfile.flush()
                        except Exception as e:
                            print(f"[webserver] Error enviando evento SSE: {e}")
                            return False
                        return True
                    
                    # Enviar estado inicial
                    status = plc_manager.get_connection_status()
                    if not send_event("connection_status", {
                        "type": "connection_status",
                        "connected": status["connected"],
                        "message": "Estado inicial"
                    }):
                        return
                    
                    # Suscribirse a eventos del PLC
                    def plc_connection_callback(connected, message):
                        event_data = {
                            "type": "connection_status",
                            "connected": connected,
                            "message": message
                        }
                        send_event("connection_status", event_data)
                    
                    plc_manager.subscribe_to_connection_events(plc_connection_callback)
                    
                    # Mantener la conexión abierta
                    try:
                        while True:
                            time.sleep(1)
                            # Verificar si el cliente se desconectó
                            try:
                                # Enviar un heartbeat cada 30 segundos
                                if int(time.time()) % 30 == 0:
                                    if not send_event("heartbeat", {"type": "heartbeat"}):
                                        break
                            except Exception:
                                break
                    except Exception as e:
                        print(f"[webserver] Error en SSE PLC: {e}")
                    finally:
                        # Desuscribirse cuando se cierre la conexión
                        plc_manager.unsubscribe_from_connection_events(plc_connection_callback)
                        
                except Exception as e:
                    error_msg = f"Error en eventos PLC: {str(e)}"
                    printTerminal("error", error_msg)
                    return self._send_json({"ok": False, "message": error_msg}, 500)

            # Servir archivos estáticos desde template/ y static/
            if self.path.startswith("/template/") or self.path.startswith("/static/") or self.path.endswith(".html"):
                # Extraer solo la ruta del archivo sin parámetros
                parsed_path = up.urlparse(self.path)
                file_path = parsed_path.path
                
                if file_path.startswith("/template/"):
                    file_path = file_path[1:]  # Remover /template/
                elif file_path.startswith("/static/"):
                    file_path = file_path[1:]  # Remover /static/
                elif file_path.startswith("/"):
                    file_path = "template" + file_path
                else:
                    file_path = "template/" + file_path
                
                try:
                    with open(file_path, 'rb') as f:
                        content = f.read()
                    
                    # Determinar content type
                    if file_path.endswith('.html'):
                        content_type = 'text/html; charset=utf-8'
                    elif file_path.endswith('.css'):
                        content_type = 'text/css'
                    elif file_path.endswith('.js'):
                        content_type = 'application/javascript'
                    elif file_path.endswith('.png'):
                        content_type = 'image/png'
                    elif file_path.endswith('.jpg') or file_path.endswith('.jpeg'):
                        content_type = 'image/jpeg'
                    else:
                        content_type = 'text/plain'
                    
                    self.send_response(200)
                    self.send_header('Content-Type', content_type)
                    self.send_header('Content-Length', str(len(content)))
                    self.end_headers()
                    self.wfile.write(content)
                    return
                    
                except FileNotFoundError:
                    self.send_response(404)
                    self.send_header('Content-Type', 'text/plain')
                    self.end_headers()
                    self.wfile.write(b'File not found')
                    return
                except Exception as e:
                    self.send_response(500)
                    self.send_header('Content-Type', 'text/plain')
                    self.end_headers()
                    self.wfile.write(f'Server error: {str(e)}'.encode())
                    return

            return super().do_GET()
        except Exception as e:
            printTerminal("error", f"Error en GET {self.path}: {str(e)}")
            return self._send_json({"ok": False, "error": "internal_error", "detail": str(e)}, 500)

    def do_POST(self):
        """
        ============================================================
        SECCIÓN POST - ENDPOINTS DE ESCRITURA/ACCIÓN
        ============================================================
        Aquí van TODOS los endpoints que modifican datos:
        - Cambiar configuraciones
        - Ejecutar comandos
        - Escribir datos
        - Acciones del sistema
        ============================================================
        """
        print(f"[webserver] POST recibido: {self.path}")
        
        try:
            length = int(self.headers.get("Content-Length", "0") or 0)
            body = self.rfile.read(length).decode("utf-8") if length > 0 else "{}"
            payload = json.loads(body or "{}")


            
            if self.path.startswith("/api/system/save_interface"):
                iface_name = payload.get("interface_name")
                if not iface_name: return self._send_json({"ok": False, "error": "Falta 'interface_name'"}, 400)
                ok, msg = network_manager.set_network_interface(iface_name)
                if ok: printTerminal("system", msg)
                else: printTerminal("error", msg)
                return self._send_json({"ok": ok, "message": msg})

            if self.path.startswith("/api/devices/save_ip"):
                device = payload.get("device")
                ip = payload.get("ip")
                if not all([device, ip]): return self._send_json({"ok": False, "error": "Faltan parámetros"}, 400)
                ok, msg = network_manager.set_device_ip(device, ip)
                if ok: printTerminal("system", msg)
                else: printTerminal("error", msg)
                return self._send_json({"ok": ok, "message": msg}, 200 if ok else 500)

            if self.path.startswith("/api/devices/ping"):
                device = payload.get("device")
                if not device: return self._send_json({"ok": False, "error": "Falta el nombre del dispositivo"}, 400)
                printTerminal("rutina", f"Haciendo ping a {device}...")
                
                # Obtener la IP del dispositivo
                device_ip = network_manager.get_device_ip(device)
                if not device_ip:
                    return self._send_json({"ok": False, "error": f"No se encontró IP para el dispositivo {device}"}, 400)
                
                success = network_manager.ping_ip(device_ip)
                if success: printTerminal("system", f"Ping a {device} ({device_ip}) exitoso.")
                else: printTerminal("warning", f"Fallo el ping a {device} ({device_ip}).")
                
                # Devolver formato que espera el frontend
                return self._send_json({
                    "ok": True, 
                    "devices": {
                        device: {
                            "status": success,
                            "ip": device_ip
                        }
                    }
                })

            if self.path.startswith("/api/plc/write"):
                print("[webserver] Recibida petición escribir PLC")
                try:
                    if plc_manager is None:
                        return self._send_json({"ok": False, "message": "PLC Manager no disponible"}, 500)
                    
                    address = payload.get("address")  # ej: "Q1", "M5"
                    valor = payload.get("valor")
                    
                    if not all([address, valor is not None]):
                        return self._send_json({"ok": False, "message": "Faltan parámetros: address, valor"}, 400)
                    
                    if valor:
                        success, message = plc_manager.write_coil(address)
                    else:
                        success, message = plc_manager.clear_coil(address)
                    
                    if success:
                        printTerminal("system", f"PLC {address} = {valor}: {message}")
                        return self._send_json({"ok": True, "message": message})
                    else:
                        printTerminal("warning", f"Error escribiendo PLC: {message}")
                        return self._send_json({"ok": False, "message": message})
                        
                except Exception as e:
                    error_msg = f"Error escribiendo PLC: {str(e)}"
                    printTerminal("error", error_msg)
                    return self._send_json({"ok": False, "message": error_msg}, 500)

            # ============================================================
            # ENDPOINTS DE CONFIGURACIÓN DE FILTROS (POST)
            # ============================================================
            
            if self.path.startswith("/api/filters/config"):
                print("[webserver] Recibida petición guardar configuración de filtros")
                try:
                    # Guardar configuración de filtros si está presente
                    if "filter_config" in payload:
                        filter_config = payload["filter_config"]
                        print(f"[webserver] Guardando configuración de filtros: {filter_config}")
                        
                        # Aplicar configuración a los filtros
                        success = cam.set_filter("detection", filter_config)
                        if success:
                            printTerminal("system", "Configuración de filtros guardada y aplicada")
                            return self._send_json({"ok": True, "message": "Configuración guardada exitosamente"})
                        else:
                            printTerminal("warning", "Error aplicando configuración de filtros")
                            return self._send_json({"ok": False, "message": "Error aplicando configuración"})
                    
                    # Otras configuraciones pueden ir aquí
                    return self._send_json({"ok": True, "message": "Configuración procesada"})
                    
                except Exception as e:
                    error_msg = f"Error guardando configuración: {str(e)}"
                    printTerminal("error", error_msg)
                    return self._send_json({"ok": False, "message": error_msg}, 500)

            # ============================================================
            # ENDPOINTS DE PERFILES (POST)
            # ============================================================
            
            if self.path.startswith("/api/profiles/create"):
                print("[webserver] Recibida petición crear perfil")
                try:
                    # Cargar configuración actual
                    config_path = os.path.join(ROOT, "filter_config.json")
                    if os.path.exists(config_path):
                        with open(config_path, "r", encoding="utf-8") as f:
                            config = json.load(f)
                    else:
                        config = {"active_profile": "default-balanced", "profiles": {}}
                    
                    # Crear nuevo perfil
                    new_profile = payload
                    profile_id = new_profile.get("id")
                    
                    if not profile_id:
                        return self._send_json({"ok": False, "error": "ID de perfil requerido"}, 400)
                    
                    # Agregar perfil a la configuración
                    config["profiles"][profile_id] = new_profile
                    
                    # Guardar configuración
                    with open(config_path, "w", encoding="utf-8") as f:
                        json.dump(config, f, ensure_ascii=False, indent=2)
                    
                    printTerminal("system", f"Perfil '{new_profile.get('name', 'Sin nombre')}' creado exitosamente")
                    return self._send_json({"ok": True, "message": "Perfil creado exitosamente"})
                    
                except Exception as e:
                    error_msg = f"Error creando perfil: {str(e)}"
                    printTerminal("error", error_msg)
                    return self._send_json({"ok": False, "error": error_msg}, 500)
            
            if self.path.startswith("/api/profiles/update"):
                print("[webserver] Recibida petición actualizar perfil")
                try:
                    # Cargar configuración actual
                    config_path = os.path.join(ROOT, "filter_config.json")
                    if os.path.exists(config_path):
                        with open(config_path, "r", encoding="utf-8") as f:
                            config = json.load(f)
                    else:
                        return self._send_json({"ok": False, "error": "Configuración no encontrada"}, 404)
                    
                    # Actualizar perfil
                    updated_profile = payload
                    profile_id = updated_profile.get("id")
                    
                    if not profile_id or profile_id not in config["profiles"]:
                        return self._send_json({"ok": False, "error": "Perfil no encontrado"}, 404)
                    
                    # Actualizar perfil
                    config["profiles"][profile_id] = updated_profile
                    
                    # Guardar configuración
                    with open(config_path, "w", encoding="utf-8") as f:
                        json.dump(config, f, ensure_ascii=False, indent=2)
                    
                    printTerminal("system", f"Perfil '{updated_profile.get('name', 'Sin nombre')}' actualizado exitosamente")
                    return self._send_json({"ok": True, "message": "Perfil actualizado exitosamente"})
                    
                except Exception as e:
                    error_msg = f"Error actualizando perfil: {str(e)}"
                    printTerminal("error", error_msg)
                    return self._send_json({"ok": False, "error": error_msg}, 500)
            
            if self.path.startswith("/api/profiles/delete/"):
                print("[webserver] Recibida petición eliminar perfil")
                try:
                    profile_id = self.path.split("/")[-1]
                    
                    # Cargar configuración actual
                    config_path = os.path.join(ROOT, "filter_config.json")
                    if os.path.exists(config_path):
                        with open(config_path, "r", encoding="utf-8") as f:
                            config = json.load(f)
                    else:
                        return self._send_json({"ok": False, "error": "Configuración no encontrada"}, 404)
                    
                    # Verificar que el perfil existe
                    if profile_id not in config["profiles"]:
                        return self._send_json({"ok": False, "error": "Perfil no encontrado"}, 404)
                    
                    # Verificar que no sea el perfil por defecto
                    profile = config["profiles"][profile_id]
                    if profile.get("is_default", False):
                        return self._send_json({"ok": False, "error": "No se puede eliminar el perfil por defecto"}, 400)
                    
                    # Eliminar perfil
                    del config["profiles"][profile_id]
                    
                    # Si era el perfil activo, cambiar a default
                    if config.get("active_profile") == profile_id:
                        config["active_profile"] = "default-balanced"
                    
                    # Guardar configuración
                    with open(config_path, "w", encoding="utf-8") as f:
                        json.dump(config, f, ensure_ascii=False, indent=2)
                    
                    printTerminal("system", f"Perfil '{profile.get('name', 'Sin nombre')}' eliminado exitosamente")
                    return self._send_json({"ok": True, "message": "Perfil eliminado exitosamente"})
                    
                except Exception as e:
                    error_msg = f"Error eliminando perfil: {str(e)}"
                    printTerminal("error", error_msg)
                    return self._send_json({"ok": False, "error": error_msg}, 500)
            
            # ============================================================
            # ENDPOINTS DE RESOLUCIÓN DUAL (POST)
            # ============================================================
            


            if self.path.startswith("/api/plc/read_inputs"):
                print("[webserver] Recibida petición leer entradas PLC")
                try:
                    if plc_manager is None:
                        return self._send_json({"ok": False, "message": "PLC Manager no disponible"}, 500)
                    
                    # Leer todas las entradas I1-I8 de una vez
                    success, inputs = plc_manager.read_all_inputs()
                    if success:
                        printTerminal("system", f"Entradas PLC leídas: {inputs}")
                        return self._send_json({"ok": True, "inputs": inputs})
                    else:
                        return self._send_json({"ok": False, "message": "Error leyendo entradas del PLC"}, 500)
                        
                except Exception as e:
                    error_msg = f"Error leyendo entradas PLC: {str(e)}"
                    printTerminal("error", error_msg)
                    return self._send_json({"ok": False, "message": error_msg}, 500)







            if self.path.startswith("/api/plc/read_all"):
                print("[webserver] Recibida petición leer todo PLC")
                try:
                    if plc_manager is None:
                        return self._send_json({"ok": False, "message": "PLC Manager no disponible"}, 500)
                    
                    # Leer todas las entradas, salidas y marcas
                    success, result = plc_manager.read_all()
                    
                    if success:
                        printTerminal("system", f"PLC leído completamente: I={result['inputs']}, Q={result['outputs']}, M={result['marks'][:8]}...")
                        return self._send_json({
                            "ok": True, 
                            "inputs": result["inputs"],
                            "outputs": result["outputs"],
                            "marks": result["marks"]
                        })
                    else:
                        error_msg = "Error leyendo datos del PLC"
                        printTerminal("warning", error_msg)
                        return self._send_json({"ok": False, "message": error_msg}, 500)
                        
                except Exception as e:
                    error_msg = f"Error leyendo todo PLC: {str(e)}"
                    printTerminal("error", error_msg)
                    return self._send_json({"ok": False, "message": error_msg}, 500)

            if self.path.startswith("/api/plc/read_outputs"):
                print("[webserver] Recibida petición leer salidas PLC")
                try:
                    if plc_manager is None:
                        return self._send_json({"ok": False, "message": "PLC Manager no disponible"}, 500)
                    
                    # Leer todas las salidas Q1-Q12
                    success, outputs = plc_manager.read_all_outputs()
                    if success:
                        printTerminal("system", f"Salidas PLC leídas: {outputs}")
                        return self._send_json({"ok": True, "outputs": outputs})
                    else:
                        return self._send_json({"ok": False, "message": "Error leyendo salidas del PLC"}, 500)
                        
                except Exception as e:
                    error_msg = f"Error leyendo salidas PLC: {str(e)}"
                    printTerminal("error", error_msg)
                    return self._send_json({"ok": False, "message": error_msg}, 500)

            if self.path.startswith("/api/plc/read_marks"):
                print("[webserver] Recibida petición leer marcas PLC")
                try:
                    if plc_manager is None:
                        return self._send_json({"ok": False, "message": "PLC Manager no disponible"}, 500)
                    
                    # Leer todas las marcas M1-M64
                    success, marks = plc_manager.read_all_marks()
                    if success:
                        printTerminal("system", f"Marcas PLC leídas: {marks[:8]}...")  # Solo mostrar primeras 8
                        return self._send_json({"ok": True, "marks": marks})
                    else:
                        return self._send_json({"ok": False, "message": "Error leyendo marcas del PLC"}, 500)
                        
                except Exception as e:
                    error_msg = f"Error leyendo marcas PLC: {str(e)}"
                    printTerminal("error", error_msg)
                    return self._send_json({"ok": False, "message": error_msg}, 500)

            if self.path.startswith("/api/feeder/pedir_junta"):
                print("[webserver] Recibida petición pedir junta")
                try:
                    # Modificar la variable global directamente
                    global_flags.flag_pedir_junta = True
                    print(f"[webserver] DEBUG: flag_pedir_junta = {global_flags.flag_pedir_junta}")
                    printTerminal("system", "Solicitud de junta enviada al feeder")
                    return self._send_json({"ok": True, "message": "Solicitud de junta enviada"})
                except Exception as e:
                    error_msg = f"Error enviando solicitud de junta: {str(e)}"
                    printTerminal("error", error_msg)
                    return self._send_json({"ok": False, "message": error_msg}, 500)


            if self.path.startswith("/api/system/reload_config"):
                """Recarga la configuración de red y reconecta dispositivos."""
                try:
                    # Recargar configuración de red
                    network_manager.initialize_network_config()
                    
                    # Recargar configuración del PLC si está disponible
                    try:
                        from PLC_LOGO_manager import reload_config as plc_reload_config
                        plc_reload_config()
                        printTerminal("system", "Configuración del PLC recargada")
                    except ImportError:
                        printTerminal("info", "PLC_LOGO_manager no disponible")
                    
                    printTerminal("system", "Configuración recargada exitosamente")
                    return self._send_json({"ok": True, "message": "Configuración recargada"})
                    
                except Exception as e:
                    error_msg = f"Error recargando configuración: {str(e)}"
                    printTerminal("error", error_msg)
                    return self._send_json({"ok": False, "error": error_msg}, 500)

            if self.path.startswith("/api/terminal/clear"):
                if not LOGGER_AVAILABLE:
                    return self._send_json({"ok": False, "error": "Sistema de logging no disponible"})
                logger.clear_terminal_logs()
                return self._send_json({"ok": True, "message": "Terminal limpiado"})

            if self.path.startswith("/api/terminal/log"):
                if not LOGGER_AVAILABLE:
                    return self._send_json({"ok": False, "error": "Sistema de logging no disponible"})
                log_type = payload.get("type", "system")
                message = payload.get("message", "")
                if not message:
                    return self._send_json({"ok": False, "error": "Mensaje requerido"}, 400)
                printTerminal(log_type, message)
                return self._send_json({"ok": True})

            if self.path.startswith("/api/connect_cam"):
                cam_id = payload.get("id")
                uid = payload.get("uid")
                w, h = payload.get("width"), payload.get("height")
                ok, err = cam.connect_by_uid(uid, w, h)
                if uid and ok:
                    cfg = cam.load_config()
                    cfg.setdefault("camera", {})["uid"] = uid
                    if "name" in payload:
                        cfg["camera"]["name"] = payload["name"]
                    if w and h:
                        cfg["camera"]["preferred_resolution"] = {"width": int(w), "height": int(h)}
                    cam.save_config(cfg)
                    printTerminal("system", f"Cámara conectada: {payload.get('name', uid)}")
                else:
                    printTerminal("error", f"Error conectando cámara: {err}")
                return self._send_json({"ok": bool(ok), "error": err if not ok else ""})

            if self.path.startswith("/api/config/save"):
                cfg = cam.load_config()
                cfg.update(payload or {})
                cam.save_config(cfg)
                return self._send_json({"ok": True})

            if self.path.startswith("/api/snapshot"):
                name = (payload.get("name") or "CalibracionEscala.png").strip()
                from pathlib import Path
                target = Path(name)
                if not target.is_absolute():
                    target = Path(ROOT) / name
                ok, path, err = cam.snapshot(str(target))
                if ok:
                    url = "/" + Path(path).name
                    printTerminal("system", f"Snapshot guardado: {Path(path).name}")
                    return self._send_json({"ok": True, "path": path, "url": url})
                else:
                    printTerminal("error", f"Error en snapshot: {err}")
                    return self._send_json({"ok": False, "error": err}, 500)

            if self.path.startswith("/api/aruco_calibrate"):
                grid, lib_size, marker_size_mm, target_id = (payload.get("grid", "4x4"), int(payload.get("lib_size", 100)), float(payload.get("marker_size_mm", 70)), int(payload.get("target_id", 0)))
                try:
                    printTerminal("rutina", f"Iniciando calibración ArUco: {grid}, {marker_size_mm}mm")
                    res = aruco.calibrate(grid, lib_size, marker_size_mm, target_id)
                    if res.get("ok"):
                        printTerminal("system", "Calibración ArUco completada exitosamente")
                    else:
                        printTerminal("error", f"Error en calibración: {res.get('message', 'Unknown')}")
                except Exception as e:
                    printTerminal("error", f"Excepción en calibración ArUco: {str(e)}")
                    res = {"ok": False, "message": f"Error interno calibrando: {e}"}
                return self._send_json(res)

            if self.path.startswith("/api/db/save"):
                item, original = (payload or {}).get("item", {}), (payload or {}).get("original")
                modelo = (item.get("modelo") or "").strip()
                if not modelo:
                    return self._send_json({"ok": False, "error": "El campo 'modelo' es obligatorio."}, 400)
                db = _db_load()
                db.setdefault("Juntas", [])
                if original and original.strip().lower() != modelo.lower():
                    idx_old, _ = _db_find(db, original)
                    if idx_old >= 0:
                        del db["Juntas"][idx_old]
                idx, _old = _db_find(db, modelo)
                action = "actualizada" if idx >= 0 else "creada"
                if idx >= 0:
                    db["Juntas"][idx] = item
                else:
                    db["Juntas"].append(item)
                _db_save(db)
                printTerminal("system", f"Junta {action}: {modelo}")
                return self._send_json({"ok": True})

            if self.path.startswith("/api/db/delete"):
                modelo = (payload or {}).get("modelo") or ""
                db = _db_load()
                idx, _old = _db_find(db, modelo)
                if idx < 0:
                    return self._send_json({"ok": False, "error": "No encontrado."}, 404)
                del db["Juntas"][idx]
                _db_save(db)
                printTerminal("warning", f"Junta eliminada: {modelo}")
                return self._send_json({"ok": True})

            if self.path.startswith("/api/db/calcular_centro"):
                modelo = (payload or {}).get("modelo") or ""
                if not modelo:
                    return self._send_json({"ok": False, "error": "Falta 'modelo'."}, 400)
                try:
                    printTerminal("rutina", f"Calculando centro para: {modelo}")
                    res = contour.calcular_centro(modelo)
                except Exception as e:
                    printTerminal("error", f"Error calculando centro {modelo}: {str(e)}")
                    res = {"ok": False, "message": f"Error interno: {e}"}
                if not res.get("ok"):
                    return self._send_json(res, 500)
                db = _db_load()
                idx, item = _db_find(db, modelo)
                if idx >= 0 and item is not None:
                    item["centroCilindros"] = {"x": res["centro"]["x"], "y": res["centro"]["y"]}
                    db["Juntas"][idx] = item
                    _db_save(db)
                    printTerminal("system", f"Centro calculado para {modelo}: ({res['centro']['x']:.2f}, {res['centro']['y']:.2f})")
                return self._send_json(res)



            if self.path.startswith("/api/process/inicio_pausa"):
                print("[webserver] Recibida petición INICIO/PAUSA")
                try:
                    estado_actual = procesos.get_estado_sistema()
                    print(f"[webserver] Estado actual: {estado_actual}")
                    
                    if estado_actual == "DETENER" or estado_actual == "PAUSA":
                        # Cambiar a INICIO
                        ok, msg = procesos.set_estado_sistema("INICIO")
                        nuevo_estado = "INICIO"
                        boton_texto = "PAUSA"
                    else:
                        # Cambiar a PAUSA
                        ok, msg = procesos.set_estado_sistema("PAUSA")
                        nuevo_estado = "PAUSA"
                        boton_texto = "INICIO"
                    
                    print(f"[webserver] set_estado_sistema retornó: ok={ok}, msg={msg}")
                    
                    status = procesos.get_process_status()
                    print(f"[webserver] get_process_status retornó: {status}")
                    
                    response = {
                        "ok": ok, 
                        "message": msg, 
                        "estado_sistema": nuevo_estado,
                        "boton_texto": boton_texto,
                        "running": status["running"]
                    }
                    print(f"[webserver] Respuesta final: {response}")
                    return self._send_json(response)
                except Exception as e:
                    print(f"[webserver] Error en inicio_pausa: {e}")
                    import traceback
                    traceback.print_exc()
                    return self._send_json({"ok": False, "message": f"Error interno: {str(e)}", "running": False})

            if self.path.startswith("/api/process/detener"):
                print("[webserver] Recibida petición DETENER")
                try:
                    ok, msg = procesos.set_estado_sistema("DETENER")
                    print(f"[webserver] set_estado_sistema retornó: ok={ok}, msg={msg}")
                    
                    status = procesos.get_process_status()
                    print(f"[webserver] get_process_status retornó: {status}")
                    
                    response = {
                        "ok": ok, 
                        "message": msg, 
                        "estado_sistema": "DETENER",
                        "boton_texto": "INICIO",
                        "running": status["running"],
                        "status": status  # Incluir el status completo para actualizar contadores
                    }
                    print(f"[webserver] Respuesta final: {response}")
                    return self._send_json(response)
                except Exception as e:
                    print(f"[webserver] Error en detener: {e}")
                    import traceback
                    traceback.print_exc()
                    return self._send_json({"ok": False, "message": f"Error interno: {str(e)}", "running": False})

            # ============================================================
            # Endpoints del Sistema de Detección de Juntas
            # ============================================================
            
            if self.path.startswith("/api/junta_detector/train_background"):
                print("[webserver] Recibida petición entrenar fondo")
                try:
                    import junta_detector as jd
                    
                    # Capturar frames para entrenamiento
                    frames = []
                    frames_needed = payload.get("frames", 30)
                    
                    # Por ahora, capturamos un solo frame
                    # En el futuro, esto se mejorará para capturar múltiples frames
                    jpeg_data = cam.get_jpeg()
                    if jpeg_data:
                        import numpy as np
                        import cv2
                        arr = np.frombuffer(jpeg_data, dtype=np.uint8)
                        frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
                        if frame is not None:
                            frames.append(frame)
                    
                    if frames:
                        result = jd.train_background(frames)
                        if result["ok"]:
                            printTerminal("system", f"Fondo entrenado: {result['message']}")
                            return self._send_json(result)
                        else:
                            printTerminal("warning", f"Error entrenando fondo: {result['message']}")
                            return self._send_json(result)
                    else:
                        return self._send_json({"ok": False, "message": "No se pudieron capturar frames"})
                        
                except Exception as e:
                    error_msg = f"Error entrenando fondo: {str(e)}"
                    printTerminal("error", error_msg)
                    return self._send_json({"ok": False, "message": error_msg}, 500)

            if self.path.startswith("/api/junta_detector/detect"):
                print("[webserver] Recibida petición detectar junta")
                try:
                    import junta_detector as jd
                    
                    modelo = payload.get("modelo", "TC-124-15")
                    
                    # Capturar frame actual
                    jpeg_data = cam.get_jpeg()
                    if not jpeg_data:
                        return self._send_json({"ok": False, "message": "No hay imagen disponible"})
                    
                    import numpy as np
                    import cv2
                    arr = np.frombuffer(jpeg_data, dtype=np.uint8)
                    frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
                    
                    if frame is None:
                        return self._send_json({"ok": False, "message": "No se pudo decodificar la imagen"})
                    
                    # Detectar junta
                    result = jd.detect_junta(frame, modelo)
                    
                    if result["ok"]:
                        printTerminal("system", f"Junta detectada: {result['message']}")
                        return self._send_json(result)
                    else:
                        # Guardar fallo
                        timestamp = __import__('datetime').datetime.now().strftime("%Y%m%d_%H%M%S")
                        filename = f"{timestamp}.png"
                        jd.save_failure_image(frame, filename)
                        jd.log_failure(result["message"], result.get("similarity_score", 0.0), modelo)
                        
                        printTerminal("warning", f"Fallo en detección: {result['message']}")
                        return self._send_json(result)
                        
                except Exception as e:
                    error_msg = f"Error detectando junta: {str(e)}"
                    printTerminal("error", error_msg)
                    return self._send_json({"ok": False, "message": error_msg}, 500)

            if self.path.startswith("/api/junta_detector/anomalies"):
                print("[webserver] Recibida petición verificar anomalías")
                try:
                    import junta_detector as jd
                    
                    # Capturar frame actual
                    jpeg_data = cam.get_jpeg()
                    if not jpeg_data:
                        return self._send_json({"ok": False, "message": "No hay imagen disponible"})
                    
                    import numpy as np
                    import cv2
                    arr = np.frombuffer(jpeg_data, dtype=np.uint8)
                    frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
                    
                    if frame is None:
                        return self._send_json({"ok": False, "message": "No se pudo decodificar la imagen"})
                    
                    # Verificar anomalías
                    result = jd.check_anomalies(frame)
                    
                    if result["ok"]:
                        if result["has_anomaly"]:
                            printTerminal("warning", f"Anomalía detectada: {result['message']}")
                        else:
                            printTerminal("system", f"Sin anomalías: {result['message']}")
                        return self._send_json(result)
                    else:
                        printTerminal("warning", f"Error verificando anomalías: {result['message']}")
                        return self._send_json(result)
                        
                except Exception as e:
                    error_msg = f"Error verificando anomalías: {str(e)}"
                    printTerminal("error", error_msg)
                    return self._send_json({"ok": False, "message": error_msg}, 500)

            if self.path.startswith("/api/junta_detector/status"):
                print("[webserver] Recibida petición estado del detector")
                try:
                    import junta_detector as jd
                    status = jd.get_status()
                    return self._send_json({"ok": True, "status": status})
                except Exception as e:
                    error_msg = f"Error obteniendo estado: {str(e)}"
                    printTerminal("error", error_msg)
                    return self._send_json({"ok": False, "message": error_msg}, 500)

            if self.path.startswith("/api/webcam/object_detection"):
                print("[webserver] Recibida petición detección de objetos")
                try:
                    if self.command == "GET":
                        # Obtener estado del aprendizaje del fondo
                        bg_status = cam.get_background_learning_status()
                        return self._send_json({
                            "ok": True,
                            "is_learning": bg_status["is_learning"],
                            "has_model": bg_status["has_model"]
                        })
                    elif self.command == "POST":
                        # Acciones de detección de objetos
                        action = payload.get("action")
                        
                        if action == "toggle_learning":
                            # Mantener compatibilidad con el sistema anterior
                            is_learning = cam.toggle_background_learning()
                            status = "iniciado" if is_learning else "detenido"
                            printTerminal("system", f"Aprendizaje del fondo {status}")
                            return self._send_json({
                                "ok": True, 
                                "message": f"Aprendizaje del fondo {status}",
                                "is_learning": is_learning
                            })
                        elif action == "start_learning":
                            # Nuevo sistema de aprendizaje automático
                            training_time = payload.get("training_time", 5000)  # ms por defecto
                            printTerminal("system", f"Iniciando aprendizaje automático por {training_time}ms")
                            
                            # Iniciar aprendizaje
                            success = cam.start_background_learning()
                            if success:
                                # Programar detención automática
                                def stop_after_time():
                                    time.sleep(training_time / 1000.0)  # Convertir ms a segundos
                                    cam.stop_background_learning()
                                    printTerminal("system", f"Aprendizaje automático completado después de {training_time}ms")
                                
                                # Ejecutar en thread separado para no bloquear
                                threading.Thread(target=stop_after_time, daemon=True).start()
                                
                                return self._send_json({
                                    "ok": True,
                                    "message": f"Aprendizaje automático iniciado por {training_time}ms",
                                    "training_time": training_time
                                })
                            else:
                                return self._send_json({"ok": False, "error": "No se pudo iniciar el aprendizaje"}, 400)
                                
                        elif action == "stop_learning":
                            # Detener aprendizaje manualmente
                            success = cam.stop_background_learning()
                            if success:
                                printTerminal("system", "Aprendizaje del fondo detenido manualmente")
                                return self._send_json({
                                    "ok": True,
                                    "message": "Aprendizaje detenido"
                                })
                            else:
                                return self._send_json({"ok": False, "error": "No se pudo detener el aprendizaje"}, 400)
                        else:
                            return self._send_json({"ok": False, "error": "Acción no válida"}, 400)
                        
                except Exception as e:
                    error_msg = f"Error en detección de objetos: {str(e)}"
                    printTerminal("error", error_msg)
                    return self._send_json({"ok": False, "message": error_msg}, 500)

            if self.path.startswith("/api/webcam/debug_knn"):
                print("[webserver] Recibida petición debug KNN")
                try:
                    from image_analisis.detection import debug_knn_detection
                    debug_info = debug_knn_detection()
                    return self._send_json({
                        "ok": True,
                        "debug_info": debug_info
                    })
                except Exception as e:
                    error_msg = f"Error en debug KNN: {str(e)}"
                    printTerminal("error", error_msg)
                    return self._send_json({"ok": False, "message": error_msg}, 500)

            if self.path.startswith("/api/webcam/detection_method"):
                print("[webserver] Recibida petición método de detección")
                try:
                    if self.command == "GET":
                        # Obtener método de detección actual
                        method_info = cam.get_detection_method()
                        return self._send_json({
                            "ok": True,
                            "method": method_info["method"],
                            "enabled": method_info["enabled"],
                            "params": method_info["params"]
                        })
                    elif self.command == "POST":
                        # Configurar método de detección
                        method = payload.get("method")
                        params = payload.get("params", {})
                        enabled = payload.get("enabled", True)
                        
                        if not method:
                            return self._send_json({"ok": False, "error": "method requerido"}, 400)
                        
                        success, message = cam.set_detection_method(method, params, enabled)
                        if success:
                            status = "habilitado" if enabled else "deshabilitado"
                            printTerminal("system", f"Método de detección {method} {status}")
                            return self._send_json({
                                "ok": True, 
                                "message": message,
                                "method": method,
                                "enabled": enabled
                            })
                        else:
                            return self._send_json({"ok": False, "error": message}, 400)
                        
                except Exception as e:
                    error_msg = f"Error en método de detección: {str(e)}"
                    printTerminal("error", error_msg)
                    return self._send_json({"ok": False, "message": error_msg}, 500)

            if self.path.startswith("/api/detection/algorithm_config"):
                print("[webserver] Recibida petición configuración de algoritmo")
                try:
                    if self.command == "GET":
                        # Obtener configuración actual del algoritmo
                        algorithm = payload.get("algorithm")
                        if not algorithm:
                            return self._send_json({"ok": False, "error": "algorithm requerido"}, 400)
                        
                        # Obtener configuración desde el sistema
                        config = cam.get_algorithm_config(algorithm)
                        return self._send_json({
                            "ok": True,
                            "algorithm": algorithm,
                            "config": config
                        })
                    elif self.command == "POST":
                        # Guardar configuración del algoritmo
                        algorithm = payload.get("algorithm")
                        config = payload.get("config", {})
                        
                        if not algorithm:
                            return self._send_json({"ok": False, "error": "algorithm requerido"}, 400)
                        
                        success, message = cam.set_algorithm_config(algorithm, config)
                        if success:
                            printTerminal("system", f"Configuración de {algorithm} guardada")
                            return self._send_json({
                                "ok": True, 
                                "message": message,
                                "algorithm": algorithm
                            })
                        else:
                            return self._send_json({"ok": False, "error": message}, 400)
                        
                except Exception as e:
                    error_msg = f"Error en configuración de algoritmo: {str(e)}"
                    printTerminal("error", error_msg)
                    return self._send_json({"ok": False, "message": error_msg}, 500)

            if self.path.startswith("/api/detection/learning_config"):
                print("[webserver] Recibida petición configuración de aprendizaje")
                try:
                    if self.command == "GET":
                        # Obtener configuración de aprendizaje actual
                        learning_config = cam.get_learning_config()
                        return self._send_json({
                            "ok": True,
                            "config": learning_config
                        })
                    elif self.command == "POST":
                        # Guardar configuración de aprendizaje
                        learning_config = payload
                        
                        success, message = cam.set_learning_config(learning_config)
                        if success:
                            printTerminal("system", "Configuración de aprendizaje guardada")
                            return self._send_json({
                                "ok": True, 
                                "message": message
                            })
                        else:
                            return self._send_json({"ok": False, "error": message}, 400)
                        
                except Exception as e:
                    error_msg = f"Error en configuración de aprendizaje: {str(e)}"
                    printTerminal("error", error_msg)
                    return self._send_json({"ok": False, "message": error_msg}, 500)

            # ============================================================
            # ENDPOINTS DE FILTROS (POST)
            # ============================================================
            
            if self.path.startswith("/api/webcam/filter"):
                print("[webserver] Recibida petición filtro webcam")
                try:
                    if self.command == "GET":
                        # Obtener filtro actual
                        current_filter = cam.get_current_filter()
                        available_filters = cam.get_available_filters()
                        return self._send_json({
                            "ok": True, 
                            "current_filter": current_filter,
                            "available_filters": available_filters
                        })
                    elif self.command == "POST":
                        # Cambiar filtro
                        filter_name = payload.get("filter_name")
                        params = payload.get("params", {})
                        
                        if not filter_name:
                            return self._send_json({"ok": False, "error": "filter_name requerido"}, 400)
                        
                        success = cam.set_filter(filter_name, params)
                        if success:
                            printTerminal("system", f"Filtro webcam cambiado a {filter_name}")
                            return self._send_json({"ok": True, "message": f"Filtro cambiado a {filter_name}"})
                        else:
                            return self._send_json({"ok": False, "error": "Filtro no válido"}, 400)
                            
                except Exception as e:
                    error_msg = f"Error en filtro webcam: {str(e)}"
                    printTerminal("error", error_msg)
                    return self._send_json({"ok": False, "message": error_msg}, 500)

            if self.path.startswith("/api/filters/smoothing"):
                print("[webserver] Recibida petición cambio filtro suavizado")
                try:
                    smoothing_type = payload.get("smoothing_filter")
                    
                    if not smoothing_type:
                        return self._send_json({"ok": False, "error": "smoothing_filter requerido"}, 400)
                    
                    # Obtener filtro actual y actualizar solo el parámetro de suavizado
                    current_filter = cam.get_current_filter()
                    current_params = current_filter.get("params", {})
                    current_params["smoothing_filter"] = smoothing_type
                    
                    success = cam.set_filter(current_filter["name"], current_params)
                    if success:
                        printTerminal("system", f"Filtro de suavizado cambiado a {smoothing_type}")
                        return self._send_json({"ok": True, "message": f"Filtro de suavizado cambiado a {smoothing_type}"})
                    else:
                        return self._send_json({"ok": False, "error": "Error cambiando filtro de suavizado"}, 400)
                        
                except Exception as e:
                    error_msg = f"Error en filtro de suavizado: {str(e)}"
                    printTerminal("error", error_msg)
                    return self._send_json({"ok": False, "message": error_msg}, 500)

            # ============================================================
            # ENDPOINTS DE FILTROS EN CASCADA (POST)
            # ============================================================
            
            if self.path.startswith("/api/cascade_filters/update"):
                print("[webserver] Recibida petición actualizar filtro en cascada")
                try:
                    filter_id = payload.get("filter_id")
                    filter_type = payload.get("filter_type")
                    params = payload.get("params", {})
                    
                    if not all([filter_id, filter_type]):
                        return self._send_json({"ok": False, "error": "filter_id y filter_type requeridos"}, 400)
                    
                    success = cam.update_cascade_filter(filter_id, filter_type, params)
                    if success:
                        printTerminal("system", f"Filtro en cascada {filter_id} actualizado: {filter_type}")
                        return self._send_json({"ok": True, "message": f"Filtro {filter_id} actualizado"})
                    else:
                        return self._send_json({"ok": False, "error": "Error actualizando filtro"}, 400)
                        
                except Exception as e:
                    error_msg = f"Error actualizando filtro en cascada: {str(e)}"
                    printTerminal("error", error_msg)
                    return self._send_json({"ok": False, "message": error_msg}, 500)
            
            if self.path.startswith("/api/cascade_filters/enable"):
                print("[webserver] Recibida petición habilitar/deshabilitar filtro en cascada")
                try:
                    filter_id = payload.get("filter_id")
                    enabled = payload.get("enabled")
                    
                    if filter_id is None or enabled is None:
                        return self._send_json({"ok": False, "error": "filter_id y enabled requeridos"}, 400)
                    
                    success = cam.enable_cascade_filter(filter_id, enabled)
                    if success:
                        status = "habilitado" if enabled else "deshabilitado"
                        printTerminal("system", f"Filtro en cascada {filter_id} {status}")
                        return self._send_json({"ok": True, "message": f"Filtro {filter_id} {status}"})
                    else:
                        return self._send_json({"ok": False, "error": "Error cambiando estado del filtro"}, 400)
                        
                except Exception as e:
                    error_msg = f"Error cambiando estado del filtro en cascada: {str(e)}"
                    printTerminal("error", error_msg)
                    return self._send_json({"ok": False, "message": error_msg}, 500)
            
            if self.path.startswith("/api/cascade_filters/save"):
                print("[webserver] Recibida petición guardar configuración de filtros en cascada")
                try:
                    # Recibir configuración completa del frontend
                    config_data = payload
                    
                    # Guardar configuración directamente en el archivo JSON
                    from datetime import datetime
                    
                    # Agregar timestamp de actualización
                    config_data["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    
                    # Guardar en filter_config.json
                    with open("filter_config.json", "w", encoding="utf-8") as f:
                        json.dump(config_data, f, indent=2, ensure_ascii=False)
                    
                    printTerminal("system", "Configuración completa guardada")
                    return self._send_json({"ok": True, "message": "Configuración guardada"})
                        
                except Exception as e:
                    error_msg = f"Error guardando configuración: {str(e)}"
                    printTerminal("error", error_msg)
                    return self._send_json({"ok": False, "message": error_msg}, 500)
            
            if self.path.startswith("/api/webcam/filter_preview"):
                print("[webserver] Recibida petición POST filter_preview")
                try:
                    filter_name = payload.get("filter_name")
                    cascade_preview = payload.get("cascade_preview", [])
                    
                    if filter_name == "original" and cascade_preview:
                        # Configurar preview con filtros específicos
                        success = cam.set_cascade_preview_filters(cascade_preview)
                        if success:
                            printTerminal("system", f"Preview configurado con filtros: {cascade_preview}")
                            return self._send_json({"ok": True, "message": "Preview configurado"})
                        else:
                            return self._send_json({"ok": False, "error": "Error configurando preview"}, 400)
                    else:
                        # Configuración normal
                        success = cam.set_preview_mode(filter_name == "original")
                        if success:
                            return self._send_json({"ok": True, "message": "Modo configurado"})
                        else:
                            return self._send_json({"ok": False, "error": "Error configurando modo"}, 400)
                        
                except Exception as e:
                    error_msg = f"Error configurando preview: {str(e)}"
                    printTerminal("error", error_msg)
                    return self._send_json({"ok": False, "message": error_msg}, 500)

            # ============================================================
            # ENDPOINTS DE SNAPSHOOT Y COMPARACIÓN (POST)
            # ============================================================
            
            if self.path.startswith("/api/webcam/snapshoot"):
                print(f"[webserver] Recibida petición POST snapshoot")
                try:
                    # Tomar snapshoot del objeto más grande detectado
                    success, message = cam.take_snapshot_with_mask()
                    if success:
                        printTerminal("system", f"Snapshoot: {message}")
                        return self._send_json({
                            "ok": True, 
                            "message": message
                        })
                    else:
                        return self._send_json({
                            "ok": False, 
                            "message": message
                        }, 400)
                except Exception as e:
                    error_msg = f"Error en snapshoot: {str(e)}"
                    printTerminal("error", error_msg)
                    return self._send_json({"ok": False, "message": error_msg}, 500)
            
            if self.path.startswith("/api/webcam/compare"):
                print(f"[webserver] Recibida petición POST compare")
                try:
                    # Limpiar modo snapshoot y volver al video normal
                    cam.clear_snapshot_mode()
                    printTerminal("system", "Modo snapshoot desactivado, volviendo al video")
                    return self._send_json({
                        "ok": True, 
                        "message": "Modo snapshoot desactivado, volviendo al video"
                    })
                except Exception as e:
                    error_msg = f"Error en comparación: {str(e)}"
                    printTerminal("error", error_msg)
                    return self._send_json({"ok": False, "message": error_msg}, 500)

            # ============================================================
            # ENDPOINTS DE ÁREA DE DETECCIÓN (POST)
            # ============================================================
            
            if self.path.startswith("/api/webcam/area_detection"):
                print(f"[webserver] Recibida petición detección en área")
                try:
                    # Acciones de área de detección
                    action = payload.get("action")
                    
                    if action == "start_drawing":
                        success = cam.start_area_drawing()
                        printTerminal("system", "Iniciando dibujo de área")
                        return self._send_json({
                            "ok": True, 
                            "message": "Dibujo de área iniciado"
                        })
                    elif action == "stop_drawing":
                        success = cam.stop_area_drawing()
                        printTerminal("system", "Deteniendo dibujo de área")
                        return self._send_json({
                            "ok": True, 
                            "message": "Dibujo de área detenido"
                        })
                    elif action == "add_point":
                        x = payload.get("x")
                        y = payload.get("y")
                        if x is not None and y is not None:
                            success = cam.add_area_point(int(x), int(y))
                            return self._send_json({
                                "ok": True, 
                                "message": f"Punto agregado: ({x}, {y})"
                            })
                        else:
                            return self._send_json({"ok": False, "error": "Coordenadas x, y requeridas"}, 400)
                    elif action == "close_area":
                        printTerminal("system", "Intentando cerrar área de detección...")
                        
                        # Verificar estado actual del área
                        area_status = cam.get_area_status()
                        printTerminal("system", f"Estado del área: {area_status}")
                        
                        success = cam.close_area()
                        if success:
                            printTerminal("system", "Área cerrada y máscara generada exitosamente")
                            return self._send_json({
                                "ok": True, 
                                "message": "Área cerrada y máscara generada exitosamente"
                            })
                        else:
                            printTerminal("error", "No se pudo cerrar el área - verificar puntos mínimos")
                            return self._send_json({"ok": False, "error": "No se pudo cerrar el área - se necesitan al menos 3 puntos"}, 400)

                    elif action == "save_polygon":
                        success = cam.save_polygon_to_config()
                        if success:
                            printTerminal("system", "Polígono guardado en configuración")
                            return self._send_json({
                                "ok": True, 
                                "message": "Polígono guardado en configuración"
                            })
                        else:
                            return self._send_json({
                                "ok": False, 
                                "message": "No se pudo guardar el polígono"
                            }, 400)
                    elif action == "load_polygon":
                        success = cam.load_polygon_from_config()
                        if success:
                            printTerminal("system", "Polígono cargado desde configuración")
                            return self._send_json({
                                "ok": True, 
                                "message": "Polígono cargado desde configuración"
                            })
                        else:
                            return self._send_json({
                                "ok": False, 
                                "message": "No se pudo cargar el polígono"
                            }, 400)
                    elif action == "toggle_drawing":
                        # Alternar entre modo dibujo y modo normal
                        current_status = cam.get_area_status()
                        if current_status["is_drawing"]:
                            success = cam.stop_area_drawing()
                            printTerminal("system", "Modo dibujo desactivado")
                            return self._send_json({
                                "ok": True, 
                                "is_drawing": False,
                                "message": "Modo dibujo desactivado"
                            })
                        else:
                            success = cam.start_area_drawing()
                            printTerminal("system", "Modo dibujo activado")
                            return self._send_json({
                                "ok": True, 
                                "is_drawing": True,
                                "message": "Modo dibujo activado"
                            })


                    else:
                        return self._send_json({"ok": False, "error": "Acción no válida"}, 400)
                        
                except Exception as e:
                    error_msg = f"Error en detección de área: {str(e)}"
                    printTerminal("error", error_msg)
                    return self._send_json({"ok": False, "message": error_msg}, 500)

            self.send_error(404, "Not Found")
        except Exception as e:
            printTerminal("error", f"Error en POST {self.path}: {str(e)}")
            return self._send_json({"ok": False, "error": "internal_error", "detail": str(e)}, 500)

    def handle_one_request(self):
        """Maneja una petición HTTP con mejor manejo de errores durante el cierre."""
        try:
            self.raw_requestline = self.rfile.readline(65537)
            if len(self.raw_requestline) > 65536:
                self.requestline = ''
                self.request_version = ''
                self.command = ''
                self.send_error(414)
                return
            if not self.raw_requestline:
                self.close_connection = True
                return
            if not self.parse_request():
                # An error code has been sent, just exit
                return
            # Llamar al método apropiado según el comando HTTP
            if self.command == "GET":
                self.do_GET()
            elif self.command == "POST":
                self.do_POST()
            else:
                self.send_error(501, f"Unsupported method ({self.command})")
        except ConnectionAbortedError:
            # Conexión cerrada por el cliente durante el cierre del servidor
            # Esto es normal durante el shutdown, no es un error
            pass
        except ConnectionResetError:
            # Conexión reseteada por el cliente
            # También normal durante el cierre
            pass
        except (socket.error, OSError) as e:
            # Otros errores de socket durante el cierre
            if "10053" in str(e) or "10054" in str(e):
                # Errores de conexión cerrada - normales durante shutdown
                pass
            else:
                # Otros errores de socket - reportar
                print(f"[webserver] Error de socket: {e}")
        except Exception as e:
            # Otros errores - reportar
            print(f"[webserver] Error en handle_one_request: {e}")
        finally:
            self.close_connection = True

# ---------------- Lógica Principal ----------------
httpd = None

def launch_chrome(url: str, kiosk: bool = False, zoom: float = 1.0):
    try:
        print(f"[launch_chrome] Iniciando Chrome - kiosk={kiosk}, zoom={zoom}")
        print(f"[launch_chrome] URL: {url}")
        print(f"[launch_chrome] CHROME_PATH: {CHROME_PATH}")
        
        # Verificar si Chrome existe
        if not os.path.exists(CHROME_PATH):
            printTerminal("error", f"Chrome no encontrado en: {CHROME_PATH}")
            return None
            
        profile_dir = os.path.join(ROOT, ".chrome_kiosk_profile")
        os.makedirs(profile_dir, exist_ok=True)
        print(f"[launch_chrome] Profile dir: {profile_dir}")
        
        # Agregar argumentos para identificar la ventana específica
        window_name = "NewIllinoisEyes"
        args = [
            CHROME_PATH, f"--user-data-dir={profile_dir}",
            "--no-first-run", "--no-default-browser-check",
            "--disable-features=Translate,HardwareMediaKeyHandling",
            "--disable-infobars", "--disable-notifications",
            "--autoplay-policy=no-user-gesture-required", "--fast-start",
            "--new-window", f"--force-device-scale-factor={zoom}",
            f"--app-name={window_name}",  # Identificar la ventana
            "--remote-debugging-port=0"  # Puerto de debugging para control
        ]
        if kiosk:
            args += ["--kiosk", "--incognito", f"--app={url}", "--start-fullscreen"]
            print(f"[launch_chrome] Modo kiosco activado")
        else:
            args += [url]
            print(f"[launch_chrome] Modo normal")
            
        print(f"[launch_chrome] Comando completo: {' '.join(args)}")
        
        process = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        printTerminal("system", "Chrome lanzado correctamente")
        print(f"[launch_chrome] Proceso iniciado con PID: {process.pid}")
        return process
    except FileNotFoundError:
        printTerminal("error", f"Chrome no encontrado en: {CHROME_PATH}")
        print(f"[launch_chrome] ERROR: Chrome no encontrado")
    except Exception as e:
        printTerminal("error", f"Error lanzando Chrome: {str(e)}")
        print(f"[launch_chrome] ERROR: {str(e)}")
        print(f"[launch_chrome] Traceback: {traceback.format_exc()}")
    return None

def close_chrome_window():
    """Cierra la ventana específica de Chrome del webserver."""
    try:
        print("[close_chrome] Intentando cerrar ventana de Chrome...")
        
        # Método 1: Buscar por título de ventana
        cmd = f'taskkill /F /FI "WINDOWTITLE eq NewIllinoisEyes*" /T'
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        
        if result.returncode == 0:
            print("[close_chrome] Ventana de Chrome cerrada por título")
            printTerminal("system", "Ventana de Chrome cerrada")
            return
            
        # Método 2: Buscar por argumentos de línea de comandos
        cmd = f'wmic process where "commandline like \'%chrome_kiosk_profile%\'" call terminate'
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        
        if result.returncode == 0:
            print("[close_chrome] Ventana de Chrome cerrada por perfil")
            printTerminal("system", "Ventana de Chrome cerrada")
            return
            
        # Método 3: Buscar por puerto de debugging
        cmd = f'wmic process where "commandline like \'%remote-debugging-port%\'" call terminate'
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        
        if result.returncode == 0:
            print("[close_chrome] Ventana de Chrome cerrada por debugging port")
            printTerminal("system", "Ventana de Chrome cerrada")
            return
            
        print("[close_chrome] No se encontró ventana específica de Chrome para cerrar")
            
    except Exception as e:
        print(f"[close_chrome] Error cerrando Chrome: {e}")
        printTerminal("error", f"Error cerrando Chrome: {e}")

def monitor_chrome_process(chrome_process, shutdown_callback):
    """Espera a que Chrome termine y luego llama al apagado completo del sistema."""
    print("[monitor] Hilo vigilante de Chrome iniciado.")
    
    try:
        # Esperar a que Chrome termine
        chrome_process.wait()
        print("[monitor] Proceso de Chrome cerrado. Iniciando apagado completo del sistema...")
        printTerminal("system", "Ventana de Chrome cerrada, apagando sistema completo...")
        
        # Llamar al shutdown callback que cerrará todo ordenadamente
        shutdown_callback()
        
        # Forzar salida del programa después de un breve delay
        time.sleep(1)
        print("[monitor] Forzando salida del programa...")
        os._exit(0)
        
    except Exception as e:
        print(f"[monitor] Error en monitoreo de Chrome: {e}")
        # En caso de error, también cerrar el sistema
        shutdown_callback()
        os._exit(1)

def shutdown_server(signum=None, frame=None):
    """Función unificada para apagar todos los servicios de forma ordenada."""
    global httpd
    print("\n🛑 Recibida señal de apagado - cerrando servidor...")
    
    # 0. Cerrar ventana de Chrome
    close_chrome_window()
    
    # 1. Detener threads de fondo del sistema
    system.stop_background_threads()
    
    # 2. Detener el proceso principal
    try:
        from procesos import stop_process
        stop_process()
        print("✅ Proceso principal detenido")
    except Exception as e:
        print(f"⚠️ Error deteniendo proceso principal: {e}")
    
    # 3. Detener la webcam
    try:
        from webcam_manager import stop_webcam
        stop_webcam()
        print("✅ Webcam detenida")
    except Exception as e:
        print(f"⚠️ Error deteniendo webcam: {e}")
    
    # 4. Cerrar el PLC manager
    try:
        from PLC_LOGO_manager import shutdown as plc_shutdown
        plc_shutdown()
        print("✅ PLC manager cerrado")
    except Exception as e:
        print(f"⚠️ Error cerrando PLC manager: {e}")
    
    # 5. Cerrar el servidor HTTP
    if httpd:
        threading.Thread(target=httpd.shutdown, daemon=True).start()
    
    # 6. Eliminar lock file
    remove_lock_file()
    
    printTerminal("system", "Servidor cerrado correctamente")
    print("✅ Servidor cerrado correctamente")

def main():
    global httpd
    parser = argparse.ArgumentParser(description="Web Server + MJPEG + APIs + Terminal")
    parser.add_argument("-p", "--port", type=int, default=DEFAULT_PORT, help="Puerto")
    parser.add_argument("-k", "--kiosk", action="store_true", help="Lanzar en modo kiosco")
    parser.add_argument("--zoom", type=float, default=None, help="Factor de zoom para Chrome")
    parser.add_argument("--force", action="store_true", help="Forzar inicio ignorando instancia existente")
    args = parser.parse_args()
    
    print(f"[main] Argumentos procesados:")
    print(f"[main] - Puerto: {args.port}")
    print(f"[main] - Kiosco: {args.kiosk}")
    print(f"[main] - Zoom: {args.zoom}")
    print(f"[main] - Force: {args.force}")

    # Verificar instancia única (a menos que se use --force)
    if not args.force:
        if not check_single_instance(args.port):
            print("\n💡 Para forzar el inicio, usa: --force")
            sys.exit(1)
    
    # Crear lock file
    create_lock_file(args.port)
    
    # Configurar manejadores de señales para limpiar al salir
    def cleanup_handler(signum, frame):
        remove_lock_file()
        shutdown_server(signum, frame)
    
    signal.signal(signal.SIGINT, cleanup_handler)
    if hasattr(signal, 'SIGTERM'): 
        signal.signal(signal.SIGTERM, cleanup_handler)

    system.start_background_threads()
    
    # Cargar polígono automáticamente al iniciar
    try:
        print("[main] Cargando polígono desde configuración...")
        success = cam.load_polygon_from_config()
        if success:
            print("[main] ✅ Polígono cargado exitosamente")
        else:
            print("[main] ⚠️ No se pudo cargar polígono, usando área completa por defecto")
    except Exception as e:
        print(f"[main] ⚠️ Error cargando polígono: {e}")
    
    # Verificar estado del modelo de fondo
    try:
        cam.check_background_model_status()
    except Exception as e:
        print(f"[main] ⚠️ Error verificando modelo de fondo: {e}")
    
    cfg = cam.load_config()
    zoom = args.zoom if args.zoom is not None else float(cfg.get("ui", {}).get("zoom_factor", 1.0))
    if args.zoom is not None:
        cfg.setdefault("ui", {})["zoom_factor"] = zoom
        cam.save_config(cfg)
    
    server_address = ("0.0.0.0", int(args.port))
    httpd = ThreadingHTTPServer(server_address, AppHandler)
    url = f"http://127.0.0.1:{args.port}/template/main.html"
    printTerminal("system", f"Servidor web iniciado en puerto {args.port}")

    print(f"[main] Lanzando Chrome con kiosk={args.kiosk}, zoom={zoom}")
    chrome_process = launch_chrome(url, kiosk=args.kiosk, zoom=zoom)
    print(f"[main] Chrome process: {chrome_process}")

    # Siempre monitorear Chrome, tanto en modo kiosco como normal
    if chrome_process:
        monitor_thread = threading.Thread(
            target=monitor_chrome_process,
            args=(chrome_process, shutdown_server),
            daemon=True, name="ChromeMonitor"
        )
        monitor_thread.start()
        print(f"[main] Monitor de Chrome iniciado (kiosk={args.kiosk})")
    else:
        print("[main] No se pudo iniciar Chrome, continuando sin monitor")

    try:
        print("🚀 Servidor ejecutándose... Presiona Ctrl+C para detener")
        httpd.serve_forever()
    except Exception as e:
        if "cannot switch to a different thread" not in str(e):
             printTerminal("error", f"Error principal del servidor: {str(e)}")
    finally:
        print("Saliendo del script principal.")
        remove_lock_file()
        os._exit(0)

if __name__ == "__main__":
    main()