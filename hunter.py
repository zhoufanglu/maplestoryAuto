import time
import cv2
import numpy as np
import pyautogui
import ctypes
import pygetwindow as gw
import threading

# 导入自定义模块
import attack
import auto_buff
import warning

# ==========================================
# 核心设置区
# ==========================================
GAME_WINDOW_TITLE = "MapleStoryGo"
HUNTER_FILES = ['hunters/img.png', 'hunters/img_1.png']
TITLE_IMG = 'char_title.png'

# 识别配置
THRESHOLD_HUNTER = 0.15 # 边缘模式门槛  越大匹配度越高
THRESHOLD_TITLE = 0.60  # 角色识别门槛
Y_DIFF_LIMIT = 200  # Y轴高度差限制
VIEW_SCALE = 0.5  # 预览缩放

data_lock = threading.Lock()
shared_info = {"char": None, "hunters": []}

try:
    ctypes.windll.user32.SetProcessDPIAware()
except:
    pass


# ==========================================
# 辅助函数：将图片转为边缘特征图
# ==========================================
def get_edge_map(img):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 100, 200)
    return edges


# ==========================================
# 子线程 1：攻击逻辑
# ==========================================
def attack_worker():
    print("🚀 [线程] 攻击逻辑子线程已启动")
    while True:
        with data_lock:
            char_center = shared_info["char"]
            hunts = shared_info["hunters"]
        if char_center and hunts:
            attack.auto_action(char_center, hunts)
        time.sleep(0.01)


# ==========================================
# 子线程 2：告警监控 (之前漏掉的部分)
# ==========================================
def warning_worker(win_title):
    print("✅ [线程] 告警监控线程已启动...")
    while True:
        try:
            wins = gw.getWindowsWithTitle(win_title)
            if wins:
                target_win = wins[0]
                # 获取游戏窗口区域，传给 warning 模块去检测
                region = (target_win.left, target_win.top, target_win.width, target_win.height)
                if warning.check_for_warning(region=region):
                    # 这里的 print 只是辅助，主要的告警逻辑（如播放声音）应该在 warning.py 里
                    print("[🚨 ALERT] 屏幕检测到异常告警图！")
        except:
            pass
        time.sleep(2.0)  # 告警不需要太高频率，2秒扫一次即可


# ==========================================
# 主运行逻辑
# ==========================================
def run():
    try:
        win = gw.getWindowsWithTitle(GAME_WINDOW_TITLE)[0]
        if win.isMinimized: win.restore()
    except:
        print("❌ 找不到窗口")
        return

    # 预处理怪物模板
    monster_templates = []
    for path in HUNTER_FILES:
        tpl = cv2.imread(path)
        if tpl is None: continue
        h, w = tpl.shape[:2]
        edge_tpl = get_edge_map(tpl)
        monster_templates.append({"edge": edge_tpl, "w": w, "h": h})

    tpl_t = cv2.imread(TITLE_IMG)
    h_t, w_t = tpl_t.shape[:2]

    # 3. 启动所有子线程
    auto_buff.start_buff_threads()  # 自动BUFF

    # 启动告警监控子线程
    t_warn = threading.Thread(target=warning_worker, args=(GAME_WINDOW_TITLE,), daemon=True)
    t_warn.start()

    # 启动攻击逻辑子线程
    t_atk = threading.Thread(target=attack_worker, daemon=True)
    t_atk.start()

    print("📸 边缘识别模式 + 告警监控 启动完毕！")

    while True:
        rect = (win.left, win.top, win.width, win.height)
        img = pyautogui.screenshot(region=rect)
        frame = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)

        # 1. 处理边缘图
        frame_edge = get_edge_map(frame)

        # 2. 识别角色
        res_t = cv2.matchTemplate(frame, tpl_t, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(res_t)
        char_center = None
        if max_val >= THRESHOLD_TITLE:
            char_center = (max_loc[0] + w_t // 2, max_loc[1] + h_t // 2)
            cv2.rectangle(frame, max_loc, (max_loc[0] + w_t, max_loc[1] + h_t), (255, 0, 0), 2)

        # 3. 识别怪物
        rects_raw = []
        for m in monster_templates:
            res = cv2.matchTemplate(frame_edge, m["edge"], cv2.TM_CCOEFF_NORMED)
            loc = np.where(res >= THRESHOLD_HUNTER)
            for pt in zip(*loc[::-1]):
                rects_raw.append([int(pt[0]), int(pt[1]), m["w"], m["h"]])
                rects_raw.append([int(pt[0]), int(pt[1]), m["w"], m["h"]])

        # 4. 过滤与绘图
        valid_hunts = []
        if len(rects_raw) > 0:
            rects_final, _ = cv2.groupRectangles(rects_raw, 1, 0.2)
            for (x, y, w, h) in rects_final:
                m_cx, m_cy = x + w // 2, y + h // 2
                if char_center:
                    if abs(m_cy - char_center[1]) <= Y_DIFF_LIMIT:
                        valid_hunts.append((m_cx, m_cy))
                        cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 0, 255), 2)  # 红框：打
                    else:
                        cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 255), 2)  # 黄框：远
                else:
                    cv2.rectangle(frame, (x, y), (x + w, y + h), (255, 255, 255), 1)  # 白框：丢人

        with data_lock:
            shared_info["char"] = char_center
            shared_info["hunters"] = valid_hunts

        # 预览
        show = cv2.resize(frame, (0, 0), fx=VIEW_SCALE, fy=VIEW_SCALE)
        cv2.imshow('System Monitor', show)

        if cv2.waitKey(1) & 0xFF == ord('q'): break
        time.sleep(0.01)

    cv2.destroyAllWindows()


if __name__ == "__main__":
    run()