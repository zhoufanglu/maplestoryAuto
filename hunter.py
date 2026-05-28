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
from navigation import NavContext, NavigationStateMachine
from minimap_locator import get_minimap_loc_size, get_player_location_on_minimap

# ==========================================
# 核心设置区
# ==========================================
GAME_WINDOW_TITLE = "WingsMS-v0.31"
HUNTER_FILES = ['hunters/img_1.png', 'hunters/img_2.png']

# 识别配置
THRESHOLD_HUNTER = 0.45 # 边缘模式门槛  越大匹配度越高
Y_DIFF_LIMIT = 200  # Y轴高度差限制
VIEW_SCALE = 0.5  # 预览缩放
PREVIEW_RIGHT_MARGIN = 40  # 预览窗距离屏幕右边距
PREVIEW_BOTTOM_MARGIN = 106  # 预览窗距离屏幕下边距（预留任务栏）

APP_CONFIG = load_config()
FEATURES_CONFIG = APP_CONFIG.get("features", {})
ENABLE_ATTACK = bool(FEATURES_CONFIG.get("enable_attack", True))
ENABLE_AUTO_BUFF = bool(FEATURES_CONFIG.get("enable_auto_buff", True))
ENABLE_WARNING = bool(FEATURES_CONFIG.get("enable_warning", True))

MINIMAP_CONFIG = APP_CONFIG.get("minimap", {})
MINIMAP_PLAYER_COLOR = tuple(MINIMAP_CONFIG.get("player_color", [136, 255, 255]))
MINIMAP_OFFSET = tuple(MINIMAP_CONFIG.get("offset", [0, 0]))
MINIMAP_PLAYER_COLOR_TOLERANCE = int(MINIMAP_CONFIG.get("player_color_tolerance", 12))
MINIMAP_MIN_PLAYER_PIXELS = int(MINIMAP_CONFIG.get("min_player_pixels", 3))
MINIMAP_BORDER_TOLERANCE = int(MINIMAP_CONFIG.get("border_tolerance", 8))
MINIMAP_USE_FALLBACK_WHEN_NOT_FOUND = bool(MINIMAP_CONFIG.get("use_fallback_when_not_found", False))
MINIMAP_FALLBACK_REGION = tuple(MINIMAP_CONFIG.get("fallback_region", [0, 0, 0, 0]))
MINIMAP_DEBUG_DRAW_REGION = bool(MINIMAP_CONFIG.get("debug_draw_region", True))

DETECT_CONFIG = APP_CONFIG.get("detection", {})
HUNTER_EDGE_THRESHOLD = float(DETECT_CONFIG.get("hunter_edge_threshold", THRESHOLD_HUNTER))
HUNTER_GRAY_THRESHOLD = float(DETECT_CONFIG.get("hunter_gray_threshold", 0.66))
HUNTER_MAX_CANDIDATES_PER_TEMPLATE = int(DETECT_CONFIG.get("hunter_max_candidates_per_template", 60))
HUNTER_GROUP_EPS = float(DETECT_CONFIG.get("hunter_group_eps", 0.24))
HUNTER_TRACK_MAX_MISS = int(DETECT_CONFIG.get("hunter_track_max_miss", 3))
HUNTER_EDGE_ONLY = bool(DETECT_CONFIG.get("hunter_edge_only", False))

PATROL_CONFIG = APP_CONFIG.get("patrol", {})
NAV_CONFIG = APP_CONFIG.get("navigation", PATROL_CONFIG)
NAV_ENABLED = bool(NAV_CONFIG.get("enabled", False))
NAV_NO_HUNTER_TIMEOUT_SEC = float(NAV_CONFIG.get("no_hunter_timeout_sec", 1.2))
NAV_MOVE_TOLERANCE_PX = int(NAV_CONFIG.get("move_tolerance_px", 24))
NAV_COMMAND_COOLDOWN_SEC = float(NAV_CONFIG.get("command_cooldown_sec", NAV_CONFIG.get("step_cooldown_sec", 0.6)))
NAV_STEPS = NAV_CONFIG.get("steps", [])


def _optional_int(value):
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        text = value.strip()
        if text:
            try:
                return int(float(text))
            except ValueError:
                return None
    return None


def _normalize_anchor_points(raw_points):
    normalized = {}
    if not isinstance(raw_points, dict):
        return normalized

    for key, value in raw_points.items():
        parsed = _optional_int(value)
        if parsed is None:
            continue
        normalized[str(key)] = parsed
    return normalized


ANCHOR_POINTS = _normalize_anchor_points(NAV_CONFIG.get("anchors", {}))

data_lock = threading.Lock()
shared_info = {"char": None, "hunters": [], "patrol_cmd": None}
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


def _normalize_patrol_steps(raw_steps):
    normalized = []
    if not isinstance(raw_steps, list):
        return normalized

    for step in raw_steps:
        if not isinstance(step, dict):
            continue
        action = str(step.get("action", "")).strip().lower()
        if action not in ("move", "down_jump", "climb_up", "wait", "scan_left", "scan_right"):
            continue

        normalized_step = {"action": action}
        anchor = step.get("anchor")
        if isinstance(anchor, str) and anchor.strip():
            normalized_step["anchor"] = anchor.strip()
        if isinstance(step.get("x"), (int, float)):
            normalized_step["x"] = int(step["x"])
        if isinstance(step.get("tol"), (int, float)):
            normalized_step["tol"] = int(step["tol"])
        if isinstance(step.get("hold_sec"), (int, float)):
            normalized_step["hold_sec"] = float(step["hold_sec"])
        if isinstance(step.get("wait_sec"), (int, float)):
            normalized_step["wait_sec"] = float(step["wait_sec"])

        normalized.append(normalized_step)

    return normalized


def _draw_debug_text(img, text: str, x: int, y: int):
    # 白描边 + 红字，复杂背景下也清晰。
    cv2.putText(img, text, (x, y), cv2.FONT_HERSHEY_SIMPLEX, 0.58, (255, 255, 255), 3, cv2.LINE_AA)
    cv2.putText(img, text, (x, y), cv2.FONT_HERSHEY_SIMPLEX, 0.58, (0, 0, 255), 1, cv2.LINE_AA)


def _normalize_fallback_region(region, frame_shape):
    if not isinstance(region, (list, tuple)) or len(region) != 4:
        return None

    try:
        x, y, w, h = [int(v) for v in region]
    except (TypeError, ValueError):
        return None

    if w <= 0 or h <= 0:
        return None

    fh, fw = frame_shape[:2]
    x = max(0, min(fw - 1, x))
    y = max(0, min(fh - 1, y))
    w = max(1, min(w, fw - x))
    h = max(1, min(h, fh - y))
    return x, y, w, h


def _count_player_pixels_on_minimap(img_minimap):
    if img_minimap is None:
        return 0
    base = np.array(MINIMAP_PLAYER_COLOR, dtype=np.int16)
    tol = max(0, int(MINIMAP_PLAYER_COLOR_TOLERANCE))
    lower = np.clip(base - tol, 0, 255).astype(np.uint8)
    upper = np.clip(base + tol, 0, 255).astype(np.uint8)
    mask = cv2.inRange(img_minimap, lower, upper)
    return int(cv2.countNonZero(mask))


# ==========================================
# 子线程 1：攻击逻辑
# ==========================================
def attack_worker():
    print("🚀 [线程] 攻击逻辑子线程已启动")
    while True:
        with data_lock:
            char_center = shared_info["char"]
            hunts = shared_info["hunters"]
            patrol_cmd = shared_info.get("patrol_cmd")
        if char_center and hunts:
            attack.auto_action(char_center, hunts)
        elif char_center and patrol_cmd:
            attack.auto_action(char_center, [], patrol_command=patrol_cmd)
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
    print(f"   - 导航状态机: {'开启' if NAV_ENABLED else '关闭'}")
    print("   - 小地图定位: 开启")
    if MINIMAP_USE_FALLBACK_WHEN_NOT_FOUND:
        print(f"   - 小地图兜底区域: {MINIMAP_FALLBACK_REGION}")

    hunter_files = _resolve_hunter_files()
    patrol_steps = _normalize_patrol_steps(NAV_STEPS)
    print(f"   - 怪物模板数量: {len(hunter_files)}")
    if NAV_ENABLED:
        print(f"   - 导航步骤数: {len(patrol_steps)}")

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

    navigator = NavigationStateMachine(
        steps=patrol_steps,
        no_hunter_timeout_sec=NAV_NO_HUNTER_TIMEOUT_SEC,
        command_cooldown_sec=NAV_COMMAND_COOLDOWN_SEC,
        move_tolerance_px=NAV_MOVE_TOLERANCE_PX,
    )

    while True:
        now_ts = time.time()
        rect = (win.left, win.top, win.width, win.height)
        img = pyautogui.screenshot(region=rect)
        frame = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)

        # 1. 处理边缘图
        frame_gray = None
        if not HUNTER_EDGE_ONLY:
            frame_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            frame_gray = cv2.GaussianBlur(frame_gray, (3, 3), 0)
        frame_edge = get_edge_map(frame)

        # 1.5 角色定位：优先小地图，其次标题模板兜底
        minimap_result = get_minimap_loc_size(frame, border_tolerance=MINIMAP_BORDER_TOLERANCE)
        minimap_source = "auto"
        if minimap_result is None and MINIMAP_USE_FALLBACK_WHEN_NOT_FOUND:
            fallback = _normalize_fallback_region(MINIMAP_FALLBACK_REGION, frame.shape)
            if fallback is not None:
                minimap_result = fallback
                minimap_source = "fallback"
        elif minimap_result is None:
            minimap_source = "none"

        loc_minimap = None
        minimap_found = minimap_result is not None
        player_pixel_count = 0
        if minimap_result is not None:
            mx, my, mw, mh = minimap_result
            img_minimap = frame[my:my + mh, mx:mx + mw]
            player_pixel_count = _count_player_pixels_on_minimap(img_minimap)
            loc_player_on_minimap = get_player_location_on_minimap(
                img_minimap,
                MINIMAP_PLAYER_COLOR,
                color_tolerance=MINIMAP_PLAYER_COLOR_TOLERANCE,
                min_pixels=MINIMAP_MIN_PLAYER_PIXELS,
            )
            if MINIMAP_DEBUG_DRAW_REGION:
                color = (0, 255, 255) if minimap_source == "auto" else (255, 200, 0)
                cv2.rectangle(frame, (mx, my), (mx + mw, my + mh), color, 1)
            if loc_player_on_minimap is not None:
                loc_minimap = (
                    mx + loc_player_on_minimap[0] + int(MINIMAP_OFFSET[0]),
                    my + loc_player_on_minimap[1] + int(MINIMAP_OFFSET[1]),
                )
                cv2.circle(frame, loc_minimap, radius=3, color=(0, 255, 0), thickness=-1)

        # 2. 角色定位：仅使用 minimap 玩家点
        char_center = loc_minimap
        nav_char_pos = loc_minimap

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

        patrol_cmd = None
        if NAV_ENABLED and nav_char_pos:
            navigator.sync_clock(now_ts)
            nav_ctx = NavContext(
                now_ts=now_ts,
                char_pos=nav_char_pos,
                hunters_pos=valid_hunts,
                anchor_points=ANCHOR_POINTS,
            )
            patrol_cmd = navigator.next_command(nav_ctx)

        with data_lock:
            shared_info["char"] = char_center
            shared_info["hunters"] = valid_hunts
            shared_info["patrol_cmd"] = patrol_cmd


        # 预览
        show = cv2.resize(frame, (0, 0), fx=VIEW_SCALE, fy=VIEW_SCALE)

        if char_center:
            pos_text = f"CHAR(minimap) x={char_center[0]} y={char_center[1]}"
        else:
            pos_text = "CHAR(minimap) x=- y=-"

        if patrol_cmd:
            action = patrol_cmd.get("action", "-")
            cmd_x = patrol_cmd.get("x")
            if isinstance(cmd_x, (int, float)):
                patrol_text = f"PATROL {action} x={int(cmd_x)}"
            else:
                patrol_text = f"PATROL {action}"
        elif NAV_ENABLED:
            patrol_text = "PATROL ready"
        else:
            patrol_text = "PATROL off"

        _draw_debug_text(show, pos_text, 12, 26)
        _draw_debug_text(show, patrol_text, 12, 50)
        _draw_debug_text(show, f"MINIMAP found={'yes' if minimap_found else 'no'} src={minimap_source}", 12, 74)
        _draw_debug_text(show, f"PLAYER_DOT pixels={player_pixel_count}", 12, 98)
        if NAV_ENABLED:
            _draw_debug_text(show, f"NAV {navigator.state.value}", 12, 122)

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