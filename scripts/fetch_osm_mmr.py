import urllib.request
import urllib.parse
import json
import os

# Overpass API with 50s timeout on kumi mirror or main
mirrors = [
    'https://overpass-api.de/api/interpreter',
    'https://overpass.kumi.systems/api/interpreter',
    'https://maps.mail.ru/osm/tools/overpass/api/interpreter'
]

q = """[out:json][timeout:45];
(
  node["amenity"="charging_station"](18.63,72.74,19.53,73.46);
  way["amenity"="charging_station"](18.63,72.74,19.53,73.46);
);
out center tags;"""

data = urllib.parse.urlencode({'data': q}).encode('utf-8')
headers = {'User-Agent': 'VoltGridMumbai/1.0 (contact: student@mumbai.edu)'}

success = False
for mirror in mirrors:
    print(f"Connecting to mirror: {mirror}...")
    try:
        req = urllib.request.Request(mirror, data=data, headers=headers)
        with urllib.request.urlopen(req, timeout=50) as r:
            res = json.loads(r.read().decode('utf-8'))
            elements = res.get('elements', [])
            print(f"Success! Retrieved {len(elements)} real EV charging stations from OpenStreetMap in MMR.")
            with open('data/osm_mmr_charging_stations.json', 'w', encoding='utf-8') as f:
                json.dump(res, f, indent=2)
            print("Saved to data/osm_mmr_charging_stations.json")
            for el in elements[:15]:
                tags = el.get('tags', {})
                lat = el.get('lat') or el.get('center', {}).get('lat')
                lon = el.get('lon') or el.get('center', {}).get('lon')
                name = tags.get('name') or tags.get('operator') or tags.get('brand') or f"EV Station {el.get('id')}"
                op = tags.get('operator') or tags.get('brand') or 'Unknown'
                print(f"  OSM {el.get('type')}/{el.get('id')}: {name} ({op}) @ {lat}, {lon}")
            success = True
            break
    except Exception as e:
        print(f"Failed with {mirror}: {e}")

if not success:
    print("All Overpass mirrors timed out or were unreachable.")
