import urllib.request
import json
import urllib.parse
from app.routing_service import extract_toll_roads_from_route

def fetch_route(start_lng, start_lat, end_lng, end_lat):
    coords = f"{start_lng},{start_lat};{end_lng},{end_lat}"
    url = f"http://router.project-osrm.org/route/v1/driving/{coords}?steps=true"
    req = urllib.request.Request(url, headers={'User-Agent': 'Test/1.0'})
    with urllib.request.urlopen(req) as response:
        return json.loads(response.read().decode())

def main():
    # Merak to Bakauheni
    data = fetch_route(105.998188,-5.934898, 105.748366,-5.864771) # From Merak to Bakauheni
    route = data['routes'][0]
    toll_roads = extract_toll_roads_from_route(route)
    print("Toll roads found:")
    for r in toll_roads:
        print("-", r['name'])

if __name__ == "__main__":
    main()
