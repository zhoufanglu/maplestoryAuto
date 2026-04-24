import pydirectinput as pd
import time
import random
import auto_buff

# 配置
pd.PAUSE = 0.01

# 距离配置
RANGE_ATTACK = 140  # 攻击距离
RANGE_STOP_RUN = 120  # 缓冲距离，防止在边缘反复起步


def auto_action(char_pos, hunters_pos, attack_key='x'):
    try:
        # 1. 状态检查
        if auto_buff.is_buffing:
            return

        if char_pos is None or not hunters_pos:
            pd.keyUp('left')
            pd.keyUp('right')
            return

        char_x, char_y = char_pos

        # 2. 寻找最近目标
        closest_hunter = None
        min_dist_x = 999999
        for h in hunters_pos:
            if isinstance(h, (list, tuple)):
                dist_x = abs(h[0] - char_x)
                if dist_x < min_dist_x:
                    min_dist_x = dist_x
                    closest_hunter = h

        if closest_hunter:
            target_x, _ = closest_hunter
            direction = 'left' if target_x < char_x else 'right'
            other_dir = 'right' if direction == 'left' else 'left'

            # --- 丝滑移动核心逻辑 ---

            # 如果距离大于攻击距离，就一直走
            if min_dist_x > RANGE_ATTACK:
                pd.keyUp(other_dir)  # 确保不按反方向
                pd.keyDown(direction)  # 保持按住，不松开
                # 这里不写 sleep，让程序快速进入下一轮识别，实现丝滑追踪

            # 如果进入攻击范围
            else:
                # 到了位置立刻松开方向键
                pd.keyUp(direction)

                # 转身处理：如果目标在左边但角色面朝右，点按一下转向
                pd.press(direction)

                # 触发攻击
                time.sleep(0.02)  # 极短停顿增加稳定性
                pd.press(attack_key)

                # 攻击后的微小随机延迟，模拟真人操作
                time.sleep(random.uniform(0.05, 0.1))
                print(f"[*] 斩击目标: {target_x} ", end='\r')

        else:
            pd.keyUp('left')
            pd.keyUp('right')

    except Exception as e:
        print(f"❌ attack.py 报错: {e}")