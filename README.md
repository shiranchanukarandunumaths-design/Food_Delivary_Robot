# 🤖 Food Delivery Robot — Firmware & Control System

> **Course:** PH 3042 - Robotics & Automation (University of Colombo)  
> **Repository:** [https://github.com/shiranchanukarandunumaths-design/Food_Delivary_Robot.git](https://github.com/shiranchanukarandunumaths-design/Food_Delivary_Robot.git)  
> **Target Hardware:** ESP32 DevKit (30-pin) + BTS7960 Drivers + JGB37-520 12V Motors + Raspberry Pi

---

## 📂 Repository Structure

```text
Food_Delivary_Robot_firmware/
├── .vscode/               # VS Code configuration & recommended extensions
│   ├── extensions.json
│   └── settings.json
├── docs/                  # Design documents & protocol contracts
│   └── protocols.md       # Pi ↔ ESP32 Serial & Server MQTT specs
├── include/               # C/C++ Header files
│   └── config.h           # ESP32 pin definitions, PWM channels, safety limits
├── src/                   # Firmware source code
│   └── main.cpp           # ESP32 core firmware (BTS7960, sensors, watchdog, UART)
├── pi/                    # Raspberry Pi & Host testing scripts
│   ├── test_serial.py     # Interactive serial test console
│   └── requirements.txt   # Python dependencies
├── platformio.ini         # PlatformIO build configuration for ESP32
├── .gitignore             # Git ignore rules for firmware, builds & binaries
└── README.md              # Project documentation
```

---

## 🔌 Hardware Pin Mapping (ESP32 DevKit 30-Pin)

### 1. Left Motor Driver (BTS7960)
| ESP32 Pin | BTS7960 Pin | Function |
|---|---|---|
| `GPIO 25` | RPWM | Forward PWM |
| `GPIO 26` | LPWM | Reverse PWM |
| `GPIO 27` | R_EN | Forward Enable |
| `GPIO 14` | L_EN | Reverse Enable |

### 2. Right Motor Driver (BTS7960)
| ESP32 Pin | BTS7960 Pin | Function |
|---|---|---|
| `GPIO 32` | RPWM | Forward PWM |
| `GPIO 33` | LPWM | Reverse PWM |
| `GPIO 18` | R_EN | Forward Enable |
| `GPIO 19` | L_EN | Reverse Enable |

### 3. Sensors & Safety
| ESP32 Pin | Device | Function |
|---|---|---|
| `GPIO 12` / `GPIO 13` | HC-SR04 Front | TRIG / ECHO |
| `GPIO 4` / `GPIO 16` | HC-SR04 Left | TRIG / ECHO |
| `GPIO 17` / `GPIO 5` | HC-SR04 Right | TRIG / ECHO |
| `GPIO 23` / `GPIO 22` | HX711 Load Cell | DOUT / SCK |
| `GPIO 34` | Voltage Divider | Battery 12V ADC input |
| `GPIO 35` | Emergency Stop | Active LOW push button |

---

## 🛠️ Working with VS Code

### Recommended Extensions
When opening this folder in VS Code, install the recommended extensions:
1. **PlatformIO IDE** (`platformio.platformio-ide`) — For building and flashing ESP32 firmware.
2. **C/C++** (`ms-vscode.cpptools`) — Code intelligence and syntax highlighting.
3. **Python** (`ms-python.python`) — For running Pi and serial test scripts.
4. **GitLens** (`eamodio.gitlens`) — Visual git tracking and blame.

### Building & Uploading
1. Open this folder in VS Code (`File` > `Open Folder...` > Select `Food_Delivary_Robot_firmware`).
2. Click the **PlatformIO** alien icon on the left activity bar.
3. Under **Project Tasks > esp32dev**:
   - Click **Build** (`✓`) to compile the firmware.
   - Connect your ESP32 via micro-USB and click **Upload** (`→`) to flash.
   - Click **Serial Monitor** (plug icon) at `115200` baud to view live logs.

---

## 🤖 Connecting with Antigravity

Antigravity operates directly inside your active workspace (`Food delivery Robot`).
- Antigravity can read, modify, and build firmware files directly in `Food_Delivary_Robot_firmware/`.
- You can ask Antigravity to implement new features (PID speed tuning, encoder tracking, MQTT bridge) and commit them automatically.

---

## 🔄 Git Workflow & Syncing with GitHub

To push your latest work to GitHub:

```bash
# 1. Check changed files
git status

# 2. Stage changes
git add .

# 3. Commit with a descriptive message
git commit -m "feat: added ESP32 firmware, BTS7960 motor driver, and test script"

# 4. Push to GitHub main branch
git push origin main
```

---

## 🧪 Testing Serial Control from Laptop / Pi

You can test motor movements without a Raspberry Pi using your laptop:

```bash
cd pi
pip install -r requirements.txt
python test_serial.py
```

Select your ESP32's COM port, then use:
- `w` / `s`: Forward / Reverse
- `a` / `d`: Turn Left / Turn Right
- `space`: Stop
- `e`: Emergency Stop
