# procesos_feeder.py - Proceso de alimentación
import time
from typing import Dict, Any
import global_flags
from PLC_LOGO_manager import plc_manager

# Variable global para detectar cambios de estado del sistema
# flag_estado_sistema_change = False # This line is removed as it's now imported directly


# Definicion de entradas y salidas del LOGO
# 
# I1: Sensor detecta Junta. Es quien detiene el motor del feeder cuando una junta cae.
# I2: Pide Junta Manual: Boton del tablero para entregar una junta.
# I3: Enable: Llave de habilitacion del sistema de alimentacion.
# I4: Sensor de Stock: Detecta si hay stock de material.

# Se pueden leer las entradas, pero por convencion solo vamos a leer marcas
# M1: Pide Junta Modbus: entrada que pide una junta via Modbus
# M2: Motor Encendido: Marca que indica que el motor esta encendido.
# M3: Marca que indica si hay Stock. Es lo mismo que leer I4.
# M4: Marca Enable. Es lo mismo que leer I3.
# M5: Marca que indica que se detecto la junta.
# M6: Marca que Resetea todo los RS del PLC. Tiene detector de pulso




class ProcesoFeeder:
    """Proceso de alimentación con máquina de estados."""
    
    def __init__(self):
        # Estado y timing
        self.estado = 0
        self.last_time_machine = 0
        self.last_time_update_marks = 0
        self.delay = 1000  # Delay inicial
        
        # Variables para las marcas del PLC
        self.M1_PIDE_JUNTA = False
        self.M2_MOTOR_ENCENDIDO = False
        self.M3_SIN_STOCK_DISPONIBLE = False
        self.M4_FEEDER_HABILITADO = False
        self.M5_JUNTA_DETECTADA = False
        self.M6_RESET_RS = False
        
        # Variable para rastrear cambios en el estado del sistema
        self.estado_sistema_anterior = 100

        self.estado_feeder_anterior = 100
        self.flag_estado_feeder_change = False
        
        # Estados del proceso
        self.ESTADOS = {
            0: "IDLE (REPOSO)",
            1: "SIN STOCK",
            2: "ANULADO",
            10: "ESPERANDO PETICIÓN",
            20: "SOLICITANDO JUNTA",
            30: "ENCENDIENDO MOTOR",
            40: "ENTREGANDO JUNTA",
            100: "ERROR GENERAL"
        }
        
        print("[feeder] Proceso Feeder inicializado")
    
    def updateMarks(self):
        """Actualiza las variables M1-M6 leyendo las marcas del PLC."""
        try:
            success, marks = plc_manager.read_all_marks()
            if success and len(marks) >= 6:
                self.M1_PIDE_JUNTA = marks[0]      # M1
                self.M2_MOTOR_ENCENDIDO = marks[1]  # M2
                self.M3_SIN_STOCK_DISPONIBLE = marks[2] # M3
                self.M4_FEEDER_HABILITADO = marks[3] # M4
                self.M5_JUNTA_DETECTADA = marks[4]   # M5
                self.M6_RESET_RS = marks[5]          # M6
                #print(f"[feeder] Marcas actualizadas: M1={self.M1_PIDE_JUNTA}, M2={self.M2_MOTOR_ENCENDIDO}, M3={self.M3_SIN_STOCK_DISPONIBLE}, M4={self.M4_FEEDER_HABILITADO}, M5={self.M5_JUNTA_DETECTADA}, M6={self.M6_RESET_RS}")
            else:
                print("[feeder] Error leyendo marcas del PLC")
        except Exception as e:
            print(f"[feeder] Error en updateMarks: {e}")
    
    def ejecutar(self, estado_sistema: str):
        """Ejecuta el proceso feeder según el estado del sistema."""
        current_time = time.time() * 1000
            
        # Verificar cambio de estado del sistema y levantar bandera
        # No necesitamos declarar global porque usamos global_flags.flag_estado_sistema_change
        if self.estado_sistema_anterior != estado_sistema:
            # Detectamos un cambio de estado del sistema
            if self.estado_sistema_anterior == "DETENER" and estado_sistema == "INICIO":
                # Si hay cambio de DETENER a INICIO, reseteamos los RS del PLC
                # De esta manera nos aseguramos entrar a la rutina en un estado seguro
                try:
                    success, message = plc_manager.write_coil("M6")
                except Exception as e:
                    print(f"[feeder] Error al resetear los RS del PLC: {e}")

            #actualizo el registro de cambio de estado
            self.estado_sistema_anterior = estado_sistema
            global_flags.flag_estado_sistema_change = True
        else:
            global_flags.flag_estado_sistema_change = False  


        if self.estado_feeder_anterior != self.estado:
            # Detectamos un cambio de estado del feeder
            print(f"[feeder] Cambio de estado del feeder: {self.estado_feeder_anterior} → {self.estado}")
            self.estado_feeder_anterior = self.estado
            self.flag_estado_feeder_change = True
        else:
            self.flag_estado_feeder_change = False

        
        # Actualizar marcas del PLC cada 500ms
        if current_time >= self.last_time_update_marks + 500:
            self.updateMarks()
            self.last_time_update_marks = current_time

        # Lógica normal del proceso
        if current_time >= self.last_time_machine + self.delay:
            self.last_time_machine = current_time

            match estado_sistema:
                case "DETENER":
                    self.estado = 0 # IDLE
                    print(f"[Sistema] Detenido")
                    self.delay = 1000
                    return
                    
                case "PAUSA":
                    #en Pausa, el estado se mantien 
                    #pero no se ejecuta la maquina de estado (return)
                    print(f"[Sistema] Pausa")
                    return
                    
                case "INICIO":   
                    # Verificamos si el feeder esta habilitado
                    print(f"[Sistema] Inicio")
                    if not self.M4_FEEDER_HABILITADO:
                        self.estado = 2  # ANULADO         

                    ######   Máquina de estados   ######
                    match self.estado:
                        #El ciclo siempre comienza en el IDLE
                        case 0:  # IDLE (REPOSO)
                            self.delay = 1000
                            print(f"[feeder] Estado IDLE")
                            #En el unico momento que verificamos el stock es en el estado IDLE
                            #Si hay stock, permitimos que se ejecute 1 ciclo.
                            if  self.M3_SIN_STOCK_DISPONIBLE:
                                print(f"[feeder] Cambiando a SIN STOCK - No hay stock")
                                self.estado = 1  # SIN STOCK
                                return
                            #si hay stock y el sisstema se inicia, pasamos al estado ESPERANDO PETICIÓN
                            if estado_sistema == "INICIO":
                                print(f"[feeder] DEBUG: Cambiando de IDLE a ESPERANDO PETICIÓN")
                                self.estado = 10  # ESPERANDO PETICIÓN
                                return
                            
                        case 1:  # SIN STOCK
                            self.delay = 500
                            print(f"[feeder] DEBUG: Estado SIN STOCK")
                            # Esperar a que haya stock 
                            if not self.M3_SIN_STOCK_DISPONIBLE:
                                self.estado = 0  # IDLE
                                return
                            
                        case 2:  # ANULADO
                            self.delay = 500
                            print(f"[feeder] Estado ANULADO")
                            # Esperar a que se habilite  el feeder (Llave del tablero)
                            if self.M4_FEEDER_HABILITADO:
                                self.estado = 0  # IDLE
                                return

                        case 10:  # ESPERANDO PETICIÓN
                            self.delay = 500
                            print(f"[feeder] DEBUG: Estado 10 - flag_pedir_junta = {global_flags.flag_pedir_junta} (tipo: {type(global_flags.flag_pedir_junta)})")
                            
                            # Esperamos a que el proceso principal nos pida una junta
                            if global_flags.flag_pedir_junta:
                                print(f"[feeder] DEBUG: Cambiando de ESPERANDO PETICIÓN a SOLICITANDO JUNTA")
                                # Primero, nos aseguramos de liberar los RS del LOGO
                                try:
                                    plc_manager.clear_coil("M6")
                                except Exception as e:
                                    print(f"[feeder] Error liberando RS: {e}")

                                #Luego, pasamos al estado SOLICITANDO JUNTA
                                self.estado = 20  # SOLICITANDO JUNTA
                                return
                            
                        case 20:  # SOLICITANDO JUNTA
                            self.delay = 100
                            try:
                                # Escribir M1=1 (PIDE JUNTA MODBUS)
                                # Con eso, encendemos el motor del feeder
                                success, message = plc_manager.write_coil("M1")

                                if success:
                                    #ahora cambiamos al estado para verificar si se enciende el motor
                                    self.estado = 30  # ENCENDIENDO MOTOR
                                    print("[feeder] Junta solicitada (M1=1)")
                                else:
                                    print(f"[feeder] Error solicitando junta: {message}")
                            except Exception as e:
                                print(f"[feeder] Error en solicitar junta: {e}")
                            
                        case 30:  # ENCENDIENDO MOTOR
                            self.delay = 200
                            if self.M2_MOTOR_ENCENDIDO:
                                # Si el motor encendió, bajamos la bandera flag_pedir_junta
                                global_flags.flag_pedir_junta = False

                                try:
                                    # Motor encendido, bajamos la marca del PLC 
                                    # M1: PEDIR JUNTA = 0
                                    plc_manager.clear_coil("M1")
                                    print("[feeder] Motor encendido detectado, M1=0")
                                    self.estado = 40  # ENTREGANDO JUNTA
                                except Exception as e:
                                    print(f"[feeder] Error poniendo M1=0: {e}")
                            
                        case 40:  # ENTREGANDO JUNTA
                            self.delay = 200
                            if self.M5_JUNTA_DETECTADA:
                                # Junta detectada, activar bandera
                                try:
                                    global_flags.flag_junta_entregada = True
                                    print("[feeder] Junta detectada, bandera activada")
                                    self.estado = 0  # IDLE
                                except Exception as e:
                                    print(f"[feeder] Error activando bandera: {e}")
                            
                        case 100:  # ERROR GENERAL
                            self.delay = 1000
                            # Por ahora no implementamos lógica de error
                            
                        case _:
                            print(f"[feeder] Estado inválido {self.estado}, volviendo a 0")
                            self.estado = 0
                            self.delay = 1000
                    
                    try:
                        estado_str = self.ESTADOS[self.estado]
                    except KeyError:
                        estado_str = f"Estado {self.estado} (no definido)"
                    print(f"[feeder] Estado: {estado_str}")
 
 
     
    def reiniciar(self):
        """Reinicia el contador y estado del proceso."""
        self.estado = 0
        self.last_time = 0
        self.delay = 1000
        print("[feeder] Proceso reiniciado")
    
    def get_status(self) -> Dict[str, Any]:
        """Obtiene el estado actual del proceso."""
        try:
            estado_str = self.ESTADOS[self.estado]
        except KeyError:
            estado_str = f"Estado {self.estado} (no definido)"
        
        # Obtener estado del PLC desde el manager automático
        try:
            plc_status = plc_manager.get_connection_status()
            plc_connected = plc_status.get("connected", False)
        except ImportError:
            plc_connected = False
        
        return {
            "estado": self.estado,
            "estado_str": estado_str,
            "plc_connected": plc_connected
        }
    
    def get_config(self) -> Dict[str, Any]:
        """Obtiene la configuración del proceso."""
        return {
            "name": "Feeder",
            "color": "success",
            "states": self.ESTADOS
        }
