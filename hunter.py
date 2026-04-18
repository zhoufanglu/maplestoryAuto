import cv2
import numpy as np
import pyautogui
import time
import ctypes
import pygetwindow as gw

# ==========================================
# 核心设置区
# ==========================================
GAME_WINDOW_TITLE = "MapleStoryGo"

# 模板图片设置
HUNTER_TARGET_IMG = 'hunters/xiaoxueren.png'  # 虽然文件名没变，但逻辑变量已改为 Hunter
CHAR_TITLE_IMG = 'char_title.png'

# 阈值设置
THRESHOLD_HUNTER = 0.55   # 猎物识别阈值
THRESHOLD_TITLE = 0.60    # 称号识别阈值

# 预览窗口设置
VIEW_SCALE = 0.7
# ==========================================

# 解决 Win11 缩放导致坐标偏移
try:
    ctypes.windll.user32.SetProcessDPIAware()
except:
    pass


def start_hunter_vision():
    print(f"[*] 正在搜寻窗口: [{GAME_WINDOW_TITLE}]...")

    try:
        all_wins = gw.getWindowsWithTitle(GAME_WINDOW_TITLE)
        target_win = [w for w in all_wins if w.title == GAME_WINDOW_TITLE][0]
    except IndexError:
        print(f"❌ 错误：没找到名为 '{GAME_WINDOW_TITLE}' 的窗口！")
        return

    print(f"[*] 窗口已锁定。预览窗口按 'q' 键退出。")
    print("[*] 正在加载特征模板...")

    # 加载猎物 (原小雪人)
    tpl_hunter = cv2.imread(HUNTER_TARGET_IMG)
    if tpl_hunter is None:
        print(f"❌ 错误：根目录下找不到 {HUNTER_TARGET_IMG}")
        return
    h_htr, w_htr = tpl_hunter.shape[:2]

    # 加载角色称号
    tpl_title = cv2.imread(CHAR_TITLE_IMG)
    if tpl_title is None:
        print(f"❌ 错误：根目录下找不到 {CHAR_TITLE_IMG}")
        return
    h_ttl, w_ttl = tpl_title.shape[:2]

    print("[*] Hunter 视觉引擎就绪！")

    while True:
        # 1. 局部截图
        rect = (target_win.left, target_win.top, target_win.width, target_win.height)
        screenshot = pyautogui.screenshot(region=rect)
        frame = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)

        # ==========================================
        # 【2. 多目标匹配：猎物 (Hunter) -> 红框】
        # ==========================================
        res_htr = cv2.matchTemplate(frame, tpl_hunter, cv2.TM_CCOEFF_NORMED)
        loc_htr = np.where(res_htr >= THRESHOLD_HUNTER)

        rects_htr = []
        for pt in zip(*loc_htr[::-1]):
            rects_htr.append([int(pt[0]), int(pt[1]), int(w_htr), int(h_htr)])
            rects_htr.append([int(pt[0]), int(pt[1]), int(w_htr), int(h_htr)])

        # 过滤重叠框
        rects_htr, _ = cv2.groupRectangles(rects_htr, groupThreshold=1, eps=0.5)

        hunter_count = 0
        for (x, y, w_box, h_box) in rects_htr:
            # 绘制红框
            cv2.rectangle(frame, (x, y), (x + w_box, y + h_box), (0, 0, 255), 2)
            # 标记改为 H (代表 Hunter)
            cv2.putText(frame, f"H:{hunter_count}", (x, y - 5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
            hunter_count += 1

        # ==========================================
        # 【3. 匹配：角色称号 -> 蓝框】
        # ==========================================
        res_ttl = cv2.matchTemplate(frame, tpl_title, cv2.TM_CCOEFF_NORMED)
        _, max_val_ttl, _, max_loc_ttl = cv2.minMaxLoc(res_ttl)

        char_count = 0
        if max_val_ttl >= THRESHOLD_TITLE:
            tx, ty = max_loc_ttl
            cv2.rectangle(frame, (tx, ty), (tx + w_ttl, ty + h_ttl), (255, 0, 0), 3)
            cv2.putText(frame, "CHARACTER", (tx, ty + h_ttl + 15),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 0), 2)
            char_count = 1

        # 打印状态
        print(f"🔍 狩猎监控中... 猎物(Hunter): {hunter_count}  角色: {char_count} (Max:{max_val_ttl:.2f})   ", end='\r')

        # 4. 显示预览
        show_frame = cv2.resize(frame, (0, 0), fx=VIEW_SCALE, fy=VIEW_SCALE)
        cv2.imshow('Hunter-Monitor-System', show_frame)

        # 按 Q 退出
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cv2.destroyAllWindows()


if __name__ == "__main__":
    start_hunter_vision()