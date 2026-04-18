import pygame
import os
import time
import winsound

# ==========================================
# 配置区
# ==========================================
ALARM_FILE = 'warning.mp3'


def test_audio():
    print("--- 🔊 告警音效兼容性测试 ---")

    # 1. 检查文件是否存在
    if not os.path.exists(ALARM_FILE):
        print(f"❌ 错误：在当前目录下没找到 {ALARM_FILE}")
        print(f"当前路径: {os.getcwd()}")
        return

    print(f"✅ 找到文件: {ALARM_FILE}")

    # 2. 尝试使用 Pygame 播放 (支持 MP3 最佳)
    try:
        print("\n🧪 测试 1：正在尝试使用 Pygame 播放...")
        pygame.mixer.init()
        pygame.mixer.music.load(ALARM_FILE)
        pygame.mixer.music.play()

        print("🎶 播放指令已发送，请听是否有声音...")
        # 等待 5 秒，确保异步播放有时间发出声音
        start_time = time.time()
        while time.time() - start_time < 5:
            if pygame.mixer.music.get_busy():
                time.sleep(0.1)
            else:
                break
        print("✨ Pygame 测试流程结束。")

    except Exception as e:
        print(f"❌ Pygame 播放失败: {e}")

    # 3. 兜底测试：系统内置音
    print("\n🧪 测试 2：正在尝试调用 Windows 系统内置音 (MessageBeep)...")
    try:
        # 这个不需要文件，直接调用系统 API
        winsound.MessageBeep(winsound.MB_ICONHAND)
        print("🔔 系统音指令已发送。")
    except Exception as e:
        print(f"❌ 系统音调用失败: {e}")

    print("\n--- 测试全部完成 ---")


if __name__ == "__main__":
    test_audio()