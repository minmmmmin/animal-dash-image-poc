"""Generate a synthetic "photo of a drawing on A4 paper" for pipeline testing,
without needing an actual scanned/photographed picture yet.

Simulates: a wood-colored desk background, an A4 sheet placed at a slight angle
with soft directional shading (to exercise perspective correction + illumination
correction), and a simple colored animal doodle drawn on it.
"""

from __future__ import annotations

import os

import cv2
import numpy as np

OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "samples")


def make_desk_background(width: int, height: int) -> np.ndarray:
    base = np.full((height, width, 3), (60, 90, 120), dtype=np.uint8)  # BGR wood-ish tone
    noise = np.random.default_rng(0).integers(-10, 10, size=(height, width, 3), endpoint=True)
    return np.clip(base.astype(int) + noise, 0, 255).astype(np.uint8)


def draw_animal_doodle(canvas: np.ndarray) -> None:
    h, w = canvas.shape[:2]
    # body
    cv2.ellipse(canvas, (w // 2, int(h * 0.6)), (int(w * 0.22), int(h * 0.15)), 0, 0, 360, (30, 80, 220), -1)
    # head
    cv2.circle(canvas, (int(w * 0.72), int(h * 0.42)), int(w * 0.1), (30, 80, 220), -1)
    # ears
    cv2.ellipse(canvas, (int(w * 0.68), int(h * 0.30)), (6, 18), -20, 0, 360, (10, 40, 160), -1)
    cv2.ellipse(canvas, (int(w * 0.78), int(h * 0.30)), (6, 18), 20, 0, 360, (10, 40, 160), -1)
    # legs
    for dx in (-0.15, -0.05, 0.08, 0.18):
        x = int(w * 0.5 + w * dx)
        cv2.line(canvas, (x, int(h * 0.7)), (x, int(h * 0.85)), (10, 40, 160), 10)
    # tail
    cv2.line(canvas, (int(w * 0.28), int(h * 0.55)), (int(w * 0.18), int(h * 0.45)), (10, 40, 160), 8)
    # eye
    cv2.circle(canvas, (int(w * 0.76), int(h * 0.40)), 3, (0, 0, 0), -1)
    # outline pass (black marker style)
    cv2.ellipse(canvas, (w // 2, int(h * 0.6)), (int(w * 0.22), int(h * 0.15)), 0, 0, 360, (0, 0, 0), 3)
    cv2.circle(canvas, (int(w * 0.72), int(h * 0.42)), int(w * 0.1), (0, 0, 0), 3)


def make_paper_with_shading(width: int, height: int) -> np.ndarray:
    paper = np.full((height, width, 3), 250, dtype=np.uint8)
    draw_animal_doodle(paper)

    # Simulate a soft directional shadow across the paper.
    yv, xv = np.mgrid[0:height, 0:width]
    shade = 1.0 - 0.25 * (xv / width)
    paper = np.clip(paper.astype(np.float32) * shade[..., None], 0, 255).astype(np.uint8)
    return paper


def composite_on_desk(paper: np.ndarray, desk_size: tuple[int, int], angle_deg: float = 6.0) -> np.ndarray:
    desk_w, desk_h = desk_size
    desk = make_desk_background(desk_w, desk_h)

    ph, pw = paper.shape[:2]
    center = (pw // 2, ph // 2)
    rot_matrix = cv2.getRotationMatrix2D(center, angle_deg, 1.0)
    cos, sin = abs(rot_matrix[0, 0]), abs(rot_matrix[0, 1])
    new_w, new_h = int(ph * sin + pw * cos), int(ph * cos + pw * sin)
    rot_matrix[0, 2] += (new_w / 2) - center[0]
    rot_matrix[1, 2] += (new_h / 2) - center[1]
    rotated = cv2.warpAffine(
        paper, rot_matrix, (new_w, new_h), borderMode=cv2.BORDER_CONSTANT, borderValue=(60, 90, 120)
    )

    x_off = (desk_w - new_w) // 2
    y_off = (desk_h - new_h) // 2
    desk[y_off : y_off + new_h, x_off : x_off + new_w] = rotated
    return desk


def main() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
    paper = make_paper_with_shading(700, 990)  # A4-ish ratio
    photo = composite_on_desk(paper, desk_size=(1000, 1300))
    out_path = os.path.join(OUT_DIR, "sample_01.jpg")
    cv2.imwrite(out_path, photo)
    print(f"wrote {os.path.abspath(out_path)}")


if __name__ == "__main__":
    main()
