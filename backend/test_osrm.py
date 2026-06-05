import urllib.request
import json
import urllib.parse

def test_osrm():
    origin_lat, origin_lng = -6.111, 106.742 # Approx PIK
    dest_lat, dest_lng = -6.0936742, 106.6769279
    url = f"https://router.project-osrm.org/route/v1/driving/{origin_lng},{origin_lat};{dest_lng},{dest_lat}?overview=full&geometries=geojson&steps=true&alternatives=3"
    
    req = urllib.request.Request(url, headers={"User-Agent": "Test/1.0"})
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode('utf-8'))
    
    print(f"Found {len(data['routes'])} routes")
    for i, route in enumerate(data['routes']):
        distance = route['distance'] / 1000
        duration = route['duration'] / 60
        uses_toll = False
        for leg in route.get('legs', []):
            for step in leg.get('steps', []):
                name = step.get('name', '').lower()
                ref = step.get('ref', '').lower()
                if 'tol ' in name or name.startswith('tol') or 'toll' in name:
                    uses_toll = True
                if 'tol ' in ref or ref.startswith('tol') or 'toll' in ref:
                    uses_toll = True
                for inter in step.get('intersections', []):
                    if 'toll' in inter.get('classes', []):
                        uses_toll = True
        print(f"Route {i}: dist={distance:.2f}km, dur={duration:.1f}min, uses_toll={uses_toll}")

if __name__ == '__main__':
    test_osrm()
