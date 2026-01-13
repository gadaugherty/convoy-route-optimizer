"""
Visualization Module
Creates interactive maps of convoy routes and logistics network.
"""

import pandas as pd
import folium
from folium import plugins
from typing import List, Optional
import sys
import os

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.optimizer import ConvoyAssignment


# Color scheme for threat levels
THREAT_COLORS = {
    'low': '#28a745',      # Green
    'medium': '#ffc107',   # Yellow
    'high': '#dc3545'      # Red
}

# Colors for different convoys
CONVOY_COLORS = [
    '#007bff',  # Blue
    '#6f42c1',  # Purple
    '#e83e8c',  # Pink
    '#fd7e14',  # Orange
    '#20c997',  # Teal
    '#17a2b8',  # Cyan
]


def create_base_map(
    supply_points: pd.DataFrame,
    destinations: pd.DataFrame,
    center: Optional[List[float]] = None
) -> folium.Map:
    """
    Create base map with supply points and destinations marked.
    """
    # Calculate center if not provided
    if center is None:
        all_lats = list(supply_points['lat']) + list(destinations['lat'])
        all_lons = list(supply_points['lon']) + list(destinations['lon'])
        center = [sum(all_lats) / len(all_lats), sum(all_lons) / len(all_lons)]
    
    # Create map
    m = folium.Map(
        location=center,
        zoom_start=8,
        tiles='CartoDB positron'
    )
    
    # Add supply points (blue squares)
    for _, sp in supply_points.iterrows():
        folium.Marker(
            location=[sp['lat'], sp['lon']],
            popup=f"""
                <b>{sp['name']}</b><br>
                ID: {sp['id']}<br>
                Inventory: {sp['inventory_tons']} tons
            """,
            icon=folium.Icon(color='blue', icon='warehouse', prefix='fa')
        ).add_to(m)
    
    # Add destinations (red circles)
    for _, dest in destinations.iterrows():
        priority_color = {
            'high': 'red',
            'medium': 'orange', 
            'low': 'green'
        }.get(dest['priority'], 'gray')
        
        folium.CircleMarker(
            location=[dest['lat'], dest['lon']],
            radius=8,
            popup=f"""
                <b>{dest['dest_name']}</b><br>
                ID: {dest['dest_id']}<br>
                Demand: {dest['demand_tons']} tons<br>
                Priority: {dest['priority'].upper()}
            """,
            color=priority_color,
            fill=True,
            fillOpacity=0.7
        ).add_to(m)
    
    return m


def add_route_network(
    m: folium.Map,
    routes: pd.DataFrame,
    supply_points: pd.DataFrame,
    destinations: pd.DataFrame
) -> folium.Map:
    """
    Add route network to map, colored by threat level.
    """
    # Create lookup for coordinates
    coords = {}
    
    for _, sp in supply_points.iterrows():
        coords[sp['id']] = [sp['lat'], sp['lon']]
    
    for _, dest in destinations.iterrows():
        coords[dest['dest_id']] = [dest['lat'], dest['lon']]
    
    # Add routes
    for _, route in routes.iterrows():
        from_id = route['from_point']
        to_id = route['to_point']
        
        if from_id not in coords or to_id not in coords:
            continue
        
        color = THREAT_COLORS.get(route['threat_level'], '#999999')
        
        folium.PolyLine(
            locations=[coords[from_id], coords[to_id]],
            weight=3,
            color=color,
            opacity=0.6,
            popup=f"""
                Route: {from_id} → {to_id}<br>
                Distance: {route['distance_km']} km<br>
                Threat: {route['threat_level'].upper()}<br>
                Condition: {route['road_condition']}
            """
        ).add_to(m)
    
    return m


def add_convoy_routes(
    m: folium.Map,
    assignments: List[ConvoyAssignment],
    supply_points: pd.DataFrame,
    destinations: pd.DataFrame
) -> folium.Map:
    """
    Add optimized convoy routes to map.
    """
    # Create lookup for coordinates
    coords = {}
    
    for _, sp in supply_points.iterrows():
        coords[sp['id']] = [sp['lat'], sp['lon']]
    
    for _, dest in destinations.iterrows():
        coords[dest['dest_id']] = [dest['lat'], dest['lon']]
    
    # Create feature group for convoy routes
    convoy_group = folium.FeatureGroup(name='Convoy Routes')
    
    for i, assignment in enumerate(assignments):
        color = CONVOY_COLORS[i % len(CONVOY_COLORS)]
        
        # Build route coordinates
        route_coords = []
        for loc_id in assignment.route_sequence:
            if loc_id in coords:
                route_coords.append(coords[loc_id])
        
        if len(route_coords) < 2:
            continue
        
        # Add route line with animation
        folium.PolyLine(
            locations=route_coords,
            weight=5,
            color=color,
            opacity=0.8,
            popup=f"""
                <b>Convoy: {assignment.vehicle_id}</b><br>
                Type: {assignment.vehicle_type}<br>
                Stops: {len(assignment.destinations)}<br>
                Distance: {assignment.total_distance_km} km<br>
                Cargo: {assignment.total_demand_tons} tons<br>
                Threat: {assignment.threat_exposure.upper()}
            """,
            dash_array='10, 10'
        ).add_to(convoy_group)
        
        # Add numbered markers for stops
        for j, loc_id in enumerate(assignment.route_sequence[1:-1], 1):
            if loc_id in coords:
                folium.Marker(
                    location=coords[loc_id],
                    icon=plugins.BeautifyIcon(
                        number=j,
                        border_color=color,
                        background_color=color,
                        text_color='white'
                    )
                ).add_to(convoy_group)
    
    convoy_group.add_to(m)
    
    return m


def add_legend(m: folium.Map) -> folium.Map:
    """Add a legend to the map."""
    legend_html = """
    <div style="position: fixed; bottom: 50px; left: 50px; z-index: 1000; 
                background-color: white; padding: 10px; border-radius: 5px;
                border: 2px solid gray; font-size: 14px;">
        <b>Legend</b><br>
        <i class="fa fa-warehouse" style="color: blue;"></i> Supply Point<br>
        <svg height="12" width="12"><circle cx="6" cy="6" r="5" fill="red"/></svg> High Priority Dest<br>
        <svg height="12" width="12"><circle cx="6" cy="6" r="5" fill="orange"/></svg> Medium Priority Dest<br>
        <svg height="12" width="12"><circle cx="6" cy="6" r="5" fill="green"/></svg> Low Priority Dest<br>
        <hr style="margin: 5px 0;">
        <b>Threat Level</b><br>
        <svg height="4" width="30"><line x1="0" y1="2" x2="30" y2="2" style="stroke:#28a745;stroke-width:3"/></svg> Low<br>
        <svg height="4" width="30"><line x1="0" y1="2" x2="30" y2="2" style="stroke:#ffc107;stroke-width:3"/></svg> Medium<br>
        <svg height="4" width="30"><line x1="0" y1="2" x2="30" y2="2" style="stroke:#dc3545;stroke-width:3"/></svg> High<br>
    </div>
    """
    m.get_root().html.add_child(folium.Element(legend_html))
    return m


def create_operations_map(
    supply_points: pd.DataFrame,
    destinations: pd.DataFrame,
    routes: pd.DataFrame,
    assignments: Optional[List[ConvoyAssignment]] = None,
    show_all_routes: bool = True,
    output_path: str = 'output/operations_map.html'
) -> folium.Map:
    """
    Create complete operations map with all layers.
    
    Args:
        supply_points: Cleaned supply points DataFrame
        destinations: Cleaned destinations DataFrame
        routes: Cleaned routes DataFrame
        assignments: Optional list of convoy assignments to display
        show_all_routes: Whether to show the full route network
        output_path: Where to save the HTML file
    """
    # Create base map
    m = create_base_map(supply_points, destinations)
    
    # Add route network
    if show_all_routes:
        m = add_route_network(m, routes, supply_points, destinations)
    
    # Add convoy routes if provided
    if assignments:
        m = add_convoy_routes(m, assignments, supply_points, destinations)
    
    # Add legend
    m = add_legend(m)
    
    # Add layer control
    folium.LayerControl().add_to(m)
    
    # Ensure output directory exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    # Save map
    m.save(output_path)
    print(f"Map saved to {output_path}")
    
    return m


if __name__ == '__main__':
    from data_loader import load_all_data
    from optimizer import ConvoyOptimizer
    
    # Load data
    supply_points, destinations, vehicles, routes = load_all_data()
    
    # Create and run optimizer
    optimizer = ConvoyOptimizer(
        supply_points=supply_points,
        destinations=destinations,
        vehicles=vehicles,
        routes=routes
    )
    
    sp001_vehicles = vehicles[vehicles['home_base'] == 'SP001']['vehicle_id'].tolist()
    assignments = optimizer.optimize_routes(
        supply_point_id='SP001',
        available_vehicles=sp001_vehicles,
        avoid_high_threat=True
    )
    
    # Create map
    create_operations_map(
        supply_points=supply_points,
        destinations=destinations,
        routes=routes,
        assignments=assignments,
        output_path='output/operations_map.html'
    )
