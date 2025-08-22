# system.py - Control del estado general del sistema
import threading
import time
from typing import Dict, Tuple, Any

# Importar el nuevo gestor de red
import network_manager

_lock = threading.Lock()
_system_thread = None
_running = False

def _system_aggregator_worker():
    """Hilo que periódicamente actualiza el estado del sistema con datos de otros managers."""
    global _running
    print("[system] Hilo agregador de estado iniciado.")
    while _running:
        try:
            # Obtener datos del network_manager
            net_status = network_manager.get_network_statuses()
            
            with _lock:
                # Actualizar el estado principal con los datos de red
                _system_state = {
                    "network": {"selected_interface": net_status["selected_interface"]},
                    "devices": net_status["devices"]
                }
            
            time.sleep(1) # El estado se actualiza cada segundo
        except Exception as e:
            print(f"[system] Error en el hilo agregador: {e}")
            time.sleep(1)
    print("[system] Hilo agregador de estado detenido.")

def start_background_threads():
    """Inicia todos los hilos de fondo."""
    global _system_thread, _running
    if _running: 
        print("[system] Los hilos de fondo ya están ejecutándose.")
        return
    
    _running = True
    
    # Iniciar el agregador de estado del sistema
    _system_thread = threading.Thread(target=_system_aggregator_worker, daemon=True, name="SystemAggregator")
    _system_thread.start()

    try:
        from logger import printTerminal
        printTerminal("system", "Hilos de fondo iniciados")
    except ImportError:
        pass

def stop_background_threads():
    """Detiene todos los hilos de fondo."""
    global _running
    if not _running: return
    
    print("[system] Deteniendo hilos de fondo...")
    _running = False

    if _system_thread and _system_thread.is_alive():
        _system_thread.join(timeout=1)
        
    try:
        from logger import printTerminal
        printTerminal("system", "Hilos de fondo detenidos")
    except ImportError:
        pass

def get_status() -> Dict[str, Any]:
    """Obtiene una copia segura del estado actual del sistema."""
    with _lock:
        return _system_state.copy() if '_system_state' in globals() else {}