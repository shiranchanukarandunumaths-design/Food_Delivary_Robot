import os
import json
from database import engine, SessionLocal, Base
from models import NodeModel, EdgeModel, UserModel

def seed_campus_database():
    print("Initializing database tables with updated schema...")
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        # Seed default users with email & password
        if db.query(UserModel).count() == 0:
            print("Seeding default users...")
            users = [
                UserModel(
                    email="admin@uoc.lk",
                    password="admin",
                    full_name="Operations Admin",
                    student_id="STAFF/ROBOTICS/01",
                    phone="0710000000",
                    department="Department of Physics",
                    role="admin"
                ),
                UserModel(
                    email="hiruna@gmail.com",
                    password="password123",
                    full_name="Hiruna Perera",
                    student_id="SC/2022/10452",
                    phone="0771234567",
                    department="Department of Physics",
                    role="student"
                ),
                UserModel(
                    email="student@gmail.com",
                    password="password123",
                    full_name="Kasun Silva",
                    student_id="SC/2022/10899",
                    phone="0719876543",
                    department="Department of Chemistry",
                    role="student"
                )
            ]
            for u in users:
                db.add(u)
            db.commit()

        # Seed campus nodes & edges if none exist
        json_path = os.path.join(os.path.dirname(__file__), "..", "docs", "campus_graph.json")
        if os.path.exists(json_path):
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            if db.query(NodeModel).count() == 0:
                print(f"Seeding {len(data['nodes'])} baseline nodes...")
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

            if db.query(EdgeModel).count() == 0:
                print(f"Seeding {len(data['edges'])} baseline edges...")
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
    db_file = os.path.join(os.path.dirname(__file__), "campus_delivery.db")
    if os.path.exists(db_file):
        try:
            os.remove(db_file)
            print("Removed old database file to apply fresh schema.")
        except Exception as e:
            print(f"Note: {e}")
    seed_campus_database()
