# aruco_manager.py
import json, time
from pathlib import Path
from typing import Dict, Any, Tuple, List, Optional

import webcam_manager as wcam

ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "config.json"
CALIB_IMG = ROOT / "CalibracionEscala.png"

def _load_config() -> Dict[str, Any]:
    if CONFIG_PATH.exists():
        try:
            return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}

def _save_config(cfg: Dict[str, Any]) -> None:
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")

# --- util: lazy import opencv + numpy (para no tirar abajo el server si faltan) ---
def _cv2_np():
    try:
        import cv2, numpy as np
        return cv2, np
    except Exception as e:
        raise RuntimeError(f"OpenCV/Numpy no disponibles: {e}")

# --- tabla de diccionarios ArUco ---
def _get_aruco_dict(cv2, grid: str, lib_size: int):
    if not hasattr(cv2, "aruco"):
        raise RuntimeError("cv2.aruco no disponible. Instalá: pip install opencv-contrib-python")
    A = cv2.aruco
    table = {
        "4x4": {50: A.DICT_4X4_50, 100: A.DICT_4X4_100, 250: A.DICT_4X4_250, 1000: A.DICT_4X4_1000},
        "5x5": {50: A.DICT_5X5_50, 100: A.DICT_5X5_100, 250: A.DICT_5X5_250, 1000: A.DICT_5X5_1000},
        "6x6": {50: A.DICT_6X6_50, 100: A.DICT_6X6_100, 250: A.DICT_6X6_250, 1000: A.DICT_6X6_1000},
        "7x7": {50: A.DICT_7X7_50, 100: A.DICT_7X7_100, 250: A.DICT_7X7_250, 1000: A.DICT_7X7_1000},
    }
    enum_val = table[grid][int(lib_size)]
    return A.getPredefinedDictionary(enum_val)

def _detect(cv2, img, ar_dict):
    A = cv2.aruco
    try:
        params = A.DetectorParameters()
    except Exception:
        params = A.DetectorParameters_create()
    try:
        detector = A.ArucoDetector(ar_dict, params)
        corners, ids, _ = detector.detectMarkers(img)
    except Exception:
        corners, ids, _ = A.detectMarkers(img, ar_dict, parameters=params)
    return corners, ids

def _angle_deg_from_corners(np, corners):
    p0, p1 = corners[0][0], corners[0][1]
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    ang = float(np.degrees(np.arctan2(dy, dx)))
    if ang <= -180: ang += 360
    if ang > 180: ang -= 360
    return ang

def _px_per_mm_from_corners(np, corners, marker_size_mm: float) -> float:
    pts = corners[0]
    d01 = np.linalg.norm(pts[1] - pts[0])
    d12 = np.linalg.norm(pts[2] - pts[1])
    d23 = np.linalg.norm(pts[3] - pts[2])
    d30 = np.linalg.norm(pts[0] - pts[3])
    px_side = float(np.mean([d01, d12, d23, d30]))
    if marker_size_mm <= 0: return 0.0
    return px_side / float(marker_size_mm)

def _center_from_corners(np, corners):
    pts = corners[0]
    cx = float(np.mean(pts[:, 0]))
    cy = float(np.mean(pts[:, 1]))
    return cx, cy

def _annotate_result(cv2, np, img, corners, target_id: int, px_per_mm: float, ang: float, dx_mm: float, dy_mm: float):
    # Dibuja el contorno / esquinas del marcador
    A = cv2.aruco
    try:
        A.drawDetectedMarkers(img, [corners], np.array([[target_id]], dtype=np.int32))
    except Exception:
        for p in corners[0].astype(int):
            cv2.circle(img, tuple(p), 3, (0,0,255), -1)

    # Puntos base (convención ArUco OpenCV): 0=TL, 1=TR, 2=BR, 3=BL
    pts = corners[0]
    p0 = pts[0]  # top-left
    p1 = pts[1]  # top-right
    p3 = pts[3]  # bottom-left

    # Centro del marcador
    cx = float(np.mean(pts[:, 0]))
    cy = float(np.mean(pts[:, 1]))
    c  = np.array([cx, cy], dtype=float)

    # Vectores de ejes locales proyectados en la imagen:
    # X_local: p0 -> p1 (borde superior) ; Y_local: p0 -> p3 (borde izquierdo)
    vx = (p1 - p0).astype(float)
    vy = (p3 - p0).astype(float)

    # Normalización y largo visual (proporcional al lado del marcador)
    side = float(np.mean([
        np.linalg.norm(pts[1] - pts[0]),
        np.linalg.norm(pts[2] - pts[1]),
        np.linalg.norm(pts[3] - pts[2]),
        np.linalg.norm(pts[0] - pts[3]),
    ]))
    L = max(20.0, 0.45 * side)  # longitud de flechas en px

    def _unit(v):
        n = np.linalg.norm(v)
        return v / n if n > 1e-6 else v

    ux = _unit(vx); uy = _unit(vy)

    tip_x = (c + ux * L).astype(int)
    tip_y = (c + uy * L).astype(int)
    c_int = c.astype(int)

    # Dibujo de ejes: X rojo, Y verde (estándar OpenCV drawAxis)
    cv2.arrowedLine(img, tuple(c_int), tuple(tip_x), (0, 0, 255), 2, tipLength=0.25)  # X
    cv2.arrowedLine(img, tuple(c_int), tuple(tip_y), (0, 255, 0), 2, tipLength=0.25)  # Y

    # Etiquetas cerca de las puntas
    cv2.putText(img, "X", tuple(tip_x + np.array([4, -4])), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0,0,255), 2, cv2.LINE_AA)
    cv2.putText(img, "Y", tuple(tip_y + np.array([4, -4])), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0,255,0), 2, cv2.LINE_AA)

    # Centro del marcador (verde)
    cv2.circle(img, tuple(c_int), 4, (0,255,0), -1)

    # Caja de leyenda
    txt = f"ID {target_id} | ang(X vs +X img)={ang:.2f}° | dx={dx_mm:.2f}mm dy={dy_mm:.2f}mm | px/mm={px_per_mm:.5f}"
    (tw, th), _ = cv2.getTextSize(txt, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
    x0, y0 = 10, 12
    cv2.rectangle(img, (x0-6, y0-10), (x0-6+tw+12, y0-10+th+12), (0,0,0), -1)
    cv2.putText(img, txt, (x0, y0+th), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255,255,255), 1, cv2.LINE_AA)

    # Mini leyenda ejes
    cv2.putText(img, "X: rojo (p0->p1)   Y: verde (p0->p3)", (10, y0+th+22),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200,200,200), 1, cv2.LINE_AA)


def calibrate_from_file(image_path: str, grid: str, lib_size: int, marker_size_mm: float, target_id: int) -> Dict[str, Any]:
    cv2, np = _cv2_np()
    img = cv2.imread(image_path, cv2.IMREAD_COLOR)
    if img is None:
        return {"ok": False, "message": "No se pudo leer la imagen para calibrar.", "found": False}
    h, w = img.shape[:2]

    try:
        ar_dict = _get_aruco_dict(cv2, grid, int(lib_size))
    except Exception as e:
        return {"ok": False, "message": str(e), "found": False}

    corners, ids = _detect(cv2, img, ar_dict)
    if ids is None or len(ids) == 0:
        cv2.imwrite(str(CALIB_IMG), img)  # guardamos igual
        return {"ok": True, "found": False, "found_ids": [], "message": "No se detectaron ArUcos en la imagen.", "image_url": f"/{CALIB_IMG.name}"}

    ids_list = [int(x) for x in ids.flatten().tolist()]
    target_id = int(target_id)

    if target_id not in ids_list:
        # marcar todos los detectados para debugging
        try:
            cv2.aruco.drawDetectedMarkers(img, corners, ids)
        except Exception:
            for c in corners:
                for p in c[0].astype(int):
                    cv2.circle(img, tuple(p), 3, (0,0,255), -1)
        cv2.imwrite(str(CALIB_IMG), img)
        return {"ok": True, "found": False, "found_ids": ids_list, "target_id": target_id,
                "message": f"ID {target_id} no encontrado. Detectados: {ids_list}", "image_url": f"/{CALIB_IMG.name}"}

    # Métricas en el objetivo
    k = ids_list.index(target_id)
    c = corners[k]
    px_per_mm = _px_per_mm_from_corners(np, c, float(marker_size_mm))
    ang = _angle_deg_from_corners(np, c)
    cx, cy = _center_from_corners(np, c)
    dx_mm = cx / px_per_mm if px_per_mm > 0 else 0.0
    dy_mm = cy / px_per_mm if px_per_mm > 0 else 0.0

    # Anotar sobre la misma imagen y guardar
    _annotate_result(cv2, np, img, c, target_id, px_per_mm, ang, dx_mm, dy_mm)
    cv2.imwrite(str(CALIB_IMG), img)

    # Persistir calibración
    cfg = _load_config()
    cfg["calibration"] = {
        "grid": str(grid),
        "lib_size": int(lib_size),
        "marker_size_mm": float(marker_size_mm),
        "target_id": target_id,
        "px_per_mm": float(round(px_per_mm, 5)),
        "angle_deg": float(round(ang, 2)),
        "origin_offset_mm": {"dx": float(round(dx_mm, 2)), "dy": float(round(dy_mm, 2))},
        "last_image_size_px": [int(w), int(h)],
        "timestamp": int(time.time())
    }
    _save_config(cfg)

    return {
        "ok": True, "found": True, "found_ids": ids_list, "target_id": target_id,
        "angle_deg": float(round(ang, 2)), "dx_mm": float(round(dx_mm, 2)), "dy_mm": float(round(dy_mm, 2)),
        "px_per_mm": float(round(px_per_mm, 5)), "message": "Calibración OK. Imagen anotada guardada.",
        "image_url": f"/{CALIB_IMG.name}"
    }

def calibrate(grid: str, lib_size: int, marker_size_mm: float, target_id: int) -> Dict[str, Any]:
    """
    1) Toma una foto del stream -> CalibracionEscala.png
    2) Corre el análisis ArUco sobre esa imagen y guarda resultados/overlay.
    """
    ok, path, err = wcam.snapshot(str(CALIB_IMG))
    if not ok:
        return {"ok": False, "message": f"No se pudo tomar la foto: {err}", "found": False}
    return calibrate_from_file(path, grid, lib_size, marker_size_mm, target_id)
