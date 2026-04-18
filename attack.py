import pydirectinput as pd
import time
import random
import auto_buff

# 配置
pd.PAUSE = 0.01

# 距离配置
RANGE_ATTACK = 140  # 攻击距离
RANGE_RUN = 300  # 超过这个距离开启“长跑模式”


def auto_action(char_pos, hunters_pos, attack_key='x'):
    try:
        # 1. 熔断检查
        if auto_buff.is_buffing:
            return

        # 2. 安全检查
        if char_pos is None or not hunters_pos or len(hunters_pos) == 0:
            pd.keyUp('left')
            pd.keyUp('right')
            return

        char_x, char_y = char_pos

        # 3. 寻找最近目标 (增加健壮性处理)
        closest_hunter = None
        min_dist_x = 999999

        for h in hunters_pos:
            # 确保拿到的是坐标点
            if isinstance(h, (list, tuple)) and len(h) >= 2:
                h_x, h_y = h[0], h[1]
                dist_x = abs(h_x - char_x)
                if dist_x < min_dist_x:
                    min_dist_x = dist_x
                    closest_hunter = (h_x, h_y)

        if closest_hunter:
            target_x, _ = closest_hunter
            direction = 'left' if target_x < char_x else 'right'
            other_dir = 'right' if direction == 'left' else 'left'

            pd.keyUp(other_dir)

            # 情况 A：远距离奔跑
            if min_dist_x > RANGE_RUN:
                pd.keyDown(direction)
                time.sleep(0.3)  # 缩短单次步长，增加响应频率
                # 不松开，交给下一轮循环

            # 情况 B：中等距离
            elif RANGE_ATTACK < min_dist_x <= RANGE_RUN:
                pd.keyDown(direction)
                time.sleep(0.1)
                pd.keyUp(direction)

            # 情况 C：攻击
            else:
                pd.keyUp(direction)
                # 转身逻辑
                pd.press(direction)  # 使用 press 代替 down/up 组合更稳定
                time.sleep(0.05)

                # 攻击
                pd.press(attack_key)
                print(f"[*] 斩击目标: {target_x} ", end='\r')
                time.sleep(0.1)

        else:
            pd.keyUp('left')
            pd.keyUp('right')

    except Exception as e:
        print(f"❌ attack.py 发生错误: {e}")