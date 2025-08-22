# logger.py - Sistema de terminal interno (versión simplificada)
import json
import threading
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

# Configuración
ROOT = Path(__file__).resolve().parent
LOG_FILE = ROOT / "log.json"
MAX_LINES = 5000

# Lock para thread safety
_lock = threading.RLock()

def _ensure_log_file():
    """Garantiza que el archivo log.json existe con estructura válida."""
    if not LOG_FILE.exists():
        try:
            with open(LOG_FILE, 'w', encoding='utf-8') as f:
                json.dump({"logs": []}, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[logger] Error creando log.json: {e}")

def _load_logs():
    """Carga los logs del archivo JSON."""
    try:
        _ensure_log_file()
        with open(LOG_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get("logs", [])
    except Exception as e:
        print(f"[logger] Error cargando logs: {e}")
        return []

def _save_logs(logs):
    """Guarda los logs al archivo JSON."""
    try:
        with open(LOG_FILE, 'w', encoding='utf-8') as f:
            json.dump({"logs": logs}, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[logger] Error guardando logs: {e}")

def printTerminal(log_type, message):
    """
    Función global para imprimir mensajes al terminal interno.
    
    Args:
        log_type: Tipo de mensaje (warning, error, system, rutina)
        message: Mensaje a registrar
    """
    try:
        with _lock:
            # Cargar logs existentes
            logs = _load_logs()
            
            # Crear nuevo log entry
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            log_entry = {
                "timestamp": timestamp,
                "type": str(log_type).upper(),
                "message": str(message).strip(),
                "id": len(logs) + 1
            }
            
            # Insertar al inicio (línea 0 = más nuevo)
            logs.insert(0, log_entry)
            
            # Mantener máximo de líneas
            if len(logs) > MAX_LINES:
                logs = logs[:MAX_LINES]
            
            # Guardar
            _save_logs(logs)
            
            # También imprimir a consola para debug
            print(f"[{timestamp}] [{log_type.upper()}] {message}")
            
    except Exception as e:
        # Si falla el logging, al menos imprimir a consola
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] [LOGGER_ERROR] Failed to log: {e}")
        print(f"[{timestamp}] [{log_type.upper()}] {message}")

def get_terminal_logs(limit=100, log_filter=None):
    """
    Obtiene logs del terminal con filtros opcionales.
    
    Args:
        limit: Número máximo de logs a devolver
        log_filter: Filtro por tipo (opcional)
    
    Returns:
        Lista de logs filtrados
    """
    try:
        with _lock:
            logs = _load_logs()
            
            # Filtrar por tipo si se especifica
            if log_filter and log_filter.upper() in ["WARNING", "ERROR", "SYSTEM", "RUTINA"]:
                logs = [log for log in logs if log.get("type") == log_filter.upper()]
            
            # Limitar cantidad
            return logs[:limit]
    except Exception as e:
        print(f"[logger] Error obteniendo logs: {e}")
        return []

def clear_terminal_logs():
    """Limpia todos los logs del terminal."""
    try:
        # Limpiar el archivo de logs bajo lock
        with _lock:
            _save_logs([])
    except Exception as e:
        print(f"[logger] Error limpiando logs: {e}")
        return
    # Registrar el evento *fuera* del lock para evitar interbloqueo
    try:
        printTerminal("system", "Terminal limpiado")
    except Exception as e:
        print(f"[logger] Error registrando 'Terminal limpiado': {e}")

def get_terminal_stats():
    """Obtiene estadísticas del terminal."""
    try:
        with _lock:
            logs = _load_logs()
            stats = {
                "total_logs": len(logs),
                "by_type": {}
            }
            
            for log in logs:
                log_type = log.get("type", "UNKNOWN")
                stats["by_type"][log_type] = stats["by_type"].get(log_type, 0) + 1
            
            return stats
    except Exception as e:
        print(f"[logger] Error obteniendo estadísticas: {e}")
        return {"total_logs": 0, "by_type": {}}

def init_logger():
    """Inicializa el sistema de logging."""
    try:
        _ensure_log_file()
        printTerminal("system", "Sistema de terminal iniciado")
    except Exception as e:
        print(f"[logger] Error inicializando: {e}")

# Auto-inicialización al importar
try:
    init_logger()
except Exception as e:
    print(f"[logger] Error en auto-inicialización: {e}")

# Para testing directo
if __name__ == "__main__":
    print("=== Test del sistema de logging ===")
    
    # Test básico
    printTerminal("system", "Test del sistema")
    printTerminal("warning", "Test de advertencia")
    printTerminal("error", "Test de error")
    
    # Ver logs
    logs = get_terminal_logs(5)
    print(f"\nLogs generados: {len(logs)}")
    for log in logs:
        print(f"[{log['timestamp']}] [{log['type']}] {log['message']}")
    
    # Estadísticas
    stats = get_terminal_stats()
    print(f"\nEstadísticas: {stats}")
