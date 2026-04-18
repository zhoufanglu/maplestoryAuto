import pydirectinput as pd
import time
import threading
import ctypes

# 1. 环境初始化（保持 test.py 的成功经验）
try:
    ctypes.windll.user32.SetProcessDPIAware()
except:
    pass

# ==========================================
# 🛠️ 配置变量区 (在这里修改按键和时间)
# ==========================================

# 技能 1 配置 (比如 F10)
BUFF1_KEY = 'f10'
BUFF1_INTERVAL = 80  # 单位：秒

# 技能 2 配置 (比如 F11)
BUFF2_KEY = 'f11'
BUFF2_INTERVAL = 200  # 单位：秒

# 动作控制变量
STOP_BEFORE_PRESS = 1.0  # 按键前的停顿时间（确保站稳）
PRESS_DURATION = 0.5  # 按键按下的持续时间（模拟长按）
STOP_AFTER_PRESS = 2.0  # 按完后的静止时间（你要求的2s）

# ==========================================
# 核心状态变量
# ==========================================
is_buffing = False


def buff_loop(key, interval):
    global is_buffing

    # 启动缓冲，防止一开脚本就手忙脚乱
    time.sleep(5)

    while True:
        # 1. 开启熔断：停止移动和攻击
        is_buffing = True
        print(f"\n[✨] Buff 熔断开启: 准备施放 {key.upper()}")

        # 2. 清理按键状态
        for k in ['left', 'right', 'x', 'shift', 'ctrl']:
            pd.keyUp(k)

        # 3. 施法前站稳
        time.sleep(STOP_BEFORE_PRESS)

        # 4. 执行按键动作
        print(f"[!] 正在按下 {key.upper()}...")
        pd.keyDown(key)
        time.sleep(PRESS_DURATION)
        pd.keyUp(key)

        # 5. 【核心】按下后绝对静止
        print(f"[⏳] 施法后摇，保持静止 {STOP_AFTER_PRESS}s...")
        time.sleep(STOP_AFTER_PRESS)

        # 6. 关闭熔断：恢复自动战斗
        is_buffing = False
        print(f"[√] {key.upper()} 施放完毕，恢复战斗状态。")

        # 7. 等待冷却周期
        # 实际等待时间减去已经消耗的施法时间，保证周期准确
        actual_wait = interval - (STOP_BEFORE_PRESS + PRESS_DURATION + STOP_AFTER_PRESS)
        time.sleep(max(0, actual_wait))


def start_buff_threads():
    """
    启动定时线程
    """
    # 线程 1
    t1 = threading.Thread(
        target=buff_loop,
        args=(BUFF1_KEY, BUFF1_INTERVAL),
        daemon=True
    )
    # 线程 2
    t2 = threading.Thread(
        target=buff_loop,
        args=(BUFF2_KEY, BUFF2_INTERVAL),
        daemon=True
    )

    t1.start()
    t2.start()
    print(f"✅ Buff 监控已启动:")
    print(f"   - 技能1: {BUFF1_KEY} (每 {BUFF1_INTERVAL}s)")
    print(f"   - 技能2: {BUFF2_KEY} (每 {BUFF2_INTERVAL}s)")
    print(f"   - 施法后固定静止: {STOP_AFTER_PRESS}s")


if __name__ == "__main__":
    print("正在进行管理员权限及变量测试...")
    print(f"测试按键: {BUFF1_KEY}")
    time.sleep(2)
    pd.keyDown(BUFF1_KEY)
    time.sleep(PRESS_DURATION)
    pd.keyUp(BUFF1_KEY)
    print("测试指令已发送。")