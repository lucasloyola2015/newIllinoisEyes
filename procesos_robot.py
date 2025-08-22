# procesos_robot.py - Subproceso Robot
import time
from typing import Dict, Any

class ProcesoRobot:
    def __init__(self):
        self.contador = 0
        self.estado = 0
        self.last_time = 0
        self.delay = 1500  # 1500ms
        
        # Estados
        self.ESTADO_A = 0
        self.ESTADO_B = 1
        self.ESTADO_C = 2
        
        self.ESTADOS = {
            0: "Inicio",
            1: "Movimiento",
            2: "Aproximación"
        }
    
    def ejecutar(self, estado_sistema: str):
        """Ejecuta el proceso robot según el estado del sistema."""
        current_time = time.time() * 1000
        
        if current_time >= self.last_time + self.delay:
            match estado_sistema:
                case "DETENER":
                    self.estado = 0
                    self.contador = 0
                    self.last_time = current_time
                    #print("[robot] Sistema DETENIDO, reiniciando máquina de estados")
                    return
                    
                case "PAUSA":
                    self.last_time = current_time
                    #print("[robot] Sistema en PAUSA, manteniendo estado actual")
                    return
                    
                case "INICIO":
                    self.contador += 1
                    self.last_time = current_time
                    
                    match self.estado:
                        case 0:
                            #print("[robot] Estado A: Iniciando secuencia")
                            self.estado = 1
                            
                        case 1:
                            #print("[robot] Estado B: Movimiento hacia objetivo")
                            self.estado = 2
                            
                        case 2:
                            #print("[robot] Estado C: Aproximación final")
                            self.estado = 0

                        case _:
                            print(f"[robot] Estado inválido {self.estado}, volviendo a 0")
                            self.estado = 0
                    
                    try:
                        estado_str = self.ESTADOS[self.estado]
                    except KeyError:
                        estado_str = f"Estado {self.estado} (no definido)"
                    print(f"[robot] {self.contador} - Estado: {estado_str}")
    
    def reiniciar(self):
        """Reinicia el contador y estado del proceso."""
        self.contador = 0
        self.estado = 0
        self.last_time = 0
        print("[robot] Proceso reiniciado")
    
    def get_status(self) -> Dict[str, Any]:
        """Obtiene el estado actual del proceso."""
        try:
            estado_str = self.ESTADOS[self.estado]
        except KeyError:
            estado_str = f"Estado {self.estado} (no definido)"
        
        return {
            "contador": self.contador,
            "estado": self.estado,
            "estado_str": estado_str
        }
    
    def get_config(self) -> Dict[str, Any]:
        """Obtiene la configuración del proceso."""
        return {
            "name": "Robot",
            "color": "warning",
            "states": self.ESTADOS
        }
