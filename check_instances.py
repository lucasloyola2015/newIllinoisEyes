#!/usr/bin/env python3
"""
Script para verificar y limpiar instancias obsoletas de NewIllinoisEyes
"""

import os
import json
import sys
import psutil
from pathlib import Path

def check_instances():
    """Verifica las instancias de NewIllinoisEyes ejecutándose."""
    lock_file = Path(__file__).parent / ".newillinoiseyes.lock"
    
    print("🔍 Verificando instancias de NewIllinoisEyes...")
    
    if not lock_file.exists():
        print("✅ No hay lock file encontrado - sistema libre")
        return True
    
    try:
        with open(lock_file, 'r') as f:
            lock_info = json.load(f)
        
        pid = lock_info.get('pid')
        port = lock_info.get('port')
        start_time = lock_info.get('start_time')
        command = lock_info.get('command_line', 'N/A')
        
        print(f"📋 Información del lock:")
        print(f"   PID: {pid}")
        print(f"   Puerto: {port}")
        print(f"   Inicio: {start_time}")
        print(f"   Comando: {command}")
        
        # Verificar si el proceso existe
        try:
            process = psutil.Process(pid)
            if process.is_running():
                print(f"⚠️ Proceso {pid} está ejecutándose")
                print(f"   Nombre: {process.name()}")
                print(f"   Estado: {process.status()}")
                print(f"   Memoria: {process.memory_info().rss / 1024 / 1024:.1f} MB")
                return False
            else:
                print(f"❌ Proceso {pid} no está ejecutándose (proceso zombie)")
                return True
                
        except psutil.NoSuchProcess:
            print(f"❌ Proceso {pid} no existe")
            return True
        except Exception as e:
            print(f"⚠️ Error verificando proceso: {e}")
            return True
            
    except json.JSONDecodeError:
        print("❌ Lock file corrupto")
        return True
    except Exception as e:
        print(f"⚠️ Error leyendo lock file: {e}")
        return True

def clean_lock_file():
    """Elimina el lock file obsoleto."""
    lock_file = Path(__file__).parent / ".newillinoiseyes.lock"
    
    if lock_file.exists():
        try:
            lock_file.unlink()
            print("✅ Lock file eliminado")
            return True
        except Exception as e:
            print(f"❌ Error eliminando lock file: {e}")
            return False
    else:
        print("ℹ️ No hay lock file para eliminar")
        return True

def kill_process(pid):
    """Mata un proceso específico."""
    try:
        process = psutil.Process(pid)
        if process.is_running():
            print(f"🔄 Terminando proceso {pid}...")
            process.terminate()
            
            # Esperar un poco
            try:
                process.wait(timeout=5)
                print(f"✅ Proceso {pid} terminado")
                return True
            except psutil.TimeoutExpired:
                print(f"⚠️ Proceso {pid} no respondió, forzando...")
                process.kill()
                print(f"✅ Proceso {pid} forzado")
                return True
        else:
            print(f"ℹ️ Proceso {pid} ya no está ejecutándose")
            return True
            
    except psutil.NoSuchProcess:
        print(f"ℹ️ Proceso {pid} no existe")
        return True
    except Exception as e:
        print(f"❌ Error terminando proceso {pid}: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Verificar y limpiar instancias de NewIllinoisEyes")
    parser.add_argument("--clean", action="store_true", help="Limpiar lock file obsoleto")
    parser.add_argument("--kill", type=int, help="Matar proceso específico por PID")
    args = parser.parse_args()
    
    if args.kill:
        success = kill_process(args.kill)
        if success:
            clean_lock_file()
        sys.exit(0 if success else 1)
    
    if args.clean:
        success = clean_lock_file()
        sys.exit(0 if success else 1)
    
    # Verificación normal
    is_free = check_instances()
    
    if is_free:
        print("\n✅ Sistema libre - puedes iniciar NewIllinoisEyes")
        sys.exit(0)
    else:
        print("\n❌ Sistema ocupado - no puedes iniciar NewIllinoisEyes")
        print("💡 Usa --clean para limpiar lock obsoleto")
        print("💡 Usa --kill <PID> para terminar proceso específico")
        sys.exit(1)

if __name__ == "__main__":
    import argparse
    main()
