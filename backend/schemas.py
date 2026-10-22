from typing import List, Optional, Any
from datetime import datetime
from pydantic import BaseModel

class Waypoint(BaseModel):
    lat: float
    lng: float

class NodeBase(BaseModel):
    code: str
    name: str
    lat: float
    lng: float
    type: str

class NodeCreate(NodeBase):
    pass

class NodeOut(NodeBase):
    id: int
    class Config:
        from_attributes = True

class EdgeBase(BaseModel):
    from_node_id: int
    to_node_id: int
    name: Optional[str] = None
    distance_m: float
    waypoints: Optional[List[Waypoint]] = None

class EdgeOut(BaseModel):
    id: int
    from_node_id: int
    to_node_id: int
    name: Optional[str]
    distance_m: float
    waypoints: Optional[List[Waypoint]] = None
    class Config:
        from_attributes = True

class OrderCreate(BaseModel):
    user_name: str = "Student"
    pickup_node_id: int
    dest_node_id: int

class OrderOut(BaseModel):
    id: int
    order_code: str
    user_name: str
    pickup_node_id: int
    dest_node_id: int
    status: str
    waypoints: Optional[List[Waypoint]] = None
    created_at: datetime
    completed_at: Optional[datetime] = None
    class Config:
        from_attributes = True

class TelemetryCreate(BaseModel):
    robot_id: int = 1
    lat: float
    lng: float
    heading: float = 0.0
    speed_mps: float = 0.0
    battery_v: float = 12.0
    load_g: int = 0
    state: str = "IDLE"

class TelemetryOut(TelemetryCreate):
    id: int
    recorded_at: datetime
    class Config:
        from_attributes = True
