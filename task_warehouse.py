
from collections import deque
from typing import Dict, List, Optional, Tuple
from models import HallCall, Passenger


class TaskWarehouse:
    """
    任务仓库：管理所有待分配和已分配的任务
    
    核心数据结构：
    - wait_queue: 优先队列，待分配的厅外呼叫
    - assigned_tasks: 按电梯ID索引的已分配任务
    - completed_history: 循环缓冲区，存储已完成任务的历史
    - historical_data: 历史流量数据，用于预测
    """
    
    def __init__(self):
        self.wait_queue: List[Tuple[float, HallCall]] = []  # (priority, call)
        self.assigned_tasks: Dict[int, List[HallCall]] = {}
        self.completed_history: deque = deque(maxlen=1000)
        self.historical_data: Dict[str, Dict] = {}  # 用于预测
    
    def add_call(self, call: HallCall, current_time: float, priority: float = 1.0):
        """
        添加新呼叫到待分配队列
        
        Args:
            call: 厅外呼叫
            current_time: 当前时间
            priority: 优先级权重
        """
        self.wait_queue.append((priority, call))
        self.wait_queue.sort(key=lambda x: x[0], reverse=True)
    
    def get_waiting_calls(self) -&gt; List[HallCall]:
        """获取待分配的呼叫列表"""
        return [call for (pri, call) in self.wait_queue]
    
    def assign_to_elevator(self, call: HallCall, elevator_id: int):
        """
        将呼叫分配给电梯
        
        Args:
            call: 厅外呼叫
            elevator_id: 电梯ID
        """
        self.wait_queue = [(pri, c) for (pri, c) in self.wait_queue if c != call]
        if elevator_id not in self.assigned_tasks:
            self.assigned_tasks[elevator_id] = []
        self.assigned_tasks[elevator_id].append(call)
    
    def unassign_from_elevator(self, call: HallCall, elevator_id: int):
        """从电梯任务中移除"""
        if elevator_id in self.assigned_tasks:
            self.assigned_tasks[elevator_id] = [c for c in self.assigned_tasks[elevator_id] if c != call]
    
    def complete_task(self, call: HallCall, elevator_id: int, completion_time: float):
        """
        标记任务完成
        
        Args:
            call: 厅外呼叫
            elevator_id: 电梯ID
            completion_time: 完成时间
        """
        self.unassign_from_elevator(call, elevator_id)
        self.completed_history.append({
            'call': call,
            'elevator_id': elevator_id,
            'completion_time': completion_time
        })
    
    def get_elevator_tasks(self, elevator_id: int) -&gt; List[HallCall]:
        """获取指定电梯的已分配任务"""
        return self.assigned_tasks.get(elevator_id, [])
    
    def reassign_task(self, call: HallCall, from_elevator_id: int, to_elevator_id: int):
        """在电梯间重新分配任务"""
        self.unassign_from_elevator(call, from_elevator_id)
        self.assign_to_elevator(call, to_elevator_id)
    
    def record_historical_data(self, period: str, floor: int, direction: str, count: int):
        """记录历史流量数据用于预测"""
        key = f"{period}_{floor}_{direction}"
        if key not in self.historical_data:
            self.historical_data[key] = {'total': 0, 'count': 0}
        self.historical_data[key]['total'] += count
        self.historical_data[key]['count'] += 1
    
    def get_prediction(self, period: str, floor: int, direction: str) -&gt; float:
        """
        基于历史数据预测流量
        
        Returns:
            预测的流量值
        """
        key = f"{period}_{floor}_{direction}"
        if key in self.historical_data:
            data = self.historical_data[key]
            return data['total'] / data['count'] if data['count'] &gt; 0 else 0.0
        return 0.0
