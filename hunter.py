import time

import cv2
import numpy as np
import pyautogui
import ctypes
import pygetwindow as gw
import attack  # 👈 确保这里导入了你的 attack.py

# =========================================x=
# 核心设置x区
# ==========================================
GAME_WINDOW_TITLE = "MapleStoryGo"
HUNTER_IMG = 'hunters/xiaoxueren.png'  # 确认路径正确
TITLE_IMG = 'char_title.png'

THRESHOLD_HUNTER = 0.55
THRESHOLD_TITLE = 0.60
VIEW_SCALE = 0.5
# ==========================================

try:
    ctypes.windll.user32.SetProcessDPIAware()
except:
    pass


def run():
    # 锁定窗口
    try:
        win = gw.getWindowsWithTitle(GAME_WINDOW_TITLE)[0]
    except:
        print("❌ 找不到游戏窗口")
        return

    # 加载图片
    tpl_h = cv2.imread(HUNTER_IMG)
    tpl_t = cv2.imread(TITLE_IMG)
    if tpl_h is None or tpl_t is None:
        print("❌ 图片加载失败，请检查路径")
        return

    h_h, w_h = tpl_h.shape[:2]
    h_t, w_t = tpl_t.shape[:2]

    while True:
        # 1. 截图
        rect = (win.left, win.top, win.width, win.height)
        img = pyautogui.screenshot(region=rect)
        frame = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)

        # 2. 找怪 (Hunter)
        res_h = cv2.matchTemplate(frame, tpl_h, cv2.TM_CCOEFF_NORMED)
        loc_h = np.where(res_h >= THRESHOLD_HUNTER)

        rects_h = []
        for pt in zip(*loc_h[::-1]):
            rects_h.append([int(pt[0]), int(pt[1]), int(w_h), int(h_h)])
            rects_h.append([int(pt[0]), int(pt[1]), int(w_h), int(h_h)])
        rects_h, _ = cv2.groupRectangles(rects_h, 1, 0.5)

        # 提取所有怪物的中心点传给 attack 模块
        hunters_pos_list = []
        for (x, y, w, h) in rects_h:
            hunters_pos_list.append((x + w // 2, y + h // 2))
            cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 0, 255), 2)

        # 3. 找人 (Title)
        res_t = cv2.matchTemplate(frame, tpl_t, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(res_t)

        char_center = None
        if max_val >= THRESHOLD_TITLE:
            char_center = (max_loc[0] + w_t // 2, max_loc[1] + h_t // 2)
            cv2.rectangle(frame, max_loc, (max_loc[0] + w_t, max_loc[1] + h_t), (255, 0, 0), 3)

        # --- 4. 关键：把坐标传给 attack 模块 ---
        if char_center and hunters_pos_list:
            attack.auto_action(char_center, hunters_pos_list)

        # 5. 显示预览
        show = cv2.resize(frame, (0, 0), fx=VIEW_SCALE, fy=VIEW_SCALE)
        cv2.imshow('Hunter System', show)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

        # ！！！必须加这一行，否则指令会堆积引发聊天框！！！
        time.sleep(0.1)


if __name__ == "__main__":
    run()