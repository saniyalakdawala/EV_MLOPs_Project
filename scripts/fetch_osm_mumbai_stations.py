import urllib.request
import json
import os

mirrors = [
    'https://overpass.kumi.systems/api/interpreter',
    'https://overpass.private.coffee/api/interpreter',
    'https://lz4.overpass-api.de/api/interpreter',
    'https://overpass-api.de/api/interpreter'
]

# Mumbai bounding box (South Mumbai to Suburbs): 18.89 to 19.30, 72.75 to 73.10
query = """[out:json][timeout:25];
(
  node["amenity"="charging_station"](18.89,72.75,19.35,73.15);
  way["amenity"="charging_station"](18.89,72.75,19.35,73.15);
);
out center;"""

success = False
for mirror in mirrors:
    try:
        print(f"Trying Overpass mirror: {mirror}")
        req = urllib.request.Request(
            mirror,
            data=query.encode('utf-8'),
            headers={'User-Agent': 'VoltGridMumbai/1.0'}
        )
        with urllib.request.urlopen(req, timeout=25) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            elements = data.get('elements', [])
            print(f"Success from {mirror}! Found {len(elements)} charging stations.")
            os.makedirs("data", exist_ok=True)
            with open("data/osm_mumbai_ev_stations.json", "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            print("Saved to data/osm_mumbai_ev_stations.json")
            success = True
            break
    except Exception as e:
        print(f"Failed with {mirror}: {e}")

if not success:
    print("Could not reach Overpass mirrors.")
