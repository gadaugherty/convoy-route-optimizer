"""
Optimizer Module
Implements vehicle routing optimization with constraints.
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from ortools.constraint_solver import routing_enums_pb2
from ortools.constraint_solver import pywrapcp


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
        max_threat_level: str = 'high'  # 'low', 'medium', 'high'
    ):
        self.supply_points = supply_points
        self.destinations = destinations
        self.vehicles = vehicles
        self.routes = routes
        self.max_threat_level = max_threat_level
        
        # Build distance matrix
        self.distance_matrix = self._build_distance_matrix()
        
        # Threat levels to avoid
        self.threat_threshold = {'low': 1, 'medium': 2, 'high': 3}
    
    def _build_distance_matrix(self) -> np.ndarray:
        """
        Build a distance matrix between all supply points and destinations.
        Uses effective distance (accounts for threat level).
        """
        # Get all location IDs
        sp_ids = self.supply_points['id'].tolist()
        dest_ids = self.destinations['dest_id'].tolist()
        all_locations = sp_ids + dest_ids
        n = len(all_locations)
        
        # Initialize with large values (no direct route)
        matrix = np.full((n, n), 9999.0)
        np.fill_diagonal(matrix, 0)
        
        # Fill in known routes
        for _, route in self.routes.iterrows():
            from_id = route['from_point']
            to_id = route['to_point']
            
            if from_id in all_locations and to_id in all_locations:
                i = all_locations.index(from_id)
                j = all_locations.index(to_id)
                
                # Use effective distance (threat-adjusted)
                matrix[i][j] = route['effective_distance']
                matrix[j][i] = route['effective_distance']  # Assume bidirectional
        
        self.location_ids = all_locations
        return matrix
    
    def _get_location_index(self, location_id: str) -> int:
        """Get matrix index for a location ID."""
        return self.location_ids.index(location_id)
    
    def optimize_routes(
        self,
        supply_point_id: str,
        available_vehicles: List[str],
        avoid_high_threat: bool = True
    ) -> List[ConvoyAssignment]:
        """
        Optimize delivery routes from a single supply point.
        
        Args:
            supply_point_id: Starting supply point
            available_vehicles: List of vehicle IDs to use
            avoid_high_threat: Whether to avoid high-threat routes
            
        Returns:
            List of ConvoyAssignment objects
        """
        # Filter vehicles
        vehicles = self.vehicles[
            self.vehicles['vehicle_id'].isin(available_vehicles)
        ].copy()
        
        if len(vehicles) == 0:
            print("No available vehicles provided")
            return []
        
        # Get destinations that need service
        destinations = self.destinations.copy()
        
        # Sort by priority (high priority first)
        destinations = destinations.sort_values('priority_score', ascending=False)
        
        assignments = []
        remaining_destinations = destinations['dest_id'].tolist()
        
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
                # Remove assigned destinations from remaining
                for dest in assignment.destinations:
                    if dest in remaining_destinations:
                        remaining_destinations.remove(dest)
        
        return assignments
    
    def _assign_vehicle_route(
        self,
        vehicle: pd.Series,
        supply_point_id: str,
        destination_ids: List[str],
        avoid_high_threat: bool
    ) -> Optional[ConvoyAssignment]:
        """
        Assign optimal route to a single vehicle using greedy nearest-neighbor.
        """
        capacity = vehicle['capacity_tons']
        max_range = vehicle['max_range_km']
        
        route = [supply_point_id]
        assigned_destinations = []
        total_distance = 0.0
        total_demand = 0.0
        max_threat_seen = 'low'
        
        current_location = supply_point_id
        remaining = destination_ids.copy()
        
        while remaining:
            # Find nearest feasible destination
            best_dest = None
            best_distance = float('inf')
            
            for dest_id in remaining:
                dest_row = self.destinations[
                    self.destinations['dest_id'] == dest_id
                ].iloc[0]
                
                demand = dest_row['demand_tons']
                
                # Check capacity constraint
                if total_demand + demand > capacity:
                    continue
                
                # Get distance
                try:
                    i = self._get_location_index(current_location)
                    j = self._get_location_index(dest_id)
                    distance = self.distance_matrix[i][j]
                except (ValueError, IndexError):
                    continue
                
                # Check if route exists and threat level
                route_info = self._get_route_info(current_location, dest_id)
                if route_info is None:
                    continue
                    
                if avoid_high_threat and route_info['threat_level'] == 'high':
                    continue
                
                # Check range constraint (need to be able to return)
                return_distance = self._estimate_return_distance(dest_id, supply_point_id)
                if total_distance + distance + return_distance > max_range:
                    continue
                
                if distance < best_distance:
                    best_distance = distance
                    best_dest = dest_id
            
            if best_dest is None:
                break
            
            # Assign this destination
            dest_row = self.destinations[
                self.destinations['dest_id'] == best_dest
            ].iloc[0]
            
            assigned_destinations.append(best_dest)
            route.append(best_dest)
            total_distance += best_distance
            total_demand += dest_row['demand_tons']
            remaining.remove(best_dest)
            
            # Track threat level
            route_info = self._get_route_info(current_location, best_dest)
            if route_info:
                threat = route_info['threat_level']
                if self.threat_threshold.get(threat, 0) > self.threat_threshold.get(max_threat_seen, 0):
                    max_threat_seen = threat
            
            current_location = best_dest
        
        if not assigned_destinations:
            return None
        
        # Add return leg
        route.append(supply_point_id)
        return_dist = self._estimate_return_distance(current_location, supply_point_id)
        total_distance += return_dist
        
        return ConvoyAssignment(
            vehicle_id=vehicle['vehicle_id'],
            vehicle_type=vehicle['type'],
            supply_point=supply_point_id,
            destinations=assigned_destinations,
            total_distance_km=round(total_distance, 1),
            total_demand_tons=total_demand,
            threat_exposure=max_threat_seen,
            route_sequence=route
        )
    
    def _get_route_info(self, from_id: str, to_id: str) -> Optional[Dict]:
        """Get route information between two points."""
        route = self.routes[
            ((self.routes['from_point'] == from_id) & (self.routes['to_point'] == to_id)) |
            ((self.routes['from_point'] == to_id) & (self.routes['to_point'] == from_id))
        ]
        
        if len(route) == 0:
            return None
            
        row = route.iloc[0]
        return {
            'distance_km': row['distance_km'],
            'threat_level': row['threat_level'],
            'road_condition': row['road_condition'],
            'effective_distance': row['effective_distance']
        }
    
    def _estimate_return_distance(self, from_id: str, to_id: str) -> float:
        """Estimate return distance to supply point."""
        try:
            i = self._get_location_index(from_id)
            j = self._get_location_index(to_id)
            return self.distance_matrix[i][j]
        except (ValueError, IndexError):
            return 50.0  # Default estimate
    
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
        print(f"  Destinations: {len(a.destinations)}")
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
