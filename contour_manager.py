# contour_manager.py
# Analítica de contornos para encontrar centroCilindros en imágenes de modelos (imgDatabase/<modelo>.png)

from pathlib import Path
from typing import Dict, Any, List, Tuple

ROOT = Path(__file__).resolve().parent
IMG_DB_DIR = ROOT / "imgDatabase"

OUT_DIR = ROOT / "imgOut"
OUT_DIR.mkdir(exist_ok=True)

__all__ = ["calcular_centro"]


def _cv2_np():
    """Import perezoso para no tirar abajo el server si falta OpenCV/Numpy."""
    try:
        import cv2, numpy as np
        return cv2, np
    except Exception as e:
        raise RuntimeError(f"OpenCV/Numpy no disponibles: {e}")


def _threshold_best(cv2, gray):
    """
    Prueba Otsu normal e invertido; devuelve el binario y sus contornos.
    Elige el que produzca más contornos (heurística simple).
    """
    bl = cv2.GaussianBlur(gray, (5, 5), 0)
    _, th = cv2.threshold(bl, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    _, thi = cv2.threshold(bl, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    cnts1, _ = cv2.findContours(th, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    cnts2, _ = cv2.findContours(thi, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

    if (cnts2 is not None and len(cnts2) > len(cnts1 or [])):
        return thi, cnts2
    return th, cnts1


def _rank_contours_by_area(cv2, contours: List) -> List[Tuple[int, float]]:
    """Devuelve [(idx, area_abs)] ordenado de mayor a menor área."""
    ranked = []
    for i, c in enumerate(contours or []):
        try:
            a = abs(cv2.contourArea(c))
        except Exception:
            a = 0.0
        ranked.append((i, float(a)))
    ranked.sort(key=lambda t: t[1], reverse=True)
    return ranked


def calcular_centro(modelo: str) -> Dict[str, Any]:
    """
    Abre imgDatabase/<modelo>.png, detecta contornos y calcula el punto medio entre
    los centros geométricos (centroides) del agujero con menor X y el de mayor X,
    considerando como 'agujeros principales' al de índice 1 (2º mayor por área)
    y todos los demás con área >= 95% del área de ese índice 1.
    - Se asume que el índice 0 (mayor área) es el contorno externo de la junta.
    - Genera overlay anotado en imgDatabase/<modelo>_annot.png.
    Devuelve: { ok, centro: {x,y}, image_url, message? }
    """
    cv2, np = _cv2_np()

    # 1) Abrir imagen
    path = IMG_DB_DIR / f"{modelo}.png"
    if not path.exists():
        return {"ok": False, "message": f"No existe la imagen: {path}"}

    img = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if img is None:
        return {"ok": False, "message": "No se pudo leer la imagen (formato o permisos)."}

    # 2) Binarizar y encontrar contornos
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    th, cnts = _threshold_best(cv2, gray)

    # Recalcular contornos sobre el binario elegido para coherencia
    cnts, hier = cv2.findContours(th, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    if cnts is None or len(cnts) < 2:
        return {"ok": False, "message": "No se detectaron suficientes contornos (mínimo 2)."}

    # 3) Ordenar por área descendente
    ranked = _rank_contours_by_area(cv2, cnts)
    if len(ranked) < 2:
        return {"ok": False, "message": "No hay agujeros internos detectados."}

    outer_idx, outer_area = ranked[0]
    ref_idx, ref_area = ranked[1]
    if ref_area <= 0:
        return {"ok": False, "message": "El área del agujero de referencia es 0."}

    # 4) Filtrar agujeros principales: índice 1 y todos con área >= 95% de ref_area
    area_threshold = 0.95 * ref_area
    principal_idxs = [idx for idx, area in ranked[1:] if area >= area_threshold]
    if len(principal_idxs) < 2:
        return {"ok": False, "message": "Se requieren al menos 2 agujeros principales para calcular el centro."}

    # 5) Calcular centroides (geométricos) de agujeros principales
    centros = []
    for idx in principal_idxs:
        M = cv2.moments(cnts[idx])
        if M["m00"] == 0:
            continue
        cx = float(M["m10"] / M["m00"])
        cy = float(M["m01"] / M["m00"])
        centros.append((idx, cx, cy))

    if len(centros) < 2:
        return {"ok": False, "message": "No se pudieron obtener centroides válidos."}

    # 6) Elegir extremos por X y punto medio
    left = min(centros, key=lambda t: t[1])
    right = max(centros, key=lambda t: t[1])
    cx_mid = (left[1] + right[1]) / 2.0
    cy_mid = (left[2] + right[2]) / 2.0

    # 7) Overlay de diagnóstico
    vis = img.copy()
    # Contorno externo en cian
    try:
        cv2.drawContours(vis, [cnts[outer_idx]], -1, (255, 255, 0), 2)
    except Exception:
        pass

    # Agujeros principales en magenta y sus centros en verde
    for idx, cx, cy in centros:
        try:
            cv2.drawContours(vis, [cnts[idx]], -1, (255, 0, 255), 2)
        except Exception:
            pass
        cv2.circle(vis, (int(cx), int(cy)), 5, (0, 255, 0), -1)

    # Segmento entre extremos (rojo)
    cv2.line(vis, (int(left[1]), int(left[2])), (int(right[1]), int(right[2])), (0, 0, 255), 2)
    # Punto medio (amarillo)
    cv2.circle(vis, (int(cx_mid), int(cy_mid)), 6, (0, 255, 255), -1)

    label = f"centroCilindros=({cx_mid:.2f}, {cy_mid:.2f})  N={len(centros)}"
    (tw, th_text), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
    cv2.rectangle(vis, (10, 10), (10 + tw + 10, 10 + th_text + 10), (0, 0, 0), -1)
    cv2.putText(vis, label, (15, 10 + th_text), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                (255, 255, 255), 1, cv2.LINE_AA)
    
    out_path = OUT_DIR / f"{modelo}_annot.png"
    cv2.imwrite(str(out_path), vis)
    return {
        "ok": True,
        "centro": {"x": round(cx_mid, 2), "y": round(cy_mid, 2)},
        "image_url": f"/imgOut/{out_path.name}"
    }


if __name__ == "__main__":
    # Prueba rápida por consola:
    # python contour_manager.py MiModelo
    import sys
    name = sys.argv[1] if len(sys.argv) > 1 else ""
    print(calcular_centro(name))
