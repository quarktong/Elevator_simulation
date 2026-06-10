import simpy
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime

plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei']
plt.rcParams['axes.unicode_minus'] = False

print("=" * 60)
print("电梯分组策略 × 调度算法 超快速验证")
print("=" * 60)
print(f"开始: {datetime.now()}")
print("组合: 9种 × 5次 = 45次仿真")
print("预计: 2-3分钟")
print("=" * 60)

# 简化电梯模型
class Elevator:
    def __init__(self, floors, env, store):
        self.pos = 1.0
        self.dir = 'idle'
        self.floors = floors
        self.env = env
        self.store = store
        self.calls = {}
        self.cars = set()
    
    def run(self):
        while True:
            next_stop = self._next()
            if next_stop is None:
                self.dir = 'idle'
                yield self.store.get()
                continue
            self.dir = 'up' if next_stop > self.pos else 'down'
            while abs(self.pos - next_stop) > 0.1:
                self.pos += 0.1 if next_stop > self.pos else -0.1
                yield self.env.timeout(0.01)
            self._handle_stop()
    
    def _next(self):
        all_calls = set(self.cars) | set(self.calls.keys())
        if not all_calls:
            return None
        c = round(self.pos)
        if self.dir == 'up':
            candidates = [f for f in all_calls if f >= c and f in self.floors]
            if candidates: return min(candidates)
            candidates = [f for f in all_calls if f < c and f in self.floors]
            if candidates: return max(candidates)
        elif self.dir == 'down':
            candidates = [f for f in all_calls if f <= c and f in self.floors]
            if candidates: return max(candidates)
            candidates = [f for f in all_calls if f > c and f in self.floors]
            if candidates: return min(candidates)
        else:
            if c in all_calls: return c
            up = min([f for f in all_calls if f >= c], default=None)
            dn = max([f for f in all_calls if f <= c], default=None)
            if up and dn:
                return up if abs(up-c) <= abs(dn-c) else dn
            return up or dn
        return None
    
    def _handle_stop(self):
        f = round(self.pos)
        if f not in self.floors: return
        changed = False
        if f in self.cars:
            self.cars.discard(f)
            changed = True
        if f in self.calls and len(self.calls[f]) < 12:
            p = self.calls[f].pop(0)
            p['wait'] = self.env.now - p['start']
            p['done'] = True
            self.cars.add(p['dest'])
            changed = True
        if changed:
            yield self.env.timeout(0.5)

def create_groups(s):
    if s == 'odd':
        return [{1,3,5,7,9,11,13,15,17}]*2 + [{1,2,4,6,8,10,12,14,16}]*2
    elif s == 'chain':
        return [{1,2,3,4,5,6,7,8,9}, {1,7,8,9,10,11,12,13,14,15}, 
                {1,11,12,13,14,15,16,17}, {1,2,3,4,5,13,14,15,16,17}]
    else:
        all_f = set(range(1, 18))
        return [all_f]*4

def dispatch_simple(elevs, p):
    avail = [e for e in elevs if p['origin'] in e.floors]
    if not avail: return
    e = min(avail, key=lambda x: abs(x.pos - p['origin']))
    if p['origin'] not in e.calls: e.calls[p['origin']] = []
    e.calls[p['origin']].append(p)

def dispatch_scan(elevs, p):
    avail = [e for e in elevs if p['origin'] in e.floors]
    if not avail: return
    idle = [e for e in avail if p['origin'] not in e.calls or len(e.calls[p['origin']]) == 0]
    if idle:
        e = min(idle, key=lambda x: abs(x.pos - p['origin']))
    else:
        same_dir = [e for e in avail if e.dir in ['up', 'down'] and 
                   (e.dir == 'up' and p['origin'] >= round(e.pos) or 
                    e.dir == 'down' and p['origin'] <= round(e.pos))]
        if same_dir:
            e = min(same_dir, key=lambda x: abs(x.pos - p['origin']))
        else:
            e = min(avail, key=lambda x: abs(x.pos - p['origin']))
    if p['origin'] not in e.calls: e.calls[p['origin']] = []
    e.calls[p['origin']].append(p)

def dispatch_smart(elevs, p):
    avail = [e for e in elevs if p['origin'] in e.floors]
    if not avail: return
    scores = {}
    for e in avail:
        dist = abs(e.pos - p['origin'])
        load = len([c for c in e.calls.values() for _ in c]) / 48
        idle = -2 if (p['origin'] not in e.calls or len(e.calls[p['origin']]) == 0) else 0
        scores[e] = dist + load * 5 + idle
    e = min(scores, key=scores.get)
    if p['origin'] not in e.calls: e.calls[p['origin']] = []
    e.calls[p['origin']].append(p)

def run_sim(gs, ds, seed, time=300):
    np.random.seed(seed)
    env = simpy.Environment()
    groups = create_groups(gs)
    stores = [simpy.Store(env) for _ in range(4)]
    elevs = [Elevator(groups[i], env, stores[i]) for i in range(4)]
    for e in elevs: env.process(e.run())
    
    passengers = []
    t = 0
    while t < time:
        t += np.random.exponential(8)
        if t >= time: break
        o = np.random.randint(1, 18)
        d = np.random.randint(1, 18)
        while d == o: d = np.random.randint(1, 18)
        p = {'origin': o, 'dest': d, 'start': t, 'wait': None, 'done': False}
        passengers.append(p)
        if ds == 'simple': dispatch_simple(elevs, p)
        elif ds == 'scan': dispatch_scan(elevs, p)
        else: dispatch_smart(elevs, p)
    
    env.run(until=time)
    completed = [p for p in passengers if p['done']]
    avg_wait = np.mean([p['wait'] for p in completed]) if completed else 0
    throughput = len(completed) / time if completed else 0
    return avg_wait, throughput

# 运行实验
groups = [('odd', '奇偶分组'), ('chain', '长链结构'), ('none', '不分组')]
dispatchs = [('simple', '简单'), ('scan', 'SCAN'), ('smart', '智能')]
results = {}

print("\n开始实验...")
for i, (gi, gl) in enumerate(groups):
    for j, (dj, dl) in enumerate(dispatchs):
        key = f"{gi}_{dj}"
        label = f"{gl}×{dl}"
        print(f"\n[{i*3+j+1}/9] {label}")
        waits, throughputs = [], []
        for k in range(5):
            w, t = run_sim(gi, dj, i*1000+j*100+k*42)
            waits.append(w)
            throughputs.append(t)
            print(f"  {k+1}/5: 等待={w:.1f}s, 吞吐={t:.3f}")
        results[key] = {
            'label': label,
            'avg_wait': np.mean(waits),
            'std_wait': np.std(waits),
            'throughput': np.mean(throughputs),
            'std_throughput': np.std(throughputs)
        }

print("\n" + "=" * 60)
print("结果汇总")
print("=" * 60)

print("\n【系统吞吐量 (人/秒)】")
print("-" * 60)
header = f"{'分组/调度':<12}" + "".join([f"{dl:>12}" for _, dl in dispatchs])
print(header)
print("-" * 60)
for gi, gl in groups:
    row = f"{gl:<12}"
    for dj, dl in dispatchs:
        key = f"{gi}_{dj}"
        row += f"{results[key]['avg_wait']:>12.1f}s"
    print(row)

print("\n【系统吞吐量 (人/秒)】")
print("-" * 60)
print(header)
print("-" * 60)
for gi, gl in groups:
    row = f"{gl:<12}"
    for dj, dl in dispatchs:
        key = f"{gi}_{dj}"
        row += f"{results[key]['throughput']:>12.4f}"
    print(row)

# 最优组合
best = min(results, key=lambda k: results[k]['avg_wait'])
print(f"\n✅ 最优: {results[best]['label']} - 等待{results[best]['avg_wait']:.1f}s")

baseline = results['odd_simple']['avg_wait']
print(f"\n【相对于基准的改进】")
for k, r in sorted(results.items(), key=lambda x: x[1]['avg_wait']):
    imp = (baseline - r['avg_wait']) / baseline * 100
    print(f"  {r['label']:<20} {imp:>+6.1f}%")

# 图表
fig, axes = plt.subplots(2, 2, figsize=(14, 11))

# 热力图等待时间
ax1 = axes[0, 0]
wait_mat = np.array([[results[f"{gi}_{dj}"]['avg_wait'] for dj, _ in dispatchs] 
                      for gi, _ in groups])
im1 = ax1.imshow(wait_mat, cmap='RdYlGn_r', aspect='auto')
ax1.set_xticks(range(3))
ax1.set_xticklabels(['简单', 'SCAN', '智能'], fontsize=12)
ax1.set_yticks(range(3))
ax1.set_yticklabels(['奇偶', '长链', '不分组'], fontsize=12)
for i in range(3):
    for j in range(3):
        ax1.text(j, i, f'{wait_mat[i,j]:.1f}s', ha='center', va='center', 
                fontsize=14, fontweight='bold',
                color='white' if wait_mat[i,j] > 45 else 'black')
ax1.set_title('平均等待时间 (秒)', fontsize=14, fontweight='bold')
plt.colorbar(im1, ax=ax1)

# 热力图吞吐量
ax2 = axes[0, 1]
tp_mat = np.array([[results[f"{gi}_{dj}"]['throughput'] for dj, _ in dispatchs] 
                    for gi, _ in groups])
im2 = ax2.imshow(tp_mat, cmap='RdYlGn', aspect='auto')
ax2.set_xticks(range(3))
ax2.set_xticklabels(['简单', 'SCAN', '智能'], fontsize=12)
ax2.set_yticks(range(3))
ax2.set_yticklabels(['奇偶', '长链', '不分组'], fontsize=12)
for i in range(3):
    for j in range(3):
        ax2.text(j, i, f'{tp_mat[i,j]:.3f}', ha='center', va='center', 
                fontsize=13, fontweight='bold',
                color='white' if tp_mat[i,j] < 0.035 else 'black')
ax2.set_title('系统吞吐量 (人/秒)', fontsize=14, fontweight='bold')
plt.colorbar(im2, ax=ax2)

# 柱状图
ax3 = axes[1, 0]
labels = [results[k]['label'] for k in results]
waits = [results[k]['avg_wait'] for k in results]
colors = plt.cm.viridis(np.linspace(0, 1, len(labels)))
bars = ax3.barh(range(len(labels)), waits, color=colors)
ax3.set_yticks(range(len(labels)))
ax3.set_yticklabels([f"{k.split('_')[0][:2]}_{k.split('_')[1][:2]}" for k in results], fontsize=10)
ax3.set_xlabel('平均等待时间 (秒)', fontsize=12)
ax3.set_title('所有组合等待时间对比', fontsize=14, fontweight='bold')
ax3.invert_yaxis()
for i, (b, w) in enumerate(zip(bars, waits)):
    ax3.text(w + 0.5, b.get_y() + b.get_height()/2, f'{w:.1f}s', va='center', fontsize=10)

# 耦合效应
ax4 = axes[1, 1]
x = np.arange(3)
width = 0.25
coupling = {'简单': [], 'SCAN': [], '智能': []}
for dj, dl in dispatchs:
    for gi, gl in groups:
        coupling[dl].append(results[f"{gi}_{dj}"]['avg_wait'])

for i, (label, values) in enumerate(coupling.items()):
    ax4.bar(x + i*width, values, width, label=label, alpha=0.8)
ax4.set_xticks(x + width)
ax4.set_xticklabels(['奇偶分组', '长链结构', '不分组'], fontsize=11)
ax4.set_ylabel('平均等待时间 (秒)', fontsize=12)
ax4.set_title('耦合效应分析\n(柱间差异=调度效果, 柱内差异=分组效果)', fontsize=13, fontweight='bold')
ax4.legend(fontsize=10)
ax4.grid(axis='y', alpha=0.3)

plt.tight_layout()
ts = datetime.now().strftime('%Y%m%d_%H%M%S')
plt.savefig(f'coupling_ultrafast_{ts}.png', dpi=300, bbox_inches='tight')
plt.close()
print(f"\n✅ 图表: coupling_ultrafast_{ts}.png")

print(f"\n总耗时: {(datetime.now() - datetime.now()).seconds:.0f}分钟")
print("=" * 60)
