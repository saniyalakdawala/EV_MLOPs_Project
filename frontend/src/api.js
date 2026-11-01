/**
 * Central API Client for FastAPI Backend
 */
const BASE_URL = import.meta.env.VITE_API_URL || (window.location.port === '5173' ? 'http://127.0.0.1:8000' : '');

export async function fetchOverview() {
  const res = await fetch(`${BASE_URL}/api/stations/overview`);
  if (!res.ok) throw new Error('Failed to fetch overview stats');
  return res.json();
}

export async function fetchStations(params = {}) {
  const query = new URLSearchParams();
  if (params.search) query.append('search', params.search);
  if (params.city) query.append('city', params.city);
  if (params.state) query.append('state', params.state);
  if (params.connector_type) query.append('connector_type', params.connector_type);
  if (params.min_power_kw) query.append('min_power_kw', params.min_power_kw);
  if (params.available_only) query.append('available_only', 'true');
  if (params.scope) query.append('scope', params.scope);
  query.append('limit', params.limit || '100');

  const res = await fetch(`${BASE_URL}/api/stations?${query.toString()}`);
  if (!res.ok) throw new Error('Failed to fetch stations');
  return res.json();
}

export async function fetchNearbyStations(lat, lon, radiusKm = 15, connector = '', minPower = null, scope = 'mmr') {
  const query = new URLSearchParams({
    lat: lat.toString(),
    lon: lon.toString(),
    radius_km: radiusKm.toString(),
    scope: scope,
    limit: '60'
  });
  if (connector) query.append('connector_type', connector);
  if (minPower) query.append('min_power_kw', minPower.toString());

  const res = await fetch(`${BASE_URL}/api/stations/nearby?${query.toString()}`);
  if (!res.ok) throw new Error('Failed to fetch nearby stations');
  return res.json();
}

export async function searchLocations(query, limit = 5) {
  if (!query || query.trim().length < 2) return [];
  const q = new URLSearchParams({
    q: query.trim(),
    limit: limit.toString(),
  });
  const res = await fetch(`${BASE_URL}/api/geocoding/search?${q.toString()}`);
  if (!res.ok) {
    const errData = await res.json().catch(() => ({}));
    throw new Error(errData.detail || `Geocoding request failed (${res.status})`);
  }
  return res.json();
}

export async function fetchStationDetail(stationId) {
  const res = await fetch(`${BASE_URL}/api/stations/${stationId}`);
  if (!res.ok) throw new Error(`Failed to fetch station #${stationId}`);
  return res.json();
}

export async function startChargingSession(portId, userIdentifier) {
  const res = await fetch(`${BASE_URL}/api/sessions/start`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ port_id: portId, user_identifier: userIdentifier })
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || `Failed to start session (${res.status})`);
  }
  return res.json();
}

export async function endChargingSession(sessionId, energyKwh = null) {
  const res = await fetch(`${BASE_URL}/api/sessions/end`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId, energy_kwh: energyKwh })
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || `Failed to end session (${res.status})`);
  }
  return res.json();
}

export async function fetchSessionHistory(params = {}) {
  const query = new URLSearchParams();
  if (params.session_status) query.append('session_status', params.session_status);
  query.append('limit', params.limit || '50');

  const res = await fetch(`${BASE_URL}/api/sessions/history?${query.toString()}`);
  if (!res.ok) throw new Error('Failed to fetch session history');
  return res.json();
}

export async function fetchPortHistory(portId) {
  const res = await fetch(`${BASE_URL}/api/sessions/ports/${portId}/history`);
  if (!res.ok) throw new Error('Failed to fetch port audit history');
  return res.json();
}

export async function fetchDbaStats() {
  const res = await fetch(`${BASE_URL}/api/dba/stats`);
  if (!res.ok) throw new Error('Failed to fetch DBA stats');
  return res.json();
}

export async function fetchDbaActivity() {
  const res = await fetch(`${BASE_URL}/api/dba/activity`);
  if (!res.ok) throw new Error('Failed to fetch active queries');
  return res.json();
}

export async function fetchDbaBenchmark() {
  const res = await fetch(`${BASE_URL}/api/dba/benchmark`);
  if (!res.ok) throw new Error('Failed to fetch benchmark comparison');
  return res.json();
}

export async function fetchForecastModelInfo() {
  const res = await fetch(`${BASE_URL}/api/forecast/model-info`);
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || 'No trained forecasting model is available.');
  return res.json();
}

export async function fetchForecastEvaluation() {
  const res = await fetch(`${BASE_URL}/api/forecast/evaluation`);
  if (!res.ok) throw new Error('Forecast evaluation is unavailable.');
  return res.json();
}

export async function requestForecast(payload) {
  const res = await fetch(`${BASE_URL}/api/forecast/predict`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || `Forecast request failed (${res.status})`);
  return data;
}
