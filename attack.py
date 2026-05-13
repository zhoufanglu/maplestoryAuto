import pydirectinput as pd
import time
import random
import auto_buff
from typing import Optional

# 配置
pd.PAUSE = 0.01

# 距离配置
RANGE_ATTACK = 200  # 攻击距离
RANGE_STOP_RUN = 120  # 缓冲距离，防止在边缘反复起步


def _release_lr():
    pd.keyUp('left')
    pd.keyUp('right')


def _move_to_x(char_x: int, target_x: int, stop_tol: int) -> bool:
    delta_x = target_x - char_x
    if abs(delta_x) <= max(1, stop_tol):
        _release_lr()
        return True

    direction = 'left' if delta_x < 0 else 'right'
    other_dir = 'right' if direction == 'left' else 'left'
    pd.keyUp(other_dir)
    pd.keyDown(direction)
    return False


def _execute_patrol_command(char_pos, patrol_command: dict):
    action = patrol_command.get('action')
    char_x, _ = char_pos

    if action == 'move':
        target_x = patrol_command.get('x')
        stop_tol = int(patrol_command.get('tol', 24))
        if isinstance(target_x, (int, float)):
            _move_to_x(char_x, int(target_x), stop_tol)
        return

    _release_lr()
    if action == 'down_jump':
        pd.keyDown('down')
        time.sleep(0.03)
        pd.press('alt')
        time.sleep(0.03)
        pd.keyUp('down')
        return

    if action == 'climb_up':
        target_x = patrol_command.get('x')
        align_tol = int(patrol_command.get('tol', 20))
        if isinstance(target_x, (int, float)) and not _move_to_x(char_x, int(target_x), align_tol):
            return

        hold_sec = float(patrol_command.get('hold_sec', 0.7))
        pd.keyDown('up')
        time.sleep(0.02)
        pd.press('alt')
        time.sleep(max(0.1, hold_sec))
        pd.keyUp('up')
        return

    if action == 'wait':
        return

    if action == 'scan_left':
        hold_sec = float(patrol_command.get('hold_sec', 0.45))
        pd.keyUp('right')
        pd.keyDown('left')
        time.sleep(max(0.05, hold_sec))
        pd.keyUp('left')
        return

    if action == 'scan_right':
        hold_sec = float(patrol_command.get('hold_sec', 0.45))
        pd.keyUp('left')
        pd.keyDown('right')
        time.sleep(max(0.05, hold_sec))
        pd.keyUp('right')
        return


def auto_action(char_pos, hunters_pos, attack_key='x', patrol_command: Optional[dict] = None):
    try:
        # 1. 状态检查
        if auto_buff.is_buffing:
            return

        if char_pos is None:
            _release_lr()
            return

        if patrol_command:
            _execute_patrol_command(char_pos, patrol_command)
            return

        if not hunters_pos:
            _release_lr()
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
            _release_lr()

    except Exception as e:
        print(f"❌ attack.py 报错: {e}")