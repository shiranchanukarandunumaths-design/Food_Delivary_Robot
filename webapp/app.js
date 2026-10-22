// Campus Autonomous Delivery Web Dashboard
// PH 3042 - Robotics & Automation (University of Colombo)

const API_BASE = "http://127.0.0.1:8000/api";
const WS_BASE = "ws://127.0.0.1:8000/ws/telemetry";

const DEFAULT_CENTER = [6.90175, 79.86050];
const DEFAULT_ZOOM = 19;

let map;
let robotMarker = null;
let activeRoutePolyline = null;
let edgeLines = [];
let nodesData = [];
let ws = null;
let isAddPointMode = false;

// --- INITIALIZE LEAFLET MAP ---
function initMap() {
  map = L.map('map', {
    maxZoom: 22
  }).setView(DEFAULT_CENTER, DEFAULT_ZOOM);

  // Satellite Imagery Layer (Esri World Imagery)
  const esriSat = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
    attribution: 'Tiles &copy; Esri &mdash; UOC Science Campus',
    maxZoom: 21
  });

  // OpenStreetMap alternative
  const osm = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}.png', {
    attribution: '&copy; OpenStreetMap contributors',
    maxZoom: 19
  });

  esriSat.addTo(map);

  L.control.layers({
    "Satellite (Esri World Imagery)": esriSat,
    "Street Map (OSM)": osm
  }, null, { position: 'topright' }).addTo(map);

  // Custom Animated Rover Icon
  const robotIcon = L.divIcon({
    className: 'rover-marker-icon',
    html: `<div id="rover-inner-icon" style="font-size: 28px; filter: drop-shadow(0 0 6px rgba(56,189,248,0.8)); transform-origin: center; transition: transform 0.4s ease;">🤖</div>`,
    iconSize: [28, 28],
    iconAnchor: [14, 14]
  });

  robotMarker = L.marker(DEFAULT_CENTER, { icon: robotIcon }).addTo(map);
  robotMarker.bindPopup("<strong>Delivery Rover #1</strong><br>Status: Standby at Main Gate");

  // Map Click Listener for Admin Node Placement
  map.on('click', handleMapClick);
}

// --- WEBSOCKET CLIENT FOR LIVE STREAMING ---
function connectWebSocket() {
  const apiStatus = document.getElementById('api-status');

  try {
    ws = new WebSocket(WS_BASE);

    ws.onopen = () => {
      console.log("[WS] Connected to rover telemetry stream");
      apiStatus.textContent = "ONLINE (WS)";
      apiStatus.className = "pill online";
    };

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        if (msg.type === "telemetry") {
          updateRoverTelemetry(msg);
        } else if (msg.type === "order_update") {
          handleOrderUpdate(msg);
        } else if (msg.type === "new_order") {
          loadOrdersQueue();
        }
      } catch (e) {
        console.error("WS Parse error", e);
      }
    };

    ws.onclose = () => {
      apiStatus.textContent = "RECONNECTING";
      apiStatus.className = "pill offline";
      setTimeout(connectWebSocket, 3000);
    };

    ws.onerror = () => {
      apiStatus.textContent = "OFFLINE (HTTP Poll)";
      apiStatus.className = "pill offline";
    };
  } catch (err) {
    console.warn("WebSocket not supported, falling back to HTTP", err);
  }
}

// Update Rover Telemetry from WebSocket or Polling
function updateRoverTelemetry(data) {
  if (!data) return;

  // 1. Move Marker smoothly
  if (robotMarker && data.lat && data.lng) {
    robotMarker.setLatLng([data.lat, data.lng]);
    const iconEl = document.getElementById('rover-inner-icon');
    if (iconEl && data.heading !== undefined) {
      iconEl.style.transform = `rotate(${data.heading}deg)`;
    }
  }

  // 2. Update Telemetry Cards
  if (data.battery_v !== undefined) {
    document.getElementById('tele-battery').textContent = `${data.battery_v.toFixed(1)} V`;
  }
  if (data.load_g !== undefined) {
    document.getElementById('tele-load').textContent = `${data.load_g} g`;
  }
  if (data.speed_mps !== undefined) {
    document.getElementById('tele-speed').textContent = `${data.speed_mps.toFixed(2)} m/s`;
  }
  if (data.heading !== undefined) {
    document.getElementById('tele-heading').textContent = `${Math.round(data.heading)}°`;
  }

  // 3. Rover State Pill
  const pill = document.getElementById('robot-status-pill');
  if (pill && data.state) {
    pill.textContent = data.state;
    pill.className = `pill ${data.state.toLowerCase()}`;
  }

  // 4. Update Live Path Situation Message
  if (data.situation_msg) {
    document.getElementById('situation-text').textContent = data.situation_msg;
  }

  // 5. Handle Arrival Notice ("Landed")
  const arrivalCard = document.getElementById('arrival-card');
  if (data.state === "ARRIVED") {
    arrivalCard.style.display = "block";
    document.getElementById('arrival-msg').textContent = data.situation_msg || "Rover #1 has landed at your location! Please collect your parcel.";
  } else {
    arrivalCard.style.display = "none";
  }
}

function handleOrderUpdate(msg) {
  if (msg.situation_msg) {
    document.getElementById('situation-text').textContent = msg.situation_msg;
  }
  if (msg.progress_percent !== undefined) {
    const bar = document.getElementById('trip-progress-bar');
    const lbl = document.getElementById('trip-progress-label');
    bar.style.width = `${msg.progress_percent}%`;
    lbl.textContent = `${Math.round(msg.progress_percent)}% completed`;
  }
  loadOrdersQueue();
}

// --- LOAD CAMPUS NODES & EDGES ---
async function loadCampus() {
  try {
    const res = await fetch(`${API_BASE}/nodes`);
    if (!res.ok) throw new Error("HTTP " + res.status);
    nodesData = await res.json();
    renderNodes(nodesData);
    populateSelects(nodesData);
    loadEdges();
    loadOrdersQueue();
  } catch (err) {
    console.warn("Backend API offline, using cached fallback...", err);
    loadFallbackData();
  }
}

function loadFallbackData() {
  nodesData = [
    { id: 1, name: "Faculty Main Gate (Reid Ave)", lat: 6.90150, lng: 79.86005, type: "entry_point" },
    { id: 2, name: "Science Quadrangle Junction", lat: 6.90175, lng: 79.86050, type: "junction" },
    { id: 3, name: "Department of Physics (PH 3042)", lat: 6.90210, lng: 79.86060, type: "destination" },
    { id: 4, name: "Department of Chemistry", lat: 6.90190, lng: 79.86120, type: "destination" },
    { id: 5, name: "Science Faculty Library", lat: 6.90140, lng: 79.86110, type: "destination" },
    { id: 6, name: "Faculty Canteen / Cafeteria", lat: 6.90120, lng: 79.86060, type: "pickup_point" },
    { id: 7, name: "Department of Mathematics", lat: 6.90230, lng: 79.86100, type: "destination" }
  ];
  renderNodes(nodesData);
  populateSelects(nodesData);
}

function renderNodes(nodes) {
  nodes.forEach(n => {
    let color = "#38bdf8";
    if (n.type === "pickup_point") color = "#f59e0b";
    if (n.type === "destination") color = "#10b981";
    if (n.type === "junction") color = "#a855f7";

    const marker = L.circleMarker([n.lat, n.lng], {
      radius: 9,
      fillColor: color,
      color: "#ffffff",
      weight: 2,
      opacity: 1,
      fillOpacity: 0.95
    }).addTo(map);

    marker.bindPopup(`<strong>${n.name}</strong><br>Type: ${n.type}`);
  });
}

function populateSelects(nodes) {
  const pickupSel = document.getElementById('pickup-select');
  const destSel = document.getElementById('dest-select');

  pickupSel.innerHTML = '';
  destSel.innerHTML = '<option value="" disabled selected>Select Your Destination...</option>';

  nodes.forEach(n => {
    const optP = new Option(n.name, n.id);
    const optD = new Option(n.name, n.id);
    pickupSel.add(optP);
    if (n.type === "destination" || n.type === "junction") {
      destSel.add(optD);
    }
  });

  // Default: Pickup at Main Gate (1), Destination at Physics Dept (3)
  pickupSel.value = "1";
  destSel.value = "3";
}

async function loadEdges() {
  try {
    const res = await fetch(`${API_BASE}/edges`);
    if (!res.ok) return;
    const edges = await res.json();

    edges.forEach(e => {
      if (e.waypoints && e.waypoints.length > 0) {
        const latlngs = e.waypoints.map(p => [p.lat, p.lng]);
        const poly = L.polyline(latlngs, {
          color: '#38bdf8',
          weight: 3,
          dashArray: '5, 8',
          opacity: 0.55
        }).addTo(map);
        edgeLines.push(poly);
      }
    });
  } catch (err) {
    console.error("Error loading edges", err);
  }
}

// --- ORDER DISPATCH HANDLER ---
document.getElementById('order-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const pickupId = parseInt(document.getElementById('pickup-select').value);
  const destId = parseInt(document.getElementById('dest-select').value);
  const recipient = document.getElementById('recipient-name').value;
  const phone = document.getElementById('recipient-phone').value;
  const itemType = document.getElementById('item-variety').value;
  const isEmergency = document.getElementById('emergency-check').checked;

  if (pickupId === destId) {
    alert("Pickup and Destination cannot be the same place!");
    return;
  }

  const payload = {
    user_name: recipient,
    user_phone: phone,
    pickup_node_id: pickupId,
    dest_node_id: destId,
    item_type: itemType,
    is_emergency: isEmergency
  };

  try {
    const res = await fetch(`${API_BASE}/orders`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });

    if (!res.ok) throw new Error("Order creation failed");
    const order = await res.json();

    // Draw Route on Satellite Map
    displayPlannedRoute(order);
    loadOrdersQueue();

    // Notify user
    document.getElementById('situation-text').textContent = order.situation_msg;
  } catch (err) {
    console.warn("Order submission fallback", err);
  }
});

function displayPlannedRoute(order) {
  if (order.waypoints && order.waypoints.length > 0) {
    const latlngs = order.waypoints.map(p => [p.lat, p.lng]);
    if (activeRoutePolyline) map.removeLayer(activeRoutePolyline);

    const lineColor = order.is_emergency ? '#ef4444' : '#10b981';

    activeRoutePolyline = L.polyline(latlngs, {
      color: lineColor,
      weight: 6,
      opacity: 0.95
    }).addTo(map);

    map.fitBounds(activeRoutePolyline.getBounds(), { padding: [50, 50] });
  }
}

// --- LOAD PRIORITY QUEUE ---
async function loadOrdersQueue() {
  const container = document.getElementById('orders-queue-list');
  try {
    const res = await fetch(`${API_BASE}/orders?limit=10`);
    if (!res.ok) return;
    const orders = await res.json();

    if (orders.length === 0) {
      container.innerHTML = '<p class="muted-text">No active orders in queue.</p>';
      return;
    }

    container.innerHTML = '';
    orders.forEach(o => {
      const isEmg = o.is_emergency;
      const itemEl = document.createElement('div');
      itemEl.className = `queue-item ${isEmg ? 'emergency' : ''}`;
      itemEl.innerHTML = `
        <div>
          <strong>${o.order_code}</strong> (${o.item_type})<br>
          <span style="font-size:0.7rem; color:#94a3b8;">${o.status} • To Node #${o.dest_node_id}</span>
        </div>
        <span class="queue-badge ${isEmg ? 'emg' : 'norm'}">${isEmg ? '🚨 RUSH' : 'NORMAL'}</span>
      `;
      container.appendChild(itemEl);
    });
  } catch (err) {
    // console.log("Queue load offline");
  }
}

// --- ADMIN NODE / ROUTE PLACEMENT MODE ---
function toggleAdminPanel() {
  const panel = document.getElementById('admin-panel');
  const icon = document.getElementById('admin-toggle-icon');
  const isHidden = panel.style.display === "none";
  panel.style.display = isHidden ? "block" : "none";
  icon.textContent = isHidden ? "▲" : "▼";
}

function enableAddPointMode() {
  isAddPointMode = !isAddPointMode;
  const btn = document.getElementById('btn-add-point-mode');
  if (isAddPointMode) {
    btn.textContent = "🎯 Click on Map to Place Point (Active)";
    btn.style.background = "#059669";
    map.getContainer().style.cursor = "crosshair";
  } else {
    btn.textContent = "📍 Click Map to Place Point";
    btn.style.background = "#334155";
    map.getContainer().style.cursor = "";
  }
}

async function handleMapClick(e) {
  if (!isAddPointMode) return;

  const lat = parseFloat(e.latlng.lat.toFixed(6));
  const lng = parseFloat(e.latlng.lng.toFixed(6));
  const nameInput = document.getElementById('new-node-name');
  const typeInput = document.getElementById('new-node-type');

  const pointName = nameInput.value.trim() || `Point at ${lat}, ${lng}`;
  const pointCode = "PT_" + Math.random().toString(36).substring(2, 7).toUpperCase();

  const payload = {
    code: pointCode,
    name: pointName,
    lat: lat,
    lng: lng,
    type: typeInput.value
  };

  try {
    const res = await fetch(`${API_BASE}/nodes`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    if (res.ok) {
      alert(`Point "${pointName}" added to campus map!`);
      nameInput.value = '';
      enableAddPointMode();
      loadCampus();
    }
  } catch (err) {
    alert("Error adding point: " + err);
  }
}

// HTTP Fallback Polling (in case WebSocket is closed)
async function fallbackPollTelemetry() {
  if (ws && ws.readyState === WebSocket.OPEN) return;
  try {
    const res = await fetch(`${API_BASE}/robot/status`);
    if (res.ok) {
      const data = await res.json();
      updateRoverTelemetry(data);
    }
  } catch (e) {}
}

window.addEventListener('DOMContentLoaded', () => {
  initMap();
  loadCampus();
  connectWebSocket();
  setInterval(fallbackPollTelemetry, 1500);
  setInterval(loadOrdersQueue, 4000);
});
