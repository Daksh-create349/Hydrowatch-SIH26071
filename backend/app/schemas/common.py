"""Common geospatial and system data contracts."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class Coordinates(BaseModel):
    """Geographic point coordinates."""
    latitude: float = Field(..., ge=-90.0, le=90.0, description="Latitude in decimal degrees")
    longitude: float = Field(..., ge=-180.0, le=180.0, description="Longitude in decimal degrees")


class GeoBoundingBox(BaseModel):
    """Geographic bounding box."""
    min_lat: float = Field(..., ge=-90.0, le=90.0)
    max_lat: float = Field(..., ge=-90.0, le=90.0)
    min_lon: float = Field(..., ge=-180.0, le=180.0)
    max_lon: float = Field(..., ge=-180.0, le=180.0)


class Location(BaseModel):
    """Location identifier and metadata."""
    name: str = Field(..., description="Region or station name, e.g., 'Mumbai'")
    state: Optional[str] = Field(None, description="State / Province")
    country: str = Field(default="India", description="Country name")
    coordinates: Coordinates = Field(..., description="Center coordinates")
    bounding_box: Optional[GeoBoundingBox] = Field(None, description="Spatial extent of region")


class ConnectionStatus(str, Enum):
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    UNAVAILABLE = "unavailable"
    NOT_CONFIGURED = "not_configured"


class DataSourceStatus(BaseModel):
    """Status metadata for an external data source or internal service."""
    source_name: str
    is_connected: bool = False
    status: ConnectionStatus = ConnectionStatus.DISCONNECTED
    last_sync: Optional[datetime] = None
    details: Dict[str, Any] = Field(default_factory=dict)


class ServiceHealthStatus(BaseModel):
    """Structured health response for backend services."""
    service: str
    status: str
    is_connected: bool
    description: str


class ErrorDetail(BaseModel):
    """Standardized error payload."""
    code: str
    message: str
    details: Dict[str, Any] = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    """Standardized API error response body."""
    success: bool = False
    error: ErrorDetail
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
