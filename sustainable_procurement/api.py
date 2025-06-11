import frappe
import json
from math import radians, cos, sin, asin, sqrt

def get_coordinates_from_geojson(geojson_str):
    """
    Safely parses a GeoJSON string and extracts the first point coordinate,
    handling various nesting possibilities.
    """
    if not geojson_str:
        return None

    data = json.loads(geojson_str)
    if not data.get("features"):
        return None

    # Find the first feature that is a Point
    for feature in data["features"]:
        if feature.get("geometry") and feature["geometry"].get("type") == "Point":
            coords = feature["geometry"].get("coordinates")
            # Handle potential extra nesting like [[lon, lat]]
            while isinstance(coords, list) and len(coords) > 0 and isinstance(coords[0], list):
                coords = coords[0]

            if isinstance(coords, list) and len(coords) >= 2:
                lon, lat = coords[0], coords[1]
                if isinstance(lon, (int, float)) and isinstance(lat, (int, float)):
                    return lon, lat
    return None


@frappe.whitelist()
def get_nearest_supplier(warehouse):
    """
    This function finds the single nearest supplier to a given warehouse
    and returns their name and distance.
    """
    if not warehouse:
        return None

    # --- Step 1: Get the coordinates for the selected warehouse ---
    try:
        warehouse_location_str = frappe.db.get_value("Warehouse", warehouse, "custom_geolocation")
        warehouse_coords = get_coordinates_from_geojson(warehouse_location_str)
        if not warehouse_coords:
            raise ValueError("Could not extract valid point coordinates from warehouse location.")
        lon1, lat1 = warehouse_coords

    except Exception as e:
        frappe.log_error(f"Geofencing: Could not parse location for warehouse '{warehouse}'. Error: {e}", "Warehouse Location Parse Error")
        return None

    # --- Step 2: Fetch all enabled suppliers and their locations ---
    enabled_suppliers = frappe.get_all(
        "Supplier",
        filters={"disabled": 0},
        fields=["name", "custom_geolocation"]
    )

    nearest_supplier_info = None
    min_distance = float('inf')

    # --- Step 3: Iterate through suppliers to find the closest one ---
    for supplier in enabled_suppliers:
        try:
            supplier_location_data = supplier.get("custom_geolocation")
            supplier_coords = get_coordinates_from_geojson(supplier_location_data)

            if not supplier_coords:
                # Skip suppliers without a valid single point location
                continue
            lon2, lat2 = supplier_coords

            # Calculate the distance using the Haversine formula.
            distance = haversine_distance(lon1, lat1, lon2, lat2)

            # Check if this supplier is the new closest one found so far.
            if distance < min_distance:
                min_distance = distance
                nearest_supplier_info = {
                    "name": supplier.name,
                    "distance": distance
                }
        except Exception as e:
            frappe.log_error(f"Geofencing: Could not process location for supplier '{supplier.name}'. Error: {e}", "Supplier Location Parse Error")
            continue

    return nearest_supplier_info


def haversine_distance(lon1, lat1, lon2, lat2):
    """
    Calculate the great-circle distance in kilometers between two points
    on the earth (specified in decimal degrees).
    """
    # Convert decimal degrees to radians
    lon1, lat1, lon2, lat2 = map(radians, [float(lon1), float(lat1), float(lon2), float(lat2)])

    # Haversine formula
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat / 2)**2 + cos(lat1) * cos(lat2) * sin(dlon / 2)**2
    c = 2 * asin(sqrt(a))
    r = 6371  # Radius of earth in kilometers.
    return c * r