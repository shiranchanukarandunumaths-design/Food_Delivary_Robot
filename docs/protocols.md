# Communication Protocols & Interface Contracts

This document specifies the exact communication formats between the **Raspberry Pi** and the **ESP32**, as well as the **Cloud Server** and the **Robot**.

---

## 1. Pi ↔ ESP32 Serial Interface (USB UART)

- **Baud Rate:** `115200` baud
- **Format:** 8-N-1, Newline-terminated (`\n`)
- **Watchdog Timeout:** 2000 ms (If no command received within 2s, ESP32 stops motors)

### Commands (Pi → ESP32)

| Command | Format | Example | Description |
|---|---|---|---|
| **Drive** | `DRIVE,<left_speed>,<right_speed>\n` | `DRIVE,150,150\n` | Left & right speeds (-255 to 255) |
| **Stop** | `STOP\n` | `STOP\n` | Smooth decelerated stop |
| **Emergency Stop** | `ESTOP\n` | `ESTOP\n` | Immediate PWM cutoff & brake |
| **Request Status** | `GET_STATUS\n` | `GET_STATUS\n` | Explicitly requests sensor telemetry |

### Telemetry (ESP32 → Pi)

Periodic broadcast every 100 ms (10 Hz) or on change:

```text
STATUS,<load_grams>,<front_dist_cm>,<left_dist_cm>,<right_dist_cm>,<battery_volts>,<state>\n
```

- `load_grams`: Integer from HX711 load cell (e.g. `4500` for 4.5 kg)
- `front_dist_cm`: Integer from front ultrasonic sensor (e.g. `45`)
- `left_dist_cm`: Integer from left ultrasonic sensor (e.g. `120`)
- `right_dist_cm`: Integer from right ultrasonic sensor (e.g. `110`)
- `battery_volts`: Float battery voltage (e.g. `12.4`)
- `state`: Status string (`IDLE`, `DRIVING`, `OBSTACLE_STOP`, `ESTOP_ACTIVE`)

---

## 2. Server ↔ Robot MQTT Topics

- **Broker:** Mosquitto MQTT Broker (Cloud / Local Server)
- **QoS:** 1 (At least once delivery)

### Topics

#### A. Commands: `robot/1/command` (Server → Pi)
```json
{
  "action": "goto",
  "order_id": 101,
  "target_node": "Faculty_Canteen",
  "waypoints": [
    {"lat": 6.90152, "lng": 79.86012},
    {"lat": 6.90180, "lng": 79.86035}
  ]
}
```

#### B. Telemetry: `robot/1/status` (Pi → Server)
```json
{
  "robot_id": 1,
  "lat": 6.90155,
  "lng": 79.86014,
  "heading": 42.5,
  "speed_mps": 0.65,
  "battery_v": 12.2,
  "load_g": 3200,
  "state": "EN_ROUTE",
  "timestamp": 1774167890
}
```

#### C. Alerts: `robot/1/alerts` (Pi → Server)
```json
{
  "robot_id": 1,
  "alert": "OBSTACLE_DETECTED",
  "severity": "WARNING",
  "distance_cm": 25,
  "timestamp": 1774167895
}
```
