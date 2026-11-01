from app.main import app
from app.main import health_check


def test_existing_health_and_station_routes_remain_registered():
    paths = {route.path for route in app.routes}
    assert "/api/health" in paths
    assert "/api/stations" in paths
    assert "/api/sessions/history" in paths
    assert "/api/forecast/predict" in paths

    assert health_check() == {"status": "healthy", "service": "ev-charging-backend"}
