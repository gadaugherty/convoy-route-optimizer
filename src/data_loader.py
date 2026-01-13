"""
Data Loader Module
Handles ingestion and cleaning of messy logistics data.
"""

import pandas as pd
import os
from typing import Tuple, Optional


def load_and_clean_supply_points(filepath: str) -> pd.DataFrame:
    """
    Load and clean supply points data.
    Handles: missing values, inconsistent IDs, status normalization.
    """
    df = pd.read_csv(filepath)
    
    # Normalize column names
    df.columns = df.columns.str.lower().str.strip()
    
    # Normalize ID format (uppercase)
    df['id'] = df['id'].str.upper()
    
    # Normalize status (lowercase)
    df['status'] = df['status'].str.lower().str.strip()
    
    # Fill missing names with ID
    df['name'] = df['name'].fillna(df['id'])
    
    # Fill missing inventory with median
    median_inventory = df['inventory_tons'].median()
    df['inventory_tons'] = df['inventory_tons'].fillna(median_inventory)
    
    # Filter to active supply points only
    df = df[df['status'] == 'active'].copy()
    
    # Reset index
    df = df.reset_index(drop=True)
    
    print(f"Loaded {len(df)} active supply points")
    return df


def load_and_clean_destinations(filepath: str) -> pd.DataFrame:
    """
    Load and clean destination data.
    Handles: column name variations, priority normalization, missing values.
    """
    df = pd.read_csv(filepath)
    
    # Normalize column names
    df.columns = df.columns.str.lower().str.strip()
    
    # Rename coordinate columns if needed
    if 'latitude' in df.columns:
        df = df.rename(columns={'latitude': 'lat', 'longitude': 'lon'})
    
    # Normalize priority levels
    df['priority'] = df['priority'].fillna('medium')
    df['priority'] = df['priority'].str.lower().str.strip()
    
    # Map priority to numeric scores for optimization
    priority_map = {'high': 3, 'medium': 2, 'low': 1}
    df['priority_score'] = df['priority'].map(priority_map).fillna(2)
    
    # Clean destination names
    df['dest_name'] = df['dest_name'].str.title()
    
    print(f"Loaded {len(df)} destinations")
    return df


def load_and_clean_vehicles(filepath: str) -> pd.DataFrame:
    """
    Load and clean vehicle fleet data.
    Handles: status normalization, missing range values, type standardization.
    """
    df = pd.read_csv(filepath)
    
    # Normalize column names
    df.columns = df.columns.str.lower().str.strip()
    
    # Normalize status and type
    df['status'] = df['status'].str.lower().str.strip()
    df['type'] = df['type'].str.upper()
    
    # Fill missing range with type-based defaults
    range_defaults = {'HEMTT': 480, 'M1078': 560, 'PLS': 520}
    for vtype, default_range in range_defaults.items():
        mask = (df['type'] == vtype) & (df['max_range_km'].isna())
        df.loc[mask, 'max_range_km'] = default_range
    
    # Filter to available vehicles only
    df = df[df['status'] == 'available'].copy()
    
    # Reset index
    df = df.reset_index(drop=True)
    
    print(f"Loaded {len(df)} available vehicles")
    return df


def load_and_clean_routes(filepath: str) -> pd.DataFrame:
    """
    Load and clean route/road network data.
    Handles: threat level normalization, missing road conditions, numeric conversion.
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
    
    # Calculate effective distance (distance * threat multiplier)
    df['effective_distance'] = df['distance_km'] * df['threat_multiplier']
    
    print(f"Loaded {len(df)} route segments")
    return df


def load_all_data(data_dir: str = 'data') -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Load and clean all data files from the data directory.
    
    Returns:
        Tuple of (supply_points, destinations, vehicles, routes) DataFrames
    """
    supply_points = load_and_clean_supply_points(os.path.join(data_dir, 'supply_points.csv'))
    destinations = load_and_clean_destinations(os.path.join(data_dir, 'destinations.csv'))
    vehicles = load_and_clean_vehicles(os.path.join(data_dir, 'vehicles.csv'))
    routes = load_and_clean_routes(os.path.join(data_dir, 'routes.csv'))
    
    return supply_points, destinations, vehicles, routes


if __name__ == '__main__':
    # Test data loading
    supply_points, destinations, vehicles, routes = load_all_data()
    
    print("\n--- Supply Points Sample ---")
    print(supply_points.head())
    
    print("\n--- Destinations Sample ---")
    print(destinations.head())
    
    print("\n--- Vehicles Sample ---")
    print(vehicles.head())
    
    print("\n--- Routes Sample ---")
    print(routes.head())
