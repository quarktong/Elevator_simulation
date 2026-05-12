
from typing import Dict, List, Optional, Tuple
from enum import Enum
from models import HallCall, Direction, ElevatorState, ElevatorSnapshot
from config import SimConfig
from task_warehouse import TaskWarehouse


class TriggerType(Enum):
    NEW_CALL = "new_call"
    ELEVATOR_STATE_CHANGE = "elevator_state_change"
    PERIODIC = "periodic"


class SmartAssigner:
    """
    智能任务分配器
    
    核心功能：
    - 多因素评分评估
    - 批量任务分配
    - 任务重分配优化
    - 预调度策略
    """
    
    def __init__(self, config: SimConfig, task_warehouse: TaskWarehouse):
        self.config = config
        self.task_warehouse = task_warehouse
        self.weights = {
            'waiting_time': 0.3,
            'distance': 0.25,
            'load_balance': 0.2,
            'direction_consistency': 0.15,
            'prediction_value': 0.1
        }
        self.reassign_count = 0
        self.prediction_hits = 0
        self.periodic_interval = 5.0  # 周期分配触发间隔
        self.last_periodic_time = 0.0
    
    def set_weights(self, period: str):
        """根据时间段动态调整权重"""
        if period == "morning_peak" or period == "noon_peak":
            self.weights = {
                'waiting_time': 0.35,
                'distance': 0.2,
                'load_balance': 0.25,
                'direction_consistency': 0.15,
                'prediction_value': 0.05
            }
        else:
            self.weights = {
                'waiting_time': 0.25,
                'distance': 0.3,
                'load_balance': 0.15,
                'direction_consistency': 0.2,
                'prediction_value': 0.1
            }
    
    def compute_score(self, call: HallCall, elevator_id: int, 
                     elevator_snapshot: ElevatorSnapshot, 
                     current_time: float, period: str) -&gt; float:
        """
        计算呼叫对指定电梯的分配分数
        
        Args:
            call: 厅外呼叫
            elevator_id: 电梯ID
            elevator_snapshot: 电梯快照
            current_time: 当前时间
            period: 当前时段
            
        Returns:
            综合评分
        """
        # 1. 等待时间因子
        wait_time = current_time - call.request_time
        wait_time_factor = min(wait_time / self.config.max_wait_time, 1.0)
        
        # 2. 距离因子
        distance = abs(elevator_snapshot.floor - call.floor)
        distance_factor = 1.0 - (distance / self.config.building.n_floors)
        
        # 3. 负载均衡因子
        load_factor = 1.0 - (elevator_snapshot.passenger_count / self.config.building.elevator_capacity)
        
        # 4. 方向一致性因子
        direction_factor = 0.0
        if elevator_snapshot.state == ElevatorState.IDLE:
            direction_factor = 0.5
        elif (elevator_snapshot.direction == Direction.UP and call.direction == Direction.UP):
            direction_factor = 1.0
        elif (elevator_snapshot.direction == Direction.DOWN and call.direction == Direction.DOWN):
            direction_factor = 1.0
        
        # 5. 预测价值因子
        prediction_factor = self.task_warehouse.get_prediction(
            period, call.floor, call.direction.value
        ) / 10.0  # 归一化
        prediction_factor = min(prediction_factor, 1.0)
        
        # 综合评分
        score = (
            self.weights['waiting_time'] * wait_time_factor +
            self.weights['distance'] * distance_factor +
            self.weights['load_balance'] * load_factor +
            self.weights['direction_consistency'] * direction_factor +
            self.weights['prediction_value'] * prediction_factor
        )
        
        return score
    
    def determine_elevator_group(self, call: HallCall) -&gt; List[int]:
        """确定该呼叫可分配的电梯组"""
        # 根据楼层奇偶性确定电梯组
        if call.floor % 2 == 1 or call.floor == 1:
            return [1, 2]  # 单数层电梯
        else:
            return [3, 4]  # 双数层电梯
    
    def check_collaboration_state(self, elevators: Dict[int, ElevatorSnapshot]) -&gt; Dict[str, List[int]]:
        """
        检查同组电梯的协作状态
        
        Returns:
            状态分组：separated, following, converging
        """
        groups = {
            'odd': [1, 2],
            'even': [3, 4]
        }
        
        state_info = {
            'separated': [],
            'following': [],
            'converging': []
        }
        
        for group_name, elevator_ids in groups.items():
            if len(elevator_ids) &lt; 2:
                continue
            
            e1_id, e2_id = elevator_ids[0], elevator_ids[1]
            if e1_id not in elevators or e2_id not in elevators:
                continue
            
            e1 = elevators[e1_id]
            e2 = elevators[e2_id]
            
            distance = abs(e1.floor - e2.floor)
            same_direction = e1.direction == e2.direction
            
            if distance &gt; 4:
                if not same_direction:
                    state_info['separated'].extend([e1_id, e2_id])
                else:
                    state_info['converging'].extend([e1_id, e2_id])
            else:
                if same_direction:
                    state_info['following'].extend([e1_id, e2_id])
                else:
                    state_info['separated'].extend([e1_id, e2_id])
        
        return state_info
    
    def assign(self, elevators: Dict[int, ElevatorSnapshot], 
              current_time: float, trigger_type: TriggerType,
              period: str = "normal") -&gt; List[Tuple[HallCall, int]]:
        """
        执行任务分配
        
        Args:
            elevators: 电梯快照字典
            current_time: 当前时间
            trigger_type: 触发类型
            period: 当前时段
            
        Returns:
            分配结果列表 (call, elevator_id)
        """
        self.set_weights(period)
        
        assignments = []
        waiting_calls = self.task_warehouse.get_waiting_calls()
        
        # 步骤1：逐个处理待分配呼叫
        for call in waiting_calls:
            candidate_elevators = self.determine_elevator_group(call)
            
            best_elevator = None
            best_score = -1.0
            
            for elevator_id in candidate_elevators:
                if elevator_id not in elevators:
                    continue
                
                score = self.compute_score(
                    call, elevator_id, elevators[elevator_id], 
                    current_time, period
                )
                
                if score &gt; best_score:
                    best_score = score
                    best_elevator = elevator_id
            
            if best_elevator is not None and best_score &gt; 0.1:  # 阈值过滤
                self.task_warehouse.assign_to_elevator(call, best_elevator)
                assignments.append((call, best_elevator))
        
        # 步骤2：仅周期触发时进行批量重分配
        if trigger_type == TriggerType.PERIODIC:
            reassignments = self.periodic_reassign(elevators, current_time)
            assignments.extend(reassignments)
        
        # 步骤3：预调度空闲电梯
        self.predispatch_idle_elevators(elevators, period)
        
        return assignments
    
    def periodic_reassign(self, elevators: Dict[int, ElevatorSnapshot], 
                         current_time: float) -&gt; List[Tuple[HallCall, int]]:
        """
        周期性重分配任务，实现负载均衡
        
        Returns:
            重分配列表
        """
        if current_time - self.last_periodic_time &lt; self.periodic_interval:
            return []
        
        self.last_periodic_time = current_time
        
        reassignments = []
        
        # 检查各组负载均衡
        groups = {
            'odd': [1, 2],
            'even': [3, 4]
        }
        
        for group_name, elevator_ids in groups.items():
            if len(elevator_ids) &lt; 2:
                continue
            
            loads = {}
            for eid in elevator_ids:
                if eid in elevators:
                    loads[eid] = len(self.task_warehouse.get_elevator_tasks(eid))
            
            if len(loads) &gt;= 2:
                max_load_eid = max(loads.items(), key=lambda x: x[1])[0]
                min_load_eid = min(loads.items(), key=lambda x: x[1])[0]
                
                if loads[max_load_eid] - loads[min_load_eid] &gt;= 2:
                    # 重分配一个任务
                    tasks = self.task_warehouse.get_elevator_tasks(max_load_eid)
                    if tasks:
                        task = tasks[-1]
                        self.task_warehouse.reassign_task(task, max_load_eid, min_load_eid)
                        reassignments.append((task, min_load_eid))
                        self.reassign_count += 1
        
        return reassignments
    
    def predispatch_idle_elevators(self, elevators: Dict[int, ElevatorSnapshot], period: str):
        """
        预调度空闲电梯到预测的热点楼层
        
        记录预测命中情况
        """
        for elevator_id, snapshot in elevators.items():
            if (snapshot.state == ElevatorState.IDLE and 
                len(self.task_warehouse.get_elevator_tasks(elevator_id)) == 0):
                
                # 简单预测：1层通常是热点
                pred_hotspot = 1
                
                # 这里可以添加更复杂的预测逻辑
                
                # 实际应用中，我们会将电梯移动到预测楼层
                # 本模块只记录预调度决策
                pass
    
    def get_statistics(self) -&gt; Dict:
        """获取分配器统计信息"""
        return {
            'reassign_count': self.reassign_count,
            'prediction_hits': self.prediction_hits
        }
