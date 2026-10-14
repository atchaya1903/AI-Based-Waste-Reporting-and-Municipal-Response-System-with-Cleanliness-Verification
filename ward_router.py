import math
import random
import string
from datetime import datetime
from database import get_db

def haversine_distance(lat1, lon1, lat2, lon2):
    """Calculate distance in kilometers between two GPS coordinates using Haversine formula."""
    R = 6371.0  # Earth radius in km
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def generate_complaint_id():
    """Generate a unique complaint ID like CMP-2026-X7K2."""
    year = datetime.now().year
    suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
    return f"CMP-{year}-{suffix}"

def determine_priority(category):
    """Determine initial priority based on municipal risk policy."""
    high_priority = [
        "Waste near lakes, rivers, or drainage areas",
        "Illegal dumping",
        "Hazardous waste"
    ]
    urgent_priority = [
        "Overflowing dustbins",
        "Construction debris"
    ]
    
    if category in high_priority:
        return "High"
    elif category in urgent_priority:
        return "High"
    elif category == "Hazardous waste":
        return "Critical"
    else:
        return "Medium"

def route_complaint(lat, lng, category, ward_id=None):
    """
    Intelligently routes a complaint to the responsible Ward and Sanitation Department.
    Returns: (ward_id, department_id, ward_name, department_name, priority, notes)
    """
    conn = get_db()
    cursor = conn.cursor()

    assigned_ward = None
    assigned_dept = None
    routing_notes = []

    # 1. Ward determination
    if ward_id:
        cursor.execute("SELECT * FROM municipal_wards WHERE ward_id = ?", (ward_id,))
        assigned_ward = cursor.fetchone()
        if assigned_ward:
            routing_notes.append(f"Ward manually selected or verified: {assigned_ward['ward_name']}")
    
    if not assigned_ward and lat is not None and lng is not None:
        try:
            lat = float(lat)
            lng = float(lng)
            cursor.execute("SELECT * FROM municipal_wards")
            wards = cursor.fetchall()
            
            closest_ward = None
            min_dist = float('inf')
            
            for w in wards:
                dist = haversine_distance(lat, lng, w['lat_center'], w['lng_center'])
                if dist < min_dist:
                    min_dist = dist
                    closest_ward = w
            
            if closest_ward and min_dist <= 25.0:  # Within 25km municipal boundary
                assigned_ward = closest_ward
                routing_notes.append(f"Auto-routed to {closest_ward['ward_name']} (Distance: {min_dist:.2f} km)")
            else:
                routing_notes.append(f"Location outside standard radius ({min_dist:.2f} km). Assigned to Default Ward 1 for manual review.")
                cursor.execute("SELECT * FROM municipal_wards WHERE ward_id = 1")
                assigned_ward = cursor.fetchone()
        except (ValueError, TypeError):
            pass

    if not assigned_ward:
        cursor.execute("SELECT * FROM municipal_wards ORDER BY ward_id ASC LIMIT 1")
        assigned_ward = cursor.fetchone()
        routing_notes.append("Assigned to Central Ward (Default routing).")

    # 2. Department determination based on Category & Routing Rules
    # Rule Mapping:
    category_dept_mapping = {
        "Garbage dumped on roads": "SAN-01",              # Ward Sanitation & Street Cleaning
        "Overflowing dustbins": "SAN-01",                 # Ward Sanitation & Street Cleaning
        "Plastic waste accumulation": "REC-03",           # Plastic & Recycling Unit
        "Food and organic waste": "ORG-02",               # Organic & Food Waste Wing
        "Construction debris": "CDB-05",                  # Construction & Debris Taskforce
        "Waste near lakes, rivers, or drainage areas": "ECO-04", # River, Lake & Drainage Eco-Squad
        "Illegal dumping": "SAN-01",                      # Ward Sanitation
        "Unclean streets and public places": "SAN-01",    # Ward Sanitation
        "Hazardous waste": "HAZ-06"                       # Hazardous Materials Wing
    }

    target_code = category_dept_mapping.get(category, "SAN-01")
    cursor.execute("SELECT * FROM departments WHERE code = ?", (target_code,))
    assigned_dept = cursor.fetchone()

    if not assigned_dept:
        # Fallback to ward's primary department
        cursor.execute("SELECT * FROM departments WHERE department_id = ?", (assigned_ward['department_id'],))
        assigned_dept = cursor.fetchone()

    priority = determine_priority(category)

    conn.close()

    return {
        "ward_id": assigned_ward['ward_id'] if assigned_ward else 1,
        "ward_name": assigned_ward['ward_name'] if assigned_ward else "Ward 1",
        "department_id": assigned_dept['department_id'] if assigned_dept else 1,
        "department_name": assigned_dept['name'] if assigned_dept else "Sanitation Division",
        "department_code": assigned_dept['code'] if assigned_dept else "SAN-01",
        "priority": priority,
        "notes": "; ".join(routing_notes)
    }
