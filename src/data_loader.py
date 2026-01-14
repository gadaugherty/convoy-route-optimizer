"""
Data Loader Module
Handles ingestion and cleaning of messy logistics data.
"""

import pandas as pd
import os
from typing import Tuple


# Supply categories
SUPPLY_CATEGORIES = ['food', 'ammo', 'fuel', 'medical']


def load_and_clean_supply_points(filepath: str) -> pd.DataFrame:
    """
    Load and clean supply points data with categorized inventory.
    """
    df = pd.read_csv(filepath, comment='#')
    
    # Normalize column names
    df.columns = df.columns.str.lower().str.strip()
    
    # Normalize ID format (uppercase)
    df['id'] = df['id'].str.upper()
    
    # Normalize status (lowercase)
    df['status'] = df['status'].str.lower().str.strip()
    
    # Fill missing names with ID
    df['name'] = df['name'].fillna(df['id'])
    
    # Handle categorized inventory columns
    for cat in SUPPLY_CATEGORIES:
        col = f'{cat}_tons'
        if col in df.columns:
            df[col] = df[col].fillna(0)
        else:
            df[col] = 0
    
    # Calculate total inventory (row-wise sum across supply categories)
    df['total_inventory_tons'] = df[[f'{cat}_tons' for cat in SUPPLY_CATEGORIES]].sum(axis=1)
    
    # Handle optional columns
    if 'region' not in df.columns:
        df['region'] = 'UNKNOWN'
    if 'country' not in df.columns:
        df['country'] = 'UNKNOWN'
    if 'base_type' not in df.columns:
        df['base_type'] = 'UNKNOWN'
    if 'troops' not in df.columns:
        df['troops'] = 0
    
    # Filter to active supply points only
    df = df[df['status'] == 'active'].copy()
    df = df.reset_index(drop=True)
    
    print(f"Loaded {len(df)} active supply points")
    return df


def load_and_clean_destinations(filepath: str) -> pd.DataFrame:
    """
    Load and clean destination data with categorized demand.
    """
    df = pd.read_csv(filepath, comment='#')
    
    # Normalize column names
    df.columns = df.columns.str.lower().str.strip()
    
    # Rename coordinate columns if needed
    if 'latitude' in df.columns:
        df = df.rename(columns={'latitude': 'lat', 'longitude': 'lon'})
    
    # Normalize priority levels
    df['priority'] = df['priority'].fillna('medium')
    df['priority'] = df['priority'].str.lower().str.strip()
    
    # Map priority to numeric scores
    priority_map = {'high': 3, 'medium': 2, 'low': 1}
    df['priority_score'] = df['priority'].map(priority_map).fillna(2)
    
    # Clean destination names
    df['dest_name'] = df['dest_name'].str.title()
    
    # Handle categorized demand columns
    for cat in SUPPLY_CATEGORIES:
        col = f'{cat}_tons'
        if col in df.columns:
            df[col] = df[col].fillna(0)
        else:
            df[col] = 0
    
    # Calculate total demand (row-wise sum across supply categories)
    df['total_demand_tons'] = df[[f'{cat}_tons' for cat in SUPPLY_CATEGORIES]].sum(axis=1)
    
    # Handle optional columns
    if 'region' not in df.columns:
        df['region'] = 'UNKNOWN'
    if 'country' not in df.columns:
        df['country'] = 'UNKNOWN'
    
    print(f"Loaded {len(df)} destinations")
    return df


def load_and_clean_vehicles(filepath: str) -> pd.DataFrame:
    """
    Load and clean vehicle fleet data.
    """
    df = pd.read_csv(filepath)
    
    # Normalize column names
    df.columns = df.columns.str.lower().str.strip()
    
    # Normalize status and type
    df['status'] = df['status'].str.lower().str.strip()
    df['type'] = df['type'].str.upper()
    
    # Normalize mode (GROUND, AIR, WATER)
    if 'mode' in df.columns:
        df['mode'] = df['mode'].str.upper().str.strip()
    else:
        df['mode'] = 'GROUND'  # Default to ground
    
    # Fill missing speed with mode-based defaults
    if 'speed_kmh' not in df.columns:
        df['speed_kmh'] = 80  # Default speed
    speed_defaults = {'GROUND': 80, 'AIR': 300, 'WATER': 40}
    for mode, default_speed in speed_defaults.items():
        mask = (df['mode'] == mode) & (df['speed_kmh'].isna())
        df.loc[mask, 'speed_kmh'] = default_speed
    
    # Fill missing range with mode-based defaults
    range_defaults = {'GROUND': 500, 'AIR': 800, 'WATER': 400}
    for mode, default_range in range_defaults.items():
        mask = (df['mode'] == mode) & (df['max_range_km'].isna())
        df.loc[mask, 'max_range_km'] = default_range
    
    # Filter to available vehicles only
    df = df[df['status'] == 'available'].copy()
    df = df.reset_index(drop=True)
    
    print(f"Loaded {len(df)} available vehicles")
    return df


def load_and_clean_routes(filepath: str) -> pd.DataFrame:
    """
    Load and clean route/road network data.
    """
    df = pd.read_csv(filepath)
    
    # Normalize column names
    df.columns = df.columns.str.lower().str.strip()
    
    # Normalize threat levels
    df['threat_level'] = df['threat_level'].fillna('medium')
    df['threat_level'] = df['threat_level'].str.lower().str.strip()
    
    # Map threat to numeric cost multiplier
    threat_cost = {'low': 1.0, 'medium': 1.5, 'high': 2.5}
    df['threat_multiplier'] = df['threat_level'].map(threat_cost).fillna(1.5)
    
    # Fill missing road conditions
    df['road_condition'] = df['road_condition'].fillna('unknown')
    df['road_condition'] = df['road_condition'].str.lower()
    
    # Calculate effective distance
    df['effective_distance'] = df['distance_km'] * df['threat_multiplier']
    
    print(f"Loaded {len(df)} route segments")
    return df


def load_all_data(data_dir: str = 'data') -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Load and clean all data files from the data directory.
    """
    supply_points = load_and_clean_supply_points(os.path.join(data_dir, 'supply_points.csv'))
    destinations = load_and_clean_destinations(os.path.join(data_dir, 'destinations.csv'))
    vehicles = load_and_clean_vehicles(os.path.join(data_dir, 'vehicles.csv'))
    routes = load_and_clean_routes(os.path.join(data_dir, 'routes.csv'))
    
    return supply_points, destinations, vehicles, routes


if __name__ == '__main__':
    supply_points, destinations, vehicles, routes = load_all_data()
    
    print("\n--- Supply Points Sample ---")
    print(supply_points.head())
    
    print("\n--- Destinations Sample ---")
    print(destinations.head())
