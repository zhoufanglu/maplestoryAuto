from __future__ import annotations

from typing import Optional

import cv2
import numpy as np


def get_minimap_loc_size(
    img_frame: np.ndarray,
    border_tolerance: int = 0,
) -> Optional[tuple[int, int, int, int]]:
    """Find the minimap position by detecting a white bordered rectangle.

    Returns (x, y, w, h) of the minimap inner area, or None if not found.
    """
    if img_frame is None:
        return None

    border_tolerance = max(0, int(border_tolerance))
    lower = np.array([255 - border_tolerance] * 3, dtype=np.uint8)
    upper = np.array([255, 255, 255], dtype=np.uint8)
    mask_white = cv2.inRange(img_frame, lower, upper)
    num_labels, _, stats, _ = cv2.connectedComponentsWithStats(mask_white, connectivity=8)

    for i in range(1, num_labels):
        x0, y0, rw, rh, _ = stats[i]
        if rw < 100 or rh < 100:
            continue

        x1 = x0 + rw - 1
        y1 = y0 + rh - 1
        top_ok = np.all(np.all(img_frame[y0, x0:x0 + rw] >= lower, axis=1))
        bottom_ok = np.all(np.all(img_frame[y1, x0:x0 + rw] >= lower, axis=1))
        if not (top_ok and bottom_ok):
            continue
        left_ok = np.all(np.all(img_frame[y0:y0 + rh, x0] >= lower, axis=1))
        right_ok = np.all(np.all(img_frame[y0:y0 + rh, x1] >= lower, axis=1))
        if not (left_ok and right_ok):
            continue

        region = img_frame[y0:y0 + rh, x0:x0 + rw]
        mask_minimap = np.any(region < lower, axis=2).astype(np.uint8)
        coords = cv2.findNonZero(mask_minimap)
        if coords is None:
            continue

        x_minimap, y_minimap, w_minimap, h_minimap = cv2.boundingRect(coords)
        x_minimap += x0
        y_minimap += y0
        return x_minimap, y_minimap, w_minimap, h_minimap

    return None


def get_player_location_on_minimap(
    img_minimap: np.ndarray,
    minimap_player_color=(67, 255, 255),
    color_tolerance: int = 0,
    min_pixels: int = 4,
) -> Optional[tuple[int, int]]:
    """Find the player dot on minimap with tolerant color matching."""
    if img_minimap is None:
        return None

    color_tolerance = max(0, int(color_tolerance))
    min_pixels = max(1, int(min_pixels))
    base = np.array(minimap_player_color, dtype=np.int16)
    lower = np.clip(base - color_tolerance, 0, 255).astype(np.uint8)
    upper = np.clip(base + color_tolerance, 0, 255).astype(np.uint8)

    mask = cv2.inRange(img_minimap, lower, upper)
    coords = cv2.findNonZero(mask)
    if coords is None or len(coords) < min_pixels:
        return None

    avg = coords.mean(axis=0)[0]
    return int(round(avg[0])), int(round(avg[1]))

