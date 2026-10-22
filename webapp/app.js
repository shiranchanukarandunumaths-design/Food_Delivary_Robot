// Campus Mission Control Frontend
const API_BASE = "http://127.0.0.1:8000/api";

// Default Center: UOC Faculty of Science
const DEFAULT_CENTER = [6.90175, 79.86050];
const DEFAULT_ZOOM = 19;

let map;
let robotMarker = null;
let activeRoutePolyline = null;
let edgeLines = [];
let nodesData = [];

// Initialize Map
function initMap() {
  map = L.map('map', {
    maxZoom: 22
  }).setView(DEFAULT_CENTER, DEFAULT_ZOOM);

  // Satellite layer (Esri World Imagery)
  const esriSat = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
    attribution: 'Tiles &copy; Esri &mdash; Source: Esri, i-cubed, USDA, USGS, AEX, GeoEye, Getmapping, Aerogrid, IGN, IGP, UPR-EGP, and the GIS User Community',
    maxZoom: 21
  });

  // Standard OpenStreetMap layer
  const osm = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}.png', {
    attribution: '&copy; OpenStreetMap contributors',
    maxZoom: 19
  });

  esriSat.addTo(map);

  L.control.layers({
    "Satellite (Esri)": esriSat,
    "Street Map (OSM)": osm
  }).addTo(map);

  // Custom Robot Icon
  const robotIcon = L.divIcon({
    className: 'robot-pin',
    html: '<div style="font-size: 26px; transform: translate(-13px, -13px);">🤖</div>',
    iconSize: [26, 26]
  });

  robotMarker = L.marker(DEFAULT_CENTER, { icon: robotIcon }).addTo(map);
  robotMarker.bindPopup("<strong>Delivery Robot #1</strong><br>Status: Ready");
}

// Check Backend Connection & Load Campus
async function loadCampus() {
  const apiStatus = document.getElementById('api-status');
  try {
    const res = await fetch(`${API_BASE}/nodes`);
    if (!res.ok) throw new Error("Backend HTTP error");
    nodesData = await res.json();
    apiStatus.textContent = "ONLINE";
    apiStatus.className = "pill online";

    renderNodes(nodesData);
    populateSelects(nodesData);
    loadEdges();
  } catch (err) {
    console.warn("Backend not yet running, loading fallback nodes...", err);
    apiStatus.textContent = "STANDBY";
    apiStatus.className = "pill offline";
    loadFallbackData();
  }
}

// Fallback data when backend is not running yet
function loadFallbackData() {
  const fallbackNodes = [
    { id: 1, name: "Faculty Main Gate (Reid Ave)", lat: 6.90150, lng: 79.86005, type: "entry_point" },
    { id: 2, name: "Science Quadrangle Junction", lat: 6.90175, lng: 79.86050, type: "junction" },
    { id: 3, name: "Department of Physics (PH 3042)", lat: 6.90210, lng: 79.86060, type: "destination" },
    { id: 4, name: "Department of Chemistry", lat: 6.90190, lng: 79.86120, type: "destination" },
    { id: 5, name: "Science Faculty Library", lat: 6.90140, lng: 79.86110, type: "destination" },
    { id: 6, name: "Faculty Canteen / Cafeteria", lat: 6.90120, lng: 79.86060, type: "pickup_point" },
    { id: 7, name: "Department of Mathematics", lat: 6.90230, lng: 79.86100, type: "destination" }
  ];
  nodesData = fallbackNodes;
  renderNodes(fallbackNodes);
  populateSelects(fallbackNodes);
}

function renderNodes(nodes) {
  nodes.forEach(n => {
    let color = "#38bdf8"; // default blue
    if (n.type === "pickup_point") color = "#f59e0b"; // yellow/orange
    if (n.type === "destination") color = "#10b981"; // green
    if (n.type === "junction") color = "#a855f7"; // purple

    const marker = L.circleMarker([n.lat, n.lng], {
      radius: 8,
      fillColor: color,
      color: "#ffffff",
      weight: 2,
      opacity: 1,
      fillOpacity: 0.9
    }).addTo(map);

    marker.bindPopup(`<strong>${n.name}</strong><br>Type: ${n.type}`);
  });
}

function populateSelects(nodes) {
  const pickupSel = document.getElementById('pickup-select');
  const destSel = document.getElementById('dest-select');

  pickupSel.innerHTML = '<option value="" disabled selected>Select Pickup...</option>';
  destSel.innerHTML = '<option value="" disabled selected>Select Destination...</option>';

  nodes.forEach(n => {
    const optP = new Option(n.name, n.id);
    const optD = new Option(n.name, n.id);
    pickupSel.add(optP);
    destSel.add(optD);
  });

  // Default Canteen -> Physics for easy testing
  pickupSel.value = "6";
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
          dashArray: '4, 8',
          opacity: 0.6
        }).addTo(map);
        edgeLines.push(poly);
      }
    });
  } catch (err) {
    console.error("Error loading edges", err);
  }
}

// Handle Order Dispatch
document.getElementById('order-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const pickupId = parseInt(document.getElementById('pickup-select').value);
  const destId = parseInt(document.getElementById('dest-select').value);
  const recipient = document.getElementById('recipient-name').value;

  if (pickupId === destId) {
    alert("Pickup and Destination cannot be the same!");
    return;
  }

  try {
    const res = await fetch(`${API_BASE}/orders`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        pickup_node_id: pickupId,
        dest_node_id: destId,
        user_name: recipient
      })
    });

    if (!res.ok) throw new Error("Order creation failed");
    const order = await res.json();

    displayMission(order);
  } catch (err) {
    console.warn("Using offline route preview:", err);
    previewOfflineRoute(pickupId, destId);
  }
});

function displayMission(order) {
  const card = document.getElementById('mission-card');
  card.style.display = 'block';
  document.getElementById('mission-code').textContent = order.order_code;
  document.getElementById('mission-pts').textContent = order.waypoints ? order.waypoints.length : 0;

  if (order.waypoints && order.waypoints.length > 0) {
    const latlngs = order.waypoints.map(p => [p.lat, p.lng]);
    if (activeRoutePolyline) map.removeLayer(activeRoutePolyline);

    activeRoutePolyline = L.polyline(latlngs, {
      color: '#10b981',
      weight: 5,
      opacity: 0.9
    }).addTo(map);

    map.fitBounds(activeRoutePolyline.getBounds(), { padding: [40, 40] });
  }
}

function previewOfflineRoute(pickupId, destId) {
  const pNode = nodesData.find(n => n.id === pickupId);
  const dNode = nodesData.find(n => n.id === destId);
  if (!pNode || !dNode) return;

  const card = document.getElementById('mission-card');
  card.style.display = 'block';
  document.getElementById('mission-code').textContent = "ORD-OFFLINE";
  document.getElementById('mission-pts').textContent = "2 (Direct Preview)";

  const latlngs = [[pNode.lat, pNode.lng], [dNode.lat, dNode.lng]];
  if (activeRoutePolyline) map.removeLayer(activeRoutePolyline);

  activeRoutePolyline = L.polyline(latlngs, {
    color: '#10b981',
    weight: 4,
    dashArray: '6, 6'
  }).addTo(map);

  map.fitBounds(activeRoutePolyline.getBounds(), { padding: [30, 30] });
}

// Telemetry Polling (every 1 second)
async function pollTelemetry() {
  try {
    const res = await fetch(`${API_BASE}/robot/status`);
    if (res.ok) {
      const data = await res.json();
      if (data) {
        document.getElementById('tele-battery').textContent = `${data.battery_v.toFixed(1)} V`;
        document.getElementById('tele-load').textContent = `${data.load_g} g`;
        document.getElementById('tele-speed').textContent = `${data.speed_mps.toFixed(2)} m/s`;
        document.getElementById('tele-heading').textContent = `${Math.round(data.heading)}°`;

        const pill = document.getElementById('robot-status-pill');
        pill.textContent = data.state;
        pill.className = `pill ${data.state.toLowerCase()}`;

        if (robotMarker && data.lat && data.lng) {
          robotMarker.setLatLng([data.lat, data.lng]);
        }
      }
    }
  } catch (e) {
    // Backend offline
  }
}

// Manual Teleop
function sendTeleop(cmd) {
  console.log("Teleop Command:", cmd);
  // Can be posted to /api/robot/teleop or sent over MQTT/WebSocket
}

window.addEventListener('DOMContentLoaded', () => {
  initMap();
  loadCampus();
  setInterval(pollTelemetry, 1000);
});
