"""
Optimizer Module
Implements vehicle routing optimization with constraints.
"""

import pandas as pd
from typing import List, Dict, Tuple, Optional, Set
from dataclasses import dataclass


@dataclass
class ConvoyAssignment:
    """Represents a single convoy mission assignment."""
    vehicle_id: str
    vehicle_type: str
    vehicle_mode: str
    supply_point: str
    destinations: List[str]
    total_distance_km: float
    total_demand_tons: float
    threat_exposure: str
    route_sequence: List[str]
    speed_kmh: float = 80.0


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
        Find distance between two points.
        First checks the route graph, then falls back to straight-line calculation.
        Returns (distance, path, threat_level).
        """
        if from_id == to_id:
            return 0.0, [from_id], 'low'
        
        # Try direct edge in graph first
        edge = self._get_edge(from_id, to_id)
        if edge:
            if avoid_high_threat and edge['threat_level'] == 'high':
                pass  # Skip direct high-threat, try to find alternate
            else:
                return edge['distance_km'], [from_id, to_id], edge['threat_level']
        
        # Try BFS for path through graph
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
                # Determine the higher threat level by comparing numeric values
                edge_threat = edge_data['threat_level']
                if self.threat_threshold.get(edge_threat, 0) > self.threat_threshold.get(max_threat, 0):
                    new_threat = edge_threat
                else:
                    new_threat = max_threat
                
                if neighbor == to_id:
                    return new_dist, new_path, new_threat
                
                visited.add(neighbor)
                queue.append((neighbor, new_path, new_dist, new_threat))
        
        # No path in graph - calculate straight line distance using coordinates
        from_coords = self._get_coords(from_id)
        to_coords = self._get_coords(to_id)
        
        if from_coords and to_coords:
            distance = self._haversine_distance(from_coords, to_coords)
            return distance, [from_id, to_id], 'low'
        
        # No path found
        return float('inf'), [], 'high'
    
    def _get_coords(self, point_id: str) -> Optional[Tuple[float, float]]:
        """Get coordinates for a supply point or destination."""
        # Check supply points
        sp_match = self.supply_points[self.supply_points['id'] == point_id]
        if len(sp_match) > 0:
            return (sp_match.iloc[0]['lat'], sp_match.iloc[0]['lon'])
        
        # Check destinations
        dest_match = self.destinations[self.destinations['dest_id'] == point_id]
        if len(dest_match) > 0:
            return (dest_match.iloc[0]['lat'], dest_match.iloc[0]['lon'])
        
        return None
    
    def _haversine_distance(self, coord1: Tuple[float, float], coord2: Tuple[float, float]) -> float:
        """Calculate distance between two lat/lon points in km."""
        import math
        lat1, lon1 = coord1
        lat2, lon2 = coord2
        
        R = 6371  # Earth's radius in km
        
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lat = math.radians(lat2 - lat1)
        delta_lon = math.radians(lon2 - lon1)
        
        a = math.sin(delta_lat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        
        return R * c
    
    def _get_demand(self, dest_row: pd.Series) -> float:
        """Get total demand from destination row, handling both old and new column names."""
        if 'total_demand_tons' in dest_row.index:
            return dest_row['total_demand_tons']
        elif 'demand_tons' in dest_row.index:
            return dest_row['demand_tons']
        else:
            # Sum up categorized demand
            total = 0
            for cat in ['food_tons', 'ammo_tons', 'fuel_tons', 'medical_tons']:
                if cat in dest_row.index:
                    total += dest_row[cat]
            return total
    
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
        
        # Get supply point coordinates
        sp_coords = self._get_coords(supply_point_id)
        if not sp_coords:
            print(f"Could not find coordinates for {supply_point_id}")
            return []
        
        # Filter destinations to those within range of at least one vehicle
        max_vehicle_range = vehicles['max_range_km'].max()
        
        reachable_destinations = []
        for _, dest in self.destinations.iterrows():
            dest_coords = (dest['lat'], dest['lon'])
            distance = self._haversine_distance(sp_coords, dest_coords)
            # Round trip must be within range
            if distance * 2 <= max_vehicle_range:
                reachable_destinations.append(dest['dest_id'])
        
        if not reachable_destinations:
            print(f"No destinations within range of {supply_point_id}")
            return []
        
        # Get destinations sorted by priority
        destinations = self.destinations[
            self.destinations['dest_id'].isin(reachable_destinations)
        ].copy()
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
        vehicle_mode = vehicle.get('mode', 'GROUND')

        # For AIR vehicles, check if supply point has an airstrip
        if vehicle_mode == 'AIR':
            sp_match = self.supply_points[self.supply_points['id'] == supply_point_id]
            if len(sp_match) > 0 and not sp_match.iloc[0].get('has_airstrip', False):
                return None  # Aircraft cannot depart from location without airstrip

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
                dest_matches = self.destinations[
                    self.destinations['dest_id'] == dest_id
                ]
                if len(dest_matches) == 0:
                    continue
                dest_row = dest_matches.iloc[0]

                # For AIR vehicles, skip destinations without airstrips
                if vehicle_mode == 'AIR' and not dest_row.get('has_airstrip', False):
                    continue

                demand = self._get_demand(dest_row)

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
            
            # Assign this destination (we know it exists since best_dest was found above)
            dest_row = self.destinations[
                self.destinations['dest_id'] == best_dest
            ].iloc[0]
            
            assigned_destinations.append(best_dest)
            
            # Add intermediate path nodes (excluding current which is already in route)
            for node in best_path[1:]:
                route_sequence.append(node)
            
            total_distance += best_distance
            total_demand += self._get_demand(dest_row)
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
        
        # If no return path found, estimate using haversine distance
        if dist_back == float('inf'):
            current_coords = self._get_coords(current_location)
            supply_coords = self._get_coords(supply_point_id)
            if current_coords and supply_coords:
                dist_back = self._haversine_distance(current_coords, supply_coords)
            else:
                dist_back = 0.0  # Can't estimate, assume negligible
        total_distance += dist_back
        
        if self.threat_threshold.get(threat_back, 0) > self.threat_threshold.get(max_threat_seen, 0):
            max_threat_seen = threat_back
        
        return ConvoyAssignment(
            vehicle_id=vehicle['vehicle_id'],
            vehicle_type=vehicle['type'],
            vehicle_mode=vehicle.get('mode', 'GROUND'),
            supply_point=supply_point_id,
            destinations=assigned_destinations,
            total_distance_km=round(total_distance, 1),
            total_demand_tons=total_demand,
            threat_exposure=max_threat_seen,
            route_sequence=route_sequence,
            speed_kmh=vehicle.get('speed_kmh', 80.0)
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
    
    # Get vehicles from SP001
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