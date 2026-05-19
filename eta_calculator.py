from config import SimConfig, TimeConfig
from models import ElevatorSnapshot, Direction

class ETACalculator:
    """
    电梯到达时间预测（ETA）计算器
    
    基于精确复刻电梯运行逻辑的预测算法
    """
    
    def __init__(self, config=None):
        self.config = config or SimConfig.default()
        self.time = self.config.time
    
    def estimate(self, snapshot: ElevatorSnapshot, target_floor: int) -> float:
        """
        估算电梯到达目标楼层的时间
        
        Args:
            snapshot: 电梯快照
            target_floor: 目标楼层
            
        Returns:
            预估时间（秒）
        """
        pos = round(snapshot.position)
        direction = snapshot.direction
        
        car_calls = set(snapshot.car_calls) if snapshot.car_calls else set()
        hall_calls = set(snapshot.hall_calls) if snapshot.hall_calls else set()
        
        all_calls = car_calls | hall_calls
        
        total_time = 0.0
        visited = set()
        
        current_pos = pos
        current_dir = direction
        
        while True:
            next_stop = self._get_next_stop(
                current_pos, current_dir, 
                all_calls - visited, target_floor
            )
            
            if next_stop is None:
                floors = abs(current_pos - target_floor)
                total_time += floors * self.time.t_travel
                return total_time
            
            floors_moved = abs(next_stop - current_pos)
            total_time += floors_moved * self.time.t_travel
            
            current_pos = next_stop
            
            if next_stop == target_floor:
                return total_time
            
            if next_stop in all_calls and next_stop not in visited:
                total_time += self.time.t_open + self.time.t_close
                visited.add(next_stop)
            
            current_dir = self._get_new_direction(
                current_pos, current_dir, 
                all_calls - visited, target_floor
            )
    
    def _get_next_stop(self, current: int, direction: Direction, 
                       calls: set, target: int) -> int:
        """获取下一个停靠楼层（复刻电梯逻辑）"""
        candidates = calls.copy()
        if target is not None:
            candidates.add(target)
        
        if not candidates:
            return None
        
        if direction == Direction.UP:
            ahead = [f for f in candidates if f >= current]
            if ahead:
                return min(ahead)
            below = [f for f in candidates if f < current]
            if below:
                return max(below)
        
        elif direction == Direction.DOWN:
            below = [f for f in candidates if f <= current]
            if below:
                return max(below)
            ahead = [f for f in candidates if f > current]
            if ahead:
                return min(ahead)
        
        if current in candidates:
            return current
        
        closer_up = min([f for f in candidates if f >= current], default=None)
        closer_down = max([f for f in candidates if f <= current], default=None)
        
        if closer_up is None: return closer_down
        if closer_down is None: return closer_up
        
        return closer_up if abs(closer_up - current) < abs(closer_down - current) else closer_down
    
    def _get_new_direction(self, pos: int, old_dir: Direction, 
                           remaining: set, target: int) -> Direction:
        """确定新的运行方向"""
        all_targets = remaining.copy()
        all_targets.add(target)
        
        if not all_targets:
            return Direction.IDLE
        
        if min(all_targets) < pos < max(all_targets):
            return old_dir
        elif pos >= max(all_targets):
            return Direction.DOWN
        elif pos <= min(all_targets):
            return Direction.UP
        
        return Direction.IDLE


def estimate_all_etas(elevator_snapshots: list, target_floor: int) -> dict:
    """
    估算所有电梯到达目标楼层的时间
    
    Returns:
        {elevator_id: eta_seconds}
    """
    calc = ETACalculator()
    results = {}
    
    for snap in elevator_snapshots:
        results[snap.id] = calc.estimate(snap, target_floor)
    
    return results


if __name__ == '__main__':
    print("电梯到达时间预测（ETA）模块")
    print("=" * 40)
    
    calc = ETACalculator()
    
    from models import ElevatorState
    
    print("\n测试案例:")
    print(f"单层运行时间 t_travel = {calc.time.t_travel}s")
    print(f"开门时间 t_open = {calc.time.t_open}s")
    print(f"关门时间 t_close = {calc.time.t_close}s")
    
    print("\nETA计算器模块加载成功！")
