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
Y_DIFF_LIMIT = 120  # Y轴高度差限制
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

PATROL_CONFIG = APP_CONFIG.get("patrol", {})
PATROL_ENABLED = bool(PATROL_CONFIG.get("enabled", False))
PATROL_NO_HUNTER_TIMEOUT_SEC = float(PATROL_CONFIG.get("no_hunter_timeout_sec", 1.2))
PATROL_MOVE_TOLERANCE_PX = int(PATROL_CONFIG.get("move_tolerance_px", 24))
PATROL_STEP_COOLDOWN_SEC = float(PATROL_CONFIG.get("step_cooldown_sec", 0.6))
PATROL_STEPS = PATROL_CONFIG.get("steps", [])
PATROL_DYNAMIC_ROPE_X = bool(PATROL_CONFIG.get("dynamic_rope_x", True))
PATROL_ROPE_MATCH_THRESHOLD = float(PATROL_CONFIG.get("rope_match_threshold", 0.32))
PATROL_ROPE_MAX_CANDIDATES = int(PATROL_CONFIG.get("rope_max_candidates_per_template", 30))


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


def _normalize_layer_bounds(raw_bounds):
    normalized = {}
    if not isinstance(raw_bounds, dict):
        return normalized

    for layer, bound in raw_bounds.items():
        if not isinstance(bound, (list, tuple)) or len(bound) != 2:
            continue
        y1 = _optional_int(bound[0])
        y2 = _optional_int(bound[1])
        if y1 is None or y2 is None:
            continue
        if y1 > y2:
            y1, y2 = y2, y1
        normalized[str(layer)] = (y1, y2)

    return normalized


def _normalize_layer_points(raw_points):
    normalized = {}
    if not isinstance(raw_points, dict):
        return normalized

    for layer, points in raw_points.items():
        if not isinstance(points, dict):
            continue
        item = {}
        for key in ("left_x", "right_x", "drop_x", "rope_x"):
            val = _optional_int(points.get(key))
            if val is not None:
                item[key] = val
        if item:
            normalized[str(layer)] = item

    return normalized


LAYER_Y_BOUNDS = _normalize_layer_bounds(PATROL_CONFIG.get("layer_y_bounds", {}))
LAYER_POINTS = _normalize_layer_points(PATROL_CONFIG.get("layer_points", {}))

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


def _resolve_rope_files():
    configured = PATROL_CONFIG.get("rope_templates")
    if isinstance(configured, list):
        files = [str(x) for x in configured if isinstance(x, str) and x.strip()]
        if files:
            return files

    default_patterns = ["hunters/ladder*.png", "hunters/rope*.png"]
    found = []
    for pattern in default_patterns:
        found.extend(sorted(Path().glob(pattern)))
    return [str(p).replace("\\", "/") for p in found]


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


def _resolve_current_layer(char_y):
    if not isinstance(char_y, (int, float)):
        return None
    for layer, bounds in LAYER_Y_BOUNDS.items():
        y1, y2 = bounds
        if y1 <= char_y <= y2:
            return layer
    return None


def _detect_rope_xs(frame_edge, rope_templates):
    rects_raw = []
    for tpl in rope_templates:
        res = cv2.matchTemplate(frame_edge, tpl["edge"], cv2.TM_CCOEFF_NORMED)
        pts = _collect_top_matches(res, PATROL_ROPE_MATCH_THRESHOLD, PATROL_ROPE_MAX_CANDIDATES)
        for pt in pts:
            rects_raw.append([int(pt[0]), int(pt[1]), tpl["w"], tpl["h"]])
            rects_raw.append([int(pt[0]), int(pt[1]), tpl["w"], tpl["h"]])

    if not rects_raw:
        return []

    rects_final, _ = cv2.groupRectangles(rects_raw, 1, 0.2)
    if len(rects_final) == 0:
        return []

    xs = sorted({int(x + w // 2) for (x, y, w, h) in rects_final})
    return xs


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
    print(f"   - 巡逻找怪: {'开启' if PATROL_ENABLED else '关闭'}")

    hunter_files = _resolve_hunter_files()
    rope_files = _resolve_rope_files()
    patrol_steps = _normalize_patrol_steps(PATROL_STEPS)
    print(f"   - 怪物模板数量: {len(hunter_files)}")
    print(f"   - 绳子模板数量: {len(rope_files)}")
    if PATROL_ENABLED:
        print(f"   - 巡逻步骤数: {len(patrol_steps)}")

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

    rope_templates = []
    for path in rope_files:
        tpl = cv2.imread(path)
        if tpl is None:
            continue
        h, w = tpl.shape[:2]
        edge_tpl = get_edge_map(tpl)
        rope_templates.append({"edge": edge_tpl, "w": w, "h": h})

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

    last_hunter_seen_ts = time.time()
    patrol_step_idx = 0
    patrol_next_ready_ts = 0.0

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
        rope_x_candidates = _detect_rope_xs(frame_edge, rope_templates) if rope_templates else []
        current_layer = _resolve_current_layer(char_center[1]) if char_center else None

        patrol_cmd = None
        if valid_hunts:
            last_hunter_seen_ts = now_ts
        elif PATROL_ENABLED and patrol_steps and char_center:
            if now_ts - last_hunter_seen_ts >= PATROL_NO_HUNTER_TIMEOUT_SEC:
                if now_ts >= patrol_next_ready_ts:
                    step = patrol_steps[patrol_step_idx % len(patrol_steps)]
                    action = step.get("action")

                    if action == "move":
                        step_x = step.get("x")
                        if isinstance(step_x, (int, float)):
                            tol = int(step.get("tol", PATROL_MOVE_TOLERANCE_PX))
                            patrol_cmd = {"action": "move", "x": int(step_x), "tol": tol}
                            if abs(char_center[0] - int(step_x)) <= max(1, tol):
                                patrol_step_idx += 1
                                patrol_next_ready_ts = now_ts + PATROL_STEP_COOLDOWN_SEC
                        else:
                            patrol_step_idx += 1
                    elif action == "wait":
                        wait_sec = float(step.get("wait_sec", PATROL_STEP_COOLDOWN_SEC))
                        patrol_cmd = {"action": "wait"}
                        patrol_step_idx += 1
                        patrol_next_ready_ts = now_ts + max(0.1, wait_sec)
                    else:
                        patrol_cmd = dict(step)
                        if action == "climb_up":
                            if PATROL_DYNAMIC_ROPE_X and rope_x_candidates:
                                nearest = min(rope_x_candidates, key=lambda x: abs(x - char_center[0]))
                                patrol_cmd["x"] = int(nearest)
                            elif current_layer in LAYER_POINTS and "rope_x" in LAYER_POINTS[current_layer]:
                                patrol_cmd["x"] = int(LAYER_POINTS[current_layer]["rope_x"])
                        patrol_step_idx += 1
                        hold_sec = float(step.get("hold_sec", 0.0))
                        patrol_next_ready_ts = now_ts + max(PATROL_STEP_COOLDOWN_SEC, hold_sec)

        with data_lock:
            shared_info["char"] = char_center
            shared_info["hunters"] = valid_hunts
            shared_info["patrol_cmd"] = patrol_cmd


        # 预览
        show = cv2.resize(frame, (0, 0), fx=VIEW_SCALE, fy=VIEW_SCALE)

        if char_center:
            pos_text = f"CHAR x={char_center[0]} y={char_center[1]}"
        else:
            pos_text = "CHAR x=- y=-"

        if patrol_cmd:
            action = patrol_cmd.get("action", "-")
            cmd_x = patrol_cmd.get("x")
            if isinstance(cmd_x, (int, float)):
                patrol_text = f"PATROL {action} x={int(cmd_x)}"
            else:
                patrol_text = f"PATROL {action}"
        elif PATROL_ENABLED:
            patrol_text = "PATROL ready"
        else:
            patrol_text = "PATROL off"

        layer_text = f"LAYER {current_layer if current_layer else '-'}"
        if rope_x_candidates:
            rope_text = f"ROPE n={len(rope_x_candidates)} near={min(rope_x_candidates, key=lambda x: abs(x - char_center[0])) if char_center else rope_x_candidates[0]}"
        else:
            rope_text = "ROPE n=0"

        _draw_debug_text(show, pos_text, 12, 26)
        _draw_debug_text(show, patrol_text, 12, 50)
        _draw_debug_text(show, layer_text, 12, 74)
        _draw_debug_text(show, rope_text, 12, 98)

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