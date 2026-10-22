"""
Autonomous Food & Parcel Delivery Robot Simulator
PH 3042 - Robotics & Automation (University of Colombo)

Simulates the complete delivery lifecycle:
1. Polls backend for highest priority order (Emergency orders first!)
2. Collects item at pickup point (Main Gate / Canteen), loads weight on load cell
3. Starts trip, smoothly interpolating GPS waypoints at realistic speeds
4. Publishes live telemetry, heading, battery, and path situation messages
5. Arrives at user's destination ("landed"), prompts collection, unloads weight, and completes order
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

# Distance between two lat/lng in meters (Haversine formula)
def haversine_dist(lat1, lon1, lat2, lon2):
    R = 6371000  # Earth radius in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = math.sin(delta_phi / 2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

# Bearing between two coordinates in degrees (0-360)
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
    except Exception as e:
        # print(f"POST {endpoint} error: {e}")
        return None

def patch_order_status(order_id: int, status: str, situation: str, progress: float):
    try:
        url = f"{API_BASE}/orders/{order_id}/status?status={status}&situation_msg={urllib.parse.quote(situation)}&progress_percent={progress:.1f}"
        req = urllib.request.Request(url, method='PATCH')
        with urllib.request.urlopen(req, timeout=3) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        # print(f"PATCH status error: {e}")
        return None

def get_active_order() -> Optional[dict]:
    try:
        url = f"{API_BASE}/orders/active"
        with urllib.request.urlopen(url, timeout=3) as resp:
            data = json.loads(resp.read().decode())
            return data
    except Exception:
        return None

def send_telemetry(lat, lng, heading, speed, battery, load, state, situation, order_id=None):
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
        "situation_msg": situation
    }
    post_json("/robot/telemetry", payload)

def run_simulation():
    print("=" * 65)
    print("🤖 AUTONOMOUS ROVER SIMULATOR (PH 3042 - University of Colombo)")
    print("Connecting to backend at:", API_BASE)
    print("=" * 65)

    current_lat = 6.90150 # Main Gate
    current_lng = 79.86005
    battery_v = 12.4
    load_cell_g = 0

    while True:
        # 1. Standby / Wait for an order
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
                situation="Rover standing by at Faculty Main Gate. Waiting for orders..."
            )
            time.sleep(2)
            continue

        order_id = order["id"]
        order_code = order["order_code"]
        item_type = order.get("item_type", "Food")
        is_emergency = order.get("is_emergency", False)
        waypoints = order.get("waypoints", [])

        if not waypoints or len(waypoints) < 2:
            print(f"Order {order_code} has insufficient waypoints. Skipping.")
            time.sleep(2)
            continue

        print(f"\n🚀 DISPATCHING MISSION: {order_code}")
        print(f"📦 Cargo: {item_type} | 🚨 Emergency: {is_emergency} | 📍 Waypoints: {len(waypoints)}")

        # Step 1: Package Collection at Pickup Point
        pkg_weight = 2400 if item_type == "Lab Equipment" else (1600 if item_type == "Drinks" else 950)
        collect_msg = f"Collecting {item_type} at Main Gate... Placing {pkg_weight}g package on rover cargo bay."
        print(f"\n[PHASE 1] {collect_msg}")
        patch_order_status(order_id, "COLLECTING", collect_msg, 0.0)
        load_cell_g = pkg_weight

        for _ in range(3):
            send_telemetry(current_lat, current_lng, 0.0, 0.0, battery_v, load_cell_g, "COLLECTING", collect_msg, order_id)
            time.sleep(1)

        # Step 2: Trip Start
        trip_start_msg = f"Package secured ({load_cell_g}g). {'🚨 EMERGENCY FAST-TRACK ACTIVE!' if is_emergency else 'Standard cruise speed.'} Starting route."
        print(f"\n[PHASE 2] {trip_start_msg}")
        patch_order_status(order_id, "EN_ROUTE", trip_start_msg, 5.0)

        # Calculate total mission path distance
        total_mission_dist = 0.0
        for i in range(len(waypoints) - 1):
            total_mission_dist += haversine_dist(
                waypoints[i]["lat"], waypoints[i]["lng"],
                waypoints[i+1]["lat"], waypoints[i+1]["lng"]
            )
        traveled_dist = 0.0

        # Step 3: Traverse Waypoints with Smooth Interpolation
        step_interval = 0.6 # seconds between updates
        speed_mps = 1.3 if is_emergency else 0.75 # faster for emergency!

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

                # Generate contextual situation message
                if progress < 25:
                    situation = f"Cruising along Main Entrance Corridor toward Science Quadrangle. Path clear."
                elif progress < 55:
                    situation = f"Navigating through Science Quadrangle Junction. Ultrasonic sonar checking for pedestrians."
                elif progress < 85:
                    situation = f"En route on Department walkway. Approaching destination zone."
                else:
                    situation = f"Slow speed final approach to user location. Preparing to land cargo."

                if is_emergency:
                    situation = "🚨 [URGENT DELIVERY] " + situation

                # Battery slight drain
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
                    order_id=order_id
                )
                patch_order_status(order_id, "EN_ROUTE", situation, progress)

                print(f"  -> [{progress:4.1f}%] Lat: {current_lat:.5f}, Lng: {current_lng:.5f} | Head: {bearing:4.0f}° | Speed: {speed_mps:.2f} m/s | {situation[:45]}...")
                time.sleep(step_interval)

            traveled_dist += segment_dist

        # Step 4: Arrived at Destination ("Landed")
        arrival_msg = f"🎉 ARRIVED! Rover #1 has landed at user's destination. Please collect your {item_type}!"
        print(f"\n[PHASE 3] {arrival_msg}")
        patch_order_status(order_id, "ARRIVED", arrival_msg, 100.0)

        # Notify arrival and wait 6 seconds for user collection
        for countdown in range(6, 0, -1):
            prompt_msg = f"🎉 ARRIVED! Please take your package from the cargo tray ({countdown}s)..."
            send_telemetry(current_lat, current_lng, 0.0, 0.0, battery_v, load_cell_g, "ARRIVED", prompt_msg, order_id)
            time.sleep(1)

        # Step 5: Unload Package
        load_cell_g = 0 # Weight removed by user!
        delivered_msg = f"Cargo unloaded (0g on load cell). {item_type} successfully delivered to user!"
        print(f"\n[PHASE 4] {delivered_msg}")
        patch_order_status(order_id, "DELIVERED", delivered_msg, 100.0)
        send_telemetry(current_lat, current_lng, 0.0, 0.0, battery_v, load_cell_g, "IDLE", delivered_msg, order_id)

        print(f"✅ MISSION COMPLETE for {order_code}!\n")
        time.sleep(3)

if __name__ == "__main__":
    run_simulation()
