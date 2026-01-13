#!/usr/bin/env python3
"""
Convoy Route Optimizer
Military logistics route optimization tool.

Usage:
    python main.py [--supply-point SP_ID] [--avoid-high-threat] [--output-map]
"""

import argparse
import os
import sys

from src.data_loader import load_all_data
from src.optimizer import ConvoyOptimizer, print_assignments
from src.visualize import create_operations_map


def main():
    parser = argparse.ArgumentParser(
        description='Optimize convoy routes for military logistics operations'
    )
    parser.add_argument(
        '--supply-point', '-sp',
        default='SP001',
        help='Supply point ID to route from (default: SP001)'
    )
    parser.add_argument(
        '--avoid-high-threat', '-safe',
        action='store_true',
        default=True,
        help='Avoid high-threat routes (default: True)'
    )
    parser.add_argument(
        '--include-high-threat',
        action='store_true',
        help='Include high-threat routes in optimization'
    )
    parser.add_argument(
        '--output-map', '-map',
        action='store_true',
        help='Generate interactive HTML map'
    )
    parser.add_argument(
        '--data-dir', '-d',
        default='data',
        help='Directory containing CSV data files'
    )
    
    args = parser.parse_args()
    
    # Determine threat avoidance setting
    avoid_high_threat = not args.include_high_threat
    
    print("="*60)
    print("CONVOY ROUTE OPTIMIZER")
    print("="*60)
    print(f"\nLoading data from: {args.data_dir}/")
    
    # Load and clean data
    try:
        supply_points, destinations, vehicles, routes = load_all_data(args.data_dir)
    except FileNotFoundError as e:
        print(f"\nError: Could not find data files. {e}")
        print("Make sure CSV files exist in the data/ directory.")
        sys.exit(1)
    
    # Validate supply point
    if args.supply_point not in supply_points['id'].values:
        print(f"\nError: Supply point '{args.supply_point}' not found.")
        print(f"Available supply points: {supply_points['id'].tolist()}")
        sys.exit(1)
    
    # Get supply point info
    sp_info = supply_points[supply_points['id'] == args.supply_point].iloc[0]
    print(f"\nOptimizing routes from: {sp_info['name']} ({args.supply_point})")
    print(f"Inventory available: {sp_info['inventory_tons']} tons")
    print(f"Threat avoidance: {'HIGH threat routes excluded' if avoid_high_threat else 'All routes included'}")
    
    # Create optimizer
    optimizer = ConvoyOptimizer(
        supply_points=supply_points,
        destinations=destinations,
        vehicles=vehicles,
        routes=routes
    )
    
    # Get available vehicles at this supply point
    available_vehicles = vehicles[
        vehicles['home_base'] == args.supply_point
    ]['vehicle_id'].tolist()
    
    if not available_vehicles:
        print(f"\nWarning: No vehicles stationed at {args.supply_point}")
        print("Using all available vehicles instead.")
        available_vehicles = vehicles['vehicle_id'].tolist()
    else:
        print(f"Vehicles available: {len(available_vehicles)}")
    
    # Run optimization
    print("\nRunning optimization...")
    assignments = optimizer.optimize_routes(
        supply_point_id=args.supply_point,
        available_vehicles=available_vehicles,
        avoid_high_threat=avoid_high_threat
    )
    
    # Display results
    if assignments:
        print_assignments(assignments)
        
        # Summary statistics
        stats = optimizer.get_summary_stats(assignments)
        print("\n" + "="*60)
        print("MISSION SUMMARY")
        print("="*60)
        print(f"  Total Convoys: {stats['total_convoys']}")
        print(f"  Destinations Served: {stats['destinations_served']} / {len(destinations)}")
        print(f"  Total Distance: {stats['total_distance_km']} km")
        print(f"  Total Cargo: {stats['total_demand_tons']} tons")
        print(f"  Avg Distance/Convoy: {stats['avg_distance_per_convoy']} km")
        print(f"  Threat Exposure: {stats['threat_exposure_summary']}")
        
        # Unserved destinations
        served = set()
        for a in assignments:
            served.update(a.destinations)
        unserved = set(destinations['dest_id']) - served
        
        if unserved:
            print(f"\n  ⚠ Unserved Destinations: {len(unserved)}")
            for dest_id in unserved:
                dest = destinations[destinations['dest_id'] == dest_id].iloc[0]
                print(f"    - {dest['dest_name']} ({dest_id}): {dest['demand_tons']} tons")
    else:
        print("\nNo valid routes found. Check vehicle availability and route network.")
    
    # Generate map if requested
    if args.output_map:
        print("\n" + "="*60)
        print("GENERATING MAP")
        print("="*60)
        
        output_path = 'output/operations_map.html'
        create_operations_map(
            supply_points=supply_points,
            destinations=destinations,
            routes=routes,
            assignments=assignments,
            output_path=output_path
        )
        print(f"\nOpen {output_path} in a browser to view the interactive map.")
    
    print("\n" + "="*60)
    print("OPTIMIZATION COMPLETE")
    print("="*60 + "\n")
    
    return assignments


if __name__ == '__main__':
    main()
