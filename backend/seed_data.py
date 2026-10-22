import os
import json
from database import engine, SessionLocal, Base
from models import NodeModel, EdgeModel, UserModel

def seed_campus_database():
    print("Re-creating database tables with updated schema...")
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        # Seed default users if none exist
        if db.query(UserModel).count() == 0:
            print("Seeding default users...")
            users = [
                UserModel(username="student1", full_name="Hiruna Perera", role="student", phone="0771234567"),
                UserModel(username="faculty1", full_name="Dr. Wickramasinghe", role="staff", phone="0719876543"),
                UserModel(username="admin", full_name="Rover Operations Admin", role="admin", phone="0700000000")
            ]
            for u in users:
                db.add(u)
            db.commit()

        # Seed campus nodes & edges
        json_path = os.path.join(os.path.dirname(__file__), "..", "docs", "campus_graph.json")
        if not os.path.exists(json_path):
            print(f"Error: {json_path} not found.")
            return

        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        existing_nodes = db.query(NodeModel).count()
        if existing_nodes == 0:
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
    # If upgrading schema, remove old db and seed fresh
    db_file = os.path.join(os.path.dirname(__file__), "campus_delivery.db")
    if os.path.exists(db_file):
        try:
            os.remove(db_file)
            print("Removed old database file to apply updated schema.")
        except Exception as e:
            print(f"Note: {e}")
    seed_campus_database()
