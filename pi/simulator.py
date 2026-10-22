"""
Autonomous Food & Parcel Delivery Robot Simulator
PH 3042 - Robotics & Automation (University of Colombo)

Simulates the complete delivery lifecycle:
1. Polls backend for highest priority order (Emergency orders first!)
2. Collects item at pickup point (Main Gate / Canteen), loads weight on load cell, LOCKS container
3. Starts trip, smoothly interpolating GPS waypoints along trained roads at realistic speeds
4. Publishes live telemetry, heading, battery, and path situation messages
5. Arrives at user's destination ("landed")
6. WAITS FOR SECURE QR CODE MATCH: Container stays locked until QR is scanned/verified!
7. Once QR verified -> Unlocks container, user collects package (weight -> 0g), completes order
"""

import time
import math
import json
import sys
import urllib.request
import urllib.error
import urllib.parse
from typing import List, Dict, Optional

# Ensure UTF-8 output on Windows terminals
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

API_BASE = "http://127.0.0.1:8000/api"

def haversine_dist(lat1, lon1, lat2, lon2):
    R = 6371000.0  # Earth radius in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = math.sin(delta_phi / 2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def calculate_bearing(lat1, lon1, lat2, lon2):
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_lambda = math.radians(lon2 - lon1)

    y = math.sin(delta_lambda) * math.cos(phi2)
    x = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(delta_lambda)
    initial_bearing = math.atan2(y, x)
    degrees = (math.degrees(initial_bearing) + 360) % 360
    return degrees

def post_json(endpoint: str, data: dict):
    try:
        url = f"{API_BASE}{endpoint}"
        req = urllib.request.Request(
            url, 
            data=json.dumps(data).encode('utf-8'),
            headers={'Content-Type': 'application/json'},
            method='POST'
        )
        with urllib.request.urlopen(req, timeout=3) as resp:
            return json.loads(resp.read().decode())
    except Exception:
        return None

def patch_order_status(order_id: int, status: str, situation: str, progress: float, container_locked: bool = True):
    try:
        locked_param = "true" if container_locked else "false"
        url = f"{API_BASE}/orders/{order_id}/status?status={status}&situation_msg={urllib.parse.quote(situation)}&progress_percent={progress:.1f}&container_locked={locked_param}"
        req = urllib.request.Request(url, method='PATCH')
        with urllib.request.urlopen(req, timeout=3) as resp:
            return json.loads(resp.read().decode())
    except Exception:
        return None

def get_active_order() -> Optional[dict]:
    try:
        url = f"{API_BASE}/orders/active"
        with urllib.request.urlopen(url, timeout=3) as resp:
            data = json.loads(resp.read().decode())
            return data
    except Exception:
        return None

def check_order_lock_status(order_id: int) -> Optional[dict]:
    try:
        url = f"{API_BASE}/orders"
        with urllib.request.urlopen(url, timeout=3) as resp:
            orders = json.loads(resp.read().decode())
            for o in orders:
                if o["id"] == order_id:
                    return o
    except Exception:
        pass
    return None

def send_telemetry(lat, lng, heading, speed, battery, load, state, situation, locked=True, order_id=None):
    payload = {
        "robot_id": 1,
        "current_order_id": order_id,
        "lat": lat,
        "lng": lng,
        "heading": heading,
        "speed_mps": speed,
        "battery_v": battery,
        "load_g": load,
        "state": state,
        "situation_msg": situation,
        "container_locked": locked
    }
    post_json("/robot/telemetry", payload)

def run_simulation():
    print("=" * 65)
    print("🤖 AUTONOMOUS ROVER SIMULATOR (PH 3042 - University of Colombo)")
    print("Connecting to backend at:", API_BASE)
    print("Features: Dynamic Roads + QR Verified Container Lock")
    print("=" * 65)

    current_lat = 6.90150
    current_lng = 79.86005
    battery_v = 12.4
    load_cell_g = 0
    container_locked = True

    while True:
        order = get_active_order()
        if not order:
            send_telemetry(
                lat=current_lat, 
                lng=current_lng, 
                heading=0.0, 
                speed=0.0, 
                battery=battery_v, 
                load=load_cell_g, 
                state="IDLE", 
                situation="Rover standby at Faculty Main Gate. Waiting for orders...",
                locked=True
            )
            time.sleep(2)
            continue

        order_id = order["id"]
        order_code = order["order_code"]
        item_type = order.get("item_type", "Food")
        is_emergency = order.get("is_emergency", False)
        waypoints = order.get("waypoints", [])
        qr_code = order.get("qr_unlock_code", "UNKNOWN")
        pin_code = order.get("pin_code", "123456")

        if not waypoints or len(waypoints) < 2:
            time.sleep(2)
            continue

        print(f"\n🚀 DISPATCHING MISSION: {order_code}")
        print(f"📦 Cargo: {item_type} | 🚨 Emergency: {is_emergency} | 🔑 PIN: {pin_code} | QR: {qr_code[:18]}...")
        print(f"📍 Trained Road Waypoints: {len(waypoints)}")

        # Step 1: Package Collection & Container Lock
        pkg_weight = 2400 if item_type == "Lab Equipment" else (1600 if item_type == "Drinks" else 950)
        collect_msg = f"Collecting {item_type} at Main Gate. Placing {pkg_weight}g in cargo bay and LOCKING container hatch."
        print(f"\n[PHASE 1] {collect_msg}")
        container_locked = True
        patch_order_status(order_id, "COLLECTING", collect_msg, 0.0, container_locked=True)
        load_cell_g = pkg_weight

        for _ in range(3):
            send_telemetry(current_lat, current_lng, 0.0, 0.0, battery_v, load_cell_g, "COLLECTING", collect_msg, locked=True, order_id=order_id)
            time.sleep(1)

        # Step 2: Trip Start
        trip_start_msg = f"Container locked. Starting trip to user location. {'🚨 EMERGENCY FAST-TRACK ACTIVE!' if is_emergency else 'Standard cruise speed.'}"
        print(f"\n[PHASE 2] {trip_start_msg}")
        patch_order_status(order_id, "EN_ROUTE", trip_start_msg, 5.0, container_locked=True)

        total_mission_dist = 0.0
        for i in range(len(waypoints) - 1):
            total_mission_dist += haversine_dist(
                waypoints[i]["lat"], waypoints[i]["lng"],
                waypoints[i+1]["lat"], waypoints[i+1]["lng"]
            )
        traveled_dist = 0.0

        step_interval = 0.6
        speed_mps = 1.3 if is_emergency else 0.75

        # Step 3: Travel through trained road waypoints
        for idx in range(len(waypoints) - 1):
            w_start = waypoints[idx]
            w_end = waypoints[idx + 1]

            segment_dist = haversine_dist(w_start["lat"], w_start["lng"], w_end["lat"], w_end["lng"])
            if segment_dist < 0.1:
                continue

            bearing = calculate_bearing(w_start["lat"], w_start["lng"], w_end["lat"], w_end["lng"])
            num_steps = max(int((segment_dist / speed_mps) / step_interval), 2)

            for step in range(1, num_steps + 1):
                fraction = step / num_steps
                current_lat = w_start["lat"] + (w_end["lat"] - w_start["lat"]) * fraction
                current_lng = w_start["lng"] + (w_end["lng"] - w_start["lng"]) * fraction

                curr_traveled = traveled_dist + (segment_dist * fraction)
                progress = min((curr_traveled / total_mission_dist) * 100.0, 98.0)

                if progress < 30:
                    situation = "Cruising along trained campus road corridor. Ultrasonic sensor path clear."
                elif progress < 70:
                    situation = "Crossing central Science junction walkway. Speed stabilized."
                else:
                    situation = "Approaching destination area. Reducing speed for landing."

                if is_emergency:
                    situation = "🚨 [URGENT DELIVERY] " + situation

                battery_v = max(battery_v - 0.001, 11.8)

                send_telemetry(
                    lat=current_lat,
                    lng=current_lng,
                    heading=round(bearing, 1),
                    speed=speed_mps,
                    battery=round(battery_v, 2),
                    load=load_cell_g,
                    state="EN_ROUTE",
                    situation=situation,
                    locked=True,
                    order_id=order_id
                )
                patch_order_status(order_id, "EN_ROUTE", situation, progress, container_locked=True)

                print(f"  -> [{progress:4.1f}%] Lat: {current_lat:.5f}, Lng: {current_lng:.5f} | Head: {bearing:4.0f}° | Speed: {speed_mps:.2f} m/s | {situation[:40]}...")
                time.sleep(step_interval)

            traveled_dist += segment_dist

        # Step 4: Arrived at Destination ("Landed") & Lock Wait
        arrival_msg = f"🎉 ARRIVED! Rover #1 has landed at your location. Please scan your Delivery QR code to unlock container."
        print(f"\n[PHASE 3] {arrival_msg}")
        print(f"🔒 Cargo Container is LOCKED. Waiting for user QR scan (PIN: {pin_code})...")
        patch_order_status(order_id, "ARRIVED", arrival_msg, 100.0, container_locked=True)

        # Loop until QR is matched via web application
        unlocked = False
        wait_seconds = 0
        while not unlocked and wait_seconds < 40: # Wait up to 40 seconds, or auto-unlock if simulated
            send_telemetry(
                lat=current_lat, lng=current_lng, heading=0.0, speed=0.0,
                battery=battery_v, load=load_cell_g, state="ARRIVED",
                situation=f"🎉 ARRIVED! Rover landed. Container LOCKED. Displaying QR code on robot screen & web app...",
                locked=True, order_id=order_id
            )
            time.sleep(1.5)
            wait_seconds += 1.5

            # Check if user unlocked on web app
            updated_order = check_order_lock_status(order_id)
            if updated_order and (not updated_order.get("container_locked", True) or updated_order.get("status") == "UNLOCKED"):
                unlocked = True
                print("\n🔓 QR CODE MATCH CONFIRMED FROM USER! Unlocking container solenoid/servo...")
                break

        # If user didn't click within 25 seconds in simulator, auto-trigger unlock test
        if not unlocked:
            print("\n[Simulator Auto-Unlock Test] Simulating successful QR match by recipient...")
            post_json("/orders/unlock", {"order_id": order_id, "unlock_code": qr_code})
            unlocked = True

        # Step 5: Container Unlocked & Cargo Retreived
        unlocked_msg = f"🔓 CONTAINER UNLOCKED! Cargo bay hatch opened. User is retrieving {item_type}."
        print(f"\n[PHASE 4] {unlocked_msg}")
        patch_order_status(order_id, "UNLOCKED", unlocked_msg, 100.0, container_locked=False)
        send_telemetry(current_lat, current_lng, 0.0, 0.0, battery_v, load_cell_g, "UNLOCKED", unlocked_msg, locked=False, order_id=order_id)
        time.sleep(3)

        # User takes package -> Weight drops to 0g
        load_cell_g = 0
        delivered_msg = f"Cargo retrieved (0g on load cell). Container hatch secured. {item_type} delivery complete!"
        print(f"\n[PHASE 5] {delivered_msg}")
        patch_order_status(order_id, "DELIVERED", delivered_msg, 100.0, container_locked=True)
        send_telemetry(current_lat, current_lng, 0.0, 0.0, battery_v, load_cell_g, "IDLE", delivered_msg, locked=True, order_id=order_id)

        print(f"✅ MISSION COMPLETED FOR {order_code}!\n")
        time.sleep(3)

if __name__ == "__main__":
    run_simulation()
