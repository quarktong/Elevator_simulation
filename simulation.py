import simpy

from config import SimConfig
from models import ElevatorSnapshot
from elevator import Elevator
from dispatcher import Dispatcher
from passenger_generator import PassengerGenerator
from statistics import Statistics

class ElevatorSimulation:
    def __init__(self, config: SimConfig = None):
        self.config = config or SimConfig.default()
        self.env = simpy.Environment()
        self.statistics = Statistics()

        self.call_stores = [simpy.Store(self.env) for _ in range(self.config.building.n_elevators)]

        self.elevators = []
        self.dispatcher = None
        self.generator = None

    def setup(self):
        self.elevators = []

        for i in range(self.config.building.n_elevators):
            is_odd_group = i < 2
            elevator = Elevator(
                elevator_id=i + 1,
                is_odd_group=is_odd_group,
                config=self.config,
                env=self.env,
                call_store=self.call_stores[i],
                statistics=self.statistics
            )
            self.elevators.append(elevator)
            self.env.process(elevator.run())

        self.dispatcher = Dispatcher(config=self.config, elevators=self.elevators)

        self.generator = PassengerGenerator(
            env=self.env,
            config=self.config,
            dispatcher=self.dispatcher,
            statistics=self.statistics
        )
        self.env.process(self.generator.run())

        self.env.process(self._monitor_process())

    def _monitor_process(self):
        while True:
            yield self.env.timeout(1.0)
            snapshots = [e.get_snapshot() for e in self.elevators]
            self.statistics.record_snapshot(snapshots)

    def run(self) -> Statistics:
        self.setup()
        self.env.run(until=self.config.sim_end)
        return self.statistics
