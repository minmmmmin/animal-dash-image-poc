"""OpenCV-based preprocessing: paper detection -> perspective correction ->
background removal -> content crop -> square padding.

Design doc pipeline (see project notes):
  撮影画像 -> 紙の領域だけ切り出す -> 明るさ・影を補正 ->
  「白に近い画素」を背景と判定 -> 背景のalphaを0にする ->
  絵の周囲だけcrop -> 透過PNG
"""

from __future__ import annotations

from dataclasses import dataclass, field

import cv2
import numpy as np

A4_ASPECT = 297.0 / 210.0  # height / width


@dataclass
class PreprocessResult:
    warped_bgr: np.ndarray
    illum_corrected_bgr: np.ndarray
    mask: np.ndarray
    rgba: np.ndarray
    cropped_rgba: np.ndarray
    padded_rgba: np.ndarray
    corners: np.ndarray | None
    debug: dict = field(default_factory=dict)


def find_paper_corners(image_bgr: np.ndarray) -> np.ndarray | None:
    """Locate the largest 4-point quadrilateral contour, assumed to be the paper sheet."""
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blurred, 50, 150)
    edges = cv2.dilate(edges, np.ones((5, 5), np.uint8), iterations=1)

    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None

    image_area = image_bgr.shape[0] * image_bgr.shape[1]
    contours = sorted(contours, key=cv2.contourArea, reverse=True)

    for contour in contours[:5]:
        area = cv2.contourArea(contour)
        if area < image_area * 0.2:
            continue
        perimeter = cv2.arcLength(contour, True)
        approx = cv2.approxPolyDP(contour, 0.02 * perimeter, True)
        if len(approx) == 4 and cv2.isContourConvex(approx):
            return approx.reshape(4, 2).astype(np.float32)

    # Fallback: rotated bounding rect of the largest contour.
    largest = contours[0]
    if cv2.contourArea(largest) < image_area * 0.1:
        return None
    rect = cv2.minAreaRect(largest)
    return cv2.boxPoints(rect).astype(np.float32)


def order_points(pts: np.ndarray) -> np.ndarray:
    """Order 4 points as top-left, top-right, bottom-right, bottom-left."""
    s = pts.sum(axis=1)
    diff = np.diff(pts, axis=1).reshape(-1)
    ordered = np.zeros((4, 2), dtype=np.float32)
    ordered[0] = pts[np.argmin(s)]  # top-left
    ordered[2] = pts[np.argmax(s)]  # bottom-right
    ordered[1] = pts[np.argmin(diff)]  # top-right
    ordered[3] = pts[np.argmax(diff)]  # bottom-left
    return ordered


def warp_perspective(image_bgr: np.ndarray, corners: np.ndarray, output_width: int = 1000) -> np.ndarray:
    ordered = order_points(corners)
    output_height = int(output_width * A4_ASPECT)
    dst = np.array(
        [[0, 0], [output_width - 1, 0], [output_width - 1, output_height - 1], [0, output_height - 1]],
        dtype=np.float32,
    )
    matrix = cv2.getPerspectiveTransform(ordered, dst)
    return cv2.warpPerspective(image_bgr, matrix, (output_width, output_height))


def correct_illumination(image_bgr: np.ndarray, blur_ksize: int = 55) -> np.ndarray:
    """Flatten uneven lighting/shadow by dividing out a heavily-blurred background estimate."""
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    background = cv2.GaussianBlur(gray, (blur_ksize, blur_ksize), 0)
    background = np.where(background == 0, 1, background).astype(np.float32)
    normalized = (gray.astype(np.float32) / background) * 255.0
    normalized = np.clip(normalized, 0, 255).astype(np.uint8)

    result = image_bgr.copy()
    gray_safe = np.where(gray == 0, 1, gray).astype(np.float32)
    scale = (normalized.astype(np.float32) / gray_safe)[..., None]
    result = np.clip(image_bgr.astype(np.float32) * scale, 0, 255).astype(np.uint8)
    return result


def build_ink_mask(
    image_bgr: np.ndarray,
    brightness_thresh: int = 225,
    saturation_thresh: int = 30,
) -> np.ndarray:
    """Mask of "ink" pixels: anything that is NOT near-white paper background."""
    hsv = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2HSV)
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    saturation = hsv[:, :, 1]

    is_background = (gray > brightness_thresh) & (saturation < saturation_thresh)
    mask = np.where(is_background, 0, 255).astype(np.uint8)

    kernel = np.ones((3, 3), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
    mask = cv2.GaussianBlur(mask, (3, 3), 0)
    return mask


def apply_mask_alpha(image_bgr: np.ndarray, mask: np.ndarray) -> np.ndarray:
    bgra = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2BGRA)
    bgra[:, :, 3] = mask
    return bgra


def crop_to_content(image_bgra: np.ndarray, margin: int = 20) -> np.ndarray:
    alpha = image_bgra[:, :, 3]
    ys, xs = np.where(alpha > 10)
    if len(xs) == 0 or len(ys) == 0:
        return image_bgra

    x0, x1 = max(xs.min() - margin, 0), min(xs.max() + margin, image_bgra.shape[1])
    y0, y1 = max(ys.min() - margin, 0), min(ys.max() + margin, image_bgra.shape[0])
    return image_bgra[y0:y1, x0:x1]


def pad_to_square(image_bgra: np.ndarray, size: int | None = None) -> np.ndarray:
    h, w = image_bgra.shape[:2]
    side = size or max(h, w)

    scale = min(side / h, side / w, 1.0) if max(h, w) > side else 1.0
    if scale != 1.0:
        image_bgra = cv2.resize(image_bgra, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
        h, w = image_bgra.shape[:2]

    canvas = np.zeros((side, side, 4), dtype=np.uint8)
    y_off = (side - h) // 2
    x_off = (side - w) // 2
    canvas[y_off : y_off + h, x_off : x_off + w] = image_bgra
    return canvas


def process_image(
    image_bgr: np.ndarray,
    output_square_size: int = 800,
    crop_margin: int = 20,
) -> PreprocessResult:
    corners = find_paper_corners(image_bgr)
    warped = warp_perspective(image_bgr, corners) if corners is not None else image_bgr.copy()

    illum_corrected = correct_illumination(warped)
    mask = build_ink_mask(illum_corrected)
    rgba = apply_mask_alpha(illum_corrected, mask)
    cropped = crop_to_content(rgba, margin=crop_margin)
    padded = pad_to_square(cropped, size=output_square_size)

    return PreprocessResult(
        warped_bgr=warped,
        illum_corrected_bgr=illum_corrected,
        mask=mask,
        rgba=rgba,
        cropped_rgba=cropped,
        padded_rgba=padded,
        corners=corners,
    )
