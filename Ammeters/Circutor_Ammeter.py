from Ammeters.base_ammeter import AmmeterEmulatorBase
from src.utils.Utils import generate_random_float


class CircutorAmmeter(AmmeterEmulatorBase):
    def __init__(self, port: int, command: str):
        super().__init__(port, command)

    @property
    def get_current_command(self) -> bytes:
        # Define the command to get the current from CIRCUTOR
        return self._command.encode('utf-8')

    def measure_current(self) -> float:
        num_samples = 10
        time_step = generate_random_float(0.001, 0.01)  # Time step (0.001s - 0.01s)
        voltages = [generate_random_float(0.1, 1.0) for _ in range(num_samples)]  # Voltage values

        print(f"CIRCUTOR Ammeter - Voltages: {voltages}, Time Step: {time_step}s")
        current = sum(v * time_step for v in voltages)
        print(f"Current: {current}A")
        return current
