import time
import cv2
import numpy as np
import pyautogui
import ctypes
import pygetwindow as gw
import threading

# 导入你自定义的三个模块
import attack
import auto_buff
import warning

# ==========================================
# 核心设置区
# ==========================================
GAME_WINDOW_TITLE = "MapleStoryGo"
HUNTER_IMG = 'hunters/xiaoxueren.png'
TITLE_IMG = 'char_title.png'

THRESHOLD_HUNTER = 0.55
THRESHOLD_TITLE = 0.60
VIEW_SCALE = 0.5

# 数据锁和共享信息
data_lock = threading.Lock()
shared_info = {"char": None, "hunters": []}

# ==========================================
# 环境初始化
# ==========================================
try:
    # 强制 DPI 意识，防止在副屏或高分屏下坐标偏移
    ctypes.windll.user32.SetProcessDPIAware()
except:
    pass


# ==========================================
# 子线程 1：攻击逻辑处理
# ==========================================
def attack_worker():
    print("🚀 [线程] 攻击逻辑子线程已启动")
    while True:
        with data_lock:
            char_center = shared_info["char"]
            hunters_pos_list = shared_info["hunters"]

        # attack.auto_action 内部会判断 auto_buff.is_buffing
        # 如果正在加 Buff，该函数会直接 return，实现原地静止
        if char_center and hunters_pos_list:
            attack.auto_action(char_center, hunters_pos_list)

        time.sleep(0.01)


# ==========================================
# 子线程 2：告警监控（warning.png）
# ==========================================
def warning_worker(win_title):
    print("✅ [线程] 告警监控线程已启动...")
    while True:
        try:
            # 实时获取窗口位置，支持窗口拖动到副屏
            wins = gw.getWindowsWithTitle(win_title)
            if wins:
                target_win = wins[0]
                region = (target_win.left, target_win.top, target_win.width, target_win.height)

                # 调用 warning 模块检测，发现匹配则发出声音
                if warning.check_for_warning(region=region):
                    print("[🚨 ALERT] 屏幕检测到异常告警图！")
        except Exception as e:
            # 防止窗口最小化或关闭时报错
            pass

        # 告警检测没必要太频繁，每 2 秒一次即可
        time.sleep(2.0)


# ==========================================
# 主运行逻辑
# ==========================================
def run():
    # 1. 窗口检测
    try:
        win = gw.getWindowsWithTitle(GAME_WINDOW_TITLE)[0]
        # 如果窗口被最小化，尝试恢复它（可选）
        if win.isMinimized:
            win.restore()
    except:
        print(f"❌ 找不到窗口名为 '{GAME_WINDOW_TITLE}' 的游戏")
        return

    # 2. 模板加载
    tpl_h = cv2.imread(HUNTER_IMG)
    tpl_t = cv2.imread(TITLE_IMG)
    if tpl_h is None or tpl_t is None:
        print(f"❌ 图片加载失败！请检查路径：\n怪物: {HUNTER_IMG}\n角色: {TITLE_IMG}")
        return

    h_h, w_h = tpl_h.shape[:2]
    h_t, w_t = tpl_t.shape[:2]

    # 3. 启动 Buff 定时线程 (F10/F11)
    auto_buff.start_buff_threads()

    # 4. 启动告警监控线程
    t_warn = threading.Thread(target=warning_worker, args=(GAME_WINDOW_TITLE,), daemon=True)
    t_warn.start()

    # 5. 启动攻击子线程
    t_atk = threading.Thread(target=attack_worker, daemon=True)
    t_atk.start()

    print("📸 视觉识别主线程启动 (按下 'Q' 键退出)...")

    while True:
        # 截取游戏窗口区域
        rect = (win.left, win.top, win.width, win.height)
        img = pyautogui.screenshot(region=rect)
        frame = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)

        # --- 怪物识别 ---
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

        # --- 角色识别 ---
        res_t = cv2.matchTemplate(frame, tpl_t, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(res_t)

        char_center = None
        if max_val >= THRESHOLD_TITLE:
            char_center = (max_loc[0] + w_t // 2, max_loc[1] + h_t // 2)
            cv2.rectangle(frame, max_loc, (max_loc[0] + w_t, max_loc[1] + h_t), (255, 0, 0), 3)

        # --- 状态显示 ---
        if auto_buff.is_buffing:
            cv2.putText(frame, "STATUS: BUFFING (STILL)", (20, 40),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
        else:
            cv2.putText(frame, "STATUS: FIGHTING", (20, 40),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)

        # --- 数据同步 ---
        with data_lock:
            shared_info["char"] = char_center
            shared_info["hunters"] = hunters_pos_list

        # --- 预览窗口展示 ---
        show = cv2.resize(frame, (0, 0), fx=VIEW_SCALE, fy=VIEW_SCALE)
        cv2.imshow('Hunter System - Monitoring', show)

        # 退出机制
        if cv2.waitKey(1) & 0xFF == ord('q'):
            print("👋 正在关闭脚本...")
            break

        # 控制主线程采样频率，避免 CPU 占用 100%
        time.sleep(0.01)

    cv2.destroyAllWindows()


if __name__ == "__main__":
    run()