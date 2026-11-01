import urllib.request
import urllib.parse
import json
import time
import os

mirrors = [
    'https://overpass-api.de/api/interpreter',
    'https://overpass.kumi.systems/api/interpreter',
    'https://maps.mail.ru/osm/tools/overpass/api/interpreter'
]

# Query EV charging stations across Mumbai Metropolitan Region (MMR)
# Covering South Mumbai, Suburban Mumbai, Thane, Navi Mumbai, Mira-Bhayandar, Kalyan-Dombivli, Vasai-Virar, Panvel
query = """[out:json][timeout:35];
(
  node["amenity"="charging_station"](18.63,72.74,19.53,73.46);
  way["amenity"="charging_station"](18.63,72.74,19.53,73.46);
);
out center tags;"""

encoded = urllib.parse.urlencode({'data': query}).encode('utf-8')
headers = {'User-Agent': 'VoltGridMumbai/2.0 (contact: student_research@mumbai.edu)'}

os.makedirs('data/raw', exist_ok=True)
raw_output_path = os.path.join('data', 'raw', 'osm_mmr_overpass_raw.json')

success = False
for mirror in mirrors:
    print(f"Connecting to mirror: {mirror}...")
    for attempt in range(1, 3):
        try:
            req = urllib.request.Request(mirror, data=encoded, headers=headers)
            with urllib.request.urlopen(req, timeout=40) as resp:
                raw_text = resp.read().decode('utf-8')
                data = json.loads(raw_text)
                elements = data.get('elements', [])
                print(f"[SUCCESS] Retrieved {len(elements)} real EV charging station features from {mirror}!")
                
                # Save unmodified raw response
                with open(raw_output_path, 'w', encoding='utf-8') as f:
                    f.write(raw_text)
                print(f"Saved unmodified raw response to {raw_output_path}")
                
                for el in elements[:10]:
                    tags = el.get('tags', {})
                    lat = el.get('lat') or el.get('center', {}).get('lat')
                    lon = el.get('lon') or el.get('center', {}).get('lon')
                    name = tags.get('name') or tags.get('operator') or tags.get('brand') or f"Station {el.get('id')}"
                    print(f"  • OSM {el.get('type')}/{el.get('id')}: {name} @ ({lat}, {lon})")
                success = True
                break
        except Exception as e:
            print(f"  Attempt {attempt} failed on {mirror}: {e}")
            time.sleep(2)
    if success:
        break

if not success:
    print("Could not retrieve live Overpass data from public mirrors. Bounded retries exhausted.")
