import json
import uuid
from typing import List, Optional
from datetime import datetime
from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from database import engine, get_db, Base
from models import NodeModel, EdgeModel, OrderModel, RobotTelemetryModel
from schemas import (
    NodeOut, EdgeOut, OrderCreate, OrderOut, 
    TelemetryCreate, TelemetryOut, Waypoint
)
from path_planner import find_shortest_path

# Create database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Campus Food Delivery Robot API",
    description="REST backend for University of Colombo Campus Autonomous Food Delivery Robot",
    version="1.0.0"
)

# Enable CORS for frontend web app
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    return {
        "project": "Food Delivery Robot - UOC PH 3042",
        "status": "online",
        "docs_url": "/docs"
    }

# --- NODES & CAMPUS GRAPH ---

@app.get("/api/nodes", response_model=List[NodeOut])
def get_all_nodes(db: Session = Depends(get_db)):
    return db.query(NodeModel).all()

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

@app.get("/api/routes/plan")
def plan_route(
    start_id: int = Query(..., description="Start / Pickup node ID"),
    target_id: int = Query(..., description="Destination node ID"),
    db: Session = Depends(get_db)
):
    node_ids, waypoints, total_dist = find_shortest_path(db, start_id, target_id)
    if not node_ids:
        raise HTTPException(status_code=404, detail="No path found between the specified nodes")

    return {
        "start_node_id": start_id,
        "target_node_id": target_id,
        "total_distance_m": round(total_dist, 2),
        "node_sequence": node_ids,
        "waypoint_count": len(waypoints),
        "waypoints": [w.dict() for w in waypoints]
    }

# --- ORDERS ---

@app.post("/api/orders", response_model=OrderOut)
def create_delivery_order(order: OrderCreate, db: Session = Depends(get_db)):
    pickup = db.query(NodeModel).filter(NodeModel.id == order.pickup_node_id).first()
    dest = db.query(NodeModel).filter(NodeModel.id == order.dest_node_id).first()

    if not pickup or not dest:
        raise HTTPException(status_code=400, detail="Invalid pickup or destination node ID")

    # Calculate optimal path
    node_ids, waypoints, total_dist = find_shortest_path(db, order.pickup_node_id, order.dest_node_id)
    pts_json = json.dumps([w.dict() for w in waypoints]) if waypoints else "[]"

    order_code = f"ORD-{uuid.uuid4().hex[:6].upper()}"
    new_order = OrderModel(
        order_code=order_code,
        user_name=order.user_name,
        pickup_node_id=order.pickup_node_id,
        dest_node_id=order.dest_node_id,
        status="PENDING",
        waypoints_json=pts_json,
        created_at=datetime.utcnow()
    )
    db.add(new_order)
    db.commit()
    db.refresh(new_order)

    return OrderOut(
        id=new_order.id,
        order_code=new_order.order_code,
        user_name=new_order.user_name,
        pickup_node_id=new_order.pickup_node_id,
        dest_node_id=new_order.dest_node_id,
        status=new_order.status,
        waypoints=waypoints,
        created_at=new_order.created_at,
        completed_at=new_order.completed_at
    )

@app.get("/api/orders", response_model=List[OrderOut])
def list_orders(limit: int = 20, db: Session = Depends(get_db)):
    orders = db.query(OrderModel).order_by(OrderModel.created_at.desc()).limit(limit).all()
    results = []
    for o in orders:
        pts = [Waypoint(**p) for p in json.loads(o.waypoints_json)] if o.waypoints_json else []
        results.append(OrderOut(
            id=o.id,
            order_code=o.order_code,
            user_name=o.user_name,
            pickup_node_id=o.pickup_node_id,
            dest_node_id=o.dest_node_id,
            status=o.status,
            waypoints=pts,
            created_at=o.created_at,
            completed_at=o.completed_at
        ))
    return results

@app.get("/api/orders/{order_id}", response_model=OrderOut)
def get_order(order_id: int, db: Session = Depends(get_db)):
    o = db.query(OrderModel).filter(OrderModel.id == order_id).first()
    if not o:
        raise HTTPException(status_code=404, detail="Order not found")
    pts = [Waypoint(**p) for p in json.loads(o.waypoints_json)] if o.waypoints_json else []
    return OrderOut(
        id=o.id,
        order_code=o.order_code,
        user_name=o.user_name,
        pickup_node_id=o.pickup_node_id,
        dest_node_id=o.dest_node_id,
        status=o.status,
        waypoints=pts,
        created_at=o.created_at,
        completed_at=o.completed_at
    )

# --- ROBOT TELEMETRY ---

@app.post("/api/robot/telemetry", response_model=TelemetryOut)
def record_robot_telemetry(data: TelemetryCreate, db: Session = Depends(get_db)):
    record = RobotTelemetryModel(
        robot_id=data.robot_id,
        lat=data.lat,
        lng=data.lng,
        heading=data.heading,
        speed_mps=data.speed_mps,
        battery_v=data.battery_v,
        load_g=data.load_g,
        state=data.state,
        recorded_at=datetime.utcnow()
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record

@app.get("/api/robot/status", response_model=Optional[TelemetryOut])
def get_latest_robot_status(robot_id: int = 1, db: Session = Depends(get_db)):
    latest = db.query(RobotTelemetryModel)\
               .filter(RobotTelemetryModel.robot_id == robot_id)\
               .order_by(RobotTelemetryModel.recorded_at.desc())\
               .first()
    if not latest:
        # Return default mock position at main gate if no telemetry yet
        return TelemetryOut(
            id=0,
            robot_id=robot_id,
            lat=6.90150,
            lng=79.86005,
            heading=0.0,
            speed_mps=0.0,
            battery_v=12.4,
            load_g=0,
            state="IDLE",
            recorded_at=datetime.utcnow()
        )
    return latest
