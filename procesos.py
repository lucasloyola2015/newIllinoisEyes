# procesos.py - Coordinador principal de procesos
import threading
import time
from typing import Dict, Any, Callable, List

# Importar variables globales
from global_flags import flag_pedir_junta, flag_junta_entregada

# Importar subprocesos
from procesos_feeder import ProcesoFeeder
from procesos_vision import ProcesoVision
from procesos_robot import ProcesoRobot

# Variables globales para comunicación entre procesos
# flag_pedir_junta = False
# flag_junta_entregada = False

# Estado global del proceso
_state_lock = threading.Lock()
_callback_lock = threading.Lock()
_process_thread = None
_running = True  # Siempre ejecutándose desde el inicio del sistema

# Estados del sistema
ESTADO_INICIO = "INICIO"
ESTADO_PAUSA = "PAUSA" 
ESTADO_DETENER = "DETENER"

# Estado actual del sistema
_estado_sistema = ESTADO_DETENER  # Inicia detenido

# Instancias de los subprocesos
_proceso_feeder = ProcesoFeeder()
_proceso_vision = ProcesoVision()
_proceso_robot = ProcesoRobot()

# Callbacks para notificar cambios
_update_callbacks: List[Callable] = []

def register_update_callback(callback: Callable):
    """Registra un callback para ser llamado cuando cambien los contadores."""
    with _callback_lock:
        if callback not in _update_callbacks:
            _update_callbacks.append(callback)

def unregister_update_callback(callback: Callable):
    """Elimina un callback registrado."""
    with _callback_lock:
        if callback in _update_callbacks:
            _update_callbacks.remove(callback)

def _notify_update():
    """Notifica a todos los callbacks registrados sobre el cambio de contadores."""
    with _callback_lock:
        callbacks = _update_callbacks.copy()
    
    for callback in callbacks:
        try:
            callback()
        except Exception as e:
            print(f"[procesos] Error en callback de actualización: {e}")

def _process_worker():
    """Hilo principal que se ejecuta cada 10ms y llama a las 3 rutinas secuencialmente."""
    global _running
    
    print("[procesos] Hilo principal iniciado.")
    
    while _running:
        try:
            # Ejecutar las 3 rutinas secuencialmente
            _proceso_feeder.ejecutar(_estado_sistema)
            _proceso_vision.ejecutar(_estado_sistema)
            _proceso_robot.ejecutar(_estado_sistema)
            
            # Notificar cambios SIEMPRE, no solo en INICIO
            # Esto permite ver el estado en tiempo real incluso cuando está DETENIDO
            _notify_update()
            
            # Esperar 10ms antes de la siguiente iteración
            time.sleep(0.01)  # 10ms
            
        except Exception as e:
            print(f"[procesos] Error en el hilo principal: {e}")
            time.sleep(0.01)
    
    print("[procesos] Hilo principal detenido.")

def set_estado_sistema(estado: str) -> tuple[bool, str]:
    """Establece el estado del sistema (INICIO/PAUSA/DETENER)."""
    global _estado_sistema
    
    if estado not in [ESTADO_INICIO, ESTADO_PAUSA, ESTADO_DETENER]:
        return False, f"Estado inválido: {estado}"
    
    with _state_lock:
        _estado_sistema = estado
        print(f"[procesos] Estado del sistema cambiado a: {estado}")
        
        # Si se cambia a DETENER, reiniciar contadores de todos los subprocesos
        if estado == "DETENER":
            _proceso_feeder.reiniciar()
            _proceso_vision.reiniciar()
            _proceso_robot.reiniciar()
            print("[procesos] Contadores reiniciados al cambiar a DETENER")
    
    try:
        from logger import printTerminal
        printTerminal("procesos", f"Estado del sistema: {estado}")
    except ImportError:
        print("[procesos] Logger no disponible")
    
    return True, f"Estado cambiado a {estado}"

def get_estado_sistema() -> str:
    """Obtiene el estado actual del sistema."""
    with _state_lock:
        return _estado_sistema

def start_process():
    """Inicia el hilo del proceso."""
    global _process_thread, _running
    
    with _state_lock:
        if _running and _process_thread and _process_thread.is_alive():
            return False, "El proceso ya está ejecutándose"
        
        _running = True
        _process_thread = threading.Thread(target=_process_worker, daemon=True, name="ProcessMain")
        _process_thread.start()
    
    try:
        from logger import printTerminal
        printTerminal("procesos", "Proceso principal iniciado")
    except ImportError:
        pass
    
    return True, "Proceso iniciado correctamente"

def get_process_status() -> Dict[str, Any]:
    """Obtiene el estado actual del proceso."""
    with _state_lock:
        # Obtener estados de los subprocesos
        feeder_status = _proceso_feeder.get_status()
        vision_status = _proceso_vision.get_status()
        robot_status = _proceso_robot.get_status()
        
        # Obtener marcas del PLC desde el feeder
        plc_marks = {
            "M3_SIN_STOCK_DISPONIBLE": _proceso_feeder.M3_SIN_STOCK_DISPONIBLE,
            "M4_FEEDER_HABILITADO": _proceso_feeder.M4_FEEDER_HABILITADO
        }
        
        status = {
            "running": _running,
            "estado_sistema": _estado_sistema,
            "cntFeeder": feeder_status.get("contador", 0),  # Contador opcional
            "cntVision": vision_status["contador"],
            "cntRobot": robot_status["contador"],
            "estadoFeeder": feeder_status["estado"],
            "estadoVision": vision_status["estado"],
            "estadoRobot": robot_status["estado"],
            "estadoFeederStr": feeder_status["estado_str"],
            "estadoVisionStr": vision_status["estado_str"],
            "estadoRobotStr": robot_status["estado_str"],
            "plc_connected": feeder_status.get("plc_connected", False),
            "plc_marks": plc_marks  # Nuevas marcas del PLC
        }
        return status

def get_process_config() -> Dict[str, Any]:
    """Obtiene la configuración de estados de todos los procesos."""
    config = {
        "feeder": _proceso_feeder.get_config(),
        "vision": _proceso_vision.get_config(),
        "robot": _proceso_robot.get_config()
    }
    return config

# Funciones para manejar variables globales del feeder

def is_running() -> bool:
    """Verifica si el proceso está ejecutándose."""
    with _state_lock:
        return _running

def stop_process():
    """Detiene el hilo del proceso de forma ordenada."""
    global _process_thread, _running
    
    with _state_lock:
        if not _running:
            return True, "El proceso ya está detenido"
        
        print("[procesos] Deteniendo proceso principal...")
        _running = False
    
    # Esperar a que el thread termine
    if _process_thread and _process_thread.is_alive():
        _process_thread.join(timeout=2)
        if _process_thread.is_alive():
            print("[procesos] Advertencia: El thread no terminó en el tiempo esperado")
        else:
            print("[procesos] Thread del proceso detenido correctamente")
    
    try:
        from logger import printTerminal
        printTerminal("procesos", "Proceso principal detenido")
    except ImportError:
        pass
    
    return True, "Proceso detenido correctamente"

# Iniciar el proceso automáticamente al importar el módulo
if __name__ != "__main__":
    # start_process()  # Comentado temporalmente para debug
    pass
