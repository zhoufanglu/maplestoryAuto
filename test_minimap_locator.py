import numpy as np
import cv2

from minimap_locator import get_minimap_loc_size, get_player_location_on_minimap


def run_tests():
    frame = np.zeros((320, 480, 3), dtype=np.uint8)

    # Draw a white minimap border.
    x0, y0, w, h = 30, 20, 180, 120
    frame[y0:y0+h, x0] = (255, 255, 255)
    frame[y0:y0+h, x0+w-1] = (255, 255, 255)
    frame[y0, x0:x0+w] = (255, 255, 255)
    frame[y0+h-1, x0:x0+w] = (255, 255, 255)

    # Fill inside with some non-white pixels.
    frame[y0+1:y0+h-1, x0+1:x0+w-1] = (10, 10, 10)

    # Put player dot inside minimap.
    player_color = (67, 255, 255)
    px, py = 40, 25
    frame[y0 + py, x0 + px] = player_color
    frame[y0 + py + 1, x0 + px] = player_color
    frame[y0 + py, x0 + px + 1] = player_color
    frame[y0 + py + 1, x0 + px + 1] = player_color

    loc = get_minimap_loc_size(frame)
    assert loc is not None, "minimap should be detected"
    mx, my, mw, mh = loc
    assert (mx, my, mw, mh) == (31, 21, 178, 118), loc

    img_minimap = frame[my:my+mh, mx:mx+mw]
    player = get_player_location_on_minimap(img_minimap, player_color)
    assert player == (40, 24), player

    print("test_minimap_locator.py passed")


if __name__ == "__main__":
    run_tests()

