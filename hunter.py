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
# 在这里增加你的怪物图片路径
HUNTER_FILES = [
    'hunters/jiangshi.png',
    'hunters/jiangshi-3.png',
    'hunters/jiangshi-2.png'
    # 'hunters/xiaoxueren.png',
    #'hunters/lang-1.png',
    #'hunters/lang-2.png'
]
TITLE_IMG = 'char_title.png'
THRESHOLD_HUNTER = 0.60  # 怪物识别阈值
THRESHOLD_TITLE = 0.60  # 角色识别阈值
VIEW_SCALE = 0.5  # 预览窗口缩放比例

# 数据锁和共享x信息
data_lock = threading.Lock()
shared_info = {"char": None, "hunters": []}

# ==========================================
# 环境初始化
# ==========================================
try:
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

        if char_center and hunters_pos_list:
            # 这里的攻击逻辑会根据主线程更新的怪物列表进行操作
            attack.auto_action(char_center, hunters_pos_list)

        time.sleep(0.01)


# ==========================================
# 子线程 2：告警监控
# ==========================================
def warning_worker(win_title):
    print("✅ [线程] 告警监控线程已启动...")
    while True:
        try:
            wins = gw.getWindowsWithTitle(win_title)
            if wins:
                target_win = wins[0]
                region = (target_win.left, target_win.top, target_win.width, target_win.height)
                if warning.check_for_warning(region=region):
                    print("[🚨 ALERT] 屏幕检测到异常告警图！")
        except:
            pass
        time.sleep(2.0)


# ==========================================
# 主运行逻辑
# ==========================================
def run():
    # 1. 窗口检测
    try:
        win = gw.getWindowsWithTitle(GAME_WINDOW_TITLE)[0]
        if win.isMinimized:
            win.restore()
    except:
        print(f"❌ 找不到窗口名为 '{GAME_WINDOW_TITLE}' 的游戏")
        return

    # 2. 批量加载怪物模板
    monster_templates = []
    for path in HUNTER_FILES:
        tpl = cv2.imread(path)
        if tpl is None:
            print(f"⚠️ 警告：图片 {path} 加载失败，请检查路径")
            continue
        h, w = tpl.shape[:2]
        monster_templates.append({"tpl": tpl, "w": w, "h": h, "path": path})

    # 加载角色模板
    tpl_t = cv2.imread(TITLE_IMG)
    if tpl_t is None:
        print(f"❌ 角色图片 {TITLE_IMG} 加载失败")
        return
    h_t, w_t = tpl_t.shape[:2]

    # 3. 启动相关线程
    auto_buff.start_buff_threads()

    t_warn = threading.Thread(target=warning_worker, args=(GAME_WINDOW_TITLE,), daemon=True)
    t_warn.start()

    t_atk = threading.Thread(target=attack_worker, daemon=True)
    t_atk.start()

    print(f"📸 视觉识别启动！已加载 {len(monster_templates)}x 种怪物模板")

    while True:
        # 截取窗口
        rect = (win.left, win.top, win.width, win.height)
        img = pyautogui.screenshot(region=rect)
        frame = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)

        # --- 多怪物识别逻辑 ---
        rects_all_hunters = []
        for m in monster_templates:
            res = cv2.matchTemplate(frame, m["tpl"], cv2.TM_CCOEFF_NORMED)
            loc = np.where(res >= THRESHOLD_HUNTER)

            # 收集当前模板匹配到的所有位置
            for pt in zip(*loc[::-1]):
                # 为了 groupRectangles 正常工作，每个框添加两次
                rects_all_hunters.append([int(pt[0]), int(pt[1]), int(m["w"]), int(m["h"])])
                rects_all_hunters.append([int(pt[0]), int(pt[1]), int(m["w"]), int(m["h"])])

        # 统一处理所有怪物的坐标
        hunters_pos_list = []
        if len(rects_all_hunters) > 0:
            # 合并不同模板可能产生的重叠框
            rects_all_hunters, _ = cv2.groupRectangles(rects_all_hunters, 1, 0.5)
            for (x, y, w, h) in rects_all_hunters:
                hunters_pos_list.append((x + w // 2, y + h // 2))
                cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 0, 255), 2)

        # --- 角色识别 ---
        res_t = cv2.matchTemplate(frame, tpl_t, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(res_t)

        char_center = None
        if max_val >= THRESHOLD_TITLE:
            char_center = (max_loc[0] + w_t // 2, max_loc[1] + h_t // 2)
            cv2.rectangle(frame, max_loc, (max_loc[0] + w_t, max_loc[1] + h_t), (255, 0, 0), 3)

        # --- 数据同步 ---
        with data_lock:
            shared_info["char"] = char_center
            shared_info["hunters"] = hunters_pos_list

        # --- UI 显示状态 ---
        status_text = "BUFFING" if auto_buff.is_buffing else "FIGHTING"
        color = (0, 255, 255) if auto_buff.is_buffing else (0, 255, 0)
        cv2.putText(frame, f"STATUS: {status_text}", (20, 40),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
        cv2.putText(frame, f"TARGETS: {len(hunters_pos_list)}", (20, 70),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)

        # 展示预览
        show = cv2.resize(frame, (0, 0), fx=VIEW_SCALE, fy=VIEW_SCALE)
        cv2.imshow('Multi-Hunter Monitoring', show)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
        time.sleep(0.01)

    cv2.destroyAllWindows()


if __name__ == "__main__":
    run()