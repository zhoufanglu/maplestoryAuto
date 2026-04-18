import time
import cv2
import numpy as np
import pyautogui
import ctypes
import pygetwindow as gw
import attack
import threading
import auto_buff  # 👈 1. 导入你新建的 auto_buff 模块

# ==========================================
# 核心设置区
# ==========================================
GAME_WINDOW_TITLE = "MapleStoryGo"
HUNTER_IMG = 'hunters/xiaoxueren.png'
TITLE_IMG = 'char_title.png'

THRESHOLD_HUNTER = 0.55
THRESHOLD_TITLE = 0.60
VIEW_SCALE = 0.5

data_lock = threading.Lock()
shared_info = {"char": None, "hunters": []}
# ==========================================

try:
    ctypes.windll.user32.SetProcessDPIAware()
except:
    pass


def attack_worker():
    print("🚀 攻击子线程已启动")
    while True:
        with data_lock:
            char_center = shared_info["char"]
            hunters_pos_list = shared_info["hunters"]

        # 这里的 attack.auto_action 内部现在会判断 auto_buff.is_buffing
        if char_center and hunters_pos_list:
            attack.auto_action(char_center, hunters_pos_list)

        time.sleep(0.01)


def run():
    try:
        win = gw.getWindowsWithTitle(GAME_WINDOW_TITLE)[0]
    except:
        print("❌ 找不到游戏窗口")
        return

    tpl_h = cv2.imread(HUNTER_IMG)
    tpl_t = cv2.imread(TITLE_IMG)
    if tpl_h is None or tpl_t is None:
        print("❌ 图片加载失败，请检查路径")
        return

    h_h, w_h = tpl_h.shape[:2]
    h_t, w_t = tpl_t.shape[:2]

    # --- 2. 启动 Buff 监控线程 ---
    # 这会启动 F10 和 F11 的两个定时器线程
    auto_buff.start_buff_threads()

    # --- 启动攻击子线程 ---
    t = threading.Thread(target=attack_worker, daemon=True)
    t.start()

    print("📸 视觉识别主线程启动...")
    while True:
        rect = (win.left, win.top, win.width, win.height)
        img = pyautogui.screenshot(region=rect)
        frame = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)

        # 找怪逻辑
        res_h = cv2.matchTemplate(frame, tpl_h, cv2.TM_CCOEFF_NORMED)
        loc_h = np.where(res_h >= THRESHOLD_HUNTER)

        rects_h = []
        for pt in zip(*loc_h[::-1]):
            rects_h.append([int(pt[0]), int(pt[1]), int(w_h), int(h_h)])
            rects_h.append([int(pt[0]), int(pt[1]), int(w_h), int(h_h)])

        hunters_pos_list = []
        if len(rects_h) > 0:
            rects_h, _ = cv2.groupRectangles(rects_h, 1, 0.5)
            for (x, y, w, h) in rects_h:
                hunters_pos_list.append((x + w // 2, y + h // 2))
                cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 0, 255), 2)

        # 找人逻辑
        res_t = cv2.matchTemplate(frame, tpl_t, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(res_t)

        char_center = None
        if max_val >= THRESHOLD_TITLE:
            char_center = (max_loc[0] + w_t // 2, max_loc[1] + h_t // 2)
            cv2.rectangle(frame, max_loc, (max_loc[0] + w_t, max_loc[1] + h_t), (255, 0, 0), 3)

        # 如果正在加 Buff，我们在预览窗上显示一个提示（可选，方便观察）
        if auto_buff.is_buffing:
            cv2.putText(frame, "STATUS: BUFFING...", (50, 50),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2)

        with data_lock:
            shared_info["char"] = char_center
            shared_info["hunters"] = hunters_pos_list

        show = cv2.resize(frame, (0, 0), fx=VIEW_SCALE, fy=VIEW_SCALE)
        cv2.imshow('Hunter System', show)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

        time.sleep(0.01)


if __name__ == "__main__":
    run()