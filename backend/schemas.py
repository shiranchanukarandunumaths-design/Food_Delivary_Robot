from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel

class Waypoint(BaseModel):
    lat: float
    lng: float

# --- USER SCHEMAS ---
class UserLogin(BaseModel):
    username: str

class UserCreate(BaseModel):
    username: str
    full_name: str
    role: str = "student"
    phone: Optional[str] = None

class UserOut(UserCreate):
    id: int
    class Config:
        from_attributes = True

# --- NODE SCHEMAS ---
class NodeBase(BaseModel):
    code: str
    name: str
    lat: float
    lng: float
    type: str = "destination"

class NodeCreate(NodeBase):
    pass

class NodeOut(NodeBase):
    id: int
    class Config:
        from_attributes = True

# --- EDGE / ROUTE SCHEMAS ---
class EdgeBase(BaseModel):
    from_node_id: int
    to_node_id: int
    name: Optional[str] = None
    distance_m: float
    waypoints: Optional[List[Waypoint]] = None

class EdgeCreate(EdgeBase):
    pass

class EdgeOut(BaseModel):
    id: int
    from_node_id: int
    to_node_id: int
    name: Optional[str]
    distance_m: float
    waypoints: Optional[List[Waypoint]] = None
    class Config:
        from_attributes = True

# --- ORDER SCHEMAS ---
class OrderCreate(BaseModel):
    user_name: str = "Student"
    user_phone: Optional[str] = None
    pickup_node_id: int
    dest_node_id: int
    item_type: str = "Food" # Food, Drinks, Clothes, Notes, Lab Equipment, Other
    is_emergency: bool = False

class OrderOut(BaseModel):
    id: int
    order_code: str
    user_name: str
    user_phone: Optional[str] = None
    pickup_node_id: int
    dest_node_id: int
    item_type: str
    is_emergency: bool
    priority: int
    status: str
    situation_msg: Optional[str] = None
    progress_percent: float = 0.0
    waypoints: Optional[List[Waypoint]] = None
    created_at: datetime
    completed_at: Optional[datetime] = None
    class Config:
        from_attributes = True

# --- TELEMETRY SCHEMAS ---
class TelemetryCreate(BaseModel):
    robot_id: int = 1
    current_order_id: Optional[int] = None
    lat: float
    lng: float
    heading: float = 0.0
    speed_mps: float = 0.0
    battery_v: float = 12.0
    load_g: int = 0
    state: str = "IDLE"
    situation_msg: Optional[str] = "Standby"

class TelemetryOut(TelemetryCreate):
    id: int
    recorded_at: datetime
    class Config:
        from_attributes = True
