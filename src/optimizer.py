"""
Optimizer Module
Implements vehicle routing optimization with constraints.
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Tuple, Optional, Set
from dataclasses import dataclass


@dataclass
class ConvoyAssignment:
    """Represents a single convoy mission assignment."""
    vehicle_id: str
    vehicle_type: str
    supply_point: str
    destinations: List[str]
    total_distance_km: float
    total_demand_tons: float
    threat_exposure: str
    route_sequence: List[str]


class ConvoyOptimizer:
    """
    Optimizes convoy routing for military logistics operations.
    
    Considers:
    - Vehicle capacity constraints
    - Maximum range limitations
    - Threat level avoidance
    - Priority-based delivery ordering
    """
    
    def __init__(
        self,
        supply_points: pd.DataFrame,
        destinations: pd.DataFrame,
        vehicles: pd.DataFrame,
        routes: pd.DataFrame,
        max_threat_level: str = 'high'
    ):
        self.supply_points = supply_points
        self.destinations = destinations
        self.vehicles = vehicles
        self.routes = routes
        self.max_threat_level = max_threat_level
        
        # Build graph representation
        self.graph = self._build_graph()
        
        # Threat levels mapping
        self.threat_threshold = {'low': 1, 'medium': 2, 'high': 3}
    
    def _build_graph(self) -> Dict[str, Dict[str, Dict]]:
        """
        Build adjacency graph from routes.
        graph[from][to] = {distance, threat_level, effective_distance, ...}
        """
        graph = {}
        
        for _, route in self.routes.iterrows():
            from_id = route['from_point']
            to_id = route['to_point']
            
            edge_data = {
                'distance_km': route['distance_km'],
                'threat_level': route['threat_level'],
                'effective_distance': route['effective_distance'],
                'road_condition': route['road_condition']
            }
            
            # Add both directions (bidirectional roads)
            if from_id not in graph:
                graph[from_id] = {}
            if to_id not in graph:
                graph[to_id] = {}
            
            graph[from_id][to_id] = edge_data
            graph[to_id][from_id] = edge_data
        
        return graph
    
    def _get_edge(self, from_id: str, to_id: str) -> Optional[Dict]:
        """Get edge data between two nodes."""
        if from_id in self.graph and to_id in self.graph[from_id]:
            return self.graph[from_id][to_id]
        return None
    
    def _find_path_distance(self, from_id: str, to_id: str, avoid_high_threat: bool) -> Tuple[float, List[str], str]:
        """
        Find shortest path between two points using BFS.
        Returns (distance, path, max_threat_level).
        """
        if from_id == to_id:
            return 0.0, [from_id], 'low'
        
        # Direct edge?
        edge = self._get_edge(from_id, to_id)
        if edge:
            if avoid_high_threat and edge['threat_level'] == 'high':
                pass  # Skip direct high-threat, try to find alternate
            else:
                return edge['distance_km'], [from_id, to_id], edge['threat_level']
        
        # BFS for shortest path
        from collections import deque
        queue = deque([(from_id, [from_id], 0.0, 'low')])
        visited = {from_id}
        
        while queue:
            current, path, dist, max_threat = queue.popleft()
            
            if current not in self.graph:
                continue
            
            for neighbor, edge_data in self.graph[current].items():
                if neighbor in visited:
                    continue
                
                # Skip high threat if avoiding
                if avoid_high_threat and edge_data['threat_level'] == 'high':
                    continue
                
                new_dist = dist + edge_data['distance_km']
                new_path = path + [neighbor]
                new_threat = max(max_threat, edge_data['threat_level'], 
                               key=lambda t: self.threat_threshold.get(t, 0))
                
                if neighbor == to_id:
                    return new_dist, new_path, new_threat
                
                visited.add(neighbor)
                queue.append((neighbor, new_path, new_dist, new_threat))
        
        # No path found
        return float('inf'), [], 'high'
    
    def optimize_routes(
        self,
        supply_point_id: str,
        available_vehicles: List[str],
        avoid_high_threat: bool = True
    ) -> List[ConvoyAssignment]:
        """
        Optimize delivery routes from a single supply point.
        """
        vehicles = self.vehicles[
            self.vehicles['vehicle_id'].isin(available_vehicles)
        ].copy()
        
        if len(vehicles) == 0:
            print("No available vehicles provided")
            return []
        
        # Sort vehicles by capacity (largest first for better packing)
        vehicles = vehicles.sort_values('capacity_tons', ascending=False)
        
        # Get destinations sorted by priority
        destinations = self.destinations.copy()
        destinations = destinations.sort_values('priority_score', ascending=False)
        
        assignments = []
        remaining_destinations = set(destinations['dest_id'].tolist())
        
        for _, vehicle in vehicles.iterrows():
            if not remaining_destinations:
                break
            
            assignment = self._assign_vehicle_route(
                vehicle=vehicle,
                supply_point_id=supply_point_id,
                destination_ids=remaining_destinations,
                avoid_high_threat=avoid_high_threat
            )
            
            if assignment and assignment.destinations:
                assignments.append(assignment)
                for dest in assignment.destinations:
                    remaining_destinations.discard(dest)
        
        return assignments
    
    def _assign_vehicle_route(
        self,
        vehicle: pd.Series,
        supply_point_id: str,
        destination_ids: Set[str],
        avoid_high_threat: bool
    ) -> Optional[ConvoyAssignment]:
        """
        Assign optimal route to a single vehicle using greedy nearest-neighbor
        with proper path finding.
        """
        capacity = vehicle['capacity_tons']
        max_range = vehicle['max_range_km']
        
        route_sequence = [supply_point_id]
        assigned_destinations = []
        total_distance = 0.0
        total_demand = 0.0
        max_threat_seen = 'low'
        
        current_location = supply_point_id
        remaining = set(destination_ids)
        
        while remaining:
            best_dest = None
            best_distance = float('inf')
            best_path = []
            best_threat = 'low'
            
            for dest_id in remaining:
                dest_row = self.destinations[
                    self.destinations['dest_id'] == dest_id
                ].iloc[0]
                
                demand = dest_row['demand_tons']
                
                # Check capacity
                if total_demand + demand > capacity:
                    continue
                
                # Find path to this destination
                dist_to_dest, path_to_dest, threat = self._find_path_distance(
                    current_location, dest_id, avoid_high_threat
                )
                
                if dist_to_dest == float('inf'):
                    continue
                
                # Check if we can still return to base
                dist_back, _, _ = self._find_path_distance(
                    dest_id, supply_point_id, avoid_high_threat
                )
                
                if dist_back == float('inf'):
                    continue
                
                # Check range constraint
                if total_distance + dist_to_dest + dist_back > max_range:
                    continue
                
                # Prefer closer destinations
                if dist_to_dest < best_distance:
                    best_distance = dist_to_dest
                    best_dest = dest_id
                    best_path = path_to_dest
                    best_threat = threat
            
            if best_dest is None:
                break
            
            # Assign this destination
            dest_row = self.destinations[
                self.destinations['dest_id'] == best_dest
            ].iloc[0]
            
            assigned_destinations.append(best_dest)
            
            # Add intermediate path nodes (excluding current which is already in route)
            for node in best_path[1:]:
                route_sequence.append(node)
            
            total_distance += best_distance
            total_demand += dest_row['demand_tons']
            remaining.remove(best_dest)
            
            # Update max threat
            if self.threat_threshold.get(best_threat, 0) > self.threat_threshold.get(max_threat_seen, 0):
                max_threat_seen = best_threat
            
            current_location = best_dest
        
        if not assigned_destinations:
            return None
        
        # Add return leg
        dist_back, path_back, threat_back = self._find_path_distance(
            current_location, supply_point_id, avoid_high_threat
        )
        
        if path_back:
            for node in path_back[1:]:
                route_sequence.append(node)
        else:
            route_sequence.append(supply_point_id)
        
        total_distance += dist_back if dist_back != float('inf') else 50.0
        
        if self.threat_threshold.get(threat_back, 0) > self.threat_threshold.get(max_threat_seen, 0):
            max_threat_seen = threat_back
        
        return ConvoyAssignment(
            vehicle_id=vehicle['vehicle_id'],
            vehicle_type=vehicle['type'],
            supply_point=supply_point_id,
            destinations=assigned_destinations,
            total_distance_km=round(total_distance, 1),
            total_demand_tons=total_demand,
            threat_exposure=max_threat_seen,
            route_sequence=route_sequence
        )
    
    def get_summary_stats(self, assignments: List[ConvoyAssignment]) -> Dict:
        """Generate summary statistics for route assignments."""
        if not assignments:
            return {}
        
        total_distance = sum(a.total_distance_km for a in assignments)
        total_demand = sum(a.total_demand_tons for a in assignments)
        total_destinations = sum(len(a.destinations) for a in assignments)
        
        threat_counts = {'low': 0, 'medium': 0, 'high': 0}
        for a in assignments:
            threat_counts[a.threat_exposure] = threat_counts.get(a.threat_exposure, 0) + 1
        
        return {
            'total_convoys': len(assignments),
            'total_distance_km': round(total_distance, 1),
            'total_demand_tons': total_demand,
            'destinations_served': total_destinations,
            'threat_exposure_summary': threat_counts,
            'avg_distance_per_convoy': round(total_distance / len(assignments), 1)
        }


def print_assignments(assignments: List[ConvoyAssignment]) -> None:
    """Pretty print convoy assignments."""
    print("\n" + "="*60)
    print("CONVOY ROUTE ASSIGNMENTS")
    print("="*60)
    
    for i, a in enumerate(assignments, 1):
        print(f"\nConvoy {i}: {a.vehicle_id} ({a.vehicle_type})")
        print(f"  Route: {' -> '.join(a.route_sequence)}")
        print(f"  Destinations: {len(a.destinations)} ({', '.join(a.destinations)})")
        print(f"  Total Distance: {a.total_distance_km} km")
        print(f"  Cargo: {a.total_demand_tons} tons")
        print(f"  Threat Exposure: {a.threat_exposure.upper()}")


if __name__ == '__main__':
    from data_loader import load_all_data
    
    # Load data
    supply_points, destinations, vehicles, routes = load_all_data()
    
    # Create optimizer
    optimizer = ConvoyOptimizer(
        supply_points=supply_points,
        destinations=destinations,
        vehicles=vehicles,
        routes=routes
    )
    
    # Get vehicles from SP001 (Camp Liberty)
    sp001_vehicles = vehicles[vehicles['home_base'] == 'SP001']['vehicle_id'].tolist()
    
    # Optimize routes
    assignments = optimizer.optimize_routes(
        supply_point_id='SP001',
        available_vehicles=sp001_vehicles,
        avoid_high_threat=True
    )
    
    # Print results
    print_assignments(assignments)
    
    # Print summary
    stats = optimizer.get_summary_stats(assignments)
    print("\n" + "="*60)
    print("SUMMARY STATISTICS")
    print("="*60)
    for key, value in stats.items():
        print(f"  {key}: {value}")
