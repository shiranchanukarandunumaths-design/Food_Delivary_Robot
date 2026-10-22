import json
import heapq
from typing import List, Dict, Tuple, Optional
from sqlalchemy.orm import Session
from models import NodeModel, EdgeModel
from schemas import Waypoint

def build_graph(db: Session) -> Dict[int, List[Tuple[int, float, List[dict]]]]:
    """
    Builds an adjacency list from edges table:
    { node_id: [ (neighbor_id, distance_m, waypoints_list), ... ] }
    Edges are treated as bidirectional.
    """
    edges = db.query(EdgeModel).all()
    graph = {}

    for edge in edges:
        waypoints = json.loads(edge.waypoints_json) if edge.waypoints_json else []
        reversed_waypoints = list(reversed(waypoints))

        # from -> to
        if edge.from_node_id not in graph:
            graph[edge.from_node_id] = []
        graph[edge.from_node_id].append((edge.to_node_id, edge.distance_m, waypoints))

        # to -> from (bidirectional)
        if edge.to_node_id not in graph:
            graph[edge.to_node_id] = []
        graph[edge.to_node_id].append((edge.from_node_id, edge.distance_m, reversed_waypoints))

    return graph

def find_shortest_path(db: Session, start_node_id: int, target_node_id: int) -> Tuple[List[int], List[Waypoint], float]:
    """
    Runs Dijkstra's algorithm to find shortest node path and compiled waypoints.
    Returns: (node_id_list, list_of_waypoints, total_distance_m)
    """
    if start_node_id == target_node_id:
        start_node = db.query(NodeModel).filter(NodeModel.id == start_node_id).first()
        pts = [Waypoint(lat=start_node.lat, lng=start_node.lng)] if start_node else []
        return [start_node_id], pts, 0.0

    graph = build_graph(db)
    if start_node_id not in graph or target_node_id not in graph:
        return [], [], float('inf')

    # Priority queue: (cost, current_node, path, accumulated_waypoints)
    queue = [(0.0, start_node_id, [start_node_id], [])]
    visited = set()

    while queue:
        cost, current, path, waypoints = heapq.heappop(queue)

        if current in visited:
            continue
        visited.add(current)

        if current == target_node_id:
            # Format waypoints
            compiled_pts = [Waypoint(lat=pt["lat"], lng=pt["lng"]) for pt in waypoints]
            return path, compiled_pts, cost

        for neighbor, edge_dist, edge_pts in graph.get(current, []):
            if neighbor not in visited:
                # Deduplicate consecutive matching points
                new_waypoints = list(waypoints)
                for pt in edge_pts:
                    if not new_waypoints or (new_waypoints[-1]["lat"] != pt["lat"] or new_waypoints[-1]["lng"] != pt["lng"]):
                        new_waypoints.append(pt)

                heapq.heappush(queue, (cost + edge_dist, neighbor, path + [neighbor], new_waypoints))

    return [], [], float('inf')
