import React, { useEffect, useRef } from 'react';
import L from 'leaflet';
import { Compass } from 'lucide-react';

export default function MapView({
  stations,
  selectedStation,
  onSelectStation,
  searchCenter,
  searchRadius,
  onSearchLocationChange,
  activeLocation,
}) {
  const mapContainerRef = useRef(null);
  const mapInstanceRef = useRef(null);
  const markersLayerRef = useRef(null);
  const radiusCircleRef = useRef(null);
  const userMarkerRef = useRef(null);

  // Initialize Leaflet Map
  useEffect(() => {
    if (!mapContainerRef.current) return;

    if (!mapInstanceRef.current) {
      const initialLat = searchCenter?.lat || 19.0760;
      const initialLon = searchCenter?.lon || 72.8777;

      const map = L.map(mapContainerRef.current, {
        center: [initialLat, initialLon],
        zoom: 12,
        zoomControl: false,
      });

      L.control.zoom({ position: 'bottomright' }).addTo(map);

      // OpenStreetMap Tile Layer with standard attribution
      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">OpenStreetMap</a> contributors',
        maxZoom: 19,
      }).addTo(map);

      const markersGroup = L.layerGroup().addTo(map);
      markersLayerRef.current = markersGroup;
      mapInstanceRef.current = map;

      // Allow clicking map to set manual location coordinates
      map.on('click', (e) => {
        if (onSearchLocationChange) {
          onSearchLocationChange(e.latlng.lat, e.latlng.lng, 'Map Selection', 'map_click');
        }
      });
    }

    return () => {
      // Leaflet container cleanup
    };
  }, []);

  // Update Markers, Radius Circle, and Selected Location Pin
  useEffect(() => {
    const map = mapInstanceRef.current;
    const markersGroup = markersLayerRef.current;
    if (!map || !markersGroup) return;

    markersGroup.clearLayers();

    // 1. Draw Search Radius Circle centered on current origin coordinates
    if (radiusCircleRef.current) {
      radiusCircleRef.current.remove();
      radiusCircleRef.current = null;
    }

    if (searchCenter && searchRadius) {
      const circle = L.circle([searchCenter.lat, searchCenter.lon], {
        radius: searchRadius * 1000, // convert km to meters
        color: '#10b981',
        fillColor: '#10b981',
        fillOpacity: 0.08,
        weight: 1.5,
        dashArray: '4, 4',
      }).addTo(map);
      radiusCircleRef.current = circle;
    }

    // 2. Render Distinct User/Place Location Marker
    if (searchCenter) {
      const markerLabel = activeLocation?.name || activeLocation?.displayName || (activeLocation?.source === 'gps' ? 'Your Location' : 'Selected Origin');

      const userIcon = L.divIcon({
        className: 'user-location-pin',
        html: `
          <div class="beacon"></div>
          <div class="core-dot"></div>
        `,
        iconSize: [32, 32],
        iconAnchor: [16, 16],
      });

      const userMarker = L.marker([searchCenter.lat, searchCenter.lon], {
        icon: userIcon,
        zIndexOffset: 1000,
      });

      userMarker.bindTooltip(markerLabel, {
        permanent: true,
        direction: 'top',
        className: 'user-location-label',
        offset: [0, -12],
      });

      const sourceLabel = activeLocation?.source === 'gps'
        ? '✓ Browser Geolocation (GPS)'
        : activeLocation?.source === 'geocoded'
        ? '✓ OpenStreetMap Nominatim Geocoding'
        : '✎ Manually Selected Point';

      const userPopupContent = `
        <div style="font-family:sans-serif;min-width:200px;padding:2px;">
          <div style="font-weight:bold;color:#0284c7;font-size:13px;margin-bottom:4px;display:flex;align-items:center;gap:5px;">
            <span>📍</span> <span>${markerLabel}</span>
          </div>
          ${activeLocation?.formattedAddress ? `
            <p style="font-size:11px;color:#334155;margin:0 0 6px;line-height:1.3;">
              ${activeLocation.formattedAddress}
            </p>
          ` : ''}
          <div style="font-size:11px;color:#475569;line-height:1.4;">
            Latitude: <strong>${searchCenter.lat.toFixed(5)}</strong><br/>
            Longitude: <strong>${searchCenter.lon.toFixed(5)}</strong>
          </div>
          <div style="font-size:10px;color:#64748b;margin-top:6px;border-top:1px solid #e2e8f0;padding-top:4px;">
            ${sourceLabel}
          </div>
        </div>
      `;
      userMarker.bindPopup(userPopupContent);
      userMarker.addTo(markersGroup);
      userMarkerRef.current = userMarker;
    }

    // 3. Render EV Charging Station Markers
    stations.forEach((st) => {
      const isSelected = selectedStation && selectedStation.station_id === st.station_id;
      const portCount = st.total_ports || 1;

      // Clean emerald pin for verified infrastructure, blue for selected
      const bgColor = isSelected ? '#2563eb' : '#059669';

      const icon = L.divIcon({
        className: 'custom-station-pin',
        html: `
          <div style="background:${bgColor};width:${isSelected ? '32px' : '26px'};height:${isSelected ? '32px' : '26px'};border-radius:50%;border:2px solid white;display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:bold;color:white;box-shadow:0 2px 8px rgba(0,0,0,0.4);" title="${st.station_name}: ${portCount} physical ports">
            ${portCount}
          </div>
        `,
        iconSize: [26, 26],
        iconAnchor: [13, 13],
      });

      const marker = L.marker([st.latitude, st.longitude], { icon });

      const connectorsText = st.connector_types?.length ? st.connector_types.join(', ') : 'Standard';
      const powerText = st.max_power_kw ? `${st.max_power_kw} kW` : (st.power_outputs?.length ? `${st.power_outputs[0]} kW` : 'Standard');

      const popupHtml = `
        <div style="font-family:sans-serif;min-width:220px;padding:2px;">
          <h4 style="margin:0 0 3px;font-size:13px;font-weight:bold;color:#0f172a;">${st.station_name}</h4>
          <p style="margin:0 0 6px;font-size:11px;color:#64748b;">${st.operator_name} • ${st.city}</p>
          
          ${st.distance_km !== null && st.distance_km !== undefined ? `
            <div style="display:flex;align-items:center;gap:4px;font-size:12px;color:#059669;font-weight:bold;margin-bottom:6px;">
              <span>📍</span> <span>${st.distance_km} km (straight-line)</span>
            </div>
          ` : ''}

          <div style="background:#f8fafc;padding:6px 8px;border-radius:6px;border:1px solid #e2e8f0;margin-bottom:8px;font-size:11px;line-height:1.4;">
            <div style="display:flex;justify-content:space-between;margin-bottom:3px;">
              <span style="color:#64748b;">Recorded Ports:</span>
              <strong style="color:#0f172a;">${portCount} ${portCount === 1 ? 'Port' : 'Ports'}</strong>
            </div>
            <div style="display:flex;justify-content:space-between;margin-bottom:3px;">
              <span style="color:#64748b;">Connectors:</span>
              <strong style="color:#1e293b;">${connectorsText}</strong>
            </div>
            <div style="display:flex;justify-content:space-between;margin-bottom:3px;">
              <span style="color:#64748b;">Max Power:</span>
              <strong style="color:#0284c7;">${powerText}</strong>
            </div>
            <div style="display:flex;justify-content:space-between;border-top:1px dashed #cbd5e1;padding-top:3px;margin-top:3px;">
              <span style="color:#64748b;">Live Status:</span>
              <span style="color:#64748b;font-size:10px;font-style:italic;">Live availability unavailable</span>
            </div>
          </div>

          <button id="btn-select-${st.station_id}" style="width:100%;padding:6px;background:#059669;color:white;border:none;border-radius:6px;font-size:12px;font-weight:600;cursor:pointer;">
            View Ports & Manage
          </button>
        </div>
      `;

      marker.bindPopup(popupHtml);
      marker.on('popupopen', () => {
        const btn = document.getElementById(`btn-select-${st.station_id}`);
        if (btn) {
          btn.onclick = () => {
            onSelectStation(st.station_id);
          };
        }
      });

      markersGroup.addLayer(marker);
    });
  }, [stations, selectedStation, searchCenter, searchRadius, activeLocation]);

  // Smooth pan to selected station or newly selected search coordinates
  useEffect(() => {
    if (selectedStation && mapInstanceRef.current) {
      mapInstanceRef.current.flyTo([selectedStation.latitude, selectedStation.longitude], 14, { duration: 1.2 });
    }
  }, [selectedStation]);

  useEffect(() => {
    if (searchCenter && mapInstanceRef.current && !selectedStation) {
      mapInstanceRef.current.flyTo([searchCenter.lat, searchCenter.lon], 13, { duration: 1.2 });
    }
  }, [searchCenter?.lat, searchCenter?.lon]);

  return (
    <div className="relative rounded-xl overflow-hidden border border-slate-800 shadow-xl bg-slate-900 h-[500px]">
      <div ref={mapContainerRef} className="w-full h-full z-10" />

      {/* Floating Map Legend & Help Note */}
      <div className="absolute top-3 right-3 z-20 bg-slate-900/90 backdrop-blur-md px-3 py-2 rounded-lg border border-slate-800 text-xs shadow-lg space-y-1.5 max-w-[210px]">
        <div className="font-semibold text-slate-300 flex items-center space-x-1.5 mb-1">
          <Compass className="w-3.5 h-3.5 text-emerald-400" />
          <span>GIS Map Legend</span>
        </div>
        <div className="flex items-center space-x-2">
          <span className="w-3 h-3 rounded-full bg-sky-500 animate-pulse"></span>
          <span className="text-slate-300">Selected Place</span>
        </div>
        <div className="flex items-center space-x-2">
          <span className="w-3 h-3 rounded-full bg-emerald-600"></span>
          <span className="text-slate-300">Verified Station (Ports)</span>
        </div>
        <div className="flex items-center space-x-2">
          <span className="w-3 h-3 rounded-full bg-blue-600"></span>
          <span className="text-slate-300">Selected Station</span>
        </div>
        <div className="text-[10px] text-slate-400 pt-1 border-t border-slate-800 leading-snug">
          💡 Click any point on map to set search center
        </div>
        <div className="text-[9px] text-slate-500 pt-0.5 leading-tight italic">
          📌 Infrastructure geodata verified; live OCPI stream unconfigured.
        </div>
      </div>
    </div>
  );
}
