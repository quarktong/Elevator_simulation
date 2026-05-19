
import simpy

from config import SimConfig
from models import ElevatorSnapshot
from elevator_optimized import ElevatorOptimized
from dispatcher import Dispatcher
from passenger_generator import PassengerGenerator
from statistics_optimized import StatisticsOptimized
from task_warehouse import TaskWarehouse
from smart_assigner import SmartAssigner, TriggerType


class ElevatorSimulationOptimized:
    """
    优化版仿真引擎：整合任务仓库、智能分配器、双电梯协作等特�?    """
    def __init__(self, config: SimConfig = None):
        self.config = config or SimConfig.default()
        self.env = simpy.Environment()
        self.statistics = StatisticsOptimized()
        
        # 优化组件
        self.task_warehouse = TaskWarehouse()
        self.smart_assigner = None

        self.call_stores = [simpy.Store(self.env) for _ in range(self.config.building.n_elevators)]

        self.elevators = []
        self.dispatcher = None
        self.generator = None

    def setup(self):
        self.elevators = []

        # 初始化电梯（优化版）
        for i in range(self.config.building.n_elevators):
            is_odd_group = i &lt; 2
            elevator = ElevatorOptimized(
                elevator_id=i + 1,
                is_odd_group=is_odd_group,
                config=self.config,
                env=self.env,
                call_store=self.call_stores[i],
                statistics=self.statistics,
                task_warehouse=self.task_warehouse
            )
            self.elevators.append(elevator)
            self.env.process(elevator.run())

        # 初始化智能分配器
        self.smart_assigner = SmartAssigner(
            config=self.config,
            task_warehouse=self.task_warehouse
        )

        # 初始化调度器（仍保留原有接口�?        self.dispatcher = DispatcherOptimized(
            config=self.config,
            elevators=self.elevators,
            task_warehouse=self.task_warehouse,
            smart_assigner=self.smart_assigner
        )

        # 乘客生成�?        self.generator = PassengerGeneratorOptimized(
            env=self.env,
            config=self.config,
            dispatcher=self.dispatcher,
            statistics=self.statistics,
            task_warehouse=self.task_warehouse
        )
        self.env.process(self.generator.run())

        # 监控进程
        self.env.process(self._monitor_process())
        
        # 周期分配进程
        self.env.process(self._periodic_assignment_process())

    def _monitor_process(self):
        while True:
            yield self.env.timeout(1.0)
            snapshots = [e.get_snapshot() for e in self.elevators]
            self.statistics.record_snapshot(snapshots)
    
    def _periodic_assignment_process(self):
        """周期性触发任务重新分�?""
        while True:
            yield self.env.timeout(5.0)  # �?秒尝试一次重新分�?            
            # 获取电梯快照
            snapshot_dict = {}
            for e in self.elevators:
                snap = e.get_snapshot()
                snapshot_dict[snap.id] = snap
            
            # 确定当前时段
            current_period = self._get_current_period()
            
            # 触发周期分配
            self.smart_assigner.assign(
                elevators=snapshot_dict,
                current_time=self.env.now,
                trigger_type=TriggerType.PERIODIC,
                period=current_period
            )
    
    def _get_current_period(self):
        """确定当前时段（简单实现）"""
        # 这里可以根据实际需求实现更复杂的时段划�?        return "normal"

    def run(self):
        self.setup()
        self.env.run(until=self.config.sim_end)
        return self.statistics


class DispatcherOptimized(Dispatcher):
    """
    优化版调度器：集成任务仓库和智能分配�?    """
    def __init__(self, config, elevators, task_warehouse, smart_assigner):
        super().__init__(config, elevators)
        self.task_warehouse = task_warehouse
        self.smart_assigner = smart_assigner
    
    def dispatch(self, call):
        """
        优化的调度逻辑
        
        1. 将呼叫加入任务仓�?        2. 使用智能分配器选择电梯
        3. 记录统计信息
        """
        # 获取电梯快照
        snapshot_dict = {}
        for e in self.elevators:
            snap = e.get_snapshot()
            snapshot_dict[snap.id] = snap
        
        # 确定当前时段
        current_period = "normal"
        
        # 将呼叫加入任务仓�?        self.task_warehouse.add_call(call, self.elevators[0].env.now if self.elevators else 0.0)
        
        # 使用智能分配�?        assignments = self.smart_assigner.assign(
            elevators=snapshot_dict,
            current_time=self.elevators[0].env.now if self.elevators else 0.0,
            trigger_type=TriggerType.NEW_CALL,
            period=current_period
        )
        
        # 执行分配
        for assigned_call, elevator_id in assignments:
            for elevator in self.elevators:
                if elevator.elevator_id == elevator_id:
                    elevator.assign_call(assigned_call)
                    return elevator_id
        
        # 回退到原有逻辑
        return super().dispatch(call)


class PassengerGeneratorOptimized(PassengerGenerator):
    """
    优化版乘客生成器：与任务仓库集成
    """
    def __init__(self, env, config, dispatcher, statistics, task_warehouse):
        super().__init__(env, config, dispatcher, statistics)
        self.task_warehouse = task_warehouse
