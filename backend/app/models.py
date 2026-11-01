"""
Pydantic Request & Response Data Models
"""
from typing import List, Optional, Union
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field

# Port Schemas
class PortSchema(BaseModel):
    port_id: int
    station_id: Union[int, str]
    port_number: int
    connector_type: str
    power_kw: float
    status: str
    updated_at: Optional[datetime] = None

# Station Schemas
class StationSummary(BaseModel):
    station_id: Union[int, str]
    station_name: str
    operator_name: str
    address: Optional[str] = None
    city: str
    state: str
    postal_code: Optional[str] = None
    latitude: float
    longitude: float
    total_ports: int = 0
    available_ports: int = 0
    distance_km: Optional[float] = None
    connector_types: List[str] = []
    power_outputs: List[float] = []
    max_power_kw: Optional[float] = None
    is_inside_mmr: Optional[bool] = None
    has_live_status: bool = False

class StationDetail(StationSummary):
    ports: List[PortSchema] = []

# Session Schemas
class StartSessionRequest(BaseModel):
    port_id: int = Field(..., description="Target port ID to book")
    user_identifier: str = Field(..., min_length=2, max_length=60, description="Driver / Vehicle Identifier")

class EndSessionRequest(BaseModel):
    session_id: str = Field(..., description="UUID of the active session to terminate")
    energy_kwh: Optional[float] = Field(None, ge=0.0, description="Metered energy consumed in kWh")

class SessionSchema(BaseModel):
    session_id: UUID
    port_id: int
    user_identifier: str
    start_time: datetime
    end_time: Optional[datetime] = None
    energy_kwh: float
    session_status: str

# Status History Schema
class StatusHistorySchema(BaseModel):
    history_id: int
    port_id: int
    old_status: Optional[str] = None
    new_status: str
    changed_at: datetime
    reason: Optional[str] = None

# Overview Dashboard Stats
class OverviewStats(BaseModel):
    total_stations: int
    maharashtra_stations: int
    mumbai_metro_stations: int
    total_national_stations: Optional[int] = None
    total_ports: int
    available_ports: int
    in_use_ports: int
    out_of_service_ports: int
    active_sessions: int
    total_energy_delivered_kwh: float

