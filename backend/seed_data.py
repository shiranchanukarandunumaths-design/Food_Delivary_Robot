import os
import json
from database import engine, SessionLocal, Base
from models import NodeModel, EdgeModel

def seed_campus_database():
    print("Creating database tables...")
    Base.metadata.create_all(bind=engine)

    json_path = os.path.join(os.path.dirname(__file__), "..", "docs", "campus_graph.json")
    if not os.path.exists(json_path):
        print(f"Error: {json_path} not found.")
        return

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    db = SessionLocal()
    try:
        # Check if already seeded
        existing_nodes = db.query(NodeModel).count()
        if existing_nodes > 0:
            print(f"Database already contains {existing_nodes} nodes. Skipping seed.")
            return

        print(f"Seeding {len(data['nodes'])} nodes...")
        for n in data["nodes"]:
            node = NodeModel(
                id=n["id"],
                code=n["code"],
                name=n["name"],
                lat=n["lat"],
                lng=n["lng"],
                type=n["type"]
            )
            db.add(node)
        db.commit()

        print(f"Seeding {len(data['edges'])} edges...")
        for e in data["edges"]:
            edge = EdgeModel(
                id=e["id"],
                from_node_id=e["from_node_id"],
                to_node_id=e["to_node_id"],
                name=e.get("name"),
                distance_m=e["distance_m"],
                waypoints_json=json.dumps(e.get("waypoints", []))
            )
            db.add(edge)
        db.commit()

        print("Campus database seeded successfully!")
    finally:
        db.close()

if __name__ == "__main__":
    seed_campus_database()
