import matplotlib.pyplot as plt
import numpy as np
from datetime import datetime

plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial Unicode MS']
plt.rcParams['axes.unicode_minus'] = False

timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

fig = plt.figure(figsize=(16, 12))

# 数据
strategies = ['奇偶分组', '长链结构', '不分组']
wait_times = [54.0, 44.4, 41.1]
wait_std = [29.7, 40.3, 32.8]
throughput = [0.0208, 0.0123, 0.0183]
throughput_std = [0.0098, 0.0069, 0.0100]

# 理论预测数据
theory_wait = [54.0, 32.0, 36.0]  # 理论预测的等待时间
theory_throughput = [0.021, 0.038, 0.028]  # 理论预测的吞吐量

# 子图1: 等待时间对比
ax1 = fig.add_subplot(2, 2, 1)
x = np.arange(len(strategies))
width = 0.35
bars1 = ax1.bar(x - width/2, wait_times, width, label='实际仿真', color='#3498db', alpha=0.8)
bars2 = ax1.bar(x + width/2, theory_wait, width, label='理论预测', color='#e74c3c', alpha=0.8)
ax1.set_ylabel('平均等待时间 (秒)', fontsize=12)
ax1.set_title('等待时间对比', fontsize=14, fontweight='bold')
ax1.set_xticks(x)
ax1.set_xticklabels(strategies)
ax1.legend()
ax1.grid(axis='y', alpha=0.3)
for bar in bars1:
    height = bar.get_height()
    ax1.annotate(f'{height:.1f}',
                xy=(bar.get_x() + bar.get_width() / 2, height),
                xytext=(0, 3), textcoords="offset points",
                ha='center', va='bottom', fontsize=10)

# 子图2: 吞吐量对比
ax2 = fig.add_subplot(2, 2, 2)
bars3 = ax2.bar(x - width/2, throughput, width, label='实际仿真', color='#2ecc71', alpha=0.8)
bars4 = ax2.bar(x + width/2, theory_throughput, width, label='理论预测', color='#e74c3c', alpha=0.8)
ax2.set_ylabel('系统吞吐量 (人/秒)', fontsize=12)
ax2.set_title('吞吐量对比', fontsize=14, fontweight='bold')
ax2.set_xticks(x)
ax2.set_xticklabels(strategies)
ax2.legend()
ax2.grid(axis='y', alpha=0.3)
for bar in bars3:
    height = bar.get_height()
    ax2.annotate(f'{height:.4f}',
                xy=(bar.get_x() + bar.get_width() / 2, height),
                xytext=(0, 3), textcoords="offset points",
                ha='center', va='bottom', fontsize=10)

# 子图3: 改进幅度
ax3 = fig.add_subplot(2, 2, 3)
improvements_wait = [(54.0 - wt) / 54.0 * 100 for wt in wait_times]
improvements_wait_theory = [(54.0 - wt) / 54.0 * 100 for wt in theory_wait]
bars5 = ax3.bar(x - width/2, improvements_wait, width, label='实际仿真', color='#9b59b6', alpha=0.8)
bars6 = ax3.bar(x + width/2, improvements_wait_theory, width, label='理论预测', color='#e74c3c', alpha=0.8)
ax3.set_ylabel('等待时间改进 (%)', fontsize=12)
ax3.set_title('等待时间改进幅度', fontsize=14, fontweight='bold')
ax3.set_xticks(x)
ax3.set_xticklabels(strategies)
ax3.legend()
ax3.grid(axis='y', alpha=0.3)
ax3.axhline(y=0, color='black', linestyle='-', linewidth=0.5)
for bar in bars5:
    height = bar.get_height()
    ax3.annotate(f'{height:.1f}%',
                xy=(bar.get_x() + bar.get_width() / 2, height),
                xytext=(0, 3), textcoords="offset points",
                ha='center', va='bottom', fontsize=10)

# 子图4: 柔性度对比
ax4 = fig.add_subplot(2, 2, 4)
flexibility = [2.12, 3.06, 4.0]
colors = ['#3498db', '#2ecc71', '#e74c3c']
bars7 = ax4.bar(strategies, flexibility, color=colors, alpha=0.8)
ax4.set_ylabel('平均柔性度', fontsize=12)
ax4.set_title('柔性度对比', fontsize=14, fontweight='bold')
ax4.grid(axis='y', alpha=0.3)
for bar in bars7:
    height = bar.get_height()
    ax4.annotate(f'{height:.2f}',
                xy=(bar.get_x() + bar.get_width() / 2, height),
                xytext=(0, 3), textcoords="offset points",
                ha='center', va='bottom', fontsize=10, fontweight='bold')

plt.suptitle('电梯分组策略完整分析报告', fontsize=16, fontweight='bold', y=0.98)
plt.tight_layout(rect=[0, 0, 1, 0.96])

filename = f'电梯分组策略完整分析_{timestamp}.png'
plt.savefig(filename, dpi=300, bbox_inches='tight')
print(f'图表已保存: {filename}')

plt.close()
