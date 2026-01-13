# Convoy Route Optimizer

A military logistics optimization tool that takes messy operational data and produces optimized convoy routes while accounting for vehicle capacity, range constraints, and threat levels.

Built to demonstrate data wrangling, constraint-based optimization, and operational planning skills.

## Problem Statement

Military logistics operations face complex routing challenges:
- Multiple supply points and forward operating bases
- Vehicle fleets with varying capacity and range
- Road networks with different threat levels
- Priority-based delivery requirements
- Real-world messy data from multiple sources

This tool ingests imperfect data, cleans it, and outputs actionable convoy assignments.

## Features

- **Data Ingestion & Cleaning**: Handles inconsistent formats, missing values, and normalization
- **Constraint-Based Optimization**: Respects vehicle capacity, fuel range, and threat avoidance
- **Priority Scheduling**: High-priority destinations served first
- **Threat-Aware Routing**: Option to avoid high-risk road segments
- **Interactive Visualization**: HTML maps showing routes, threat levels, and assignments

## Tech Stack

| Component | Technology |
|-----------|------------|
| Language | Python 3.10+ |
| Data Processing | pandas, numpy |
| Optimization | Google OR-Tools |
| Visualization | Folium (Leaflet.js maps) |

## Project Structure

```
convoy-route-optimizer/
├── data/
│   ├── supply_points.csv    # Base locations and inventory
│   ├── destinations.csv     # Delivery points and demand
│   ├── vehicles.csv         # Fleet capacity and status
│   └── routes.csv           # Road network with threat levels
├── src/
│   ├── data_loader.py       # Data ingestion and cleaning
│   ├── optimizer.py         # Route optimization engine
│   └── visualize.py         # Map generation
├── output/                   # Generated maps and reports
├── main.py                   # CLI entry point
├── requirements.txt
└── README.md
```

## Quick Start

### Installation

```bash
git clone https://github.com/gadaugherty/convoy-route-optimizer.git
cd convoy-route-optimizer
pip install -r requirements.txt
```

### Usage

Basic run with default settings:
```bash
python main.py
```

Generate interactive map:
```bash
python main.py --output-map
```

Route from a specific supply point:
```bash
python main.py --supply-point SP004 --output-map
```

Include high-threat routes (for urgent missions):
```bash
python main.py --include-high-threat --output-map
```

### Example Output

```
============================================================
CONVOY ROUTE ASSIGNMENTS
============================================================

Convoy 1: V001 (HEMTT)
  Route: SP001 -> D001 -> D002 -> D004 -> SP001
  Destinations: 3
  Total Distance: 48.8 km
  Cargo: 60 tons
  Threat Exposure: LOW

Convoy 2: V002 (HEMTT)
  Route: SP001 -> D003 -> SP001
  Destinations: 1
  Total Distance: 35.4 km
  Cargo: 30 tons
  Threat Exposure: MEDIUM

============================================================
MISSION SUMMARY
============================================================
  Total Convoys: 2
  Destinations Served: 4 / 12
  Total Distance: 84.2 km
  Total Cargo: 90 tons
```

## Data Format

The tool expects CSV files with the following schemas (handles messy data):

**supply_points.csv**
```
id,name,lat,lon,inventory_tons,status
SP001,Camp Liberty,33.312,-44.366,150,active
```

**destinations.csv**
```
dest_id,dest_name,lat,lon,demand_tons,priority
D001,Patrol Base Alpha,33.245,-44.412,25,HIGH
```

**vehicles.csv**
```
vehicle_id,type,capacity_tons,max_range_km,status,home_base
V001,HEMTT,10,480,available,SP001
```

**routes.csv**
```
route_id,from_point,to_point,distance_km,road_condition,threat_level
R001,SP001,D001,12.5,paved,low
```

## Algorithm

The optimizer uses a greedy nearest-neighbor heuristic with constraint checking:

1. **Sort destinations** by priority (HIGH → MEDIUM → LOW)
2. **For each available vehicle**:
   - Find nearest unassigned destination
   - Check capacity constraint (cumulative demand ≤ vehicle capacity)
   - Check range constraint (round-trip distance ≤ max range)
   - Check threat constraint (skip HIGH threat if flag set)
   - Assign and continue until no feasible destinations remain
3. **Return** list of convoy assignments with routes

Future improvements could include:
- Full Vehicle Routing Problem (VRP) solver using OR-Tools
- Time windows for delivery
- Multi-depot optimization
- Dynamic re-routing based on real-time threat intel

## Visualization

The tool generates interactive HTML maps using Folium:

- **Blue markers**: Supply points
- **Colored circles**: Destinations (red=high priority, orange=medium, green=low)
- **Route lines**: Colored by threat level (green=low, yellow=medium, red=high)
- **Dashed lines**: Optimized convoy routes

## Why This Project?

This project demonstrates skills relevant to defense tech and enterprise software:

- **Data Engineering**: Real operational data is messy. This shows ability to ingest, clean, and normalize disparate data sources.
- **Optimization**: Logistics is fundamentally about optimization under constraints—a core problem in military operations.
- **Practical AI/Software**: Not just ML models, but software that solves real operational problems.
- **Domain Understanding**: Military logistics context shows ability to learn and apply domain knowledge.

## License

MIT

## Author

Built by a U.S. military veteran transitioning to tech.
