# 🤖 Campus Food Delivery Robot

> **Course:** PH 3042 - Robotics & Automation (University of Colombo)  
> **Repository:** [https://github.com/shiranchanukarandunumaths-design/Food_Delivary_Robot.git](https://github.com/shiranchanukarandunumaths-design/Food_Delivary_Robot.git)  
> **System Architecture:** ESP32 Firmware + Raspberry Pi Navigator + FastAPI Server + Leaflet Web App

---

## 📂 Project Structure

```text
Food_Delivary_Robot/
├── .vscode/               # VS Code configurations & recommended extensions
│   ├── extensions.json
│   └── settings.json
├── docs/                  # Architecture & Phase 0 Specifications
│   ├── protocols.md       # Serial (UART) & MQTT communication contracts
│   ├── campus_graph.json  # University of Colombo Science Faculty nodes & edges
│   ├── campus_graph.md    # Topological graph documentation & Dijkstra pathfinder
│   └── team_tracks.md     # Team roles & responsibilities (Tracks 1, 2, 3)
├── backend/               # FastAPI REST Backend & Route Planner
│   ├── main.py            # REST API endpoints (nodes, edges, orders, telemetry)
│   ├── database.py        # SQLite engine & database sessions
│   ├── models.py          # SQLAlchemy models (nodes, edges, orders, status)
│   ├── schemas.py         # Pydantic validation schemas
│   ├── path_planner.py    # Dijkstra shortest-path algorithm
│   ├── seed_data.py       # Auto-populates UOC campus graph from JSON
│   └── requirements.txt   # FastAPI, SQLAlchemy, Uvicorn, Paho-MQTT
├── webapp/                # Mission Control Frontend (Leaflet + Satellite Map)
│   ├── index.html         # Interactive dashboard UI
│   ├── style.css          # Dark-theme mission control styling
│   ├── app.js             # Map rendering, order dispatch, telemetry & teleop
│   └── package.json
├── pi/                    # Raspberry Pi Software & Host Test Scripts
│   ├── test_serial.py     # USB Serial motor control & telemetry test utility
│   └── requirements.txt
├── src/                   # ESP32 Core Firmware
│   └── main.cpp           # BTS7960 PWM control, watchdog timer, collision avoidance
├── include/
│   └── config.h           # ESP32 30-pin pinout, PWM channels, safety parameters
├── platformio.ini         # PlatformIO build configuration for ESP32
├── .gitignore             # Ignore rules for builds, dependencies & binaries
└── README.md              # Project documentation
```

---

## 🚀 Quick Start Guide

### 1. ESP32 Firmware (Track 3)
1. Open this repository in **VS Code** with the **PlatformIO** extension installed.
2. Connect your ESP32 via micro-USB.
3. In PlatformIO, click **Build** (`✓`) and **Upload** (`→`).
4. Click **Serial Monitor** at `115200` baud to verify boot telemetry.

### 2. Backend Server & Path Planner (Track 1)
```bash
cd backend
pip install -r requirements.txt

# Seed the UOC campus nodes and edges into SQLite
python seed_data.py

# Start the FastAPI server
uvicorn main:app --reload --port 8000
```
* **Interactive API Docs:** Open [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs) in your browser.

### 3. Mission Control Web App (Track 1)
Open `webapp/index.html` directly in your browser or serve it locally:
```bash
cd webapp
npx serve .
```
* Shows the **University of Colombo Faculty of Science** satellite map.
* Displays clickable campus nodes, path network, order dispatch form, and live telemetry cards.

### 4. Serial Testing from Laptop or Pi (Track 2)
```bash
cd pi
pip install -r requirements.txt
python test_serial.py
```
* Press `w`/`s` (Forward/Reverse), `a`/`d` (Turn), `space` (Stop), `e` (E-Stop).

---

## 🗺️ Campus Graph (University of Colombo - Science Faculty)

| Node | Name | Type |
|---|---|---|
| **1** | Faculty Main Gate (Reid Ave) | Entry Point |
| **2** | Science Quadrangle Junction | Central Junction |
| **3** | Department of Physics (PH 3042) | Destination |
| **4** | Department of Chemistry | Destination |
| **5** | Science Faculty Library | Destination |
| **6** | Faculty Canteen / Cafeteria | Food Pickup Point |
| **7** | Department of Mathematics | Destination |

---

## 🔒 Safety Layer

- **Watchdog Timer:** The ESP32 auto-stops all motors if no command arrives within **2000 ms**.
- **Ultrasonic Obstacle Detection:** Front obstacle `< 30 cm` automatically halts forward drive.
- **Hardware Emergency Stop:** Dedicated active-LOW push button immediately cuts driver enable lines.
