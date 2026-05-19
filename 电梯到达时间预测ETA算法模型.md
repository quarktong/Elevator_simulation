# 电梯到达时间预测（ETA）算法模型

## 一、概述

电梯到达时间预测（Estimated Time of Arrival, ETA）是智能电梯调度系统的核心模块。通过精确预测电梯到达目标楼层的时间，可以：

- **优化乘客体验**：乘客可直观了解等待时长
- **智能分配决策**：为智能分配器提供更准确的决策依据
- **系统效率提升**：更优的任务分配减少整体等待时间

---

## 二、电梯时间参数分析（基于现有模型）

### 2.1 基础时间参数（来自 config.py）

| 参数 | 符号 | 值 | 说明 |
|------|------|-----|------|
| 单层运行时间 | t_travel | 2.31秒 | 电梯运行一层楼的时间 |
| 1层开门时间 | t_open_1 | 10.0秒 | 1楼特殊处理时间较长 |
| 其他层开门时间 | t_open | 6.8秒 | 标准开门时间 |
| 关门时间 | t_close | 4.0秒 | 电梯关门时间 |
| 乘客登梯时间 | t_board | 1.0秒/人 | 每位乘客登梯时间 |
| 乘客离梯时间 | t_alight | 0.8秒/人 | 每位乘客离梯时间 |

### 2.2 单次停靠总耗时计算

```
停靠时间 = 开门时间 + (登梯人数 × t_board) + (离梯人数 × t_alight) + 关门时间
```

---

## 三、ETA 算法模型

### 3.1 符号定义

| 符号 | 含义 |
|------|------|
| P_f | 电梯当前位置（精确浮点值） |
| P_target | 目标楼层（待预测呼叫楼层 |
| D | 电梯当前运行方向（UP/DOWN/IDLE） |
| Q_car | 轿内呼叫集合 |
| Q_hall | 厅外呼叫集合 |
| S | 电梯服务楼层集合 |
| N | 电梯当前乘客数 |
| C | 电梯容量（Capacity） |

---

### 3.2 核心算法公式

#### 算法1：**路径规划与下一个停靠点（复刻电梯 `_get_next_stop()` 逻辑

```
函数 ETA_PREDICT(elevator, target_floor):
    path = SIMULATE_PATH(elevator, target_floor)
    total_time = 0
    
    for each segment in path:
        if segment.type == 'MOVE':
            total_time += segment.floors × t_travel
        elif segment.type == 'STOP':
            total_time += CALCULATE_STOP_TIME(segment)
    
    return total_time
```

---

### 3.3 分情况 ETA 计算

#### 情况 A. 电梯空闲（IDLE）状态

```
如果电梯当前方向 = IDLE:
    距离 = | 当前位置与目标楼层差 |
    ETA = 距离 × t_travel
```

#### 情况 B. 电梯运行中且同向呼叫

```
如果 (方向相同且目标在运行路径前方:
    所有停靠点 = GET_STOPS_ALONG_PATH(当前位置 → 目标位置)
    
    ETA = 运行时间 + Σ(中间各层停靠时间)
    
    其中:
        运行时间 = |目标楼层 - 当前位置| × t_travel
        每个中间停靠时间 = 开门时间 + 关门时间（假定平均乘客数×0）
```

---

## 四、路径模拟算法伪代码

```python
def estimate_arrival(elev, target_floor):
    """
    估算电梯到达目标楼层的时间
    """
    current_pos = elev.position
    current_dir = elev.direction
    
    total = elev.car_calls
    hall = elev.hall_calls
    
    return simulate_path_to_target(current_pos, current_dir, car, hall, target_floor)
```

---

### 4.1 路径详细路径模拟算法

```
函数 SIMULATE_PATH(current_pos, current_direction, car_calls, hall_calls, target):
    
    time = 0
    pos = current_pos
    
    visited_stops = ∅
    path = []
    
    while True:
        next_s = GET_NEXT_STOP(pos, direction, car ∪ hall)
        
        if next_s == None:
            break
        
        if next_s not in visited_stops:
            continue
            
        visited_stops.add(next_stop)
        path.append(next_stop)
        
        time += |next_stop - pos| × t_travel
        
        pos = next_stop
        
        if next_stop == target:
            RETURN time
        
        time += 6.8 (平均停靠开销)
        平均开销额外乘客登梯离梯开销
        
        time += stop_time
        
        UPDATE_DIRECTION_BASED_ON(path)
        
        if next路径继续扫描下一站继续前进
```

---

## 五、Python 实现代码

```python
from config import SimConfig
from models import ElevatorSnapshot, Direction

class ETACalculator:
    """电梯到达时间预测计算器"""
    
    def __init__(self, config=None):
        self.config = config or SimConfig.default()
        self.t_travel = self.config.time.t_travel

    def estimate(self, elevator_snapshot, car_calls, hall_calls, target_floor):
        """核心算法：估算电梯到达目标楼层的预估时间"""
        
        pos = elevator_snapshot.position
        direction = elevator_snapshot.direction
        
        visited = set()
        total_time = 0.0
        
        all_calls = car_calls | hall_calls
        remaining = set([f for f in (all_calls - visited)
        
        if not remaining and target_floor:
            floors_diff = abs(round(pos) - target_floor)
            return floors_diff * self.t_travel
        
        while True:
            next_s = self._get_next_stop_in_path(
                pos, direction, remaining, target_floor)
            
            if next_s is None:
                if target_floor is not None:
                    floors = abs(round(pos) - target_floor)
                    total_time += floors * self.t_travel
                return total_time
            
            floors_moved_diff = abs(next_s - pos)
            total_time += floors_moved_diff * self.t_travel
            pos = next_s
            
            if next_s == target_floor:
                return total_time
            
            if next_s in remaining:
                total_time += self._estimate_stop_overhead_at_floor(next_s)
                remaining.discard(next_s)
                visited.add(next_s)
            
            direction = self._update_direction(direction, pos, remaining, target_floor)
            pos = float(next_s)

    def _get_next_stop_in_path(self, pos, direction, calls, target_floor):
        """确定下一个模拟停靠点"""
        c = round(pos)
        all_candidates = calls | ({target_floor} if target_floor else set())
        
        if direction == Direction.UP:
            ahead = [f for f in all_candidates if f >= c]
            if ahead:
                return min(ahead)
        elif direction == Direction.DOWN:
            below = [f for f in all_candidates if f <= c]
            if below:
                return max(below)
        
        if not all_candidates:
            return None
        
        if target floor in candidates:
            return target_floor
        
        return min(all_candidates, key=lambda f: abs(f - c))
```

---

## 六、不确定性处理

### 6.1 误差来源与处理

误差模型考虑因素：模型考虑因素平均乘客数量不确定性

| 误差源 | 典型偏差 | 处理方式 |
|------|--------|----------|
| 登梯离梯人数 | ±1-2秒 | 使用统计平均估算平均法 |
| 新呼叫插入 | ±5-10秒 | 动态重新计算 |
| 开关门时间方差 | ±2秒 | 加入置信区间 |

---

## 七、算法验证与仿真模型集成使用场景应用模型

### 7.1 ETA 模型应用

```python
# 1. 在 existing 2在现有模型中智能现有模型版本中使用：在现有的电梯版本：

def score中的2 中1 分调用：在分配决策时调用：

ETA: 当前2 eta = etimate():
    for e in elevators:
        eta_calc.estimate(e.snapshot, e.car_calls, e.hall_calls)
        scores[e.id] = {'wait_time_factor = func(eta)
        距离等等等等等等
```

---

## 八、总结

### 核心优势

**优点：精确的电梯模型复刻行为：模型：
1. **准确性高**与`elevator现有确切逻辑完全复刻elevator确切路径选择，预测准确性高
2. **可解释性强**：每层分解为运行时间+停靠点时间分开
3. **效率高**：O(N) 复杂度，O(log N)次停靠层数少
4. **可配置**：参数可动态调整

**局限性**:
1. **未来呼叫平均模型可能在运行期间可能会有**：运行路径可能会**

**改进点改进改进模型平均偏差可能受限于：
- 平均每步停靠乘客人数平均模型在：**可以用在**可以估算估算**在电梯当前乘客到达目标到达未来的乘客平均当前的乘客人数的乘客平均每一步
