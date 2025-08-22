# network_manager.py - Gestiona la conectividad y configuración de dispositivos de red.
import threading
import time
import platform
import subprocess
import socket
from typing import Dict, Any, Tuple

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

try:
    from webcam_manager import load_config, save_config
except ImportError:
    import json, os
    ROOT = os.path.abspath(os.path.dirname(__file__))
    CONFIG_PATH = os.path.join(ROOT, "config.json")
    def load_config():
        if not os.path.exists(CONFIG_PATH): return {}
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f: return json.load(f)
    def save_config(cfg):
        with open(CONFIG_PATH, 'w', encoding='utf-8') as f: json.dump(cfg, f, indent=2)

_lock = threading.Lock()

# Estado interno del gestor de red
_network_state = {
    "selected_interface": None,
    "devices": {
        "plc": {"ip": "192.168.0.10"},
        "winc5g": {"ip": "192.168.0.20"},
        "robot": {"ip": "192.168.0.30"}
    }
}

def initialize_network_config():
    """Carga la configuración de red desde config.json al estado interno."""
    with _lock:
        cfg = load_config()
        network_cfg = cfg.get("network", {})
        _network_state["selected_interface"] = network_cfg.get("selected_interface")
        
        device_cfg = cfg.get("devices", {})
        for device_name in _network_state["devices"]:
            if device_name in device_cfg and "ip" in device_cfg[device_name]:
                _network_state["devices"][device_name]["ip"] = device_cfg[device_name]["ip"]
        
        print(f"[network] Configuración cargada:")
        print(f"[network]   - Interfaz seleccionada: {_network_state['selected_interface']}")
        print(f"[network]   - Dispositivos: {_network_state['devices']}")

def get_network_statuses() -> Dict[str, Any]:
    """Devuelve una copia del estado de la red."""
    with _lock:
        return _network_state.copy()

def ping_ip(ip_address: str) -> bool:
    """Función genérica de ping para configuración de dispositivos."""
    with _lock:
        selected_interface = _network_state["selected_interface"]
    
    if not selected_interface:
        print("[network] No hay interfaz seleccionada para hacer ping")
        return False
    
    try:
        # Obtener la IP de la interfaz seleccionada
        interface_ip = None
        if PSUTIL_AVAILABLE:
            net_if_addrs = psutil.net_if_addrs()
            if selected_interface in net_if_addrs:
                for addr in net_if_addrs[selected_interface]:
                    if addr.family == socket.AF_INET:
                        interface_ip = addr.address
                        break
        
        if not interface_ip:
            print(f"[network] No se pudo obtener IP de la interfaz {selected_interface}")
            return False
        
        print(f"[network] Haciendo ping a {ip_address} desde interfaz {selected_interface} ({interface_ip})")
        
        # Construir comando ping con interfaz específica
        if platform.system().lower() == 'windows':
            # Windows: usar -S para especificar interfaz
            param = '-n'
            command = ['ping', param, '1', '-w', '1000', '-S', interface_ip, ip_address]
        else:
            # Linux/Mac: usar -I para especificar interfaz
            param = '-c'
            command = ['ping', param, '1', '-W', '1', '-I', interface_ip, ip_address]
        
        print(f"[network] Comando: {' '.join(command)}")
        response = subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        success = response.returncode == 0
        
        if success:
            print(f"[network] ✓ Ping exitoso a {ip_address} desde {interface_ip}")
        else:
            print(f"[network] ✗ Ping fallido a {ip_address} desde {interface_ip}")
        
        return success
    except Exception as e:
        print(f"[network] Error al hacer ping a {ip_address} desde {selected_interface}: {e}")
        return False

def set_device_ip(device_name: str, ip_address: str) -> Tuple[bool, str]:
    """Actualiza la IP de un dispositivo y la guarda en config.json."""
    with _lock:
        if device_name not in _network_state["devices"]: return False, "Dispositivo no válido"
        _network_state["devices"][device_name]["ip"] = ip_address
        try:
            cfg = load_config()
            cfg.setdefault("devices", {}).setdefault(device_name, {})["ip"] = ip_address
            save_config(cfg)
            return True, f"IP para {device_name} guardada como {ip_address}"
        except Exception as e:
            return False, f"Error guardando config.json: {e}"

def set_network_interface(interface_name: str) -> Tuple[bool, str]:
    """Guarda la interfaz de red seleccionada en config.json."""
    with _lock:
        _network_state["selected_interface"] = interface_name
        try:
            cfg = load_config()
            cfg.setdefault("network", {})["selected_interface"] = interface_name
            save_config(cfg)
            return True, f"Interfaz de red guardada: {interface_name}"
        except Exception as e:
            return False, f"Error guardando config.json: {e}"

def get_network_interfaces() -> Dict[str, Any]:
    """Obtiene las interfaces de red disponibles del sistema."""
    interfaces = []
    
    if PSUTIL_AVAILABLE:
        try:
            # Usar psutil para obtener interfaces de red
            net_if_addrs = psutil.net_if_addrs()
            for interface_name, addresses in net_if_addrs.items():
                for addr in addresses:
                    if addr.family == socket.AF_INET:  # Solo IPv4
                        interfaces.append({
                            "name": interface_name,
                            "ip": addr.address,
                            "netmask": addr.netmask
                        })
                        break  # Solo tomar la primera IP por interfaz
        except Exception as e:
            print(f"[network] Error obteniendo interfaces con psutil: {e}")
    
    # Fallback: usar comandos del sistema
    if not interfaces:
        try:
            if platform.system().lower() == 'windows':
                # Windows: usar ipconfig
                result = subprocess.run(['ipconfig'], capture_output=True, text=True, timeout=10)
                if result.returncode == 0:
                    lines = result.stdout.split('\n')
                    current_interface = None
                    for line in lines:
                        line = line.strip()
                        if line and not line.startswith(' '):
                            # Nueva interfaz
                            if ':' in line:
                                current_interface = line.split(':')[0].strip()
                        elif line.startswith('IPv4') and ':' in line:
                            # IP encontrada
                            ip_part = line.split(':')[1].strip()
                            if current_interface and ip_part:
                                interfaces.append({
                                    "name": current_interface,
                                    "ip": ip_part,
                                    "netmask": "255.255.255.0"  # Default
                                })
            else:
                # Linux/Mac: usar ip addr
                result = subprocess.run(['ip', 'addr'], capture_output=True, text=True, timeout=10)
                if result.returncode == 0:
                    lines = result.stdout.split('\n')
                    current_interface = None
                    for line in lines:
                        line = line.strip()
                        if line.startswith('inet ') and current_interface:
                            # IP encontrada
                            ip_part = line.split()[1].split('/')[0]
                            interfaces.append({
                                "name": current_interface,
                                "ip": ip_part,
                                "netmask": "255.255.255.0"  # Default
                            })
                        elif line and not line.startswith(' ') and ':' in line:
                            # Nueva interfaz
                            current_interface = line.split(':')[0].strip()
        except Exception as e:
            print(f"[network] Error obteniendo interfaces con comandos del sistema: {e}")
    
    # Filtrar interfaces válidas (con IP)
    valid_interfaces = [iface for iface in interfaces if iface["ip"] and iface["ip"] != "127.0.0.1"]
    
    return {
        "ok": True,
        "interfaces": valid_interfaces
    }

def get_device_ip(device_name: str) -> str:
    """Obtiene la IP configurada para un dispositivo específico."""
    with _lock:
        if device_name in _network_state["devices"]:
            return _network_state["devices"][device_name]["ip"]
        return None

def get_selected_interface() -> str:
    """Obtiene el nombre de la interfaz de red seleccionada."""
    with _lock:
        return _network_state["selected_interface"]

# Cargar configuración al iniciar
initialize_network_config()