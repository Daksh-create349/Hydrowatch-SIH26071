"""Base abstraction for all data providers and domain services."""

from abc import ABC, abstractmethod
import logging
from typing import Any, Dict, Optional
from backend.app.schemas.common import ConnectionStatus, DataSourceStatus, ServiceHealthStatus


class BaseService(ABC):
    """Abstract base class for system services and data integration adapters."""

    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
        self.logger = logging.getLogger(f"rainfall_backend.services.{name}")
        self._is_connected: bool = False
        self._last_error: Optional[str] = None

    @property
    def is_connected(self) -> bool:
        """Indicate whether the external integration or model pipeline is actively connected."""
        return self._is_connected

    def get_health_status(self) -> ServiceHealthStatus:
        """Return standardized health status."""
        return ServiceHealthStatus(
            service=self.name,
            status="connected" if self._is_connected else "disconnected",
            is_connected=self._is_connected,
            description=self.description,
        )

    def get_data_source_status(self) -> DataSourceStatus:
        """Return detailed data source connection metadata."""
        return DataSourceStatus(
            source_name=self.name,
            is_connected=self._is_connected,
            status=ConnectionStatus.CONNECTED if self._is_connected else ConnectionStatus.DISCONNECTED,
            last_sync=None,
            details={
                "description": self.description,
                "last_error": self._last_error,
            },
        )

    @abstractmethod
    def check_connection(self) -> bool:
        """
        Verify live connection or model asset presence.
        Must NOT return True if integration is incomplete.
        """
        pass
