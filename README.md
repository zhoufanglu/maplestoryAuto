# 截图工具使用
- 控制台使用
Set-Location "D:\workspace\maplestoryAuto"
python -u capture_hunter_roi.py
按r截图，q退出，图片会自动存放在hunters/img****.png内


# 屏幕外找怪巡逻（可选）
- 在 `config.jsonc` 中开启：`"patrol": { "enabled": true }`
- `steps` 支持 4 种动作：
  - `{ "action": "move", "x": 760 }`：移动到指定 X
  - `{ "action": "down_jump" }`：执行下跳（down+alt）
  - `{ "action": "climb_up", "x": 470, "tol": 20, "hold_sec": 0.8 }`：对齐后上跳爬绳
  - `{ "action": "wait", "wait_sec": 0.4 }`：等待
- 当连续 `no_hunter_timeout_sec` 秒没识别到怪物时，会按 `steps` 轮询执行。


