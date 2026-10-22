from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.orm import relationship
from database import Base

class UserModel(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(120), unique=True, index=True, nullable=False)
    password = Column(String(100), nullable=False)
    full_name = Column(String(100), nullable=False)
    student_id = Column(String(50), nullable=True) # e.g. SC/2022/1234
    phone = Column(String(30), nullable=True)
    department = Column(String(100), nullable=True) # e.g. Physics / Chemistry
    role = Column(String(20), default="student") # student, admin, staff
    created_at = Column(DateTime, default=datetime.utcnow)

class NodeModel(Base):
    __tablename__ = "nodes"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(50), unique=True, index=True, nullable=False)
    name = Column(String(100), nullable=False)
    lat = Column(Float, nullable=False)
    lng = Column(Float, nullable=False)
    type = Column(String(50), default="destination") # entry_point, pickup_point, destination, junction

class EdgeModel(Base):
    __tablename__ = "edges"

    id = Column(Integer, primary_key=True, index=True)
    from_node_id = Column(Integer, ForeignKey("nodes.id"), nullable=False)
    to_node_id = Column(Integer, ForeignKey("nodes.id"), nullable=False)
    name = Column(String(100), nullable=True)
    distance_m = Column(Float, nullable=False)
    waypoints_json = Column(Text, nullable=True) # JSON list of {lat, lng}

    from_node = relationship("NodeModel", foreign_keys=[from_node_id])
    to_node = relationship("NodeModel", foreign_keys=[to_node_id])

class OrderModel(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    order_code = Column(String(50), unique=True, index=True, nullable=False)
    user_name = Column(String(100), default="Student")
    user_email = Column(String(120), nullable=True)
    user_phone = Column(String(30), nullable=True)
    pickup_node_id = Column(Integer, ForeignKey("nodes.id"), nullable=False)
    dest_node_id = Column(Integer, ForeignKey("nodes.id"), nullable=False)
    item_type = Column(String(50), default="Food") # Food, Drinks, Clothes, Notes, Lab Equipment, Other
    is_emergency = Column(Boolean, default=False)
    priority = Column(Integer, default=5) # 1 = Emergency (high), 5 = Normal
    status = Column(String(50), default="PENDING") # PENDING, COLLECTING, DISPATCHED, EN_ROUTE, ARRIVED, UNLOCKED, DELIVERED, CANCELLED
    situation_msg = Column(String(255), default="Order submitted. Waiting for robot assignment.")
    progress_percent = Column(Float, default=0.0)
    waypoints_json = Column(Text, nullable=True)
    qr_unlock_code = Column(String(100), nullable=True) # QR Verification token
    pin_code = Column(String(10), nullable=True) # 6-digit backup PIN
    container_locked = Column(Boolean, default=True) # Locks cargo hatch until QR verification
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    pickup_node = relationship("NodeModel", foreign_keys=[pickup_node_id])
    dest_node = relationship("NodeModel", foreign_keys=[dest_node_id])

class RobotTelemetryModel(Base):
    __tablename__ = "robot_telemetry"

    id = Column(Integer, primary_key=True, index=True)
    robot_id = Column(Integer, default=1, index=True)
    current_order_id = Column(Integer, nullable=True)
    lat = Column(Float, nullable=False)
    lng = Column(Float, nullable=False)
    heading = Column(Float, default=0.0)
    speed_mps = Column(Float, default=0.0)
    battery_v = Column(Float, default=12.0)
    load_g = Column(Integer, default=0)
    state = Column(String(50), default="IDLE") # IDLE, COLLECTING, EN_ROUTE, ARRIVED, UNLOCKED, DELIVERED
    situation_msg = Column(String(255), default="Robot standby at Main Gate.")
    container_locked = Column(Boolean, default=True)
    recorded_at = Column(DateTime, default=datetime.utcnow)
