# autotune.py - Optimización automática de parámetros
import time
import random
import json
from typing import List, Dict, Optional, Tuple, Callable
from .utils import _cv2_safe, _np_safe

class AutoTuneOptimizer:
    """Optimizador automático de parámetros para filtros de imagen."""
    
    def __init__(self):
        self.best_params = {}
        self.best_score = 0.0
        self.iteration_count = 0
        self.max_iterations = 100
        self.evaluation_history = []
        
    def optimize_filter_params(self, filter_type: str, frame, target_metrics: Dict) -> Dict:
        """
        Optimiza los parámetros de un filtro específico.
        
        Args:
            filter_type: Tipo de filtro a optimizar
            frame: Imagen de entrada para evaluación
            target_metrics: Métricas objetivo (ej: {"noise_reduction": 0.8, "detail_preservation": 0.7})
        
        Returns:
            Diccionario con los mejores parámetros encontrados
        """
        print(f"[autotune] Iniciando optimización para filtro: {filter_type}")
        
        # Definir espacio de búsqueda según el tipo de filtro
        param_ranges = self._get_param_ranges(filter_type)
        
        # Inicializar variables
        self.best_params = {}
        self.best_score = 0.0
        self.iteration_count = 0
        self.evaluation_history = []
        
        # Estrategia de optimización: combinación de búsqueda aleatoria y hill climbing
        for iteration in range(self.max_iterations):
            self.iteration_count = iteration + 1
            
            # Generar parámetros de prueba
            if iteration < 20:  # Primera fase: exploración aleatoria
                test_params = self._generate_random_params(param_ranges)
            else:  # Segunda fase: refinamiento local
                test_params = self._generate_local_params(self.best_params, param_ranges)
            
            # Evaluar parámetros
            score = self._evaluate_filter_performance(filter_type, frame, test_params, target_metrics)
            
            # Actualizar mejor resultado
            if score > self.best_score:
                self.best_score = score
                self.best_params = test_params.copy()
                print(f"[autotune] Iteración {iteration + 1}: Nuevo mejor score = {score:.4f}")
            
            # Guardar historial
            self.evaluation_history.append({
                'iteration': iteration + 1,
                'params': test_params,
                'score': score
            })
            
            # Criterio de parada: si no hay mejora en las últimas 10 iteraciones
            if iteration > 10:
                recent_scores = [h['score'] for h in self.evaluation_history[-10:]]
                if max(recent_scores) <= self.best_score:
                    print(f"[autotune] Convergencia alcanzada en iteración {iteration + 1}")
                    break
        
        print(f"[autotune] Optimización completada. Mejor score: {self.best_score:.4f}")
        print(f"[autotune] Mejores parámetros: {self.best_params}")
        
        return self.best_params
    
    def _get_param_ranges(self, filter_type: str) -> Dict:
        """Define los rangos de parámetros para cada tipo de filtro."""
        ranges = {
            'bilateral': {
                'd': (5, 25),
                'sigma_color': (25, 150),
                'sigma_space': (25, 150)
            },
            'gaussian': {
                'kernel_size': (3, 15),
                'sigma': (0.5, 3.0)
            },
            'median': {
                'kernel_size': (3, 11)
            },
            'morphological': {
                'kernel_size': (3, 9),
                'operation': ['open', 'close', 'gradient', 'tophat', 'blackhat'],
                'kernel_type': ['ellipse', 'rect', 'cross']
            },
            'noise_reduction': {
                'h': (5, 20)
            },
            'contrast_enhance': {
                'alpha': (0.5, 2.0),
                'beta': (-50, 50)
            },
            'edge_enhance': {
                'strength': (0.1, 1.0)
            },
            'clahe': {
                'clip_limit': (1.0, 4.0),
                'tile_grid_size': (4, 16)
            },
            'sharpen': {
                'strength': (0.1, 1.0)
            }
        }
        
        return ranges.get(filter_type, {})
    
    def _generate_random_params(self, param_ranges: Dict) -> Dict:
        """Genera parámetros aleatorios dentro de los rangos especificados."""
        params = {}
        
        for param_name, param_range in param_ranges.items():
            if isinstance(param_range, tuple):
                if isinstance(param_range[0], int):
                    # Parámetro entero
                    params[param_name] = random.randint(param_range[0], param_range[1])
                else:
                    # Parámetro flotante
                    params[param_name] = random.uniform(param_range[0], param_range[1])
            elif isinstance(param_range, list):
                # Parámetro categórico
                params[param_name] = random.choice(param_range)
        
        return params
    
    def _generate_local_params(self, base_params: Dict, param_ranges: Dict) -> Dict:
        """Genera parámetros cercanos a los mejores encontrados."""
        params = base_params.copy()
        
        for param_name, param_range in param_ranges.items():
            if param_name in params:
                if isinstance(param_range, tuple):
                    if isinstance(param_range[0], int):
                        # Variación local para enteros
                        current_value = params[param_name]
                        variation = random.randint(-2, 2)
                        new_value = max(param_range[0], min(param_range[1], current_value + variation))
                        params[param_name] = new_value
                    else:
                        # Variación local para flotantes
                        current_value = params[param_name]
                        variation = random.uniform(-0.2, 0.2) * (param_range[1] - param_range[0])
                        new_value = max(param_range[0], min(param_range[1], current_value + variation))
                        params[param_name] = new_value
                elif isinstance(param_range, list):
                    # Para parámetros categóricos, ocasionalmente cambiar
                    if random.random() < 0.3:
                        params[param_name] = random.choice(param_range)
        
        return params
    
    def _evaluate_filter_performance(self, filter_type: str, frame, params: Dict, target_metrics: Dict) -> float:
        """
        Evalúa el rendimiento de un conjunto de parámetros.
        Retorna un score entre 0 y 1 (mayor es mejor).
        """
        try:
            # Aplicar filtro con los parámetros de prueba
            from .filters import _apply_cascade_filter_v2
            filtered_frame = _apply_cascade_filter_v2(frame.copy(), filter_type, params)
            
            if filtered_frame is None:
                return 0.0
            
            # Calcular métricas de calidad
            metrics = self._calculate_image_metrics(filtered_frame, target_metrics)
            
            # Calcular score ponderado
            score = self._calculate_weighted_score(metrics, target_metrics)
            
            return score
            
        except Exception as e:
            print(f"[autotune] Error evaluando parámetros: {e}")
            return 0.0
    
    def _calculate_image_metrics(self, frame, target_metrics: Dict) -> Dict:
        """Calcula métricas de calidad de la imagen."""
        cv2 = _cv2_safe()
        np = _np_safe()
        if cv2 is None or np is None:
            return {}
        
        metrics = {}
        
        try:
            # Convertir a escala de grises si es necesario
            if len(frame.shape) == 3:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            else:
                gray = frame
            
            # 1. Reducción de ruido (usando varianza de Laplaciano)
            if 'noise_reduction' in target_metrics:
                laplacian = cv2.Laplacian(gray, cv2.CV_64F)
                noise_level = laplacian.var()
                # Normalizar: menor ruido = mejor score
                noise_score = max(0, 1 - (noise_level / 200.0))
                metrics['noise_reduction'] = noise_score
            
            # 2. Preservación de detalles (usando gradiente)
            if 'detail_preservation' in target_metrics:
                grad_x = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
                grad_y = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
                gradient_magnitude = np.sqrt(grad_x**2 + grad_y**2)
                detail_score = np.mean(gradient_magnitude) / 255.0
                metrics['detail_preservation'] = detail_score
            
            # 3. Nitidez (usando varianza de gradiente)
            if 'sharpness' in target_metrics:
                sharpness = np.var(gradient_magnitude)
                sharpness_score = min(1.0, sharpness / 1000.0)
                metrics['sharpness'] = sharpness_score
            
            # 4. Contraste (usando desviación estándar)
            if 'contrast' in target_metrics:
                contrast = np.std(gray)
                contrast_score = contrast / 128.0  # Normalizar
                metrics['contrast'] = contrast_score
            
            # 5. Separación de objetos (usando entropía local)
            if 'object_separation' in target_metrics:
                # Calcular entropía local usando ventanas pequeñas
                entropy = self._calculate_local_entropy(gray)
                metrics['object_separation'] = entropy
            
        except Exception as e:
            print(f"[autotune] Error calculando métricas: {e}")
        
        return metrics
    
    def _calculate_local_entropy(self, gray_image) -> float:
        """Calcula la entropía local de la imagen."""
        np = _np_safe()
        if np is None:
            return 0.0
        
        try:
            # Dividir imagen en bloques pequeños
            block_size = 8
            height, width = gray_image.shape
            entropy_sum = 0.0
            block_count = 0
            
            for y in range(0, height - block_size, block_size):
                for x in range(0, width - block_size, block_size):
                    block = gray_image[y:y+block_size, x:x+block_size]
                    
                    # Calcular histograma del bloque
                    hist, _ = np.histogram(block, bins=256, range=(0, 256))
                    hist = hist / hist.sum()  # Normalizar
                    
                    # Calcular entropía
                    entropy = 0.0
                    for p in hist:
                        if p > 0:
                            entropy -= p * np.log2(p)
                    
                    entropy_sum += entropy
                    block_count += 1
            
            # Promedio de entropías locales
            if block_count > 0:
                return entropy_sum / block_count
            else:
                return 0.0
                
        except Exception as e:
            print(f"[autotune] Error calculando entropía local: {e}")
            return 0.0
    
    def _calculate_weighted_score(self, metrics: Dict, target_metrics: Dict) -> float:
        """Calcula un score ponderado basado en las métricas calculadas."""
        if not metrics:
            return 0.0
        
        total_score = 0.0
        total_weight = 0.0
        
        for metric_name, target_value in target_metrics.items():
            if metric_name in metrics:
                # Peso basado en la importancia del target
                weight = 1.0
                if target_value > 0.8:
                    weight = 1.5  # Métricas muy importantes
                elif target_value < 0.3:
                    weight = 0.7  # Métricas menos importantes
                
                # Calcular score para esta métrica
                actual_value = metrics[metric_name]
                # Score basado en qué tan cerca está del target
                metric_score = 1.0 - abs(actual_value - target_value)
                metric_score = max(0.0, metric_score)  # No permitir scores negativos
                
                total_score += metric_score * weight
                total_weight += weight
        
        if total_weight > 0:
            return total_score / total_weight
        else:
            return 0.0
    
    def get_optimization_report(self) -> Dict:
        """Genera un reporte de la optimización realizada."""
        return {
            'best_params': self.best_params,
            'best_score': self.best_score,
            'iterations': self.iteration_count,
            'convergence': len(self.evaluation_history) < self.max_iterations,
            'evaluation_history': self.evaluation_history[-10:]  # Últimas 10 evaluaciones
        }

def run_filter_autotune(filter_type: str, frame, target_metrics: Dict) -> Dict:
    """
    Función de conveniencia para ejecutar autotune en un filtro.
    
    Args:
        filter_type: Tipo de filtro a optimizar
        frame: Imagen de entrada
        target_metrics: Métricas objetivo
    
    Returns:
        Diccionario con los mejores parámetros encontrados
    """
    optimizer = AutoTuneOptimizer()
    best_params = optimizer.optimize_filter_params(filter_type, frame, target_metrics)
    
    # Generar reporte
    report = optimizer.get_optimization_report()
    
    print(f"[autotune] Reporte final:")
    print(f"  - Mejores parámetros: {best_params}")
    print(f"  - Score final: {report['best_score']:.4f}")
    print(f"  - Iteraciones: {report['iterations']}")
    print(f"  - Convergencia: {'Sí' if report['convergence'] else 'No'}")
    
    return best_params

def get_default_target_metrics(filter_type: str) -> Dict:
    """Obtiene métricas objetivo por defecto para cada tipo de filtro."""
    default_targets = {
        'bilateral': {
            'noise_reduction': 0.8,
            'detail_preservation': 0.7
        },
        'gaussian': {
            'noise_reduction': 0.9,
            'detail_preservation': 0.5
        },
        'median': {
            'noise_reduction': 0.8,
            'detail_preservation': 0.6
        },
        'morphological': {
            'noise_reduction': 0.7,
            'object_separation': 0.8
        },
        'noise_reduction': {
            'noise_reduction': 0.9,
            'detail_preservation': 0.8
        },
        'contrast_enhance': {
            'contrast': 0.8,
            'object_separation': 0.7
        },
        'edge_enhance': {
            'sharpness': 0.8,
            'detail_preservation': 0.6
        },
        'clahe': {
            'contrast': 0.8,
            'detail_preservation': 0.7
        },
        'sharpen': {
            'sharpness': 0.9,
            'detail_preservation': 0.8
        }
    }
    
    return default_targets.get(filter_type, {
        'noise_reduction': 0.7,
        'detail_preservation': 0.7
    })

def validate_filter_params(filter_type: str, params: Dict) -> bool:
    """Valida que los parámetros estén dentro de rangos aceptables."""
    cv2 = _cv2_safe()
    if cv2 is None:
        return False
    
    try:
        # Crear una imagen de prueba pequeña
        test_image = np.zeros((100, 100, 3), dtype=np.uint8)
        
        # Intentar aplicar el filtro
        from .filters import _apply_cascade_filter_v2
        result = _apply_cascade_filter_v2(test_image, filter_type, params)
        
        return result is not None
        
    except Exception as e:
        print(f"[autotune] Error validando parámetros: {e}")
        return False
