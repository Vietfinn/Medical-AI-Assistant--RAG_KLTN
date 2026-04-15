import logging
import time
from abc import ABC, abstractmethod
from typing import Any

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """
    Abstract base class for all agents in the Multi-Agent RAG system.

    Provides unified interface, logging, and latency tracking.
    """

    def __init__(self, name: str):
        """
        Initialize base agent

        Args:
            name: Human-readable name of the agent
        """
        self.name = name
        self.logger = logging.getLogger(f"agent.{name}")

    @abstractmethod
    def execute(self, **kwargs) -> Any:
        """
        Execute the agent's task.

        Must be implemented by subclasses.

        Returns:
            Agent-specific result object
        """
        pass

    def _measure_time(self, func, **kwargs) -> tuple:
        """
        Execute a function and measure its execution time.

        Args:
            func: Callable to execute
            **kwargs: Arguments to pass to the function

        Returns:
            Tuple of (result, latency_seconds)
        """
        start = time.time()
        result = func(**kwargs)
        latency = time.time() - start
        self.logger.info(f"[{self.name}] Completed in {latency:.3f}s")
        return result, latency
