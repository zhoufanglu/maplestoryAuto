import pydirectinput as pd
import time
import ctypes

# 强制开启 DPI 意识，防止坐标或按键偏移
try:
    ctypes.windll.user32.SetProcessDPIAware()
except:
    pass


def test_keys():
    print("=" * 30)
    print("🎮 游戏按键模拟测试工具")
    print("=" * 30)
    print("请在 2 秒内切换到游戏窗口，并确保输入法为 ENG (英文)...")

    # 倒计时
    for i in range(2, 0, -1):
        print(f"倒计时: {i}...")
        time.sleep(1)

    # --- 测试 F10 ---
    print("\n[1/2] 正在尝试按 F10...")
    pd.keyDown('f10')
    time.sleep(0.5)  # 模拟长按 0.5 秒
    pd.keyUp('f10')
    print("   -> 指令已发送，请观察游戏内是否施放技能。")

    time.sleep(2)  # 间隔一下

    # --- 测试 F11 ---
    print("\n[2/2] 正在尝试按 F11...")
    pd.keyDown('f11')
    time.sleep(0.5)  # 模拟长按 0.5 秒
    pd.keyUp('f11')
    print("   -> 指令已发送，请观察游戏内是否切换窗口或施放技能。")

    print("\n" + "=" * 30)
    print("测试结束。如果没反应，请检查游戏是否为管理员运行。")


if __name__ == "__main__":
    test_keys()