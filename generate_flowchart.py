import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, FancyBboxPatch, Arrow
import numpy as np

plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei']
plt.rcParams['axes.unicode_minus'] = False

fig, ax = plt.subplots(figsize=(16, 12))
ax.set_xlim(0, 100)
ax.set_ylim(0, 100)
ax.axis('off')

def add_box(x, y, w, h, text, color='#667eea', text_color='white', rounded=True):
    if rounded:
        box = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.3", 
                            facecolor=color, edgecolor='white', linewidth=2)
    else:
        box = Rectangle((x, y), w, h, facecolor=color, edgecolor='white', linewidth=2)
    ax.add_patch(box)
    ax.text(x + w/2, y + h/2, text, ha='center', va='center', 
            color=text_color, fontsize=12, fontweight='bold')
    return x + w/2, y + h/2

def add_arrow(x1, y1, x2, y2, color='#667eea', label=''):
    dx = x2 - x1
    dy = y2 - y1
    ax.arrow(x1, y1, dx, dy, head_width=1.5, head_length=1.5, 
             fc=color, ec=color, linewidth=2)
    if label:
        mid_x = (x1 + x2) / 2
        mid_y = (y1 + y2) / 2
        ax.text(mid_x, mid_y + 2, label, ha='center', va='bottom', 
                color='#666', fontsize=10)

def add_text(x, y, text, color='#333', fontsize=12):
    ax.text(x, y, text, ha='center', va='center', color=color, fontsize=fontsize)

# 标题
ax.text(50, 95, '🚀 电梯楼层显示屏ETA预测算法流程', 
        ha='center', va='center', color='#333', fontsize=20, fontweight='bold')

# 第一步：触发事件
cx1, cy1 = add_box(35, 80, 30, 10, '楼层呼叫事件触发', color='#e74c3c')

# 箭头1
add_arrow(cx1, 75, cx1, 68, label='')

# 第二步：收集状态
cx2, cy2 = add_box(20, 58, 60, 12, '收集所有电梯实时状态\n[ID, 当前楼层, 方向, 状态, 目标队列, 乘客数]', color='#3498db')

# 箭头2
add_arrow(cx2, 53, cx2, 46, label='')

# 第三步：计算ETA（循环）
cx3, cy3 = add_box(15, 36, 70, 14, '对每台电梯计算ETA', color='#9b59b6')

# ETA计算步骤
step_x = 20
step_y = 28
add_text(step_x, step_y, '1. 楼层距离: distance = |current - target|', fontsize=10)
add_text(step_x, step_y-3, '2. 基础时间: base_time = distance × 2秒', fontsize=10)
add_text(step_x, step_y-6, '3. 停靠预测: stop_time = n_stop × 7秒', fontsize=10)
add_text(step_x, step_y-9, '4. 开门延迟: door_delay = 3秒(如果开门中)', fontsize=10)
add_text(step_x, step_y-12, '5. ETA = base_time + stop_time + door_delay', fontsize=10)

# 箭头3
add_arrow(cx3, 31, cx3, 18, label='')

# 第四步：选择最优电梯
cx4, cy4 = add_box(30, 8, 40, 12, '选择最优电梯(ETA最小者)', color='#2ecc71')

# 箭头4
add_arrow(cx4, 3, cx4, -3, label='')

# 第五步：更新显示
cx5, cy5 = add_box(15, -12, 70, 12, '更新楼层显示屏内容', color='#f39c12')

# 显示屏示意图
screen_x, screen_y = 50, -25
add_box(25, -35, 50, 15, '', color='#1a1a1a', text_color='white', rounded=False)
add_text(screen_x, screen_y-3, 'E1 [█████●     ] 8层 │ 预计: 12秒', color='#00ff00', fontsize=11)
add_text(screen_x, screen_y-8, 'E2 [███████████] 15层 │ 预计: 25秒', color='#00ff00', fontsize=11)
add_text(screen_x, screen_y-13, '系统状态: ✅ 正常运行', color='#00ff00', fontsize=10)

# 添加算法公式
formula_x, formula_y = 50, 90
add_text(formula_x, formula_y, r'$\text{ETA}(e, f) = |floor_e - f| \times 2 + n_{stop} \times 7 + t_{door}$', 
         color='#667eea', fontsize=14)

plt.tight_layout()
plt.savefig('eta_algorithm_flowchart.png', dpi=300, bbox_inches='tight', transparent=True)
print('流程图已保存: eta_algorithm_flowchart.png')