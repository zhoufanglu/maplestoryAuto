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
SNOWMAN_IMG = 'xiaoxueren.png'
CHAR_TITLE_IMG = 'char_title.png'  # 👈 更新：使用角色的称号图片

# 阈值设置
THRESHOLD_SNOWMAN = 0.55  # 雪人识别阈值 (根据你的反馈保持0.40)
THRESHOLD_TITLE = 0.60  # 👈 称号识别阈值 (称号是固定的，建议先设高，如0.70-0.80)

# 预览窗口设置
VIEW_SCALE = 0.7
# ==========================================

# 解决 Win11 缩放导致坐标偏移
try:
    ctypes.windll.user32.SetProcessDPIAware()
except:
    pass


def start_title_vision():
    print(f"[*] 正在搜寻窗口: [{GAME_WINDOW_TITLE}]...")

    try:
        all_wins = gw.getWindowsWithTitle(GAME_WINDOW_TITLE)
        target_win = [w for w in all_wins if w.title == GAME_WINDOW_TITLE][0]
    except IndexError:
        print(f"❌ 错误：没找到名为 '{GAME_WINDOW_TITLE}' 的窗口！")
        return

    print(f"[*] 窗口已锁定。预览窗口按 'q' 键退出。")

    print("[*] 正在加载特征模板...")

    # 加载雪人
    tpl_snowman = cv2.imread(SNOWMAN_IMG)
    if tpl_snowman is None:
        print(f"❌ 错误：根目录下找不到 {SNOWMAN_IMG}")
        return
    h_snw, w_snw = tpl_snowman.shape[:2]

    # 加载角色称号
    tpl_title = cv2.imread(CHAR_TITLE_IMG)
    if tpl_title is None:
        print(f"❌ 错误：根目录下找不到 {CHAR_TITLE_IMG}")
        return
    h_ttl, w_ttl = tpl_title.shape[:2]

    print("[*] 称号视觉引擎就绪！")

    while True:
        # 1. 局部截图
        rect = (target_win.left, target_win.top, target_win.width, target_win.height)
        screenshot = pyautogui.screenshot(region=rect)
        frame = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)

        # ==========================================
        # 【2. 多目标匹配：雪人 -> 红框】(保持不变)
        # ==========================================
        res_snw = cv2.matchTemplate(frame, tpl_snowman, cv2.TM_CCOEFF_NORMED)
        loc_snw = np.where(res_snw >= THRESHOLD_SNOWMAN)

        rects_snw = []
        for pt in zip(*loc_snw[::-1]):
            rects_snw.append([int(pt[0]), int(pt[1]), int(w_snw), int(h_snw)])
            rects_snw.append([int(pt[0]), int(pt[1]), int(w_snw), int(h_snw)])

        rects_snw, _ = cv2.groupRectangles(rects_snw, groupThreshold=1, eps=0.5)

        snw_count = 0
        for (x, y, w_box, h_box) in rects_snw:
            cv2.rectangle(frame, (x, y), (x + w_box, y + h_box), (0, 0, 255), 2)
            cv2.putText(frame, f"S:{snw_count}", (x, y - 5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
            snw_count += 1

        # ==========================================
        # 【3. 匹配：角色称号 -> 蓝框】(重点修改)
        # ==========================================
        res_ttl = cv2.matchTemplate(frame, tpl_title, cv2.TM_CCOEFF_NORMED)

        # 使用单点匹配模式即可，因为只有一个主角色
        _, max_val_ttl, _, max_loc_ttl = cv2.minMaxLoc(res_ttl)

        char_count = 0
        if max_val_ttl >= THRESHOLD_TITLE:
            x, y = max_loc_ttl
            # 绘制称号蓝框 (线条稍微粗一点以示区别)
            cv2.rectangle(frame, max_loc_ttl, (x + w_ttl, y + h_ttl), (255, 0, 0), 3)
            # 在蓝框下方写上“CHAR”
            cv2.putText(frame, "CHAR TITLE", (x, y + h_ttl + 15),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 0), 2)
            char_count = 1

        # 打印状态
        print(f"🔍 监控中... 雪人: {snw_count}  角色称号: {char_count} (Max:{max_val_ttl:.2f})   ", end='\r')

        # 4. 显示预览
        show_frame = cv2.resize(frame, (0, 0), fx=VIEW_SCALE, fy=VIEW_SCALE)
        cv2.imshow('Title-Monitor', show_frame)

        # 按 Q 退出
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cv2.destroyAllWindows()


if __name__ == "__main__":
    start_title_vision()