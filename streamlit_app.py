"""VoltGrid's Streamlit-first dashboard. Data stays in the existing FastAPI service."""
from __future__ import annotations

import os
from typing import Any

import pandas as pd
import plotly.express as px
import requests
import streamlit as st

st.set_page_config(page_title="VoltGrid Mumbai", page_icon="⚡", layout="wide")
API_BASE = os.getenv("VOLTGRID_API_URL", "http://127.0.0.1:8000").rstrip("/")
try:
    API_BASE = st.secrets.get("VOLTGRID_API_URL", API_BASE).rstrip("/")
except (FileNotFoundError, AttributeError):
    pass

st.markdown("""
<style>
  .block-container {padding-top: 1.7rem; padding-bottom: 2rem; max-width: 1440px;}
  [data-testid="stMetric"] {border-left: 2px solid #168b83; padding-left: .8rem;}
  h1, h2, h3 {letter-spacing: -.02em;}
</style>
""", unsafe_allow_html=True)

class ServiceError(RuntimeError):
    pass

def api_get(path: str, params: dict[str, Any] | None = None) -> Any:
    try:
        response = requests.get(f"{API_BASE}{path}", params=params, timeout=(3, 15))
        response.raise_for_status()
        return response.json()
    except requests.Timeout as exc:
        raise ServiceError("VoltGrid API took too long to respond. Check that the backend is running.") from exc
    except requests.ConnectionError as exc:
        raise ServiceError(f"Cannot reach the VoltGrid API at {API_BASE}. Start the backend and retry.") from exc
    except requests.HTTPError as exc:
        try:
            detail = "The API service encountered an internal error." if response.status_code >= 500 else response.json().get("detail", response.reason)
        except (ValueError, AttributeError):
            detail = response.reason
        raise ServiceError(f"API returned {response.status_code}: {detail}") from exc

def api_post(path: str, payload: dict[str, Any]) -> Any:
    try:
        response = requests.post(f"{API_BASE}{path}", json=payload, timeout=(3, 30))
        response.raise_for_status()
        return response.json()
    except requests.Timeout as exc:
        raise ServiceError("The request timed out. Check backend status and try again.") from exc
    except requests.ConnectionError as exc:
        raise ServiceError(f"Cannot reach the VoltGrid API at {API_BASE}.") from exc
    except requests.HTTPError as exc:
        try:
            detail = "The API service encountered an internal error." if response.status_code >= 500 else response.json().get("detail", response.reason)
        except (ValueError, AttributeError):
            detail = response.reason
        raise ServiceError(f"API returned {response.status_code}: {detail}") from exc

@st.cache_data(ttl=30, show_spinner=False)
def cached_get(path: str, params: dict[str, Any] | None = None) -> Any:
    return api_get(path, params)

def as_frame(rows: Any) -> pd.DataFrame:
    return pd.DataFrame(rows if isinstance(rows, list) else [])

def show_error(action: str, exc: Exception) -> None:
    st.error(f"{action}: {exc}")

st.title("VoltGrid Mumbai")
st.caption("EV charging infrastructure, spatial exploration, and demand forecasting")
with st.sidebar:
    st.subheader("Workspace")
    page = st.radio("Navigate", ["Overview", "Station explorer", "Charging sessions", "Forecasting", "Database"], label_visibility="collapsed")
    st.divider()
    try:
        health = cached_get("/health")
        st.success(f"API {health.get('status', 'available')}")
    except ServiceError as exc:
        st.warning("API unavailable")
        st.caption(str(exc))
    st.caption("Station results come from the configured VoltGrid database.")

if page == "Overview":
    st.header("Infrastructure overview")
    try:
        overview = cached_get("/api/stations/overview")
        cols = st.columns(5)
        metrics = [("Stations · MMR", overview.get("mumbai_metro_stations")), ("Stations · Maharashtra", overview.get("maharashtra_stations")), ("Charging ports", overview.get("total_ports")), ("Available ports", overview.get("available_ports")), ("Active sessions", overview.get("active_sessions"))]
        for col, (label, value) in zip(cols, metrics):
            col.metric(label, f"{value:,}" if isinstance(value, (int, float)) else "—")
        st.metric("Recorded energy delivered", f"{overview.get('total_energy_delivered_kwh', 0):,.2f} kWh")
        stations = as_frame(cached_get("/api/stations", {"scope": "mmr", "limit": 500}))
        if not stations.empty and {"latitude", "longitude"}.issubset(stations.columns):
            st.subheader("Mapped MMR stations")
            st.map(stations[["latitude", "longitude"]].rename(columns={"latitude": "lat", "longitude": "lon"}), size=40, color="#168b83")
            st.caption(f"Showing {len(stations)} records returned by the API.")
        else:
            st.info("No station coordinates are available to map from the current database response.")
    except ServiceError as exc:
        show_error("Overview data is unavailable", exc)

elif page == "Station explorer":
    st.header("Station explorer")
    tab_search, tab_nearby = st.tabs(["Search stations", "Nearby search"])
    with tab_search:
        with st.form("station-search"):
            c1, c2, c3 = st.columns([2, 1, 1])
            term = c1.text_input("Station, operator, or address")
            city = c2.text_input("City")
            scope = c3.selectbox("Dataset scope", ["mmr", "all"], format_func=lambda x: "Mumbai region" if x == "mmr" else "National staging")
            c4, c5, c6 = st.columns([1, 1, 1])
            connector = c4.text_input("Connector type")
            min_power = c5.number_input("Minimum power (kW)", min_value=0.0, value=0.0, step=10.0)
            limit = c6.select_slider("Maximum results", options=[25, 50, 100, 250, 500], value=100)
            submitted = st.form_submit_button("Search", type="primary")
        if submitted:
            params = {"scope": scope, "limit": limit}
            if term.strip(): params["search"] = term.strip()
            if city.strip(): params["city"] = city.strip()
            if connector.strip(): params["connector_type"] = connector.strip()
            if min_power > 0: params["min_power_kw"] = min_power
            st.session_state.station_results = params
        params = st.session_state.get("station_results")
        if params:
            try:
                frame = as_frame(api_get("/api/stations", params))
                if frame.empty:
                    st.info("No stations match these filters.")
                else:
                    st.caption(f"{len(frame)} station records returned.")
                    st.dataframe(frame, use_container_width=True, hide_index=True)
                    if {"latitude", "longitude"}.issubset(frame.columns):
                        st.map(frame[["latitude", "longitude"]].rename(columns={"latitude": "lat", "longitude": "lon"}), size=40, color="#168b83")
                    selected = st.selectbox("Station details", frame["station_id"].astype(str).tolist(), key="station_detail_id")
                    if st.button("Load selected station details"):
                        try:
                            st.session_state.station_detail = api_get(f"/api/stations/{selected}")
                        except ServiceError as exc:
                            show_error("Station details unavailable", exc)
                    detail = st.session_state.get("station_detail")
                    if detail and str(detail.get("station_id")) == selected:
                        st.json(detail)
            except ServiceError as exc:
                show_error("Station search failed", exc)
    with tab_nearby:
        st.write("Search by a place name or enter coordinates directly.")
        with st.form("nearby-search"):
            place = st.text_input("Place name", placeholder="Tardeo, Mumbai")
            c1, c2 = st.columns(2)
            lat = c1.number_input("Latitude", min_value=-90.0, max_value=90.0, value=19.0760, format="%.6f")
            lon = c2.number_input("Longitude", min_value=-180.0, max_value=180.0, value=72.8777, format="%.6f")
            c3, c4, c5 = st.columns(3)
            radius = c3.number_input("Radius (km)", min_value=0.1, max_value=2000.0, value=5.0)
            nearby_scope = c4.selectbox("Scope", ["mmr", "all"], key="nearby_scope")
            nearby_limit = c5.number_input("Result limit", min_value=1, max_value=500, value=50)
            run_nearby = st.form_submit_button("Find nearby stations", type="primary")
        if run_nearby:
            try:
                if place.strip():
                    geocodes = api_get("/api/geocoding/search", {"q": place.strip(), "limit": 5})
                    if not geocodes:
                        st.warning("No location match found. Try another place or use the coordinates above.")
                    else:
                        chosen = geocodes[0]
                        lat, lon = float(chosen["latitude"]), float(chosen["longitude"])
                        st.caption(f"Location matched: {chosen['name']} · {chosen['formatted_address']}")
                if not place.strip() or geocodes:
                    results = api_get("/api/stations/nearby", {"lat": lat, "lon": lon, "radius_km": radius, "scope": nearby_scope, "limit": nearby_limit})
                    frame = as_frame(results)
                    if frame.empty:
                        st.info(f"No stations found within {radius:g} km. Try expanding the radius.")
                    else:
                        st.dataframe(frame, use_container_width=True, hide_index=True)
                        st.map(frame[["latitude", "longitude"]].rename(columns={"latitude": "lat", "longitude": "lon"}), size=60, color="#168b83")
            except ServiceError as exc:
                show_error("Nearby search failed", exc)

elif page == "Charging sessions":
    st.header("Charging sessions")
    st.caption("Session updates use the API's existing row locks and transaction handling.")
    history_tab, start_tab, end_tab = st.tabs(["Session history", "Start a session", "End a session"])
    with history_tab:
        status_filter = st.selectbox("Session status", ["All", "ACTIVE", "COMPLETED", "ABORTED"])
        st.button("Refresh session history")
        try:
            history_params = {"limit": 100}
            if status_filter != "All":
                history_params["session_status"] = status_filter
            sessions = as_frame(api_get("/api/sessions/history", history_params))
            if sessions.empty:
                st.info("No session records match this filter.")
            else:
                active_count = int((sessions["session_status"] == "ACTIVE").sum())
                total_energy = float(sessions["energy_kwh"].fillna(0).sum())
                m1, m2, m3 = st.columns(3)
                m1.metric("Visible sessions", len(sessions))
                m2.metric("Active sessions", active_count)
                m3.metric("Recorded energy", f"{total_energy:.2f} kWh")
                safe_columns = [c for c in ["session_id", "port_id", "start_time", "end_time", "energy_kwh", "session_status"] if c in sessions.columns]
                st.dataframe(sessions[safe_columns], use_container_width=True, hide_index=True)
        except ServiceError as exc:
            show_error("Session history unavailable", exc)
    with start_tab:
        try:
            station_rows = as_frame(cached_get("/api/stations", {"scope": "mmr", "limit": 500}))
            if station_rows.empty:
                st.info("No stations are available to select.")
            else:
                station_ids = station_rows["station_id"].astype(str).tolist()
                station_id = st.selectbox("Station", station_ids, format_func=lambda value: station_rows.loc[station_rows.station_id.astype(str) == value, "station_name"].iloc[0])
                if st.session_state.get("available_port_station") != station_id:
                    st.session_state.pop("available_session_ports", None)
                if st.button("Load available ports"):
                    detail = api_get(f"/api/stations/{station_id}")
                    available_ports = [port for port in detail.get("ports", []) if port.get("status") == "AVAILABLE"]
                    st.session_state.available_port_station = station_id
                    st.session_state.available_session_ports = available_ports
                available_ports = st.session_state.get("available_session_ports", [])
                if not available_ports:
                    st.info("Load ports for a station to see current availability.")
                else:
                    port_ids = [int(port["port_id"]) for port in available_ports]
                    with st.form("start-session"):
                        port_id = st.selectbox("Available port", port_ids)
                        user_identifier = st.text_input("Driver or vehicle identifier", max_chars=60)
                        start_submit = st.form_submit_button("Start session", type="primary")
                    if start_submit:
                        if len(user_identifier.strip()) < 2:
                            st.warning("Enter a driver or vehicle identifier with at least two characters.")
                        else:
                            result = api_post("/api/sessions/start", {"port_id": port_id, "user_identifier": user_identifier.strip()})
                            st.session_state.pop("available_session_ports", None)
                            st.success(f"Session started: {result.get('session_id')}")
        except ServiceError as exc:
            show_error("Unable to load stations or start a session", exc)
    with end_tab:
        try:
            active_rows = api_get("/api/sessions/history", {"session_status": "ACTIVE", "limit": 200})
            if not active_rows:
                st.info("There are no active sessions to end.")
            else:
                options = {f"{row['session_id']} · port {row['port_id']}": row for row in active_rows}
                with st.form("end-session"):
                    selected_label = st.selectbox("Active session", list(options))
                    energy = st.number_input("Metered energy delivered (kWh)", min_value=0.0, value=0.0, step=0.5)
                    end_submit = st.form_submit_button("Complete session", type="primary")
                if end_submit:
                    if energy <= 0:
                        st.warning("Enter a positive measured kWh value to complete the session.")
                    else:
                        result = api_post("/api/sessions/end", {"session_id": str(options[selected_label]["session_id"]), "energy_kwh": energy})
                        st.success(f"Session completed · {result.get('energy_kwh')} kWh recorded.")
        except ServiceError as exc:
            show_error("Unable to load or end active sessions", exc)

elif page == "Forecasting":
    st.header("Demand forecasting")
    st.caption("Forecasts use a trained artifact served by the existing API. Opening this page never retrains a model.")
    try:
        model = cached_get("/api/forecast/model-info")
        st.success(f"Model {model.get('model_version')} · {model.get('model_name')} · provenance: {model.get('provenance')}")
        st.write(f"Target: {model.get('target', 'Not specified')}")
        evaluation = cached_get("/api/forecast/evaluation")
        with st.expander("Evaluation results", expanded=True):
            st.write("Chronological validation metrics")
            st.dataframe(pd.json_normalize(evaluation.get("validation_metrics", {}), sep="."), use_container_width=True)
            st.write("Held-out test metrics")
            st.dataframe(pd.json_normalize(evaluation.get("held_out_test_metrics", {}), sep="."), use_container_width=True)
        sites = model.get("site_ids", [])
        if sites:
            with st.form("forecast-form"):
                site = st.selectbox("Site", sites)
                horizon = st.slider("Forecast horizon (hours)", 1, 168, 24)
                origin = model.get("history_end", {}).get(site, model.get("latest_observed_hour"))
                st.caption(f"Forecast origin: {origin}")
                forecast_submit = st.form_submit_button("Generate forecast", type="primary")
            if forecast_submit:
                st.session_state.forecast_result = api_post("/api/forecast/predict", {"site_id": site, "forecast_origin": origin, "horizon_hours": horizon})
            result = st.session_state.get("forecast_result")
            if result and result.get("site_id") == site:
                forecast_frame = as_frame(result.get("forecasts"))
                if not forecast_frame.empty:
                    st.metric("Forecast energy across horizon", f"{forecast_frame['predicted_kwh'].sum():,.2f} kWh")
                    st.plotly_chart(px.line(forecast_frame, x="timestamp", y="predicted_kwh", title="Predicted session-arrival energy"), use_container_width=True)
                    st.dataframe(forecast_frame, use_container_width=True, hide_index=True)
    except ServiceError as exc:
        st.info("A trained model is not currently available. Train a candidate and approve it for serving to enable forecasts.")
        st.caption(str(exc))

else:
    st.header("Database operations")
    st.caption("Live PostgreSQL statistics are read from the existing DBA API endpoints.")
    try:
        stats = cached_get("/api/dba/stats")
        c1, c2 = st.columns(2)
        c1.metric("Database size", stats.get("total_size", "Unavailable"))
        hit = stats.get("cache_hit_percentage")
        c2.metric("Buffer cache hit", f"{hit:.2f}%" if isinstance(hit, (int, float)) else "Unavailable")
        tables = as_frame(stats.get("tables_storage"))
        if not tables.empty:
            st.subheader("Table storage")
            st.dataframe(tables.drop(columns=["total_bytes"], errors="ignore"), use_container_width=True, hide_index=True)
        with st.expander("Current database activity"):
            try:
                activity = as_frame(cached_get("/api/dba/activity"))
                if activity.empty:
                    st.info("No other database sessions are currently visible.")
                else:
                    st.dataframe(activity.drop(columns=["query_snippet", "client_ip"], errors="ignore"), use_container_width=True, hide_index=True)
            except ServiceError as exc:
                st.warning(str(exc))
        if st.button("Run index query-plan benchmark"):
            try:
                benchmark = api_get("/api/dba/benchmark")
                st.subheader("Measured query plans")
                st.json(benchmark)
            except ServiceError as exc:
                show_error("Query-plan benchmark unavailable", exc)
    except ServiceError as exc:
        show_error("Database statistics are unavailable", exc)
