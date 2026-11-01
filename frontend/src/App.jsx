import React, { useState, useEffect } from 'react';
import Navbar from './components/Navbar';
import OverviewCards from './components/OverviewCards';
import LocationSearchBar from './components/LocationSearchBar';
import MapView from './components/MapView';
import StationList from './components/StationList';
import StationDetailModal from './components/StationDetailModal';
import SessionHistoryView from './components/SessionHistoryView';
import DbaOperationsPanel from './components/DbaOperationsPanel';
import { fetchOverview, fetchStations, fetchNearbyStations, fetchStationDetail, fetchDbaStats } from './api';

export default function App() {
  const [activeTab, setActiveTab] = useState('map');
  const [stats, setStats] = useState(null);
  const [dbaStats, setDbaStats] = useState(null);
  const [stations, setStations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [apiError, setApiError] = useState(null);
  const [isRefreshing, setIsRefreshing] = useState(false);

  // Filter state
  const [filters, setFilters] = useState({
    search: '',
    city: 'All',
    connector_type: 'All',
    available_only: false,
  });

  // Spatial Radius Search State (Defaults to true for Nearby GIS Mode)
  const [isRadiusMode, setIsRadiusMode] = useState(true);
  const [searchCenter, setSearchCenter] = useState({ lat: 19.0760, lon: 72.8777 }); // Default: Mumbai MMR Center
  const [searchRadius, setSearchRadius] = useState(15); // km

  // Selected Location metadata (Browser GPS or OpenStreetMap Geocoding or Map click)
  const [activeLocation, setActiveLocation] = useState({
    lat: 19.0760,
    lon: 72.8777,
    name: 'Mumbai Central / MMR',
    displayName: 'Mumbai Metropolitan Region, Maharashtra',
    source: 'default',
  });

  const [isLocating, setIsLocating] = useState(false);
  const [geoError, setGeoError] = useState(null);

  // Selected station for modal
  const [selectedStationId, setSelectedStationId] = useState(null);
  const [selectedStationDetail, setSelectedStationDetail] = useState(null);

  // Scope filter: 'mmr' (default: Mumbai Metropolitan Region) or 'all' (All-India National Master)
  const [scope, setScope] = useState('mmr');

  // Load Overview & DBA summary
  const loadStats = async () => {
    try {
      const [ovData, dbaData] = await Promise.all([
        fetchOverview(),
        fetchDbaStats().catch(() => null),
      ]);
      setStats(ovData);
      setDbaStats(dbaData);
    } catch (err) {
      console.error('Failed to load stats:', err);
    }
  };

  // Load Stations from real database using PostGIS spatial queries or filters
  const loadStations = async () => {
    setLoading(true);
    setApiError(null);
    try {
      let data;
      if (isRadiusMode) {
        data = await fetchNearbyStations(
          searchCenter.lat,
          searchCenter.lon,
          searchRadius,
          filters.connector_type !== 'All' ? filters.connector_type : '',
          null,
          scope
        );
      } else {
        data = await fetchStations({
          search: filters.search,
          city: filters.city !== 'All' ? filters.city : '',
          connector_type: filters.connector_type !== 'All' ? filters.connector_type : '',
          available_only: filters.available_only,
          scope: scope,
          limit: 150,
        });
      }
      setStations(data || []);
      setApiError(null);
    } catch (err) {
      console.error('Failed to load genuine stations:', err);
      // Cleanly clear stations and surface genuine error; never fall back to mock data
      setStations([]);
      const errMsg = err.message || 'Failed to retrieve genuine database records from backend API.';
      setApiError(errMsg);
      if (isRadiusMode) {
        setGeoError(`Database Spatial Query Error: ${errMsg}`);
      }
    } finally {
      setLoading(false);
    }
  };

  // Initial load
  useEffect(() => {
    loadStats();
  }, []);

  // Re-fetch stations whenever search coordinates, radius, scope, or filters change
  useEffect(() => {
    loadStations();
  }, [filters, isRadiusMode, searchCenter.lat, searchCenter.lon, searchRadius, scope]);

  // Option A: Use My Current Location (Browser Geolocation API)
  // Request permission ONLY after explicit user button click
  const handleUseCurrentLocation = () => {
    if (!navigator.geolocation) {
      setGeoError('Geolocation API is not supported by your current browser.');
      return;
    }

    setIsLocating(true);
    setGeoError(null);

    // One-shot location retrieval (no continuous tracking)
    navigator.geolocation.getCurrentPosition(
      (position) => {
        const { latitude, longitude } = position.coords;
        const newCoords = { lat: latitude, lon: longitude };

        setActiveLocation({
          lat: latitude,
          lon: longitude,
          name: 'Your Location',
          displayName: 'Your Location (Current Device GPS)',
          formattedAddress: `GPS Latitude: ${latitude.toFixed(5)}, Longitude: ${longitude.toFixed(5)}`,
          source: 'gps',
        });
        setSearchCenter(newCoords);
        setIsRadiusMode(true);
        setIsLocating(false);
        setGeoError(null);
      },
      (error) => {
        setIsLocating(false);
        let errorMsg = 'Failed to obtain GPS location.';

        switch (error.code) {
          case error.PERMISSION_DENIED:
            errorMsg = 'Location permission was denied. You can search any place name or address above without requiring GPS access.';
            break;
          case error.POSITION_UNAVAILABLE:
            errorMsg = 'Location information is currently unavailable from your device.';
            break;
          case error.TIMEOUT:
            errorMsg = 'Location request timed out. Please try searching for your area by name above.';
            break;
          default:
            errorMsg = error.message || 'An unknown error occurred while retrieving GPS position.';
            break;
        }

        // Never silently substitute coordinates!
        setGeoError(errorMsg);
      },
      {
        enableHighAccuracy: true,
        timeout: 10000,
        maximumAge: 0,
      }
    );
  };

  // Option B: Select a Place from Autocomplete Geocoding
  const handleSelectLocation = (place) => {
    setActiveLocation({
      lat: place.lat,
      lon: place.lon,
      name: place.name,
      displayName: place.displayName,
      formattedAddress: place.formattedAddress,
      source: 'geocoded',
    });
    setSearchCenter({ lat: place.lat, lon: place.lon });
    setIsRadiusMode(true);
    setGeoError(null);
  };

  // Option C: Map Click custom location selection
  const handleSearchLocationChange = (lat, lon, label = 'Map Selection', source = 'map_click') => {
    setActiveLocation({
      lat,
      lon,
      name: label,
      displayName: `Map Point (${lat.toFixed(4)}, ${lon.toFixed(4)})`,
      formattedAddress: `Selected Point: ${lat.toFixed(5)}, ${lon.toFixed(5)}`,
      source,
    });
    setSearchCenter({ lat, lon });
    setIsRadiusMode(true);
    setGeoError(null);
  };

  // Open Station Modal
  const handleSelectStation = async (stationId) => {
    setSelectedStationId(stationId);
    try {
      const detail = await fetchStationDetail(stationId);
      setSelectedStationDetail(detail);
    } catch (err) {
      console.error(err);
    }
  };

  // Refresh entire dashboard
  const handleRefreshAll = async () => {
    setIsRefreshing(true);
    await Promise.all([loadStats(), loadStations()]);
    if (selectedStationId) {
      const detail = await fetchStationDetail(selectedStationId).catch(() => null);
      if (detail) setSelectedStationDetail(detail);
    }
    setIsRefreshing(false);
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans">
      
      {/* Top Navigation */}
      <Navbar
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        onRefresh={handleRefreshAll}
        isRefreshing={isRefreshing}
      />

      {/* Main Content Area */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-6">
        
        {/* KPI Summary Cards */}
        <OverviewCards stats={stats} dbaStats={dbaStats} />

        {/* Tab 1: GIS Map & Stations Explorer */}
        {activeTab === 'map' && (
          <div className="space-y-4">
            
            {/* Location Selection Bar: Option A (GPS) + Option B (Place Autocomplete) */}
            <div className="p-4 rounded-2xl bg-slate-900/70 border border-slate-800 shadow-xl backdrop-blur-md">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-bold uppercase tracking-wider text-slate-300">
                  Find EV Charging Stations Near Location
                </span>
                <span className="text-[10px] text-slate-500">
                  OpenStreetMap Nominatim Geocoding + PostGIS ev_db
                </span>
              </div>
              <LocationSearchBar
                onSelectLocation={handleSelectLocation}
                onUseCurrentLocation={handleUseCurrentLocation}
                isLocating={isLocating}
                activeLocation={activeLocation}
                geoError={geoError}
                onDismissGeoError={() => setGeoError(null)}
              />
            </div>

            {/* Map and Stations List Split Layout */}
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
              
              {/* Map Column */}
              <div className="lg:col-span-7 flex flex-col space-y-3">
                <MapView
                  stations={stations}
                  selectedStation={selectedStationDetail}
                  onSelectStation={handleSelectStation}
                  searchCenter={searchCenter}
                  searchRadius={isRadiusMode ? searchRadius : null}
                  onSearchLocationChange={handleSearchLocationChange}
                  activeLocation={activeLocation}
                />

                {/* Spatial Info & Attribution Banner */}
                <div className="p-3.5 rounded-xl bg-slate-900/60 border border-slate-800 text-xs text-slate-400 flex flex-wrap items-center justify-between gap-2">
                  <div className="flex items-center space-x-2">
                    <span className="text-slate-300">
                      Search Origin:{' '}
                      <strong className="text-white font-mono">
                        {activeLocation?.name || 'Selected'} ({searchCenter.lat.toFixed(4)}, {searchCenter.lon.toFixed(4)})
                      </strong>
                    </span>
                  </div>
                  <div className="flex items-center space-x-2">
                    <span className="text-emerald-400 font-semibold text-[11px]">
                      PostGIS GiST Geodesic Distance
                    </span>
                    <span className="text-slate-600">•</span>
                    <span className="text-[10px] text-slate-500">
                      Map & Geodata © OpenStreetMap
                    </span>
                  </div>
                </div>
              </div>

              {/* Station List & Filters Column */}
              <div className="lg:col-span-5">
                <StationList
                  stations={stations}
                  loading={loading}
                  apiError={apiError}
                  onRetry={loadStations}
                  filters={filters}
                  onFilterChange={(key, val) => setFilters(prev => ({ ...prev, [key]: val }))}
                  onSelectStation={handleSelectStation}
                  selectedStationId={selectedStationId}
                  isRadiusMode={isRadiusMode}
                  setIsRadiusMode={setIsRadiusMode}
                  searchRadius={searchRadius}
                  setSearchRadius={setSearchRadius}
                  searchCenter={searchCenter}
                  activeLocation={activeLocation}
                  scope={scope}
                  onScopeChange={setScope}
                />
              </div>

            </div>

          </div>
        )}

        {/* Tab 2: Operational Charging Sessions */}
        {activeTab === 'sessions' && <SessionHistoryView />}

        {/* Tab 3: DBA Operations, Diagnostics & Benchmarks */}
        {activeTab === 'dba' && <DbaOperationsPanel />}

      </main>

      {/* Station Detail & Booking Modal */}
      {selectedStationDetail && (
        <StationDetailModal
          station={selectedStationDetail}
          onClose={() => {
            setSelectedStationDetail(null);
            setSelectedStationId(null);
          }}
          onSessionUpdated={handleRefreshAll}
        />
      )}

      {/* Footer with Mandatory Attribution */}
      <footer className="mt-auto border-t border-slate-800/80 bg-slate-950/90 py-5 text-center text-xs text-slate-500">
        <div className="max-w-7xl mx-auto px-4 flex flex-col sm:flex-row items-center justify-between gap-2">
          <span>Smart EV Charging Infrastructure Database • B.Tech Data Science ADBMS Project</span>
          <span className="text-slate-400">
            Map tiles & Place Geocoding: <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer" className="underline hover:text-emerald-400">OpenStreetMap contributors (ODbL)</a>
          </span>
        </div>
      </footer>

    </div>
  );
}
