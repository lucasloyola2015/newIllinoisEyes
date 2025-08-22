#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import os
from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.parse as up

class TestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        print(f"[test_server] GET: {self.path}")
        
        if self.path.startswith("/api/cascade_filters/config"):
            try:
                # Cargar configuración desde filter_config.json
                if os.path.exists("filter_config.json"):
                    print("[test_server] Archivo filter_config.json encontrado")
                    with open("filter_config.json", "r", encoding="utf-8") as f:
                        config = json.load(f)
                    print(f"[test_server] Configuración cargada: {len(config.get('profiles', {}))} perfiles")
                    
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    self.wfile.write(json.dumps({"ok": True, "config": config}).encode())
                else:
                    print("[test_server] Archivo filter_config.json no encontrado")
                    self.send_response(404)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps({"ok": False, "error": "Archivo no encontrado"}).encode())
            except Exception as e:
                print(f"[test_server] Error: {e}")
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"ok": False, "error": str(e)}).encode())
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Not found")

if __name__ == "__main__":
    server = HTTPServer(('localhost', 8001), TestHandler)
    print("Servidor de prueba iniciado en http://localhost:8001")
    print("Presiona Ctrl+C para detener")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor detenido")
        server.server_close()
