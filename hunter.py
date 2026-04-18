import time
import cv2
import numpy as np
import pyautogui
import ctypes
import pygetwindow as gw
import attack
import threading  # 👈 引入线程库

# ==========================================
# 核心设置区
# ==========================================
GAME_WINDOW_TITLE = "MapleStoryGo"
HUNTER_IMG = 'hunters/xiaoxueren.png'
TITLE_IMG = 'char_title.png'

THRESHOLD_HUNTER = 0.55
THRESHOLD_TITLE = 0.60
VIEW_SCALE = 0.5

# 共享数据锁，防止两个线程同时读写坐标导致奔溃
data_lock = threading.Lock()
shared_info = {"char": None, "hunters": []}
# ==========================================

try:
    ctypes.windll.user32.SetProcessDPIAware()
except:
    pass


def attack_worker():
    """
    专门负责执行动作的后台线程
    它会不断检查 shared_info 里的坐标并执行 attack 逻辑
    """
    print("🚀 攻击子线程已启动")
    while True:
        with data_lock:
            char_center = shared_info["char"]
            hunters_pos_list = shared_info["hunters"]

        if char_center and hunters_pos_list:
            # 执行攻击动作（即使这里有 time.sleep，也不会卡住主界面的预览窗口）
            attack.auto_action(char_center, hunters_pos_list)

        # 线程极短暂休息，降低CPU占用
        time.sleep(0.01)


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

    # --- 启动攻击子线程 ---
    t = threading.Thread(target=attack_worker, daemon=True)
    t.start()

    print("📸 视觉识别主线程启动...")
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

        hunters_pos_list = []
        if len(rects_h) > 0:
            rects_h, _ = cv2.groupRectangles(rects_h, 1, 0.5)
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

        # --- 4. 关键：更新共享数据给攻击线程 ---
        with data_lock:
            shared_info["char"] = char_center
            shared_info["hunters"] = hunters_pos_list

        # 5. 显示预览 (现在这里会非常流畅)
        show = cv2.resize(frame, (0, 0), fx=VIEW_SCALE, fy=VIEW_SCALE)
        cv2.imshow('Hunter System', show)

        # cv2.waitKey(1) 是画面刷新的核心，不能改大
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

        # 主线程只需要负责快速识别和显示，不需要长时间sleep
        time.sleep(0.01)


if __name__ == "__main__":
    run()