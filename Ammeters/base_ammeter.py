import socket
import time
import random
import threading
from abc import ABC, abstractmethod

from src.utils.constants import HOST, SOCKET_TIMEOUT_SEC

NotImplementedErrorMsg = "Subclasses must implement this property."

class AmmeterEmulatorBase(ABC):
    def __init__(self, port: int, command: str):
        self.port = port
        self._command = command
        self._stop_event = threading.Event()
        random.seed(time.time())  # Seed the random number generator for each instance

    def stop(self):
        """Signal the server loop to exit."""
        self._stop_event.set()

    def start_server(self):
        """
        Starts the server to listen for client requests.
        Runs until stop() is called.
        """
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind((HOST, self.port))
            s.listen()
            s.settimeout(SOCKET_TIMEOUT_SEC)
            print(f"{self.__class__.__name__} is running on port {self.port}")
            while not self._stop_event.is_set():
                try:
                    conn, addr = s.accept()
                except socket.timeout:
                    continue
                with conn:
                    conn.settimeout(SOCKET_TIMEOUT_SEC)
                    print(f"Connected by {addr}")
                    data = conn.recv(1024)
                    if data == self.get_current_command:
                        # Call the specific measure_current() method defined in subclasses
                        current = self.measure_current()
                        conn.sendall(str(current).encode('utf-8'))
        finally:
            s.close()

    @property
    @abstractmethod
    def get_current_command(self) -> bytes:
        """
        This property must be implemented by each subclass to provide the specific
        command to get the current measurement.
        """
        raise NotImplementedError(NotImplementedErrorMsg)

    @abstractmethod
    def measure_current(self) -> float:
        """
        This method must be implemented by each subclass to provide the specific
        logic for current measurement.
        """
        raise NotImplementedError(NotImplementedErrorMsg)

