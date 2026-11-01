import urllib.request
import urllib.parse
import json

# Overpass API requires POST body to be 'data=<query>'
q = """[out:json][timeout:15];
(
  node["amenity"="charging_station"](18.90,72.78,19.05,72.88);
  way["amenity"="charging_station"](18.90,72.78,19.05,72.88);
);
out center;"""

encoded = urllib.parse.urlencode({'data': q}).encode('utf-8')
headers = {'User-Agent': 'VoltGridMumbai/1.0 (contact: student@mumbai.edu)'}
req = urllib.request.Request('https://overpass-api.de/api/interpreter', data=encoded, headers=headers)

try:
    with urllib.request.urlopen(req, timeout=20) as r:
        res = json.loads(r.read().decode())
        elements = res.get('elements', [])
        print(f"Results in South Mumbai: {len(elements)}")
        for el in elements:
            print(el)
except Exception as e:
    print("Error:", e)
