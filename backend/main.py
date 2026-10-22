import json
import uuid
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
    Waypoint, UserLogin, UserCreate, UserOut
)
from path_planner import find_shortest_path

# Ensure tables exist
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Campus Autonomous Food & Parcel Delivery Robot API",
    description="Backend for University of Colombo Campus Autonomous Rover (PH 3042)",
    version="1.1.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- WEBSOCKET CONNECTION MANAGER FOR REAL-TIME TRACKING ---
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

# --- OPTIONAL MQTT CLIENT BRIDGE (Mosquitto) ---
mqtt_client = None
try:
    import paho.mqtt.client as mqtt
    def on_mqtt_connect(client, userdata, flags, rc):
        if rc == 0:
            print("[MQTT] Connected to Mosquitto broker on localhost:1883")
            client.subscribe("robot/+/status")
            client.subscribe("robot/+/alerts")
        else:
            print(f"[MQTT] Connection returned code {rc}")

    def on_mqtt_message(client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode())
            # Forward MQTT status to WebSocket clients
            asyncio.run(ws_manager.broadcast({"type": "mqtt_relay", "topic": msg.topic, "data": payload}))
        except Exception:
            pass

    mqtt_client = mqtt.Client(client_id="fastapi_backend")
    mqtt_client.on_connect = on_mqtt_connect
    mqtt_client.on_message = on_mqtt_message
    try:
        mqtt_client.connect_async("localhost", 1883, 60)
        mqtt_client.loop_start()
    except Exception as e:
        print(f"[MQTT] Mosquitto broker not running locally ({e}). Using WebSocket/HTTP mode.")
except Exception as e:
    print(f"[MQTT] Paho-MQTT not initialized: {e}")

@app.get("/")
def root():
    return {
        "project": "Campus Food & Parcel Delivery Robot - UOC PH 3042",
        "status": "online",
        "docs_url": "/docs",
        "ws_url": "/ws/telemetry"
    }

# --- AUTHENTICATION & USERS ---

@app.post("/api/auth/login", response_model=UserOut)
def login_user(payload: UserLogin, db: Session = Depends(get_db)):
    user = db.query(UserModel).filter(UserModel.username == payload.username.strip().lower()).first()
    if not user:
        # Create a new student user on the fly if not exists
        user = UserModel(
            username=payload.username.strip().lower(),
            full_name=payload.username.capitalize(),
            role="student"
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    return user

@app.get("/api/users", response_model=List[UserOut])
def get_users(db: Session = Depends(get_db)):
    return db.query(UserModel).all()

# --- CAMPUS NODES & PLACES ---

@app.get("/api/nodes", response_model=List[NodeOut])
def get_all_nodes(db: Session = Depends(get_db)):
    return db.query(NodeModel).order_by(NodeModel.id).all()

@app.post("/api/nodes", response_model=NodeOut)
def create_node(node: NodeCreate, db: Session = Depends(get_db)):
    existing = db.query(NodeModel).filter(NodeModel.code == node.code).first()
    if existing:
        raise HTTPException(status_code=400, detail="Node code already exists")
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

# --- CAMPUS EDGES / ROUTES ---

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

@app.post("/api/edges", response_model=EdgeOut)
def create_or_save_edge(edge: EdgeCreate, db: Session = Depends(get_db)):
    pts_json = json.dumps([w.dict() for w in edge.waypoints]) if edge.waypoints else "[]"
    new_edge = EdgeModel(
        from_node_id=edge.from_node_id,
        to_node_id=edge.to_node_id,
        name=edge.name,
        distance_m=edge.distance_m,
        waypoints_json=pts_json
    )
    db.add(new_edge)
    db.commit()
    db.refresh(new_edge)
    return EdgeOut(
        id=new_edge.id,
        from_node_id=new_edge.from_node_id,
        to_node_id=new_edge.to_node_id,
        name=new_edge.name,
        distance_m=new_edge.distance_m,
        waypoints=edge.waypoints
    )

@app.get("/api/routes/plan")
def plan_route(
    start_id: int = Query(..., description="Start / Pickup node ID"),
    target_id: int = Query(..., description="Destination node ID"),
    db: Session = Depends(get_db)
):
    node_ids, waypoints, total_dist = find_shortest_path(db, start_id, target_id)
    if not node_ids:
        raise HTTPException(status_code=404, detail="No path found between specified nodes")
    return {
        "start_node_id": start_id,
        "target_node_id": target_id,
        "total_distance_m": round(total_dist, 2),
        "node_sequence": node_ids,
        "waypoint_count": len(waypoints),
        "waypoints": [w.dict() for w in waypoints]
    }

# --- ORDERS & PRIORITIZATION QUEUE ---

@app.post("/api/orders", response_model=OrderOut)
async def create_delivery_order(order: OrderCreate, db: Session = Depends(get_db)):
    pickup = db.query(NodeModel).filter(NodeModel.id == order.pickup_node_id).first()
    dest = db.query(NodeModel).filter(NodeModel.id == order.dest_node_id).first()

    if not pickup or not dest:
        raise HTTPException(status_code=400, detail="Invalid pickup or destination node ID")

    # Priority calculation: Emergency orders get priority 1, regular get priority 5
    priority_level = 1 if order.is_emergency else 5

    # Compute optimal waypoint route with Dijkstra
    node_ids, waypoints, total_dist = find_shortest_path(db, order.pickup_node_id, order.dest_node_id)
    pts_json = json.dumps([w.dict() for w in waypoints]) if waypoints else "[]"

    order_code = f"ORD-{'EMG-' if order.is_emergency else ''}{uuid.uuid4().hex[:6].upper()}"
    situation = f"Order placed for {order.item_type}. {'🚨 EMERGENCY RUSH' if order.is_emergency else 'Standard delivery'}. Waiting for collection at {pickup.name}."

    new_order = OrderModel(
        order_code=order_code,
        user_name=order.user_name,
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
        created_at=datetime.utcnow()
    )
    db.add(new_order)
    db.commit()
    db.refresh(new_order)

    # Publish to MQTT if available
    if mqtt_client and mqtt_client.is_connected():
        try:
            cmd_payload = {
                "action": "new_order",
                "order_id": new_order.id,
                "order_code": new_order.order_code,
                "priority": priority_level,
                "pickup": pickup.name,
                "destination": dest.name,
                "item_type": new_order.item_type,
                "waypoints": [w.dict() for w in waypoints]
            }
            mqtt_client.publish("robot/1/command", json.dumps(cmd_payload), qos=1)
        except Exception as e:
            print(f"[MQTT] Publish failed: {e}")

    # Broadcast new order to WebSocket
    await ws_manager.broadcast({
        "type": "new_order",
        "order_id": new_order.id,
        "order_code": new_order.order_code,
        "is_emergency": new_order.is_emergency,
        "item_type": new_order.item_type,
        "situation_msg": new_order.situation_msg
    })

    return OrderOut(
        id=new_order.id,
        order_code=new_order.order_code,
        user_name=new_order.user_name,
        user_phone=new_order.user_phone,
        pickup_node_id=new_order.pickup_node_id,
        dest_node_id=new_order.dest_node_id,
        item_type=new_order.item_type,
        is_emergency=new_order.is_emergency,
        priority=new_order.priority,
        status=new_order.status,
        situation_msg=new_order.situation_msg,
        progress_percent=new_order.progress_percent,
        waypoints=waypoints,
        created_at=new_order.created_at,
        completed_at=new_order.completed_at
    )

@app.get("/api/orders", response_model=List[OrderOut])
def list_orders(limit: int = 50, db: Session = Depends(get_db)):
    # Sorted by Priority ascending (1=Emergency first), then created_at ascending
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
            user_phone=o.user_phone,
            pickup_node_id=o.pickup_node_id,
            dest_node_id=o.dest_node_id,
            item_type=o.item_type,
            is_emergency=o.is_emergency,
            priority=o.priority,
            status=o.status,
            situation_msg=o.situation_msg,
            progress_percent=o.progress_percent,
            waypoints=pts,
            created_at=o.created_at,
            completed_at=o.completed_at
        ))
    return results

@app.get("/api/orders/active", response_model=Optional[OrderOut])
def get_active_or_next_order(db: Session = Depends(get_db)):
    # 1. First check if any order is currently IN_PROGRESS (COLLECTING, DISPATCHED, EN_ROUTE, ARRIVED)
    active = db.query(OrderModel)\
               .filter(OrderModel.status.in_(["COLLECTING", "DISPATCHED", "EN_ROUTE", "ARRIVED"]))\
               .order_by(asc(OrderModel.priority), asc(OrderModel.created_at))\
               .first()
    if active:
        pts = [Waypoint(**p) for p in json.loads(active.waypoints_json)] if active.waypoints_json else []
        return OrderOut(
            id=active.id,
            order_code=active.order_code,
            user_name=active.user_name,
            user_phone=active.user_phone,
            pickup_node_id=active.pickup_node_id,
            dest_node_id=active.dest_node_id,
            item_type=active.item_type,
            is_emergency=active.is_emergency,
            priority=active.priority,
            status=active.status,
            situation_msg=active.situation_msg,
            progress_percent=active.progress_percent,
            waypoints=pts,
            created_at=active.created_at,
            completed_at=active.completed_at
        )

    # 2. Next check highest priority PENDING order
    pending = db.query(OrderModel)\
                .filter(OrderModel.status == "PENDING")\
                .order_by(asc(OrderModel.priority), asc(OrderModel.created_at))\
                .first()
    if pending:
        pts = [Waypoint(**p) for p in json.loads(pending.waypoints_json)] if pending.waypoints_json else []
        return OrderOut(
            id=pending.id,
            order_code=pending.order_code,
            user_name=pending.user_name,
            user_phone=pending.user_phone,
            pickup_node_id=pending.pickup_node_id,
            dest_node_id=pending.dest_node_id,
            item_type=pending.item_type,
            is_emergency=pending.is_emergency,
            priority=pending.priority,
            status=pending.status,
            situation_msg=pending.situation_msg,
            progress_percent=pending.progress_percent,
            waypoints=pts,
            created_at=pending.created_at,
            completed_at=pending.completed_at
        )

    return None

@app.patch("/api/orders/{order_id}/status")
async def update_order_status(
    order_id: int, 
    status: str = Query(...), 
    situation_msg: Optional[str] = Query(None),
    progress_percent: Optional[float] = Query(None),
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
    if status == "DELIVERED":
        order.completed_at = datetime.utcnow()

    db.commit()

    # Broadcast live status update to WebSocket
    await ws_manager.broadcast({
        "type": "order_update",
        "order_id": order.id,
        "order_code": order.order_code,
        "status": order.status,
        "situation_msg": order.situation_msg,
        "progress_percent": order.progress_percent
    })

    return {"status": "success", "order_id": order_id, "new_status": status}

# --- ROBOT TELEMETRY & SITUATION ---

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
        recorded_at=datetime.utcnow()
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    # Real-time WebSocket broadcast to all connected web dashboards
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
            recorded_at=datetime.utcnow()
        )
    return latest

# --- WEBSOCKET FOR REAL-TIME CLIENT STREAMING ---

@app.websocket("/ws/telemetry")
async def websocket_telemetry_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        while True:
            # Keep connection alive, listen for ping or teleop override
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                if msg.get("type") == "teleop":
                    cmd = msg.get("command")
                    print(f"[Teleop WS Command]: {cmd}")
                    if mqtt_client and mqtt_client.is_connected():
                        mqtt_client.publish("robot/1/command", json.dumps({"action": "teleop", "cmd": cmd}))
            except Exception:
                pass
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
