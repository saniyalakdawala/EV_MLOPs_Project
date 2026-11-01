"""
Classify MMR Stations by Sub-region
"""
import csv

stations = [
    # OCM
    {"id": "OCM-510426", "name": "SEL Dev Maharashtra", "op": "SEL", "lat": 19.105321, "lon": 72.875887, "town": "Mumbai", "area": "Mumbai Suburban (Kurla / Sakinaka)"},
    {"id": "OCM-502290", "name": "MobiLane Equinox Business Park", "op": "MobiLane", "lat": 19.071566, "lon": 72.877213, "town": "Mumbai", "area": "Mumbai Suburban (Kurla / BKC)"},
    {"id": "OCM-502276", "name": "MobiLane Saya Grand By Treat", "op": "MobiLane", "lat": 19.219162, "lon": 73.043920, "town": "Thane", "area": "Thane (Bhiwandi / Thane border)"},
    {"id": "OCM-307102", "name": "Andheri West", "op": "Ather Grid", "lat": 19.116600, "lon": 72.829270, "town": "Mumbai", "area": "Mumbai Suburban (Andheri West)"},
    {"id": "OCM-298738", "name": "Balasaheb Thackeray Flyover", "op": "Ather Grid", "lat": 19.139951, "lon": 72.851974, "town": "Mumbai", "area": "Mumbai Suburban (Jogeshwari West)"},
    {"id": "OCM-201254", "name": "Cinemax", "op": "Tata Power", "lat": 19.243652, "lon": 73.134756, "town": "Kalyan", "area": "Kalyan-Dombivli"},
    {"id": "OCM-190068", "name": "Mira Road", "op": "Ather Grid", "lat": 19.140006, "lon": 72.853444, "town": "Mira-Bhayandar", "area": "Mira-Bhayandar / Jogeshwari Link"},
    {"id": "OCM-92772", "name": "Tata Power Receiving Station", "op": "Tata Power", "lat": 19.095796, "lon": 72.926011, "town": "Mumbai", "area": "Mumbai Suburban (Vikhroli East)"},
    # OSM
    {"id": "node/9215039103", "name": "Fortum EV Charger", "op": "Fortum", "lat": 19.232958, "lon": 72.976061, "town": "Thane", "area": "Thane (Majiwada)"},
    {"id": "node/9252505223", "name": "PowerGrid Charging Station", "op": "PowerGrid", "lat": 19.024524, "lon": 73.013512, "town": "Navi Mumbai", "area": "Navi Mumbai (Nerul)"},
    {"id": "node/10205648223", "name": "Go e go", "op": "Go e go", "lat": 18.643349, "lon": 72.876221, "town": "Alibag / Raigad (MMR)", "area": "MMR Southern Perimeter (Alibag/Pen)"},
    {"id": "node/10285393622", "name": "Tata Power", "op": "Tata Power", "lat": 18.956177, "lon": 73.162788, "town": "Panvel", "area": "Panvel (Rasayani / Mohopada)"},
    {"id": "node/10285406628", "name": "Jio-BP", "op": "Jio-BP", "lat": 19.087490, "lon": 73.079632, "town": "Navi Mumbai", "area": "Navi Mumbai (Turbhe / Mahape)"},
    {"id": "node/10553764693", "name": "Tata power", "op": "Tata Power", "lat": 19.159794, "lon": 72.858293, "town": "Mumbai", "area": "Mumbai Suburban (Goregaon / Malad)"},
    {"id": "node/10827297703", "name": "Mahavitaran charging station", "op": "Mahavitaran", "lat": 19.067149, "lon": 73.007534, "town": "Navi Mumbai", "area": "Navi Mumbai (Vashi)"},
    {"id": "node/14158954590", "name": "Honda Battery Swapping", "op": "Honda", "lat": 19.146307, "lon": 72.833653, "town": "Mumbai", "area": "Mumbai Suburban (Oshiwara / Andheri)"},
]

print("MMR Stations by Area:")
from collections import Counter
counts = Counter()
for s in stations:
    if "Mumbai Suburban" in s["area"]:
        counts["Mumbai Suburban"] += 1
    elif "Navi Mumbai" in s["area"]:
        counts["Navi Mumbai"] += 1
    elif "Thane" in s["area"]:
        counts["Thane"] += 1
    elif "Kalyan" in s["area"]:
        counts["Kalyan-Dombivli"] += 1
    elif "Panvel" in s["area"]:
        counts["Panvel"] += 1
    elif "Mira" in s["area"]:
        counts["Mira-Bhayandar"] += 1
    elif "Raigad" in s["area"] or "Southern Perimeter" in s["area"]:
        counts["Raigad / South MMR"] += 1

for k, v in counts.items():
    print(f"  {k}: {v}")
print(f"Total: {sum(counts.values())}")
