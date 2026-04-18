import pygetwindow as gw

# 获取所有打开的窗口标题
all_titles = gw.getAllTitles()

print("--- 当前电脑所有窗口标题如下 ---")
for title in all_titles:
    if title.strip():  # 只打印不为空的名字
        print(f"[{title}]")
print("------------------------------")