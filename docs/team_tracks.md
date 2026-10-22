# 👥 Team Tracks & Responsibilities

To make fast, parallel progress, the project is divided into three distinct technical tracks. Each track works against the agreed interfaces defined in [`protocols.md`](protocols.md) and [`campus_graph.json`](campus_graph.json).

---

## Track 1: Web App & Backend Server
- **Primary Tech:** React, Leaflet, FastAPI, SQLite / PostgreSQL, Mosquitto MQTT
- **Core Responsibilities:**
  1. Build the user order UI (select pickup point, delivery destination, food order details).
  2. Implement interactive campus map with satellite tiles (Esri World Imagery) displaying:
     - Campus nodes and walkable paths.
     - Live robot position, orientation, and battery indicator.
     - Live video stream embedded in the tracking tab.
  3. Implement backend database models (`nodes`, `edges`, `orders`, `robot_status`).
  4. Implement Dijkstra graph pathfinding to convert (Pickup, Destination) into an ordered list of GPS waypoints.
  5. Publish waypoint missions to `robot/1/command` via MQTT.
  6. Subscribe to `robot/1/status` and store history for post-run analysis.

---

## Track 2: Raspberry Pi Software & Navigation
- **Primary Tech:** Python 3, PySerial, Paho-MQTT, OpenCV (video streaming)
- **Hardware Owned:** Raspberry Pi 4/5, u-blox NEO-M8N GPS, BNO055 9-DOF IMU, Pi Camera / USB Cam, 4G / Wi-Fi dongle
- **Core Responsibilities:**
  1. **GPS & IMU Ingestion:** Parse NMEA sentences from NEO-M8N and orientation from BNO055.
  2. **MQTT Client:** Connect to the backend broker, receive mission waypoints, report telemetry at 10 Hz.
  3. **Teach-and-Repeat Route Recorder:** Manual drive mode that records GPS waypoints every 1–2 meters.
  4. **Waypoint Follower (Pure Pursuit):**
     - Compute heading error between robot heading and current target waypoint.
     - Calculate differential drive speed and turn commands.
     - Send `DRIVE,<left>,<right>` over USB serial to ESP32.
  5. **Fail-Safe Supervisor:** If MQTT disconnects or Pi software stalls, command ESP32 to `STOP`.
  6. **Camera Streamer:** Low-latency MJPEG video stream to the web app.

---

## Track 3: ESP32 Firmware & Electronics Hardware
- **Primary Tech:** C/C++, PlatformIO / Arduino IDE, FreeRTOS
- **Hardware Owned:** ESP32 DevKit, 2× BTS7960 43A motor drivers, 4× JGB37-520 12V DC gear motors, 3× HC-SR04 ultrasonic sensors, 10kg Load Cell + HX711, AS5600 magnetic encoders, 12V Li-ion battery pack, 12V→5V buck converter.
- **Core Responsibilities:**
  1. **Motor Control:** Smooth PWM generation (20 kHz silent drive) for BTS7960 H-bridges with acceleration ramping.
  2. **Safety Watchdog:** Hardware timer that cuts motor PWM if no serial command is received within 2000 ms.
  3. **Collision Avoidance:** Dedicated non-blocking ultrasonic distance reading (< 30 cm auto-stops forward drive).
  4. **Load Cell Integration:** Weight measurement via HX711 to detect load addition and removal at delivery.
  5. **Hardware E-Stop:** Physical push button that cuts driver enable pins immediately.
  6. **Encoders & Closed-Loop PID:** Read AS5600 encoders for RPM and odometry feedback.

---

## 🤝 Interface Contracts & Handoff Checklist

- [x] **Pi ↔ ESP32 Serial Protocol:** `DRIVE,<left>,<right>`, `STOP`, `ESTOP`, `STATUS`
- [x] **Server ↔ Robot MQTT Topics:** `robot/1/command`, `robot/1/status`, `robot/1/alerts`
- [x] **Campus Graph Schema:** Defined in `campus_graph.json`
