import json
import math
import heapq
from typing import List, Dict, Tuple, Optional
from sqlalchemy.orm import Session
from models import NodeModel, EdgeModel
from schemas import Waypoint

def haversine_dist(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371000.0  # Earth radius in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = math.sin(delta_phi / 2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def compute_polyline_distance(waypoints: List[dict]) -> float:
    if not waypoints or len(waypoints) < 2:
        return 0.0
    dist = 0.0
    for i in range(len(waypoints) - 1):
        dist += haversine_dist(waypoints[i]["lat"], waypoints[i]["lng"], waypoints[i+1]["lat"], waypoints[i+1]["lng"])
    return dist

def build_graph(db: Session, exclude_edge_ids: Optional[List[int]] = None) -> Dict[int, List[Tuple[int, float, List[dict], int]]]:
    """
    Builds an adjacency list from the edges table.
    Returns: { node_id: [ (neighbor_id, distance_m, waypoints_list, edge_id), ... ] }
    Edges are treated as bidirectional.
    exclude_edge_ids: list of edge IDs to omit (used for Yen's k-shortest / alternative paths).
    """
    edges = db.query(EdgeModel).all()
    graph: Dict[int, List] = {}
    exclude_set = set(exclude_edge_ids or [])

    for edge in edges:
        if edge.id in exclude_set:
            continue
        waypoints = json.loads(edge.waypoints_json) if edge.waypoints_json else []
        reversed_waypoints = list(reversed(waypoints))
        dist = edge.distance_m if (edge.distance_m and edge.distance_m > 0) else compute_polyline_distance(waypoints)

        # from -> to
        if edge.from_node_id not in graph:
            graph[edge.from_node_id] = []
        graph[edge.from_node_id].append((edge.to_node_id, dist, waypoints, edge.id))

        # to -> from (bidirectional)
        if edge.to_node_id not in graph:
            graph[edge.to_node_id] = []
        graph[edge.to_node_id].append((edge.from_node_id, dist, reversed_waypoints, edge.id))

    return graph

def _run_dijkstra(
    graph: Dict[int, List],
    start_node_id: int,
    target_node_id: int
) -> Tuple[List[int], List[Waypoint], float, List[int]]:
    """
    Core Dijkstra implementation.
    Returns: (node_id_path, waypoints, total_distance_m, edge_id_path)
    """
    if start_node_id not in graph or target_node_id not in graph:
        return [], [], float('inf'), []

    # Priority queue: (cost, current_node, path_nodes, accumulated_waypoints, path_edge_ids)
    queue = [(0.0, start_node_id, [start_node_id], [], [])]
    visited = set()

    while queue:
        cost, current, path, waypoints, edge_ids = heapq.heappop(queue)

        if current in visited:
            continue
        visited.add(current)

        if current == target_node_id:
            compiled_pts = [Waypoint(lat=pt["lat"], lng=pt["lng"]) for pt in waypoints]
            return path, compiled_pts, cost, edge_ids

        for neighbor, edge_dist, edge_pts, edge_id in graph.get(current, []):
            if neighbor not in visited:
                # Deduplicate consecutive matching points
                new_waypoints = list(waypoints)
                for pt in edge_pts:
                    if not new_waypoints or (new_waypoints[-1]["lat"] != pt["lat"] or new_waypoints[-1]["lng"] != pt["lng"]):
                        new_waypoints.append(pt)

                heapq.heappush(queue, (
                    cost + edge_dist,
                    neighbor,
                    path + [neighbor],
                    new_waypoints,
                    edge_ids + [edge_id]
                ))

    return [], [], float('inf'), []

def find_shortest_path(db: Session, start_node_id: int, target_node_id: int) -> Tuple[List[int], List[Waypoint], float]:
    """
    Runs Dijkstra's algorithm to find the shortest node path and compiled waypoints.
    Returns: (node_id_list, list_of_waypoints, total_distance_m)
    """
    if start_node_id == target_node_id:
        start_node = db.query(NodeModel).filter(NodeModel.id == start_node_id).first()
        pts = [Waypoint(lat=start_node.lat, lng=start_node.lng)] if start_node else []
        return [start_node_id], pts, 0.0

    graph = build_graph(db)
    node_path, waypoints, cost, _ = _run_dijkstra(graph, start_node_id, target_node_id)
    return node_path, waypoints, cost

def find_alternative_path(db: Session, start_node_id: int, target_node_id: int) -> Tuple[List[int], List[Waypoint], float]:
    """
    Finds a second (alternative) shortest path using the edge-exclusion strategy:
    1. Run Dijkstra to find the primary path.
    2. For each edge in the primary path, temporarily remove that edge and re-run Dijkstra.
    3. Return the best alternative (shortest among all single-edge-excluded sub-runs).

    This is a simplified variant of Yen's K-Shortest Paths algorithm.
    Returns: (node_id_list, list_of_waypoints, total_distance_m)
    """
    if start_node_id == target_node_id:
        return [], [], float('inf')

    graph = build_graph(db)
    primary_nodes, primary_wps, primary_cost, primary_edges = _run_dijkstra(graph, start_node_id, target_node_id)

    if not primary_edges:
        # No primary path at all
        return [], [], float('inf')

    best_alt_nodes: List[int] = []
    best_alt_wps: List[Waypoint] = []
    best_alt_cost = float('inf')

    # Try excluding each edge in the primary path
    for excluded_edge_id in primary_edges:
        alt_graph = build_graph(db, exclude_edge_ids=[excluded_edge_id])
        alt_nodes, alt_wps, alt_cost, _ = _run_dijkstra(alt_graph, start_node_id, target_node_id)

        # Only accept if it's a genuinely different path (different node sequence)
        if alt_cost < float('inf') and alt_nodes != primary_nodes and alt_cost < best_alt_cost:
            best_alt_cost = alt_cost
            best_alt_nodes = alt_nodes
            best_alt_wps = alt_wps

    return best_alt_nodes, best_alt_wps, best_alt_cost
