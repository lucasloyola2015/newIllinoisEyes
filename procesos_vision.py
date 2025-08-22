# procesos_vision.py - Subproceso Vision
import time
from typing import Dict, Any

class ProcesoVision:
    def __init__(self):
        self.contador = 0
        self.estado = 0
        self.last_time = 0
        self.delay = 1000  # 1000ms
        
        # Estados
        self.ESTADO_A = 0
        self.ESTADO_B = 1
        self.ESTADO_C = 2
        
        self.ESTADOS = {
            0: "Capturando",
            1: "Procesando",
            2: "Validando"
        }
    
    def ejecutar(self, estado_sistema: str):
        """Ejecuta el proceso vision según el estado del sistema."""
        current_time = time.time() * 1000
        
        if current_time >= self.last_time + self.delay:
            match estado_sistema:
                case "DETENER":
                    self.estado = 0
                    self.contador = 0
                    self.last_time = current_time
                    #print("[vision] Sistema DETENIDO, reiniciando máquina de estados")
                    return
                    
                case "PAUSA":
                    self.last_time = current_time
                    #print("[vision] Sistema en PAUSA, manteniendo estado actual")
                    return
                    
                case "INICIO":
                    self.contador += 1
                    self.last_time = current_time
                    
                    match self.estado:
                        case 0:
                            #print("[vision] Estado A: Capturando imagen")
                            self.estado = 1
                            
                        case 1:
                            #print("[vision] Estado B: Procesando datos de imagen")
                            self.estado = 2
                            
                        case 2:
                            #print("[vision] Estado C: Analizando resultados")
                            self.estado = 0
                            
                        case _:
                            print(f"[vision] Estado inválido {self.estado}, volviendo a 0")
                            self.estado = 0
                    
                    try:
                        estado_str = self.ESTADOS[self.estado]
                    except KeyError:
                        estado_str = f"Estado {self.estado} (no definido)"
                    print(f"[vision] {self.contador} - Estado: {estado_str}")
    
    def reiniciar(self):
        """Reinicia el contador y estado del proceso."""
        self.contador = 0
        self.estado = 0
        self.last_time = 0
        print("[vision] Proceso reiniciado")
    
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
            "name": "Vision",
            "color": "info",
            "states": self.ESTADOS
        }
