"""
Geocoding API Router
Provides place name and address to geographic coordinate (latitude, longitude) conversion
using OpenStreetMap Nominatim API with compliant caching, rate limiting, and local fallback.

Usage Policy Adherence:
- Identifies application via custom User-Agent.
- Limits requests to max 1 request/second towards upstream Nominatim.
- Caches results in-memory (TTL 15 minutes) to avoid redundant network calls.
- Provides mandatory OSM attribution: "Data © OpenStreetMap contributors, ODbL 1.0".
"""
import time
import json
import urllib.request
import urllib.parse
from typing import List, Optional
from threading import Lock
from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException, Query

router = APIRouter(prefix="/api/geocoding", tags=["Geocoding"])

class GeocodeResult(BaseModel):
    place_id: str
    display_name: str
    name: str
    formatted_address: str
    latitude: float
    longitude: float
    place_type: Optional[str] = None
    attribution: str = "Data © OpenStreetMap contributors, ODbL 1.0"

# Verified Mumbai MMR Landmark Fallback Index (for offline resilience and zero-downtime)
MUMBAI_FALLBACK_INDEX = [
    {
        "place_id": "fallback_bkc",
        "name": "Bandra Kurla Complex (BKC)",
        "display_name": "Bandra Kurla Complex, Bandra East, Mumbai, Maharashtra 400051, India",
        "formatted_address": "BKC, Bandra East, Mumbai, Maharashtra, 400051",
        "latitude": 19.065716,
        "longitude": 72.868725,
        "place_type": "commercial_hub",
        "keywords": ["bkc", "bandra kurla complex", "bkc hub", "bandra east"]
    },
    {
        "place_id": "fallback_bandra_west",
        "name": "Bandra West",
        "display_name": "Bandra West, Mumbai, Mumbai Suburban District, Maharashtra 400050, India",
        "formatted_address": "Bandra West, Mumbai, Maharashtra, 400050",
        "latitude": 19.058336,
        "longitude": 72.830267,
        "place_type": "suburb",
        "keywords": ["bandra", "bandra west", "linking road", "bandstand"]
    },
    {
        "place_id": "fallback_andheri_stn_w",
        "name": "Andheri Railway Station (West)",
        "display_name": "Andheri Station (W), Swami Vivekanand Road, Andheri West, Mumbai, Maharashtra 400058, India",
        "formatted_address": "Andheri Station (W), SV Road, Andheri West, Mumbai, 400058",
        "latitude": 19.119705,
        "longitude": 72.846081,
        "place_type": "railway_station",
        "keywords": ["andheri", "andheri station", "andheri west", "andheri stn"]
    },
    {
        "place_id": "fallback_andheri_stn_e",
        "name": "Andheri Railway Station (East)",
        "display_name": "Andheri Station (E), MV Road, Andheri East, Mumbai, Maharashtra 400069, India",
        "formatted_address": "Andheri Station (E), Andheri East, Mumbai, 400069",
        "latitude": 19.119900,
        "longitude": 72.847500,
        "place_type": "railway_station",
        "keywords": ["andheri east", "andheri station east", "andheri stn east"]
    },
    {
        "place_id": "fallback_powai",
        "name": "Powai",
        "display_name": "Powai, Hiranandani Gardens, Mumbai, Mumbai Suburban District, Maharashtra 400076, India",
        "formatted_address": "Powai, Hiranandani Gardens, Mumbai, Maharashtra, 400076",
        "latitude": 19.118720,
        "longitude": 72.907348,
        "place_type": "suburb",
        "keywords": ["powai", "iit bombay", "hiranandani powai", "powai lake"]
    },
    {
        "place_id": "fallback_csm_airport",
        "name": "Chhatrapati Shivaji Maharaj International Airport (BOM)",
        "display_name": "Chhatrapati Shivaji Maharaj International Airport (T2), Sahar, Andheri East, Mumbai, Maharashtra 400099, India",
        "formatted_address": "CSMI Airport Terminal 2, Sahar, Mumbai, Maharashtra, 400099",
        "latitude": 19.090138,
        "longitude": 72.863822,
        "place_type": "aerodrome",
        "keywords": ["airport", "mumbai airport", "chhatrapati shivaji airport", "bom airport", "t2 airport", "t1 airport"]
    },
    {
        "place_id": "fallback_nariman_point",
        "name": "Nariman Point",
        "display_name": "Nariman Point, Marine Drive, Mumbai, Maharashtra 400021, India",
        "formatted_address": "Nariman Point, Marine Drive, Churchgate, Mumbai, 400021",
        "latitude": 18.926000,
        "longitude": 72.823000,
        "place_type": "commercial_hub",
        "keywords": ["nariman point", "marine drive", "ncpa", "churchgate"]
    },
    {
        "place_id": "fallback_csmt",
        "name": "Chhatrapati Shivaji Maharaj Terminus (CSMT)",
        "display_name": "CSMT Railway Terminus, Fort, Mumbai, Maharashtra 400001, India",
        "formatted_address": "CSMT, DN Road, Fort, Mumbai, Maharashtra, 400001",
        "latitude": 18.940100,
        "longitude": 72.835400,
        "place_type": "railway_station",
        "keywords": ["csmt", "vt", "victoria terminus", "cst", "fort mumbai"]
    },
    {
        "place_id": "fallback_vashi",
        "name": "Vashi, Navi Mumbai",
        "display_name": "Vashi, Sector 17, Navi Mumbai, Thane District, Maharashtra 400703, India",
        "formatted_address": "Vashi Sector 17, Navi Mumbai, Maharashtra, 400703",
        "latitude": 19.077100,
        "longitude": 72.998600,
        "place_type": "suburb",
        "keywords": ["vashi", "navi mumbai", "vashi sector 17", "vashi plaza"]
    },
    {
        "place_id": "fallback_thane",
        "name": "Thane West",
        "display_name": "Thane West, Gokhale Road, Thane, Maharashtra 400601, India",
        "formatted_address": "Thane West, Thane, Maharashtra, 400601",
        "latitude": 19.218300,
        "longitude": 72.978100,
        "place_type": "city",
        "keywords": ["thane", "thane west", "viviana mall", "korum mall"]
    },
    {
        "place_id": "fallback_dadar",
        "name": "Dadar Central",
        "display_name": "Dadar, Shivaji Park, Mumbai, Maharashtra 400028, India",
        "formatted_address": "Dadar, Shivaji Park, Mumbai, Maharashtra, 400028",
        "latitude": 19.017800,
        "longitude": 72.847800,
        "place_type": "railway_hub",
        "keywords": ["dadar", "dadar station", "shivaji park"]
    },
    {
        "place_id": "fallback_gateway",
        "name": "Gateway of India",
        "display_name": "Gateway of India, Apollo Bandar, Colaba, Mumbai, Maharashtra 400001, India",
        "formatted_address": "Apollo Bandar, Colaba, Mumbai, Maharashtra, 400001",
        "latitude": 18.922000,
        "longitude": 72.834700,
        "place_type": "monument",
        "keywords": ["gateway of india", "colaba", "taj hotel"]
    }
]

# Thread-safe in-memory cache and rate limiter
_CACHE = {}  # {query: (timestamp, results)}
_CACHE_TTL = 900  # 15 minutes
_CACHE_LOCK = Lock()
_LAST_REQUEST_TIME = 0.0
_MIN_INTERVAL = 1.05  # Nominatim max 1 req / second

def _match_fallback(query: str, limit: int = 5) -> List[GeocodeResult]:
    """Matches search query against curated local Mumbai landmark index."""
    q_lower = query.lower().strip()
    words = [w for w in q_lower.replace(',', ' ').split() if len(w) > 1]
    matches = []

    for item in MUMBAI_FALLBACK_INDEX:
        score = 0
        text_corp = f"{item['name']} {item['display_name']} {' '.join(item['keywords'])}".lower()
        if q_lower in text_corp:
            score += 10
        for w in words:
            if w in text_corp:
                score += 2

        if score > 0:
            matches.append((score, item))

    matches.sort(key=lambda x: x[0], reverse=True)
    results = []
    for _, item in matches[:limit]:
        results.append(GeocodeResult(
            place_id=item["place_id"],
            display_name=item["display_name"],
            name=item["name"],
            formatted_address=item["formatted_address"],
            latitude=item["latitude"],
            longitude=item["longitude"],
            place_type=item["place_type"],
            attribution="Curated VoltGrid Mumbai Geodata / OpenStreetMap"
        ))
    return results

@router.get("/search", response_model=List[GeocodeResult])
def geocode_search(
    q: str = Query(..., min_length=2, max_length=120, description="Place name, landmark, or address to geocode"),
    limit: int = Query(5, ge=1, le=10, description="Maximum suggestions to return")
):
    """
    Geocodes a place name or address into geographic coordinates.
    Utilizes OpenStreetMap Nominatim with caching, rate limiting, and fallback.
    """
    global _LAST_REQUEST_TIME
    clean_q = q.strip()
    cache_key = f"{clean_q.lower()}_{limit}"

    # 1. Check in-memory cache
    with _CACHE_LOCK:
        if cache_key in _CACHE:
            ts, cached_res = _CACHE[cache_key]
            if time.time() - ts < _CACHE_TTL:
                return cached_res

    # 2. Try Nominatim API with rate limiting
    results: List[GeocodeResult] = []
    nominatim_success = False

    try:
        # Enforce >= 1.0 second between upstream Nominatim requests
        with _CACHE_LOCK:
            now = time.time()
            elapsed = now - _LAST_REQUEST_TIME
            if elapsed < _MIN_INTERVAL:
                time.sleep(_MIN_INTERVAL - elapsed)
            _LAST_REQUEST_TIME = time.time()

        # Build Nominatim query with India bias & viewbox around Maharashtra / Mumbai MMR
        params = {
            "q": clean_q,
            "format": "json",
            "limit": limit,
            "countrycodes": "in",
            "addressdetails": "1"
        }
        encoded_query = urllib.parse.urlencode(params)
        url = f"https://nominatim.openstreetmap.org/search?{encoded_query}"

        headers = {
            "User-Agent": "VoltGridMumbai-ADBMS/1.0 (academic-database-project; contact: student@voltgrid.local)",
            "Accept": "application/json"
        }
        req = urllib.request.Request(url, headers=headers)

        with urllib.request.urlopen(req, timeout=4.0) as resp:
            if resp.status == 200:
                raw_data = json.loads(resp.read().decode("utf-8"))
                for item in raw_data:
                    lat = float(item.get("lat"))
                    lon = float(item.get("lon"))
                    disp = item.get("display_name", "")
                    # Extract clean short title
                    addr = item.get("address", {})
                    short_name = (
                        addr.get("suburb") or 
                        addr.get("neighbourhood") or 
                        addr.get("road") or 
                        addr.get("commercial") or 
                        addr.get("aerodrome") or 
                        addr.get("station") or 
                        disp.split(",")[0]
                    )
                    
                    results.append(GeocodeResult(
                        place_id=str(item.get("place_id", f"osm_{lat}_{lon}")),
                        display_name=disp,
                        name=short_name,
                        formatted_address=disp,
                        latitude=lat,
                        longitude=lon,
                        place_type=item.get("type", "landmark"),
                        attribution="Data © OpenStreetMap contributors, ODbL 1.0"
                    ))
                nominatim_success = True
    except Exception as e:
        print(f"[GEOCODING WARN] Upstream Nominatim request for '{clean_q}' had notice: {e}. Checking local index fallback...")

    # 3. If Nominatim returned empty or failed, consult verified local Mumbai landmark index
    if not results:
        fallback_matches = _match_fallback(clean_q, limit=limit)
        if fallback_matches:
            results = fallback_matches

    # 4. Cache and return results
    with _CACHE_LOCK:
        _CACHE[cache_key] = (time.time(), results)

    return results
