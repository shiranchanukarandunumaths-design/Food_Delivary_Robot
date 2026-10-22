"""
Interactive Serial Test Client for ESP32 Robot Firmware
Tests the serial protocol contract: DRIVE, STOP, ESTOP, STATUS.
Works on Windows (COMx) and Linux/Raspberry Pi (/dev/ttyUSBx or /dev/ttyACMx).
"""

import time
import sys
import serial
import serial.tools.list_ports

def find_serial_port():
    ports = list(serial.tools.list_ports.comports())
    if not ports:
        print("No serial ports found. Connect ESP32 via USB.")
        return None
    print("Available serial ports:")
    for idx, p in enumerate(ports):
        print(f"  [{idx}] {p.device} - {p.description}")
    choice = input(f"Select port [0-{len(ports)-1}] (default 0): ").strip()
    idx = int(choice) if choice.isdigit() and int(choice) < len(ports) else 0
    return ports[idx].device

def main():
    port = sys.argv[1] if len(sys.argv) > 1 else find_serial_port()
    if not port:
        return

    baud = 115200
    print(f"Connecting to {port} at {baud} baud...")

    try:
        ser = serial.Serial(port, baud, timeout=0.1)
        time.sleep(2)  # Wait for ESP32 reset after serial connection
        print("Connected! Type commands:")
        print("  w -> Forward (DRIVE,120,120)")
        print("  s -> Reverse (DRIVE,-120,-120)")
        print("  a -> Left Turn (DRIVE,-100,100)")
        print("  d -> Right Turn (DRIVE,100,-100)")
        print("  space / x -> Stop (STOP)")
        print("  e -> Emergency Stop (ESTOP)")
        print("  r -> Reset E-Stop (RESET_ESTOP)")
        print("  q -> Quit")
        print("-" * 50)

        while True:
            # Print incoming telemetry
            if ser.in_waiting:
                line = ser.readline().decode('utf-8', errors='ignore').strip()
                if line:
                    print(f"ESP32 -> {line}")

            # Check keyboard input if non-blocking (or simple prompt)
            cmd = input("cmd> ").strip().lower()
            if cmd == 'q':
                ser.write(b"STOP\n")
                break
            elif cmd == 'w':
                ser.write(b"DRIVE,120,120\n")
            elif cmd == 's':
                ser.write(b"DRIVE,-120,-120\n")
            elif cmd == 'a':
                ser.write(b"DRIVE,-100,100\n")
            elif cmd == 'd':
                ser.write(b"DRIVE,100,-100\n")
            elif cmd in [' ', 'x', 'stop']:
                ser.write(b"STOP\n")
            elif cmd in ['e', 'estop']:
                ser.write(b"ESTOP\n")
            elif cmd in ['r', 'reset']:
                ser.write(b"RESET_ESTOP\n")
            elif cmd:
                # Send raw command with newline
                ser.write(f"{cmd}\n".encode('utf-8'))

    except KeyboardInterrupt:
        print("\nExiting...")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        if 'ser' in locals() and ser.is_open:
            ser.write(b"STOP\n")
            ser.close()

if __name__ == "__main__":
    main()
