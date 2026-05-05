import argparse
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
import pyautogui
import pygetwindow as gw

DEFAULT_WINDOW_TITLE = "WingsMS-v0.31"
OUTPUT_DIR = Path("hunters")


def _find_window(title: str):
    windows = gw.getWindowsWithTitle(title)
    return windows[0] if windows else None


def _next_output_path() -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return OUTPUT_DIR / f"img_capture_{timestamp}.png"


def _capture_window_frame(win):
    region = (win.left, win.top, win.width, win.height)
    screenshot = pyautogui.screenshot(region=region)
    frame = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
    return frame


def main():
    parser = argparse.ArgumentParser(description="Capture hunter template ROIs from game window")
    parser.add_argument("--title", default=DEFAULT_WINDOW_TITLE, help="Game window title")
    args = parser.parse_args()

    print("[INFO] hunter 模板采集工具启动")
    print("[INFO] 快捷键: r=框选并保存, q=退出")

    while True:
        win = _find_window(args.title)
        if win is None:
            print(f"[WARN] 未找到窗口: {args.title}")
            print("[WARN] 2秒后重试...")
            cv2.waitKey(2000)
            continue

        frame = _capture_window_frame(win)
        preview = frame.copy()
        cv2.putText(preview, "R: select ROI and save", (12, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        cv2.putText(preview, "Q: quit", (12, 48), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        cv2.imshow("Hunter Template Capture", preview)

        key = cv2.waitKey(1) & 0xFF
        if key == ord("q"):
            break

        if key == ord("r"):
            roi = cv2.selectROI("Hunter Template Capture", frame, fromCenter=False, showCrosshair=True)
            x, y, w, h = roi
            if w <= 0 or h <= 0:
                print("[INFO] 已取消框选")
                continue

            crop = frame[y:y + h, x:x + w]
            out_path = _next_output_path()
            cv2.imwrite(str(out_path), crop)
            print(f"[OK] 已保存模板: {out_path}")

    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()

