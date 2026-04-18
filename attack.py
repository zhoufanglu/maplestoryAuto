import pydirectinput as pd
import time
import random

# 配置
pd.PAUSE = 0.01

# 距离配置
RANGE_ATTACK = 140  # 攻击距离
RANGE_RUN = 300  # 超过这个距离开启“长跑模式”


def auto_action(char_pos, hunters_pos, attack_key='x'):
    if char_pos is None or not hunters_pos:
        # 没怪的时候确保按键释放
        pd.keyUp('left')
        pd.keyUp('right')
        return

    char_x, char_y = char_pos

    # 1. 寻找最近目标
    closest_hunter = None
    min_dist_x = 999999
    for h_x, h_y in hunters_pos:
        dist_x = abs(h_x - char_x)
        if dist_x < min_dist_x:
            min_dist_x = dist_x
            closest_hunter = (h_x, h_y)

    if closest_hunter:
        target_x, _ = closest_hunter
        direction = 'left' if target_x < char_x else 'right'
        other_dir = 'right' if direction == 'left' else 'left'

        # 确保不会同时按住反方向
        pd.keyUp(other_dir)

        # --- 优化后的丝滑移动逻辑 ---

        # 情况 A：怪很远 -> 开启长跑模式
        if min_dist_x > RANGE_RUN:
            pd.keyDown(direction)
            # 增加单次按住的时间，减少“走走停停”
            time.sleep(random.uniform(0.5, 0.8))
            # 注意：这里不急着 keyUp，让下一轮循环决定是否继续跑
            print(f"[*] 远距离奔跑: {direction} ", end='\r')

        # 情况 B：中等距离 -> 小碎步接近
        elif RANGE_ATTACK < min_dist_x <= RANGE_RUN:
            pd.keyDown(direction)
            time.sleep(random.uniform(0.1, 0.2))
            pd.keyUp(direction)
            print(f"[*] 小碎步接近: {direction} ", end='\r')

        # 情况 C：到达攻击距离 -> 瞬间转向 + 攻击
        else:
            # 如果之前在跑，先松开方向键站稳
            pd.keyUp(direction)
            time.sleep(0.05)

            # 转身（极短）
            pd.keyDown(direction)
            time.sleep(0.02)
            pd.keyUp(direction)

            # 攻击
            time.sleep(0.05)
            pd.keyDown(attack_key)
            time.sleep(random.uniform(0.1, 0.15))
            pd.keyUp(attack_key)

            # 攻击后随机发呆时间缩短，提升连贯性
            time.sleep(random.uniform(0.1, 0.2))
            print(f"[*] 斩击完成！          ", end='\r')

    else:
        # 没目标时释放按键
        pd.keyUp('left')
        pd.keyUp('right')