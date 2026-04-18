import pyautogui
import winsound
import time

# ==========================================
# 🛠️ 告警配置
# ==========================================
WARNING_IMAGE = 'warning.png'  # 告警图片路径
CONFIDENCE_LEVEL = 0.5  # 匹配精度
ALARM_DURATION = 1000  # 声音持续时间 (毫秒)
ALARM_FREQUENCY = 1000  # 声音频率 (Hz)


def check_for_warning():
    """
    检查屏幕是否存在告警图片，如果存在则鸣叫
    """
    try:
        # 在全屏范围内查找告警图
        location = pyautogui.locateOnScreen(WARNING_IMAGE, confidence=CONFIDENCE_LEVEL)

        if location:
            print(f"\n[🚨 ALERT] 检测到告警图片 {WARNING_IMAGE}！正在发出警报...")
            # 发出蜂鸣声 (持续 1 秒)
            winsound.Beep(ALARM_FREQUENCY, ALARM_DURATION)
            return True
        return False
    except Exception as e:
        # 如果是因为没找到图片报错，通常是由于 confidence 没装 opencv
        # print(f"检测告警时出错: {e}")
        return False


if __name__ == "__main__":
    print("正在进行告警声测试，请听声音...")
    winsound.Beep(ALARM_FREQUENCY, ALARM_DURATION)
    print("测试结束。")