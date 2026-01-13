#!/usr/bin/env python3
"""Debug script to check optimizer behavior"""

import sys
sys.path.insert(0, '.')

from src.data_loader import load_all_data
from src.optimizer import ConvoyOptimizer

# Load data
supply_points, destinations, vehicles, routes = load_all_data()

print("\n=== VEHICLES AT SP001 ===")
sp001_vehicles = vehicles[vehicles['home_base'] == 'SP001']
print(sp001_vehicles[['vehicle_id', 'type', 'capacity_tons', 'max_range_km']])

print("\n=== DESTINATIONS (sorted by priority) ===")
dests = destinations.sort_values('priority_score', ascending=False)
print(dests[['dest_id', 'dest_name', 'demand_tons', 'priority']])

print("\n=== ROUTES FROM SP001 ===")
sp001_routes = routes[(routes['from_point'] == 'SP001') | (routes['to_point'] == 'SP001')]
print(sp001_routes[['from_point', 'to_point', 'distance_km', 'threat_level']])

# Create optimizer and check graph
optimizer = ConvoyOptimizer(
    supply_points=supply_points,
    destinations=destinations,
    vehicles=vehicles,
    routes=routes
)

print("\n=== GRAPH CONNECTIONS FROM SP001 ===")
if 'SP001' in optimizer.graph:
    for dest, edge in optimizer.graph['SP001'].items():
        print(f"  SP001 -> {dest}: {edge['distance_km']} km, threat: {edge['threat_level']}")

print("\n=== TESTING PATH FINDING ===")
test_dests = ['D001', 'D002', 'D003', 'D004', 'D005', 'D006', 'D007']
for dest in test_dests:
    dist, path, threat = optimizer._find_path_distance('SP001', dest, avoid_high_threat=True)
    print(f"  SP001 -> {dest}: dist={dist}, path={path}, threat={threat}")

print("\n=== CHECKING CAPACITY CONSTRAINTS ===")
vehicle = sp001_vehicles.iloc[0]  # PLS with 16.5 tons
print(f"Vehicle: {vehicle['vehicle_id']}, Capacity: {vehicle['capacity_tons']} tons, Range: {vehicle['max_range_km']} km")

# Check each high-priority destination
for _, dest in dests.head(6).iterrows():
    demand = dest['demand_tons']
    dest_id = dest['dest_id']
    
    dist_to, _, _ = optimizer._find_path_distance('SP001', dest_id, True)
    dist_back, _, _ = optimizer._find_path_distance(dest_id, 'SP001', True)
    
    print(f"\n  {dest_id} ({dest['dest_name']}): demand={demand} tons")
    print(f"    Distance to: {dist_to} km, back: {dist_back} km, total: {dist_to + dist_back} km")
    print(f"    Fits capacity? {demand <= vehicle['capacity_tons']}")
    print(f"    Fits range? {dist_to + dist_back <= vehicle['max_range_km']}")
