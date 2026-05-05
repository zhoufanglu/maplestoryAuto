import time
import cv2
import numpy as np
import pyautogui
import ctypes
import pygetwindow as gw
import threading
from pathlib import Path

# 导入自定义模块
import attack
import auto_buff
import warning
from app_config import load_config

# ==========================================
# 核心设置区
# ==========================================
GAME_WINDOW_TITLE = "WingsMS-v0.31"
HUNTER_FILES = ['hunters/img_1.png', 'hunters/img_2.png']
TITLE_IMG = 'char_title.png'

# 识别配置
THRESHOLD_HUNTER = 0.45 # 边缘模式门槛  越大匹配度越高
THRESHOLD_TITLE = 0.60  # 角色识别门槛
Y_DIFF_LIMIT = 200  # Y轴高度差限制
VIEW_SCALE = 0.5  # 预览缩放
PREVIEW_RIGHT_MARGIN = 40  # 预览窗距离屏幕右边距
PREVIEW_BOTTOM_MARGIN = 106  # 预览窗距离屏幕下边距（预留任务栏）

APP_CONFIG = load_config()
FEATURES_CONFIG = APP_CONFIG.get("features", {})
ENABLE_ATTACK = bool(FEATURES_CONFIG.get("enable_attack", True))
ENABLE_AUTO_BUFF = bool(FEATURES_CONFIG.get("enable_auto_buff", True))
ENABLE_WARNING = bool(FEATURES_CONFIG.get("enable_warning", True))

DETECT_CONFIG = APP_CONFIG.get("detection", {})
HUNTER_EDGE_THRESHOLD = float(DETECT_CONFIG.get("hunter_edge_threshold", THRESHOLD_HUNTER))
HUNTER_GRAY_THRESHOLD = float(DETECT_CONFIG.get("hunter_gray_threshold", 0.66))
HUNTER_MAX_CANDIDATES_PER_TEMPLATE = int(DETECT_CONFIG.get("hunter_max_candidates_per_template", 60))
HUNTER_GROUP_EPS = float(DETECT_CONFIG.get("hunter_group_eps", 0.24))
HUNTER_TRACK_MAX_MISS = int(DETECT_CONFIG.get("hunter_track_max_miss", 3))
HUNTER_EDGE_ONLY = bool(DETECT_CONFIG.get("hunter_edge_only", False))

data_lock = threading.Lock()
shared_info = {"char": None, "hunters": []}
_last_valid_hunts = []
_hunter_miss_frames = 0

try:
    ctypes.windll.user32.SetProcessDPIAware()
except:
    pass


# ==========================================
# 辅助函数：将图片转为边缘特征图
# ==========================================
def get_edge_map(img):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (3, 3), 0)
    edges = cv2.Canny(gray, 70, 170)
    # 膨胀边缘，让高速移动时的轮廓断裂更少。
    edges = cv2.dilate(edges, np.ones((3, 3), np.uint8), iterations=1)
    return edges


def _collect_top_matches(result_map, threshold, max_candidates):
    ys, xs = np.where(result_map >= threshold)
    if len(xs) == 0:
        return []

    values = result_map[ys, xs]
    order = np.argsort(values)[::-1]
    limit = min(max_candidates, len(order))
    picked = []
    for idx in order[:limit]:
        picked.append((int(xs[idx]), int(ys[idx])))
    return picked


def _smooth_hunters(current_hunts):
    global _last_valid_hunts
    global _hunter_miss_frames

    if current_hunts:
        _last_valid_hunts = current_hunts
        _hunter_miss_frames = 0
        return current_hunts

    if _last_valid_hunts and _hunter_miss_frames < HUNTER_TRACK_MAX_MISS:
        _hunter_miss_frames += 1
        return _last_valid_hunts

    _last_valid_hunts = []
    _hunter_miss_frames = 0
    return []


def _resolve_hunter_files():
    files = sorted(Path("hunters").glob("img*.png"))
    if files:
        return [str(p).replace("\\", "/") for p in files]
    return HUNTER_FILES


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
    print("🧩 功能开关加载完成:")
    print(f"   - 自动攻击: {'开启' if ENABLE_ATTACK else '关闭'}")
    print(f"   - 自动BUFF: {'开启' if ENABLE_AUTO_BUFF else '关闭'}")
    print(f"   - 自动报警: {'开启' if ENABLE_WARNING else '关闭'}")
    print(f"   - 怪物识别模式: {'仅边缘' if HUNTER_EDGE_ONLY else '边缘+灰度'}")

    hunter_files = _resolve_hunter_files()
    print(f"   - 怪物模板数量: {len(hunter_files)}")

    screen_w, screen_h = pyautogui.size()

    try:
        win = gw.getWindowsWithTitle(GAME_WINDOW_TITLE)[0]
        if win.isMinimized: win.restore()
    except:
        print("❌ 找不到窗口")
        return

    # 预处理怪物模板
    monster_templates = []
    for path in hunter_files:
        tpl = cv2.imread(path)
        if tpl is None: continue
        h, w = tpl.shape[:2]
        gray_tpl = None
        if not HUNTER_EDGE_ONLY:
            gray_tpl = cv2.cvtColor(tpl, cv2.COLOR_BGR2GRAY)
            gray_tpl = cv2.GaussianBlur(gray_tpl, (3, 3), 0)
        edge_tpl = get_edge_map(tpl)
        monster_templates.append({"edge": edge_tpl, "gray": gray_tpl, "w": w, "h": h})

    tpl_t = cv2.imread(TITLE_IMG)
    h_t, w_t = tpl_t.shape[:2]

    # 3. 启动所有子线程
    if ENABLE_AUTO_BUFF:
        auto_buff.start_buff_threads()
    else:
        print("⏸️ 自动BUFF已在配置中关闭")

    # 启动告警监控子线程
    if ENABLE_WARNING:
        t_warn = threading.Thread(target=warning_worker, args=(GAME_WINDOW_TITLE,), daemon=True)
        t_warn.start()
    else:
        print("⏸️ 自动报警已在配置中关闭")

    # 启动攻击逻辑子线程
    if ENABLE_ATTACK:
        t_atk = threading.Thread(target=attack_worker, daemon=True)
        t_atk.start()
    else:
        print("⏸️ 自动攻击已在配置中关闭")

    print("📸 边缘识别模式 + 告警监控 启动完毕！")

    while True:
        rect = (win.left, win.top, win.width, win.height)
        img = pyautogui.screenshot(region=rect)
        frame = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)

        # 1. 处理边缘图
        frame_gray = None
        if not HUNTER_EDGE_ONLY:
            frame_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            frame_gray = cv2.GaussianBlur(frame_gray, (3, 3), 0)
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
            # 边缘匹配对形状鲁棒，灰度匹配补足动态模糊时的纹理信息。
            res_edge = cv2.matchTemplate(frame_edge, m["edge"], cv2.TM_CCOEFF_NORMED)

            edge_pts = _collect_top_matches(
                res_edge,
                HUNTER_EDGE_THRESHOLD,
                HUNTER_MAX_CANDIDATES_PER_TEMPLATE,
            )
            gray_pts = []
            if not HUNTER_EDGE_ONLY and frame_gray is not None and m["gray"] is not None:
                res_gray = cv2.matchTemplate(frame_gray, m["gray"], cv2.TM_CCOEFF_NORMED)
                gray_pts = _collect_top_matches(
                    res_gray,
                    HUNTER_GRAY_THRESHOLD,
                    HUNTER_MAX_CANDIDATES_PER_TEMPLATE,
                )

            for pt in edge_pts + gray_pts:
                rects_raw.append([int(pt[0]), int(pt[1]), m["w"], m["h"]])
                rects_raw.append([int(pt[0]), int(pt[1]), m["w"], m["h"]])

        # 4. 过滤与绘图
        valid_hunts = []
        if len(rects_raw) > 0:
            rects_final, _ = cv2.groupRectangles(rects_raw, 1, HUNTER_GROUP_EPS)
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

        valid_hunts = _smooth_hunters(valid_hunts)

        with data_lock:
            shared_info["char"] = char_center
            shared_info["hunters"] = valid_hunts

        # 预览
        show = cv2.resize(frame, (0, 0), fx=VIEW_SCALE, fy=VIEW_SCALE)
        cv2.imshow('System Monitor', show)
        show_h, show_w = show.shape[:2]
        win_x = max(0, screen_w - show_w - PREVIEW_RIGHT_MARGIN)
        win_y = max(0, screen_h - show_h - PREVIEW_BOTTOM_MARGIN)
        cv2.moveWindow('System Monitor', win_x, win_y)

        if cv2.waitKey(1) & 0xFF == ord('q'): break
        time.sleep(0.01)

    cv2.destroyAllWindows()


if __name__ == "__main__":
    run()