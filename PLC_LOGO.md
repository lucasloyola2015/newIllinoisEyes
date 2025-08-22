# PLC_LOGO_manager.py - Documentación

## Descripción General

El módulo `PLC_LOGO_manager.py` proporciona una interfaz completa para la comunicación con PLC LOGO de Siemens mediante protocolo Modbus TCP. Este gestor maneja automáticamente la conexión, reconexión y monitoreo de estado del PLC.

## Características Principales

- **Conexión automática** con reconexión automática en caso de pérdida de comunicación
- **Keep-alive** cada 5 segundos para verificar conectividad
- **Thread-safe** para operaciones concurrentes
- **Sistema de callbacks** para notificaciones de eventos
- **API simple** para lectura y escritura de datos

## Instalación y Dependencias

```bash
pip install pymodbus
```

## Configuración Inicial

```python
from PLC_LOGO_manager import Connect, Disconnect, write_PLC, read_PLC, isAlive

# Configurar y conectar al PLC
success, message = Connect("192.168.29.3", 502)
if success:
    print("Conectado al PLC")
else:
    print(f"Error: {message}")
```

## API de Funciones

### 1. Connect(ip, port)

**Descripción:** Se conecta al PLC y mantiene la conexión activa. Si se cae, se reconecta automáticamente.

**Parámetros:**
- `ip` (str): Dirección IP del PLC (default: "192.168.29.3")
- `port` (int): Puerto Modbus TCP (default: 502)

**Retorna:**
- `tuple[bool, str]`: (éxito, mensaje)

**Ejemplo:**
```python
success, message = Connect("192.168.29.3")
if success:
    print("Conectado exitosamente")
else:
    print(f"Error de conexión: {message}")
```

### 2. Disconnect()

**Descripción:** Desconecta el dispositivo del PLC.

**Parámetros:** Ninguno

**Retorna:**
- `tuple[bool, str]`: (éxito, mensaje)

**Ejemplo:**
```python
success, message = Disconnect()
if success:
    print("Desconectado exitosamente")
```

### 3. isAlive()

**Descripción:** Verifica si la conexión está activa.

**Parámetros:** Ninguno

**Retorna:**
- `bool`: True si está conectado, False en caso contrario

**Ejemplo:**
```python
if isAlive():
    print("PLC conectado")
else:
    print("PLC desconectado")
```

### 4. write_PLC(destino, indice, valor)

**Descripción:** Escribe un dato en una dirección MODBUS.

**Parámetros:**
- `destino` (str): 'Q' para salidas físicas o 'M' para marcas
- `indice` (int): Número de la salida (1-12) o marca (1-4)
- `valor` (bool): True para SET, False para CLEAR

**Retorna:**
- `tuple[bool, str]`: (éxito, mensaje)

**Ejemplos:**
```python
# Activar salida Q1
success, message = write_PLC('Q', 1, True)

# Desactivar salida Q2
success, message = write_PLC('Q', 2, False)

# Activar marca M1
success, message = write_PLC('M', 1, True)

# Desactivar marca M2
success, message = write_PLC('M', 2, False)
```

### 5. read_PLC(index)

**Descripción:** Lee una entrada del PLC. Es un snapshot de las entradas del PLC.

**Parámetros:**
- `index` (int): Número de entrada (1-8)

**Retorna:**
- `tuple[bool, str]`: (éxito, resultado) donde resultado es el estado (True/False) o mensaje de error

**Ejemplos:**
```python
# Leer entrada I1
success, result = read_PLC(1)
if success:
    state = result == "True"
    print(f"I1 está {'ON' if state else 'OFF'}")
else:
    print(f"Error: {result}")

# Leer entrada I5
success, result = read_PLC(5)
if success:
    state = result == "True"
    print(f"I5 está {'ON' if state else 'OFF'}")
```

## Mapeo de Direcciones Modbus

### Salidas Físicas (Q1-Q12)
- Q1: Dirección 8192
- Q2: Dirección 8193
- Q3: Dirección 8194
- ...
- Q12: Dirección 8203

### Marcas (M1-M4)
- M1: Dirección 8256
- M2: Dirección 8257
- M3: Dirección 8258
- M4: Dirección 8259

### Entradas (I1-I8)
- I1-I8: Direcciones 0-7 (discrete inputs)

## Sistema de Keep-Alive

El gestor implementa un sistema de keep-alive que:

1. **Verifica conectividad** cada 5 segundos mediante ping
2. **Detecta desconexiones** automáticamente
3. **Reconecta automáticamente** si se pierde la conexión
4. **Notifica cambios** de estado mediante callbacks

## Sistema de Callbacks

### Registro de Callbacks

```python
from PLC_LOGO_manager import plc_manager

def on_connection_change(connected, message):
    if connected:
        print(f"PLC conectado: {message}")
    else:
        print(f"PLC desconectado: {message}")

def on_input_change(input_num, new_state):
    print(f"Entrada I{input_num} cambió a {'ON' if new_state else 'OFF'}")

# Registrar callbacks
plc_manager.register_connection_callback(on_connection_change)
plc_manager.register_input_change_callback(on_input_change)
```

## Manejo de Errores

### Errores Comunes

1. **"No está conectado al PLC"**
   - Solución: Llamar `Connect()` antes de operaciones

2. **"Índice de salida inválido"**
   - Solución: Usar índices 1-12 para salidas Q, 1-4 para marcas M

3. **"Índice de entrada inválido"**
   - Solución: Usar índices 1-8 para entradas I

4. **"Error de conexión"**
   - Solución: Verificar IP, puerto y conectividad de red

### Ejemplo de Manejo de Errores

```python
def safe_write_output(output_num, value):
    success, message = write_PLC('Q', output_num, value)
    if not success:
        print(f"Error escribiendo Q{output_num}: {message}")
        # Intentar reconectar si es un error de conexión
        if "No está conectado" in message:
            Connect()
    return success

def safe_read_input(input_num):
    success, result = read_PLC(input_num)
    if not success:
        print(f"Error leyendo I{input_num}: {result}")
        return None
    return result == "True"
```

## Ejemplo de Uso Completo

```python
from PLC_LOGO_manager import Connect, Disconnect, write_PLC, read_PLC, isAlive
import time

def main():
    # Conectar al PLC
    success, message = Connect("192.168.29.3")
    if not success:
        print(f"Error de conexión: {message}")
        return
    
    print("Conectado al PLC")
    
    try:
        # Verificar estado de conexión
        if isAlive():
            print("PLC está activo")
        
        # Leer estado de entrada I1
        success, result = read_PLC(1)
        if success:
            state = result == "True"
            print(f"Estado de I1: {'ON' if state else 'OFF'}")
        
        # Activar salida Q1
        success, message = write_PLC('Q', 1, True)
        if success:
            print("Q1 activada")
        
        # Esperar 2 segundos
        time.sleep(2)
        
        # Desactivar salida Q1
        success, message = write_PLC('Q', 1, False)
        if success:
            print("Q1 desactivada")
        
        # Activar marca M1
        success, message = write_PLC('M', 1, True)
        if success:
            print("M1 activada")
            
    except KeyboardInterrupt:
        print("\nInterrumpido por usuario")
    finally:
        # Desconectar al finalizar
        success, message = Disconnect()
        if success:
            print("Desconectado del PLC")

if __name__ == "__main__":
    main()
```

## Consideraciones de Rendimiento

- **Keep-alive cada 5 segundos**: Balance entre responsividad y carga de red
- **Thread-safe**: Operaciones seguras para uso concurrente
- **Reconexión automática**: Minimiza tiempo de inactividad
- **Logging detallado**: Facilita debugging y monitoreo

## Limitaciones

- **8 entradas máximo**: I1-I8
- **12 salidas máximo**: Q1-Q12
- **4 marcas máximo**: M1-M4
- **Protocolo Modbus TCP**: Requiere conectividad de red estable

## Troubleshooting

### Problemas de Conexión

1. **Verificar IP y puerto**
2. **Comprobar conectividad de red**
3. **Verificar configuración del PLC**
4. **Revisar logs del sistema**

### Problemas de Comunicación

1. **Verificar timeout de conexión**
2. **Comprobar firewall**
3. **Verificar configuración Modbus del PLC**
4. **Revisar logs de errores**

## Logs y Debugging

El módulo genera logs detallados con prefijo `[PLC_LOGO]`:

```
[PLC_LOGO] Gestor de PLC LOGO inicializado
[PLC_LOGO] Intentando conectar a 192.168.29.3:502
[PLC_LOGO] Conectado exitosamente a 192.168.29.3
[PLC_LOGO] Keep-alive iniciado
[PLC_LOGO] Q1 SET: dirección 8192
[PLC_LOGO] I1 leída: ON
```

## Integración con Otros Módulos

El gestor puede integrarse fácilmente con otros módulos del proyecto:

```python
# Integración con procesos.py
from PLC_LOGO_manager import write_PLC, read_PLC

def proceso_feeder():
    # Leer sensor de presencia
    success, result = read_PLC(1)
    if success and result == "True":
        # Activar alimentador
        write_PLC('Q', 1, True)
```

## Versión y Compatibilidad

- **Python**: 3.7+
- **pymodbus**: 3.0+
- **PLC LOGO**: Todas las versiones con Modbus TCP
- **Sistema**: Windows, Linux, macOS
