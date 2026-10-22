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

// User Account State
let currentUser = null;

// Map & Admin States
let isMapVisible = true;
let isAddPointMode = false;
let isRoadTrainingMode = false;
let trainedRoadPoints = [];
let trainedRoadPolyline = null;

// Current Active Order State
let currentActiveOrder = null;
let qrCodeInstance = null;

// ==========================================
// 1. INITIALIZE LEAFLET SATELLITE MAP
// ==========================================
function initMap() {
  map = L.map('map', { maxZoom: 22 }).setView(DEFAULT_CENTER, DEFAULT_ZOOM);

  // Satellite Imagery Layer (Esri World Imagery)
  const esriSat = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
    attribution: 'Tiles &copy; Esri &mdash; UOC Science Campus',
    maxZoom: 21
  });

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

  // Map Click Listener (for Admin Node placement & Road Waypoint Training)
  map.on('click', handleMapClick);
}

// Optional Map View Toggle
function toggleMapView() {
  const mapContainer = document.getElementById('map-container');
  const btn = document.getElementById('btn-toggle-map');
  const sidebar = document.querySelector('.sidebar');

  isMapVisible = !isMapVisible;
  if (isMapVisible) {
    mapContainer.style.display = 'block';
    sidebar.style.width = '440px';
    sidebar.style.minWidth = '440px';
    btn.textContent = "🗺️ Hide Satellite Map (Compact View)";
    setTimeout(() => { map.invalidateSize(); }, 300);
  } else {
    mapContainer.style.display = 'none';
    sidebar.style.width = '100%';
    sidebar.style.minWidth = '100%';
    btn.textContent = "🗺️ View Delivery Path / Satellite Map";
  }
}

// ==========================================
// 2. USER AUTHENTICATION & SESSIONS
// ==========================================
function loadUserSession() {
  const stored = localStorage.getItem("rover_user");
  if (stored) {
    try {
      currentUser = JSON.parse(stored);
    } catch (e) {
      currentUser = null;
    }
  }

  if (!currentUser) {
    // Default account for quick demo
    currentUser = {
      email: "hiruna@gmail.com",
      full_name: "Hiruna Perera",
      student_id: "SC/2022/10452",
      phone: "0771234567",
      department: "Department of Physics",
      role: "student"
    };
    localStorage.setItem("rover_user", JSON.stringify(currentUser));
  }

  updateUserBadge();
}

function updateUserBadge() {
  const badgeText = document.getElementById('user-name-display');
  if (currentUser) {
    badgeText.textContent = `${currentUser.full_name.split(' ')[0]} (${currentUser.department || 'Student'})`;
  } else {
    badgeText.textContent = "Sign In";
  }
}

function openAuthModal() {
  document.getElementById('auth-modal').style.display = 'flex';
}

function closeAuthModal() {
  document.getElementById('auth-modal').style.display = 'none';
}

function switchAuthTab(tab) {
  const tabLogin = document.getElementById('tab-login');
  const tabReg = document.getElementById('tab-register');
  const formLogin = document.getElementById('login-form');
  const formReg = document.getElementById('register-form');

  if (tab === 'login') {
    tabLogin.classList.add('active');
    tabReg.classList.remove('active');
    formLogin.style.display = 'block';
    formReg.style.display = 'none';
  } else {
    tabReg.classList.add('active');
    tabLogin.classList.remove('active');
    formReg.style.display = 'block';
    formLogin.style.display = 'none';
  }
}

async function handleLogin(e) {
  e.preventDefault();
  const email = document.getElementById('login-email').value.trim();
  const password = document.getElementById('login-password').value;

  try {
    const res = await fetch(`${API_BASE}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password })
    });
    if (!res.ok) throw new Error("Invalid email or password");
    currentUser = await res.json();
    localStorage.setItem("rover_user", JSON.stringify(currentUser));
    updateUserBadge();
    closeAuthModal();
    alert(`Welcome back, ${currentUser.full_name}!`);
  } catch (err) {
    alert(err.message);
  }
}

async function handleRegister(e) {
  e.preventDefault();
  const email = document.getElementById('reg-email').value.trim();
  const password = document.getElementById('reg-password').value;
  const fullName = document.getElementById('reg-name').value.trim();
  const studentId = document.getElementById('reg-studentid').value.trim();
  const phone = document.getElementById('reg-phone').value.trim();
  const dept = document.getElementById('reg-dept').value.trim();

  try {
    const res = await fetch(`${API_BASE}/auth/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email,
        password,
        full_name: fullName,
        student_id: studentId,
        phone,
        department: dept
      })
    });
    if (!res.ok) {
      const data = await res.json();
      throw new Error(data.detail || "Registration failed");
    }
    currentUser = await res.json();
    localStorage.setItem("rover_user", JSON.stringify(currentUser));
    updateUserBadge();
    closeAuthModal();
    alert(`Account created successfully for ${currentUser.full_name}!`);
  } catch (err) {
    alert(err.message);
  }
}

// Close modal when clicking outside box
window.onclick = function(event) {
  const modal = document.getElementById('auth-modal');
  if (event.target === modal) {
    closeAuthModal();
  }
};

// ==========================================
// 3. WEBSOCKET FOR REAL-TIME TELEMETRY & QR
// ==========================================
function connectWebSocket() {
  const apiStatus = document.getElementById('api-status');

  try {
    ws = new WebSocket(WS_BASE);

    ws.onopen = () => {
      console.log("[WS] Telemetry connected");
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
        } else if (msg.type === "container_unlocked") {
          handleContainerUnlocked(msg);
        } else if (msg.type === "new_order" || msg.type === "road_network_updated") {
          loadCampus();
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
      apiStatus.textContent = "OFFLINE (HTTP)";
      apiStatus.className = "pill offline";
    };
  } catch (err) {
    console.warn("WebSocket fallback", err);
  }
}

function updateRoverTelemetry(data) {
  if (!data) return;

  // 1. Move Marker smoothly & rotate icon
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

  // 4. Container Lock Pill
  const lockPill = document.getElementById('container-lock-pill');
  if (lockPill && data.container_locked !== undefined) {
    if (data.container_locked) {
      lockPill.textContent = "🔒 LOCKED";
      lockPill.className = "pill locked";
    } else {
      lockPill.textContent = "🔓 UNLOCKED";
      lockPill.className = "pill unlocked";
    }
  }

  // 5. Update Live Path Situation Message
  if (data.situation_msg) {
    document.getElementById('situation-text').textContent = data.situation_msg;
  }

  // 6. Arrival & QR Display
  const arrivalCard = document.getElementById('arrival-card');
  if (data.state === "ARRIVED") {
    arrivalCard.style.display = "block";
    document.getElementById('arrival-msg').textContent = data.situation_msg || "Rover #1 has arrived at your destination! Cargo container is locked. Match QR code below to unlock.";
    
    // Render QR if active order
    if (currentActiveOrder && currentActiveOrder.qr_unlock_code) {
      renderQRCode(currentActiveOrder.qr_unlock_code, currentActiveOrder.pin_code);
    }
  } else if (data.state === "UNLOCKED") {
    arrivalCard.style.display = "block";
    document.getElementById('arrival-msg').textContent = "🔓 CONTAINER UNLOCKED! Cargo bay hatch opened. Please retrieve your items.";
  } else if (data.state === "IDLE") {
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
  if (msg.qr_unlock_code) {
    currentActiveOrder = msg;
    renderQRCode(msg.qr_unlock_code, msg.pin_code);
  }
  loadOrdersQueue();
}

function handleContainerUnlocked(msg) {
  const lockPill = document.getElementById('container-lock-pill');
  lockPill.textContent = "🔓 UNLOCKED";
  lockPill.className = "pill unlocked";
  document.getElementById('arrival-msg').textContent = "🔓 QR MATCHED! Container hatch opened. Please take your package.";
  alert("🎉 QR Code Matched! Rover Container is now Unlocked.");
}

// Render QR Code in Web App
function renderQRCode(text, pin) {
  const qrContainer = document.getElementById('user-qrcode');
  qrContainer.innerHTML = '';
  document.getElementById('qr-pin-text').textContent = pin || "------";

  try {
    qrCodeInstance = new QRCode(qrContainer, {
      text: text,
      width: 100,
      height: 100,
      colorDark: "#0b132b",
      colorLight: "#ffffff",
      correctLevel: QRCode.CorrectLevel.M
    });
  } catch (e) {
    qrContainer.innerHTML = `<span style="font-size:0.75rem; color:#1e293b; font-weight:bold;">${text}</span>`;
  }
}

// Simulate Robot Optical Scanner matching user's QR code
async function simulateQRScan() {
  if (!currentActiveOrder) {
    alert("No active delivery order to unlock!");
    return;
  }

  const unlockToken = currentActiveOrder.qr_unlock_code || currentActiveOrder.pin_code;
  try {
    const res = await fetch(`${API_BASE}/orders/unlock`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        order_id: currentActiveOrder.id || currentActiveOrder.order_id,
        unlock_code: unlockToken
      })
    });

    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Unlock failed");

    handleContainerUnlocked(data);
  } catch (err) {
    alert("Error unlocking container: " + err.message);
  }
}

// ==========================================
// 4. LOAD CAMPUS NODES, ROADS & SELECTS
// ==========================================
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
  }
}

function renderNodes(nodes) {
  // Clear existing markers
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
  const roadStartSel = document.getElementById('road-start-node');
  const roadEndSel = document.getElementById('road-end-node');

  pickupSel.innerHTML = '';
  destSel.innerHTML = '<option value="" disabled selected>Where are you staying? (Your Place)...</option>';
  if (roadStartSel) roadStartSel.innerHTML = '';
  if (roadEndSel) roadEndSel.innerHTML = '';

  nodes.forEach(n => {
    const optP = new Option(n.name, n.id);
    const optD = new Option(n.name, n.id);
    pickupSel.add(optP);

    // Any destination or junction can be a user staying location
    if (n.type === "destination" || n.type === "junction") {
      destSel.add(optD);
    }

    if (roadStartSel) roadStartSel.add(new Option(n.name, n.id));
    if (roadEndSel) roadEndSel.add(new Option(n.name, n.id));
  });

  // Default: Pickup Main Gate, Destination Physics Dept
  if (nodes.length > 0) {
    pickupSel.value = nodes[0].id;
    if (destSel.options.length > 1) destSel.selectedIndex = 1;
  }
}

async function loadEdges() {
  try {
    const res = await fetch(`${API_BASE}/edges`);
    if (!res.ok) return;
    const edges = await res.json();

    // Clear old lines
    edgeLines.forEach(l => map.removeLayer(l));
    edgeLines = [];

    edges.forEach(e => {
      if (e.waypoints && e.waypoints.length > 0) {
        const latlngs = e.waypoints.map(p => [p.lat, p.lng]);
        const poly = L.polyline(latlngs, {
          color: '#38bdf8',
          weight: 4,
          dashArray: '5, 8',
          opacity: 0.6
        }).addTo(map);
        poly.bindPopup(`<strong>Road:</strong> ${e.name}<br><strong>Distance:</strong> ${e.distance_m} m`);
        edgeLines.push(poly);
      }
    });
  } catch (err) {
    console.error("Error loading edges", err);
  }
}

// ==========================================
// 5. ORDER CREATION
// ==========================================
document.getElementById('order-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const pickupId = parseInt(document.getElementById('pickup-select').value);
  const destId = parseInt(document.getElementById('dest-select').value);
  const itemType = document.getElementById('item-variety').value;
  const isEmergency = document.getElementById('emergency-check').checked;

  if (pickupId === destId) {
    alert("Pickup and Destination cannot be the same place!");
    return;
  }

  const payload = {
    user_name: currentUser ? currentUser.full_name : "Student",
    user_email: currentUser ? currentUser.email : "student@gmail.com",
    user_phone: currentUser ? currentUser.phone : "0771234567",
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

    currentActiveOrder = order;
    displayPlannedRoute(order);
    loadOrdersQueue();

    // If map is currently hidden, prompt user that they can view path
    document.getElementById('situation-text').textContent = order.situation_msg;
  } catch (err) {
    alert("Error creating order: " + err.message);
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

    if (isMapVisible) {
      map.fitBounds(activeRoutePolyline.getBounds(), { padding: [50, 50] });
    }
  }
}

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
          <span style="font-size:0.68rem; color:#94a3b8;">${o.status} • PIN: ${o.pin_code || '---'}</span>
        </div>
        <span class="queue-badge ${isEmg ? 'emg' : 'norm'}">${isEmg ? '🚨 RUSH' : 'NORMAL'}</span>
      `;
      container.appendChild(itemEl);

      // Save latest active order if matches
      if (o.status !== "DELIVERED" && !currentActiveOrder) {
        currentActiveOrder = o;
      }
    });
  } catch (err) {}
}

// ==========================================
// 6. ADMIN ROUTE TRAINER & ROAD BUILDER
// ==========================================
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
    btn.textContent = "🎯 Click Map to Place Point";
    btn.style.background = "#059669";
    map.getContainer().style.cursor = "crosshair";
    if (isRoadTrainingMode) cancelRoadTraining();
  } else {
    btn.textContent = "📍 Place on Map";
    btn.style.background = "#334155";
    map.getContainer().style.cursor = "";
  }
}

function toggleRoadTraining() {
  isRoadTrainingMode = !isRoadTrainingMode;
  const banner = document.getElementById('road-training-banner');
  const btnTrain = document.getElementById('btn-train-road');
  const counter = document.getElementById('road-points-counter');
  const btnSave = document.getElementById('btn-save-road');

  if (isRoadTrainingMode) {
    trainedRoadPoints = [];
    if (trainedRoadPolyline) map.removeLayer(trainedRoadPolyline);
    banner.style.display = 'flex';
    btnTrain.textContent = "⏹ Stop Marking Road";
    btnTrain.className = "btn btn-secondary";
    counter.style.display = 'block';
    btnSave.style.display = 'block';
    document.getElementById('road-pts-count').textContent = '0';
    map.getContainer().style.cursor = "pointer";
    if (isAddPointMode) enableAddPointMode();
  } else {
    cancelRoadTraining();
  }
}

function cancelRoadTraining() {
  isRoadTrainingMode = false;
  document.getElementById('road-training-banner').style.display = 'none';
  const btnTrain = document.getElementById('btn-train-road');
  btnTrain.textContent = "🛣️ Start Clicking Road Waypoints";
  btnTrain.className = "btn btn-warning";
  document.getElementById('road-points-counter').style.display = 'none';
  document.getElementById('btn-save-road').style.display = 'none';
  map.getContainer().style.cursor = "";
  if (trainedRoadPolyline) map.removeLayer(trainedRoadPolyline);
  trainedRoadPoints = [];
}

async function saveTrainedRoad() {
  const startNodeId = parseInt(document.getElementById('road-start-node').value);
  const endNodeId = parseInt(document.getElementById('road-end-node').value);
  const roadName = document.getElementById('road-name-input').value.trim() || "Trained Campus Road";

  if (startNodeId === endNodeId) {
    alert("Start node and End node cannot be the same!");
    return;
  }
  if (trainedRoadPoints.length < 2) {
    alert("Please click at least 2 points on the map to define the road shape!");
    return;
  }

  const payload = {
    name: roadName,
    from_node_id: startNodeId,
    to_node_id: endNodeId,
    waypoints: trainedRoadPoints
  };

  try {
    const res = await fetch(`${API_BASE}/admin/roads`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    if (!res.ok) throw new Error("Failed to save road");
    const saved = await res.json();
    alert(`Road "${saved.name}" (${saved.distance_m}m) saved successfully! Dijkstra will now use this road.`);
    cancelRoadTraining();
    loadCampus();
  } catch (err) {
    alert("Error saving road: " + err.message);
  }
}

async function clearAllTrainedRoads() {
  if (!confirm("Are you sure you want to clear all sample roads? You can then train and draw all roads from scratch.")) {
    return;
  }
  try {
    const res = await fetch(`${API_BASE}/admin/clear-all-roads`, { method: "POST" });
    if (res.ok) {
      alert("All sample roads cleared! Please train and save your real campus roads.");
      loadCampus();
    }
  } catch (err) {
    alert("Error: " + err.message);
  }
}

async function handleMapClick(e) {
  const lat = parseFloat(e.latlng.lat.toFixed(6));
  const lng = parseFloat(e.latlng.lng.toFixed(6));

  // 1. Add Point Mode
  if (isAddPointMode) {
    const nameInput = document.getElementById('new-node-name');
    const typeInput = document.getElementById('new-node-type');
    const pointName = nameInput.value.trim() || `Place (${lat}, ${lng})`;
    const pointCode = "PT_" + Math.random().toString(36).substring(2, 7).toUpperCase();

    try {
      const res = await fetch(`${API_BASE}/nodes`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          code: pointCode,
          name: pointName,
          lat: lat,
          lng: lng,
          type: typeInput.value
        })
      });
      if (res.ok) {
        alert(`New location "${pointName}" added to campus!`);
        nameInput.value = '';
        enableAddPointMode();
        loadCampus();
      }
    } catch (err) {
      alert("Error adding point: " + err);
    }
    return;
  }

  // 2. Road Training Mode
  if (isRoadTrainingMode) {
    trainedRoadPoints.push({ lat, lng });
    document.getElementById('road-pts-count').textContent = trainedRoadPoints.length;

    // Draw / update amber polyline
    const latlngs = trainedRoadPoints.map(p => [p.lat, p.lng]);
    if (trainedRoadPolyline) map.removeLayer(trainedRoadPolyline);

    trainedRoadPolyline = L.polyline(latlngs, {
      color: '#f59e0b',
      weight: 5,
      dashArray: '2, 6',
      opacity: 0.95
    }).addTo(map);

    // Place temporary marker on each clicked waypoint
    L.circleMarker([lat, lng], {
      radius: 5,
      fillColor: '#f59e0b',
      color: '#ffffff',
      weight: 1,
      fillOpacity: 1
    }).addTo(map);
  }
}

// ==========================================
// 7. BOOTSTRAP ON LOAD
// ==========================================
window.addEventListener('DOMContentLoaded', () => {
  initMap();
  loadUserSession();
  loadCampus();
  connectWebSocket();
  setInterval(loadOrdersQueue, 4000);
});
