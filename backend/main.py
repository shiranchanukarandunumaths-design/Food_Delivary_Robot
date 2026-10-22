import json
import uuid
import random
import asyncio
from typing import List, Optional, Set
from datetime import datetime
from fastapi import FastAPI, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import desc, asc

from database import engine, get_db, Base
from models import NodeModel, EdgeModel, OrderModel, RobotTelemetryModel, UserModel
from schemas import (
    NodeCreate, NodeOut, EdgeCreate, EdgeOut, 
    OrderCreate, OrderOut, TelemetryCreate, TelemetryOut, 
    Waypoint, UserLogin, UserRegister, UserOut, QRUnlockRequest
)
from path_planner import find_shortest_path, compute_polyline_distance

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Campus Autonomous Food & Parcel Delivery Rover API",
    description="Backend for University of Colombo Campus Autonomous Rover (PH 3042)",
    version="1.2.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- WEBSOCKET CONNECTION MANAGER FOR REAL-TIME STREAMING ---
class ConnectionManager:
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)

    async def broadcast(self, message: dict):
        dead_connections = set()
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                dead_connections.add(connection)
        for dead in dead_connections:
            self.active_connections.discard(dead)

ws_manager = ConnectionManager()

@app.get("/")
def root():
    return {
        "project": "Campus Food & Parcel Delivery Robot - UOC PH 3042",
        "status": "online",
        "docs_url": "/docs",
        "ws_url": "/ws/telemetry"
    }

# ==========================================
# 1. USER AUTHENTICATION & ACCOUNTS
# ==========================================

@app.post("/api/auth/register", response_model=UserOut)
def register_user(payload: UserRegister, db: Session = Depends(get_db)):
    email = payload.email.strip().lower()
    existing = db.query(UserModel).filter(UserModel.email == email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Account with this email already exists")

    new_user = UserModel(
        email=email,
        password=payload.password, # For local demo
        full_name=payload.full_name,
        student_id=payload.student_id,
        phone=payload.phone,
        department=payload.department,
        role="student"
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

@app.post("/api/auth/login", response_model=UserOut)
def login_user(payload: UserLogin, db: Session = Depends(get_db)):
    email = payload.email.strip().lower()
    user = db.query(UserModel).filter(UserModel.email == email).first()
    if not user or user.password != payload.password:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    return user

@app.get("/api/auth/profile", response_model=UserOut)
def get_user_profile(email: str = Query(...), db: Session = Depends(get_db)):
    user = db.query(UserModel).filter(UserModel.email == email.strip().lower()).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

# ==========================================
# 2. CAMPUS NODES / LANDMARKS (ADMIN & USERS)
# ==========================================

@app.get("/api/nodes", response_model=List[NodeOut])
def get_all_nodes(db: Session = Depends(get_db)):
    return db.query(NodeModel).order_by(NodeModel.id).all()

@app.post("/api/nodes", response_model=NodeOut)
def create_node(node: NodeCreate, db: Session = Depends(get_db)):
    existing = db.query(NodeModel).filter(NodeModel.code == node.code).first()
    if existing:
        node.code = f"{node.code}_{uuid.uuid4().hex[:4].upper()}"

    new_node = NodeModel(
        code=node.code,
        name=node.name,
        lat=node.lat,
        lng=node.lng,
        type=node.type
    )
    db.add(new_node)
    db.commit()
    db.refresh(new_node)
    return new_node

@app.delete("/api/nodes/{node_id}")
def delete_node(node_id: int, db: Session = Depends(get_db)):
    node = db.query(NodeModel).filter(NodeModel.id == node_id).first()
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    # Delete connected edges
    db.query(EdgeModel).filter((EdgeModel.from_node_id == node_id) | (EdgeModel.to_node_id == node_id)).delete()
    db.delete(node)
    db.commit()
    return {"status": "success", "deleted_node_id": node_id}

# ==========================================
# 3. ADMIN ROAD & PATH TRAINING
# ==========================================

@app.get("/api/edges", response_model=List[EdgeOut])
def get_all_edges(db: Session = Depends(get_db)):
    edges = db.query(EdgeModel).all()
    results = []
    for e in edges:
        pts = [Waypoint(**p) for p in json.loads(e.waypoints_json)] if e.waypoints_json else []
        results.append(EdgeOut(
            id=e.id,
            from_node_id=e.from_node_id,
            to_node_id=e.to_node_id,
            name=e.name,
            distance_m=e.distance_m,
            waypoints=pts
        ))
    return results

@app.post("/api/admin/roads", response_model=EdgeOut)
async def train_and_save_road(road: EdgeCreate, db: Session = Depends(get_db)):
    from_node = db.query(NodeModel).filter(NodeModel.id == road.from_node_id).first()
    to_node = db.query(NodeModel).filter(NodeModel.id == road.to_node_id).first()
    if not from_node or not to_node:
        raise HTTPException(status_code=400, detail="Start or End node does not exist")

    pts_dicts = [w.dict() for w in road.waypoints]
    # Ensure start and end node coordinates are included
    if not pts_dicts or (pts_dicts[0]["lat"] != from_node.lat or pts_dicts[0]["lng"] != from_node.lng):
        pts_dicts.insert(0, {"lat": from_node.lat, "lng": from_node.lng})
    if pts_dicts[-1]["lat"] != to_node.lat or pts_dicts[-1]["lng"] != to_node.lng:
        pts_dicts.append({"lat": to_node.lat, "lng": to_node.lng})

    # Compute real road distance along waypoints
    real_dist = compute_polyline_distance(pts_dicts)
    road_name = road.name or f"{from_node.name} to {to_node.name}"

    new_edge = EdgeModel(
        from_node_id=road.from_node_id,
        to_node_id=road.to_node_id,
        name=road_name,
        distance_m=round(real_dist, 2),
        waypoints_json=json.dumps(pts_dicts)
    )
    db.add(new_edge)
    db.commit()
    db.refresh(new_edge)

    # Broadcast updated map network to all connected clients
    await ws_manager.broadcast({
        "type": "road_network_updated",
        "new_road_id": new_edge.id,
        "name": road_name,
        "distance_m": new_edge.distance_m
    })

    return EdgeOut(
        id=new_edge.id,
        from_node_id=new_edge.from_node_id,
        to_node_id=new_edge.to_node_id,
        name=new_edge.name,
        distance_m=new_edge.distance_m,
        waypoints=[Waypoint(**p) for p in pts_dicts]
    )

@app.delete("/api/admin/roads/{road_id}")
def delete_road(road_id: int, db: Session = Depends(get_db)):
    edge = db.query(EdgeModel).filter(EdgeModel.id == road_id).first()
    if not edge:
        raise HTTPException(status_code=404, detail="Road segment not found")
    db.delete(edge)
    db.commit()
    return {"status": "success", "deleted_road_id": road_id}

@app.post("/api/admin/clear-all-roads")
def clear_all_roads(db: Session = Depends(get_db)):
    db.query(EdgeModel).delete()
    db.commit()
    return {"status": "success", "message": "All road segments cleared. Ready for fresh route training."}

# ==========================================
# 4. ORDER CREATION, ROUTE PLANNING & QR UNLOCK
# ==========================================

@app.post("/api/orders", response_model=OrderOut)
async def create_delivery_order(order: OrderCreate, db: Session = Depends(get_db)):
    pickup = db.query(NodeModel).filter(NodeModel.id == order.pickup_node_id).first()
    dest = db.query(NodeModel).filter(NodeModel.id == order.dest_node_id).first()

    if not pickup or not dest:
        raise HTTPException(status_code=400, detail="Invalid pickup or destination place")

    # Priority level
    priority_level = 1 if order.is_emergency else 5

    # Compute path using trained roads in database
    node_ids, waypoints, total_dist = find_shortest_path(db, order.pickup_node_id, order.dest_node_id)
    if not waypoints:
        # Fallback straight-line if no connected trained roads exist yet between these nodes
        waypoints = [Waypoint(lat=pickup.lat, lng=pickup.lng), Waypoint(lat=dest.lat, lng=dest.lng)]
        total_dist = compute_polyline_distance([w.dict() for w in waypoints])

    pts_json = json.dumps([w.dict() for w in waypoints])

    order_suffix = uuid.uuid4().hex[:6].upper()
    order_code = f"ORD-{'EMG-' if order.is_emergency else ''}{order_suffix}"
    
    # Generate unique QR unlock code and 6-digit PIN
    qr_unlock = f"UOC-ROVER-UNLOCK-{order_suffix}-{uuid.uuid4().hex[:4].upper()}"
    pin_code = str(random.randint(100000, 999999))

    situation = f"Order created for {order.item_type}. {'🚨 EMERGENCY RUSH' if order.is_emergency else 'Standard'}. Waiting for pickup at {pickup.name}."

    new_order = OrderModel(
        order_code=order_code,
        user_name=order.user_name,
        user_email=order.user_email,
        user_phone=order.user_phone,
        pickup_node_id=order.pickup_node_id,
        dest_node_id=order.dest_node_id,
        item_type=order.item_type,
        is_emergency=order.is_emergency,
        priority=priority_level,
        status="PENDING",
        situation_msg=situation,
        progress_percent=0.0,
        waypoints_json=pts_json,
        qr_unlock_code=qr_unlock,
        pin_code=pin_code,
        container_locked=True,
        created_at=datetime.utcnow()
    )
    db.add(new_order)
    db.commit()
    db.refresh(new_order)

    # Broadcast new order to WebSocket
    await ws_manager.broadcast({
        "type": "new_order",
        "order_id": new_order.id,
        "order_code": new_order.order_code,
        "is_emergency": new_order.is_emergency,
        "item_type": new_order.item_type,
        "qr_unlock_code": new_order.qr_unlock_code,
        "pin_code": new_order.pin_code,
        "situation_msg": new_order.situation_msg
    })

    return OrderOut(
        id=new_order.id,
        order_code=new_order.order_code,
        user_name=new_order.user_name,
        user_email=new_order.user_email,
        user_phone=new_order.user_phone,
        pickup_node_id=new_order.pickup_node_id,
        dest_node_id=new_order.dest_node_id,
        item_type=new_order.item_type,
        is_emergency=new_order.is_emergency,
        priority=new_order.priority,
        status=new_order.status,
        situation_msg=new_order.situation_msg,
        progress_percent=new_order.progress_percent,
        qr_unlock_code=new_order.qr_unlock_code,
        pin_code=new_order.pin_code,
        container_locked=new_order.container_locked,
        waypoints=waypoints,
        created_at=new_order.created_at,
        completed_at=new_order.completed_at
    )

@app.get("/api/orders", response_model=List[OrderOut])
def list_orders(limit: int = 50, db: Session = Depends(get_db)):
    orders = db.query(OrderModel)\
               .order_by(asc(OrderModel.priority), asc(OrderModel.created_at))\
               .limit(limit)\
               .all()
    results = []
    for o in orders:
        pts = [Waypoint(**p) for p in json.loads(o.waypoints_json)] if o.waypoints_json else []
        results.append(OrderOut(
            id=o.id,
            order_code=o.order_code,
            user_name=o.user_name,
            user_email=o.user_email,
            user_phone=o.user_phone,
            pickup_node_id=o.pickup_node_id,
            dest_node_id=o.dest_node_id,
            item_type=o.item_type,
            is_emergency=o.is_emergency,
            priority=o.priority,
            status=o.status,
            situation_msg=o.situation_msg,
            progress_percent=o.progress_percent,
            qr_unlock_code=o.qr_unlock_code,
            pin_code=o.pin_code,
            container_locked=o.container_locked,
            waypoints=pts,
            created_at=o.created_at,
            completed_at=o.completed_at
        ))
    return results

@app.get("/api/orders/active", response_model=Optional[OrderOut])
def get_active_or_next_order(db: Session = Depends(get_db)):
    active = db.query(OrderModel)\
               .filter(OrderModel.status.in_(["COLLECTING", "DISPATCHED", "EN_ROUTE", "ARRIVED", "UNLOCKED"]))\
               .order_by(asc(OrderModel.priority), asc(OrderModel.created_at))\
               .first()
    if not active:
        active = db.query(OrderModel)\
                   .filter(OrderModel.status == "PENDING")\
                   .order_by(asc(OrderModel.priority), asc(OrderModel.created_at))\
                   .first()

    if active:
        pts = [Waypoint(**p) for p in json.loads(active.waypoints_json)] if active.waypoints_json else []
        return OrderOut(
            id=active.id,
            order_code=active.order_code,
            user_name=active.user_name,
            user_email=active.user_email,
            user_phone=active.user_phone,
            pickup_node_id=active.pickup_node_id,
            dest_node_id=active.dest_node_id,
            item_type=active.item_type,
            is_emergency=active.is_emergency,
            priority=active.priority,
            status=active.status,
            situation_msg=active.situation_msg,
            progress_percent=active.progress_percent,
            qr_unlock_code=active.qr_unlock_code,
            pin_code=active.pin_code,
            container_locked=active.container_locked,
            waypoints=pts,
            created_at=active.created_at,
            completed_at=active.completed_at
        )
    return None

# --- SECURE QR CONTAINER UNLOCK ENDPOINT ---
@app.post("/api/orders/unlock")
async def unlock_container(req: QRUnlockRequest, db: Session = Depends(get_db)):
    order = db.query(OrderModel).filter(OrderModel.id == req.order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    token = req.unlock_code.strip()
    if token != order.qr_unlock_code and token != order.pin_code:
        raise HTTPException(status_code=400, detail="Invalid QR Code or PIN. Container remains locked!")

    # Matched! Open cargo hatch
    order.container_locked = False
    order.status = "UNLOCKED"
    order.situation_msg = "🔓 QR MATCHED! Rover container unlocked. Please collect your cargo."
    db.commit()

    # Broadcast unlock to WebSocket clients and robot display
    await ws_manager.broadcast({
        "type": "container_unlocked",
        "order_id": order.id,
        "order_code": order.order_code,
        "situation_msg": order.situation_msg
    })

    return {
        "status": "success",
        "order_id": order.id,
        "container_locked": False,
        "message": "QR matched! Container unlocked successfully."
    }

@app.patch("/api/orders/{order_id}/status")
async def update_order_status(
    order_id: int, 
    status: str = Query(...), 
    situation_msg: Optional[str] = Query(None),
    progress_percent: Optional[float] = Query(None),
    container_locked: Optional[bool] = Query(None),
    db: Session = Depends(get_db)
):
    order = db.query(OrderModel).filter(OrderModel.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    order.status = status
    if situation_msg:
        order.situation_msg = situation_msg
    if progress_percent is not None:
        order.progress_percent = progress_percent
    if container_locked is not None:
        order.container_locked = container_locked
    if status == "DELIVERED":
        order.completed_at = datetime.utcnow()

    db.commit()

    await ws_manager.broadcast({
        "type": "order_update",
        "order_id": order.id,
        "order_code": order.order_code,
        "status": order.status,
        "situation_msg": order.situation_msg,
        "progress_percent": order.progress_percent,
        "container_locked": order.container_locked,
        "qr_unlock_code": order.qr_unlock_code,
        "pin_code": order.pin_code
    })

    return {"status": "success", "order_id": order_id, "new_status": status}

# ==========================================
# 5. ROBOT TELEMETRY & WEBSOCKET
# ==========================================

@app.post("/api/robot/telemetry", response_model=TelemetryOut)
async def record_robot_telemetry(data: TelemetryCreate, db: Session = Depends(get_db)):
    record = RobotTelemetryModel(
        robot_id=data.robot_id,
        current_order_id=data.current_order_id,
        lat=data.lat,
        lng=data.lng,
        heading=data.heading,
        speed_mps=data.speed_mps,
        battery_v=data.battery_v,
        load_g=data.load_g,
        state=data.state,
        situation_msg=data.situation_msg,
        container_locked=data.container_locked,
        recorded_at=datetime.utcnow()
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    await ws_manager.broadcast({
        "type": "telemetry",
        "robot_id": record.robot_id,
        "current_order_id": record.current_order_id,
        "lat": record.lat,
        "lng": record.lng,
        "heading": record.heading,
        "speed_mps": record.speed_mps,
        "battery_v": record.battery_v,
        "load_g": record.load_g,
        "state": record.state,
        "situation_msg": record.situation_msg,
        "container_locked": record.container_locked,
        "timestamp": record.recorded_at.isoformat()
    })

    return record

@app.get("/api/robot/status", response_model=Optional[TelemetryOut])
def get_latest_robot_status(robot_id: int = 1, db: Session = Depends(get_db)):
    latest = db.query(RobotTelemetryModel)\
               .filter(RobotTelemetryModel.robot_id == robot_id)\
               .order_by(desc(RobotTelemetryModel.recorded_at))\
               .first()
    if not latest:
        return TelemetryOut(
            id=0,
            robot_id=robot_id,
            current_order_id=None,
            lat=6.90150,
            lng=79.86005,
            heading=0.0,
            speed_mps=0.0,
            battery_v=12.4,
            load_g=0,
            state="IDLE",
            situation_msg="Standing by at Main Gate.",
            container_locked=True,
            recorded_at=datetime.utcnow()
        )
    return latest

@app.websocket("/ws/telemetry")
async def websocket_telemetry_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
