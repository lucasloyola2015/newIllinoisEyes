# PLC_LOGO_manager.py - Gestión simple de conexión al PLC LOGO
import threading
import time
import json
import os
import socket
from typing import Optional, Callable, Dict, Any
from pymodbus.client import ModbusTcpClient

class PLC_LOGOManager:
    """Gestor simple de conexión y comunicación con PLC LOGO via Modbus TCP."""
    
    def __init__(self):
        # Configuración de conexión
        self.plc_ip: str = "192.168.29.3"
        
        # Conexión Modbus - Ahora temporal (como en GUI Simple original)
        self.client: Optional[ModbusTcpClient] = None
        self.is_connected: bool = False
        
        # Sistema de subscripción de eventos
        self.connection_subscribers: list[Callable] = []
        
        # Thread dedicado para gestión de conexión
        self.connection_thread = None
        self.thread_running = False
        
        # Control de reconexión
        self.last_connection_attempt = 0
        self.connection_attempt_interval = 5  # segundos entre intentos
        
        # Cargar configuración inicial
        self.load_config_from_json()
        
        # Iniciar thread de conexión
        self.start_connection_thread()
        
        print("[PLC_LOGO] Gestor de PLC LOGO inicializado")
    
    def load_config_from_json(self):
        """Carga la configuración del PLC desde config.json."""
        try:
            config_path = os.path.join(os.path.dirname(__file__), "config.json")
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                
                # Obtener IP del PLC desde la sección devices
                plc_config = config.get("devices", {}).get("plc", {})
                if "ip" in plc_config:
                    new_ip = plc_config["ip"]
                    if new_ip != self.plc_ip:
                        print(f"[PLC_LOGO] IP actualizada: {self.plc_ip} -> {new_ip}")
                        self.plc_ip = new_ip
                else:
                    print(f"[PLC_LOGO] No se encontró IP del PLC en config.json, usando: {self.plc_ip}")
            else:
                print(f"[PLC_LOGO] config.json no encontrado, usando IP default: {self.plc_ip}")
        except Exception as e:
            print(f"[PLC_LOGO] Error cargando configuración: {e}")
    
    def start_connection_thread(self):
        """Inicia el thread dedicado para gestión de conexión."""
        if self.connection_thread and self.connection_thread.is_alive():
            return
        
        self.thread_running = True
        self.connection_thread = threading.Thread(target=self._connection_worker, daemon=True, name="PLCConnectionThread")
        self.connection_thread.start()
        print("[PLC_LOGO] Thread de conexión iniciado")
    
    def stop_connection_thread(self):
        """Detiene el thread de conexión."""
        self.thread_running = False
        if self.connection_thread and self.connection_thread.is_alive():
            self.connection_thread.join(timeout=2)
        print("[PLC_LOGO] Thread de conexión detenido")
    
    def _connection_worker(self):
        """Thread dedicado que gestiona la conexión al PLC."""
        print("[PLC_LOGO] Thread de conexión iniciado")
        last_connection_state = None
        
        while self.thread_running:
            try:
                current_time = time.time()
                
                # Verificar conectividad cada 5 segundos, sin importar el estado actual
                if (current_time - self.last_connection_attempt) >= self.connection_attempt_interval:
                    self.last_connection_attempt = current_time
                    self._test_connectivity()
                
                # Solo notificar si el estado cambió
                if last_connection_state != self.is_connected:
                    if self.is_connected:
                        self._notify_connection_change(True, "PLC conectado")
                        print(f"[PLC_LOGO] Estado cambiado: DESCONECTADO -> CONECTADO")
                    else:
                        self._notify_connection_change(False, "PLC desconectado")
                        print(f"[PLC_LOGO] Estado cambiado: CONECTADO -> DESCONECTADO")
                    
                    last_connection_state = self.is_connected
                
                # Esperar siempre 5 segundos
                time.sleep(5)
                
            except Exception as e:
                print(f"[PLC_LOGO] Error en thread de conexión: {e}")
                time.sleep(5)
        
        print("[PLC_LOGO] Thread de conexión finalizado")
    
    def _test_connectivity(self):
        """Prueba la conectividad básica al PLC."""
        try:
            # Crear una conexión temporal para probar - EXACTAMENTE como GUI Simple
            test_client = ModbusTcpClient(self.plc_ip, port=502, timeout=3)
            
            if test_client.connect():
                # Si se conecta, actualizar estado
                self.is_connected = True
                print(f"[PLC_LOGO] ✅ Conectividad verificada con {self.plc_ip}")
                # Cerrar conexión de prueba inmediatamente
                test_client.close()
            else:
                self.is_connected = False
                print(f"[PLC_LOGO] ❌ No se pudo conectar a {self.plc_ip}")
                
        except Exception as e:
            self.is_connected = False
            print(f"[PLC_LOGO] ❌ Error verificando conectividad: {e}")
    
    def _create_temporary_connection(self) -> Optional[ModbusTcpClient]:
        """Crea una conexión temporal para operaciones."""
        try:
            # EXACTAMENTE como GUI Simple
            client = ModbusTcpClient(self.plc_ip, port=502, timeout=3)
            
            if client.connect():
                return client
            else:
                return None
                
        except Exception as e:
            print(f"[PLC_LOGO] Error creando conexión temporal: {e}")
            return None
    
    def _safe_close_connection(self, client: ModbusTcpClient):
        """Cierra una conexión de forma segura."""
        try:
            if client:
                client.close()
        except Exception as e:
            print(f"[PLC_LOGO] Error cerrando conexión: {e}")
    
    def subscribe_to_connection_events(self, callback: Callable):
        """Suscribe un callback para recibir eventos de conexión/desconexión."""
        if callback not in self.connection_subscribers:
            self.connection_subscribers.append(callback)
            print(f"[PLC_LOGO] Subscripción registrada: {callback}")
    
    def unsubscribe_from_connection_events(self, callback: Callable):
        """Desuscribe un callback de eventos de conexión."""
        if callback in self.connection_subscribers:
            self.connection_subscribers.remove(callback)
            print(f"[PLC_LOGO] Subscripción removida: {callback}")
    
    def _notify_connection_change(self, connected: bool, message: str = ""):
        """Notifica a todos los subscribers sobre cambios de conexión."""
        for callback in self.connection_subscribers:
            try:
                callback(connected, message)
            except Exception as e:
                print(f"[PLC_LOGO] Error en callback de conexión: {e}")
    
    def reload_config(self):
        """Recarga la configuración desde config.json."""
        print("[PLC_LOGO] Recargando configuración...")
        self.load_config_from_json()
    
    def get_connection_status(self) -> Dict[str, Any]:
        """Obtiene el estado actual de la conexión."""
        return {
            "connected": self.is_connected,
            "ip": self.plc_ip,
            "port": 502
        }
    
    def write_coil(self, address: str) -> tuple[bool, str]:
        """Escribe un coil (Qx o Mx) con conexión temporal."""
        if not self.is_connected:
            return False, "PLC no conectado"
        
        client = None
        try:
            # Crear conexión temporal
            client = self._create_temporary_connection()
            if not client:
                return False, "No se pudo conectar al PLC"
            
            # Parsear dirección (ej: "Q1", "M5")
            if len(address) < 2:
                return False, f"Dirección inválida: {address}"
            
            tipo = address[0].upper()
            indice = int(address[1:])
            
            if tipo == 'Q':
                if not (1 <= indice <= 12):
                    return False, f"Índice de salida inválido: {indice} (debe ser 1-12)"
                coil_address = 8192 + (indice - 1)  # Q1=8192, Q2=8193, etc.
            elif tipo == 'M':
                if not (1 <= indice <= 64):
                    return False, f"Índice de marca inválido: {indice} (debe ser 1-64)"
                coil_address = 8256 + (indice - 1)  # M1=8256, M2=8257, etc.
            else:
                return False, f"Tipo inválido: {tipo} (debe ser 'Q' o 'M')"
            
            # Escribir coil
            client.write_coil(coil_address, True)
            print(f"[PLC_LOGO] {address} SET exitoso")
            return True, f"{address} SET exitoso"
                
        except Exception as e:
            print(f"[PLC_LOGO] Excepción al escribir coil {address}: {e}")
            return False, f"Error escribiendo {address}: {str(e)}"
        finally:
            # Siempre cerrar la conexión
            self._safe_close_connection(client)
    
    def clear_coil(self, address: str) -> tuple[bool, str]:
        """Limpia un coil (Qx o Mx) con conexión temporal."""
        if not self.is_connected:
            return False, "PLC no conectado"
        
        client = None
        try:
            # Crear conexión temporal
            client = self._create_temporary_connection()
            if not client:
                return False, "No se pudo conectar al PLC"
            
            # Parsear dirección (ej: "Q1", "M5")
            if len(address) < 2:
                return False, f"Dirección inválida: {address}"
            
            tipo = address[0].upper()
            indice = int(address[1:])
            
            if tipo == 'Q':
                if not (1 <= indice <= 12):
                    return False, f"Índice de salida inválido: {indice} (debe ser 1-12)"
                coil_address = 8192 + (indice - 1)  # Q1=8192, Q2=8193, etc.
            elif tipo == 'M':
                if not (1 <= indice <= 64):
                    return False, f"Índice de marca inválido: {indice} (debe ser 1-64)"
                coil_address = 8256 + (indice - 1)  # M1=8256, M2=8257, etc.
            else:
                return False, f"Tipo inválido: {tipo} (debe ser 'Q' o 'M')"
            
            # Limpiar coil
            client.write_coil(coil_address, False)
            print(f"[PLC_LOGO] {address} CLEAR exitoso")
            return True, f"{address} CLEAR exitoso"
                
        except Exception as e:
            print(f"[PLC_LOGO] Excepción al limpiar coil {address}: {e}")
            return False, f"Error limpiando {address}: {str(e)}"
        finally:
            # Siempre cerrar la conexión
            self._safe_close_connection(client)
    
    def read_all_inputs(self) -> tuple[bool, list[bool]]:
        """Lee todas las entradas del PLC (I1-I8) con conexión temporal."""
        if not self.is_connected:
            return False, []
        
        client = None
        try:
            # Crear conexión temporal
            client = self._create_temporary_connection()
            if not client:
                return False, []
            
            # Leer todas las entradas
            response = client.read_discrete_inputs(address=0, count=8)
            
            if response is None:
                return False, []
            
            if response.isError():
                return False, []
            
            # Procesar respuesta exitosa
            inputs = [bool(bit) for bit in response.bits[:8]]
            print(f"[PLC_LOGO] Entradas leídas: {inputs}")
            return True, inputs
                
        except Exception as e:
            print(f"[PLC_LOGO] Error durante lectura de entradas: {e}")
            return False, []
        finally:
            # Siempre cerrar la conexión
            self._safe_close_connection(client)
    
    def read_all_outputs(self) -> tuple[bool, list[bool]]:
        """Lee todas las salidas del PLC (Q1-Q12) con conexión temporal."""
        if not self.is_connected:
            return False, []
        
        client = None
        try:
            # Crear conexión temporal
            client = self._create_temporary_connection()
            if not client:
                return False, []
            
            # Leer todas las salidas (coils Q1-Q12)
            response = client.read_coils(address=8192, count=12)
            
            if response is None:
                return False, []
            
            if response.isError():
                return False, []
            
            # Procesar respuesta exitosa
            outputs = [bool(bit) for bit in response.bits[:12]]
            print(f"[PLC_LOGO] Salidas leídas: {outputs}")
            return True, outputs
                
        except Exception as e:
            print(f"[PLC_LOGO] Error durante lectura de salidas: {e}")
            return False, []
        finally:
            # Siempre cerrar la conexión
            self._safe_close_connection(client)
    
    def read_all_marks(self) -> tuple[bool, list[bool]]:
        """Lee las primeras 8 marcas del PLC (M1-M8) con conexión temporal."""
        if not self.is_connected:
            return False, []
        
        client = None
        try:
            # Crear conexión temporal
            client = self._create_temporary_connection()
            if not client:
                return False, []
            
            # Leer las primeras 8 marcas (coils M1-M8)
            response = client.read_coils(address=8256, count=8)
            
            if response is None:
                return False, []
            
            if response.isError():
                return False, []
            
            # Procesar respuesta exitosa
            marks = [bool(bit) for bit in response.bits[:8]]
            #print(f"[PLC_LOGO] Marcas leídas (M1-M8): {marks}")
            return True, marks
                
        except Exception as e:
            print(f"[PLC_LOGO] Error durante lectura de marcas: {e}")
            return False, []
        finally:
            # Siempre cerrar la conexión
            self._safe_close_connection(client)
    
    def read_all(self) -> tuple[bool, dict]:
        """Lee todas las entradas, salidas y marcas del PLC."""
        if not self.is_connected:
            return False, {}
        
        # Leer entradas
        inputs_success, inputs = self.read_all_inputs()
        
        # Leer salidas
        outputs_success, outputs = self.read_all_outputs()
        
        # Leer marcas
        marks_success, marks = self.read_all_marks()
        
        # Preparar resultado
        result = {
            "inputs": inputs if inputs_success else [],
            "outputs": outputs if outputs_success else [],
            "marks": marks if marks_success else []
        }
        
        # Considerar exitoso si al menos las entradas se leyeron
        success = inputs_success
        
        if success:
            print(f"[PLC_LOGO] Lectura completa: I={inputs}, Q={outputs}, M={marks[:8]}...")  # Solo mostrar primeras 8 marcas
        
        return success, result
    
    def shutdown(self):
        """Cierra el gestor de PLC de forma ordenada."""
        print("[PLC_LOGO] Cerrando gestor de PLC...")
        
        # Detener thread de conexión
        self.stop_connection_thread()
        
        # Limpiar subscribers
        self.connection_subscribers.clear()
        
        print("[PLC_LOGO] Gestor de PLC cerrado correctamente")

# Instancia global del PLC Manager
plc_manager = PLC_LOGOManager()

# Funciones de conveniencia para el webserver
def get_plc_manager() -> PLC_LOGOManager:
    """Obtiene la instancia global del PLC Manager."""
    return plc_manager

def subscribe_to_connection_events(callback: Callable):
    """Suscribe un callback para recibir eventos de conexión."""
    plc_manager.subscribe_to_connection_events(callback)

def unsubscribe_from_connection_events(callback: Callable):
    """Desuscribe un callback de eventos de conexión."""
    plc_manager.unsubscribe_from_connection_events(callback)

def get_connection_status() -> Dict[str, Any]:
    """Obtiene el estado actual de la conexión."""
    return plc_manager.get_connection_status()

def write_coil(address: str) -> tuple[bool, str]:
    """Escribe un coil (Qx o Mx)."""
    return plc_manager.write_coil(address)

def clear_coil(address: str) -> tuple[bool, str]:
    """Limpia un coil (Qx o Mx)."""
    return plc_manager.clear_coil(address)

def read_all_inputs() -> tuple[bool, list[bool]]:
    """Lee todas las entradas del PLC."""
    return plc_manager.read_all_inputs()

def read_all_outputs() -> tuple[bool, list[bool]]:
    """Lee todas las salidas del PLC."""
    return plc_manager.read_all_outputs()

def read_all_marks() -> tuple[bool, list[bool]]:
    """Lee todas las marcas del PLC."""
    return plc_manager.read_all_marks()

def read_all() -> tuple[bool, dict]:
    """Lee todas las entradas, salidas y marcas del PLC."""
    return plc_manager.read_all()

def shutdown():
    """Cierra el gestor de PLC."""
    plc_manager.shutdown()
