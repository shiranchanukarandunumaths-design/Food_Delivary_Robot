from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from database import Base

class NodeModel(Base):
    __tablename__ = "nodes"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(50), unique=True, index=True, nullable=False)
    name = Column(String(100), nullable=False)
    lat = Column(Float, nullable=False)
    lng = Column(Float, nullable=False)
    type = Column(String(50), default="destination")

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
    pickup_node_id = Column(Integer, ForeignKey("nodes.id"), nullable=False)
    dest_node_id = Column(Integer, ForeignKey("nodes.id"), nullable=False)
    status = Column(String(50), default="PENDING") # PENDING, EN_ROUTE, DELIVERED, CANCELLED
    waypoints_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    pickup_node = relationship("NodeModel", foreign_keys=[pickup_node_id])
    dest_node = relationship("NodeModel", foreign_keys=[dest_node_id])

class RobotTelemetryModel(Base):
    __tablename__ = "robot_telemetry"

    id = Column(Integer, primary_key=True, index=True)
    robot_id = Column(Integer, default=1, index=True)
    lat = Column(Float, nullable=False)
    lng = Column(Float, nullable=False)
    heading = Column(Float, default=0.0)
    speed_mps = Column(Float, default=0.0)
    battery_v = Column(Float, default=12.0)
    load_g = Column(Integer, default=0)
    state = Column(String(50), default="IDLE")
    recorded_at = Column(DateTime, default=datetime.utcnow)
