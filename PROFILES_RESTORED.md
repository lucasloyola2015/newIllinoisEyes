# 🎯 PERFILES DE DETECCIÓN RESTAURADOS

## ✅ **3 PERFILES COMPLETOS DISPONIBLES**

### 📊 **COMPARATIVA DE PERFILES**

| Característica | **Balanceado** | **Sensible** | **Estricto** |
|----------------|----------------|--------------|--------------|
| **Algoritmo** | MOG2 | KNN | MOG |
| **Área Mínima** | 500px | 200px | 1000px |
| **Área Máxima** | 50,000px | 30,000px | 100,000px |
| **Solidez Mín** | 0.5 | 0.3 | 0.8 |
| **Solidez Filtro** | 0.7 | 0.5 | 0.9 |
| **Tiempo Training** | 5s | 8s | 10s |
| **Aspecto Ratio** | 0.3-3.0 | 0.5-2.0 | 0.7-1.5 |

---

## 🎯 **1. PERFIL BALANCEADO (Defecto)**
- **ID**: `default-balanced`
- **Algoritmo**: MOG2
- **Uso**: Configuración equilibrada para la mayoría de casos
- **Características**:
  - Área mínima: 500px (objetos medianos)
  - Solidez: 0.7 (formas regulares)
  - Training: 5 segundos
  - Detección de sombras: NO

## 🔍 **2. PERFIL SENSIBLE**
- **ID**: `sensitive` 
- **Algoritmo**: KNN (optimizado)
- **Uso**: Detectar objetos pequeños y sutiles
- **Características**:
  - Área mínima: 200px (objetos pequeños)
  - Solidez: 0.5 (formas irregulares)
  - Training: 8 segundos
  - Umbral de distancia: 1000 (alta sensibilidad)

## 🎯 **3. PERFIL ESTRICTO**
- **ID**: `strict`
- **Algoritmo**: MOG
- **Uso**: Solo objetos bien definidos y grandes
- **Características**:
  - Área mínima: 1000px (objetos grandes)
  - Solidez: 0.9 (formas muy regulares)
  - Training: 10 segundos
  - Aspecto ratio: 0.7-1.5 (formas cuadradas/rectangulares)

---

## 🔧 **PARÁMETROS ESPECÍFICOS POR PERFIL**

### **Balanceado (MOG2)**
```json
"detection_method": "MOG2",
"var_threshold": 25,
"min_contour_area": 500,
"solidity_threshold": 0.7,
"training_time": 5000
```

### **Sensible (KNN)**
```json
"detection_method": "KNN",
"var_threshold": 15,
"min_contour_area": 200,
"solidity_threshold": 0.5,
"training_time": 8000
```

### **Estricto (MOG)**
```json
"detection_method": "MOG",
"var_threshold": 40,
"min_contour_area": 1000,
"solidity_threshold": 0.9,
"training_time": 10000
```

---

## 🎮 **CÓMO USAR LOS PERFILES**

1. **Acceder a configuración de detección**
2. **Seleccionar perfil en el dropdown superior**
3. **Los parámetros se cargan automáticamente**
4. **Hacer aprendizaje del fondo**
5. **Probar detección según el perfil elegido**

---

## 💡 **RECOMENDACIONES DE USO**

- **🎯 Balanceado**: Para uso general y primer acercamiento
- **🔍 Sensible**: Para objetos pequeños, irregulares o con poco contraste
- **🎯 Estricto**: Para aplicaciones que requieren alta precisión y pocos falsos positivos

---

## ✅ **ESTADO ACTUAL**

- **Perfiles disponibles**: ✅ 3 completos
- **Perfil activo**: `default-balanced`
- **Configuración**: ✅ Sincronizada
- **Parámetros**: ✅ Optimizados
- **Sistema**: ✅ Funcionando correctamente

**¡Los 3 perfiles están completamente restaurados y listos para usar!** 🎉
