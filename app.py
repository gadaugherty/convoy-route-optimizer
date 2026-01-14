#!/usr/bin/env python3
"""
Convoy Route Optimizer - Flask Web Application
Real-time military logistics optimization dashboard.
"""

from flask import Flask, render_template, jsonify, request
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.data_loader import load_all_data
from src.optimizer import ConvoyOptimizer

app = Flask(__name__, 
    template_folder='templates',
    static_folder='static'
)

# Load data globally
DATA_DIR = 'data'
supply_points, destinations, vehicles, routes = load_all_data(DATA_DIR)

# Create optimizer
optimizer = ConvoyOptimizer(
    supply_points=supply_points,
    destinations=destinations,
    vehicles=vehicles,
    routes=routes
)


def get_coords_dict():
    """Build coordinate lookup dictionary."""
    coords = {}
    for _, sp in supply_points.iterrows():
        coords[sp['id']] = {'lat': sp['lat'], 'lon': sp['lon'], 'name': sp['name']}
    for _, dest in destinations.iterrows():
        coords[dest['dest_id']] = {'lat': dest['lat'], 'lon': dest['lon'], 'name': dest['dest_name']}
    return coords


@app.route('/')
def index():
    """Main dashboard page."""
    return render_template('index.html')


@app.route('/api/supply-points')
def get_supply_points():
    """Get all supply points."""
    data = []
    for _, sp in supply_points.iterrows():
        data.append({
            'id': sp['id'],
            'name': sp['name'],
            'lat': sp['lat'],
            'lon': sp['lon'],
            'region': sp.get('region', 'UNKNOWN'),
            'country': sp.get('country', 'UNKNOWN'),
            'base_type': sp.get('base_type', 'UNKNOWN'),
            'troops': int(sp.get('troops', 0)),
            'food_tons': sp.get('food_tons', 0),
            'ammo_tons': sp.get('ammo_tons', 0),
            'fuel_tons': sp.get('fuel_tons', 0),
            'medical_tons': sp.get('medical_tons', 0),
            'total_inventory': sp.get('total_inventory_tons', 0)
        })
    return jsonify(data)


@app.route('/api/destinations')
def get_destinations():
    """Get all destinations."""
    data = []
    for _, dest in destinations.iterrows():
        data.append({
            'id': dest['dest_id'],
            'name': dest['dest_name'],
            'lat': dest['lat'],
            'lon': dest['lon'],
            'region': dest.get('region', 'UNKNOWN'),
            'country': dest.get('country', 'UNKNOWN'),
            'priority': dest['priority'],
            'food_tons': dest.get('food_tons', 0),
            'ammo_tons': dest.get('ammo_tons', 0),
            'fuel_tons': dest.get('fuel_tons', 0),
            'medical_tons': dest.get('medical_tons', 0),
            'total_demand': dest.get('total_demand_tons', 0)
        })
    return jsonify(data)


@app.route('/api/vehicles')
def get_vehicles():
    """Get all vehicles."""
    data = []
    for _, v in vehicles.iterrows():
        data.append({
            'id': v['vehicle_id'],
            'type': v['type'],
            'mode': v.get('mode', 'GROUND'),
            'capacity': v['capacity_tons'],
            'max_range': v['max_range_km'],
            'speed_kmh': v.get('speed_kmh', 80),
            'home_base': v['home_base']
        })
    return jsonify(data)


@app.route('/api/routes')
def get_routes():
    """Get all route segments."""
    coords = get_coords_dict()
    data = []
    for _, r in routes.iterrows():
        from_id = r['from_point']
        to_id = r['to_point']
        
        if from_id in coords and to_id in coords:
            data.append({
                'from_id': from_id,
                'to_id': to_id,
                'from_coords': [coords[from_id]['lat'], coords[from_id]['lon']],
                'to_coords': [coords[to_id]['lat'], coords[to_id]['lon']],
                'distance_km': r['distance_km'],
                'threat_level': r['threat_level'],
                'road_condition': r['road_condition']
            })
    return jsonify(data)


@app.route('/api/optimize', methods=['POST'])
def optimize():
    """Run optimization for a supply point."""
    data = request.get_json()
    
    supply_point_id = data.get('supply_point', 'SP001')
    avoid_high_threat = data.get('avoid_high_threat', True)
    selected_vehicles = data.get('vehicles', None)
    
    # Get available vehicles
    if selected_vehicles:
        available_vehicles = selected_vehicles
    else:
        available_vehicles = vehicles[
            vehicles['home_base'] == supply_point_id
        ]['vehicle_id'].tolist()
        
        # If no vehicles at this base, use all available
        if not available_vehicles:
            available_vehicles = vehicles['vehicle_id'].tolist()
    
    # Run optimization
    assignments = optimizer.optimize_routes(
        supply_point_id=supply_point_id,
        available_vehicles=available_vehicles,
        avoid_high_threat=avoid_high_threat
    )
    
    # Get coordinates for building routes
    coords = get_coords_dict()
    
    # Format response
    convoy_data = []
    for i, a in enumerate(assignments):
        # Build coordinate path
        route_coords = []
        for loc_id in a.route_sequence:
            if loc_id in coords:
                route_coords.append([coords[loc_id]['lat'], coords[loc_id]['lon']])
        
        # Calculate ETA (assuming 60 km/h)
        eta_hours = a.total_distance_km / 60
        if eta_hours < 1:
            eta_str = f"{int(eta_hours * 60)} min"
        else:
            h = int(eta_hours)
            m = int((eta_hours - h) * 60)
            eta_str = f"{h}h {m}m"
        
        # Calculate ETA using actual vehicle speed
        speed = getattr(a, 'speed_kmh', 80)
        eta_hours = a.total_distance_km / speed
        if eta_hours < 1:
            eta_str = f"{int(eta_hours * 60)} min"
        else:
            h = int(eta_hours)
            m = int((eta_hours - h) * 60)
            eta_str = f"{h}h {m}m"
        
        # Determine transport mode
        mode = getattr(a, 'vehicle_mode', 'GROUND')
        
        convoy_data.append({
            'id': i + 1,
            'vehicle_id': a.vehicle_id,
            'vehicle_type': a.vehicle_type,
            'mode': mode,
            'speed_kmh': speed,
            'supply_point': a.supply_point,
            'destinations': a.destinations,
            'route_sequence': a.route_sequence,
            'route_coords': route_coords,
            'total_distance_km': a.total_distance_km,
            'total_demand_tons': a.total_demand_tons,
            'threat_exposure': a.threat_exposure,
            'eta': eta_str
        })
    
    # Calculate summary stats
    total_distance = sum(a.total_distance_km for a in assignments)
    total_cargo = sum(a.total_demand_tons for a in assignments)
    served_destinations = set()
    for a in assignments:
        served_destinations.update(a.destinations)
    
    return jsonify({
        'success': True,
        'convoys': convoy_data,
        'summary': {
            'total_convoys': len(assignments),
            'total_distance_km': round(total_distance, 1),
            'total_cargo_tons': round(total_cargo, 1),
            'destinations_served': len(served_destinations),
            'total_destinations': len(destinations)
        }
    })


@app.route('/api/road-route')
def get_road_route():
    """Get actual road route between two points using OSRM."""
    import requests
    
    start_lat = request.args.get('start_lat', type=float)
    start_lon = request.args.get('start_lon', type=float)
    end_lat = request.args.get('end_lat', type=float)
    end_lon = request.args.get('end_lon', type=float)
    
    if not all([start_lat, start_lon, end_lat, end_lon]):
        return jsonify({'error': 'Missing coordinates'}), 400
    
    try:
        url = f"http://router.project-osrm.org/route/v1/driving/{start_lon},{start_lat};{end_lon},{end_lat}"
        params = {'overview': 'full', 'geometries': 'geojson'}
        response = requests.get(url, params=params, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            if data['code'] == 'Ok' and data['routes']:
                coords = data['routes'][0]['geometry']['coordinates']
                # Convert from [lon, lat] to [lat, lon]
                path = [[c[1], c[0]] for c in coords]
                return jsonify({'path': path})
    except Exception as e:
        pass
    
    # Fallback to straight line
    return jsonify({'path': [[start_lat, start_lon], [end_lat, end_lon]]})


if __name__ == '__main__':
    print("\n" + "="*60)
    print("CONVOY ROUTE OPTIMIZER - WEB DASHBOARD")
    print("="*60)
    print(f"\nServer starting...")
    print(f"Open http://localhost:5000 in your browser")
    print("="*60 + "\n")
    
    app.run(debug=True, host='0.0.0.0', port=5000)
