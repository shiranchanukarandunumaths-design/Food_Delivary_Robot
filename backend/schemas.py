from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, EmailStr

class Waypoint(BaseModel):
    lat: float
    lng: float

# --- USER AUTH SCHEMAS ---
class UserRegister(BaseModel):
    email: str
    password: str
    full_name: str
    student_id: Optional[str] = None
    phone: Optional[str] = None
    department: Optional[str] = None

class UserLogin(BaseModel):
    email: str
    password: str

class UserOut(BaseModel):
    id: int
    email: str
    full_name: str
    student_id: Optional[str] = None
    phone: Optional[str] = None
    department: Optional[str] = None
    role: str
    created_at: datetime
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

# --- EDGE / ROAD SCHEMAS ---
class EdgeBase(BaseModel):
    from_node_id: int
    to_node_id: int
    name: Optional[str] = None
    distance_m: Optional[float] = None
    waypoints: Optional[List[Waypoint]] = None

class EdgeCreate(BaseModel):
    name: Optional[str] = None
    from_node_id: int
    to_node_id: int
    waypoints: List[Waypoint]

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
    user_email: Optional[str] = None
    user_phone: Optional[str] = None
    pickup_node_id: int
    dest_node_id: int
    item_type: str = "Food" # Food, Drinks, Clothes, Notes, Lab Equipment, Other
    is_emergency: bool = False

class OrderOut(BaseModel):
    id: int
    order_code: str
    user_name: str
    user_email: Optional[str] = None
    user_phone: Optional[str] = None
    pickup_node_id: int
    dest_node_id: int
    item_type: str
    is_emergency: bool
    priority: int
    status: str
    situation_msg: Optional[str] = None
    progress_percent: float = 0.0
    qr_unlock_code: Optional[str] = None
    pin_code: Optional[str] = None
    container_locked: bool = True
    waypoints: Optional[List[Waypoint]] = None
    created_at: datetime
    completed_at: Optional[datetime] = None
    class Config:
        from_attributes = True

class QRUnlockRequest(BaseModel):
    order_id: int
    unlock_code: str # QR token or 6-digit PIN

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
    container_locked: bool = True

class TelemetryOut(TelemetryCreate):
    id: int
    recorded_at: datetime
    class Config:
        from_attributes = True
