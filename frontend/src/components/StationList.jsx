import React from 'react';
import { Search, Filter, BatteryCharging, Zap, MapPin, ChevronRight, Navigation, PlugZap, RotateCcw, AlertCircle } from 'lucide-react';

export default function StationList({
  stations = [],
  loading = false,
  apiError = null,
  onRetry,
  filters,
  onFilterChange,
  onSelectStation,
  selectedStationId,
  isRadiusMode,
  setIsRadiusMode,
  searchRadius,
  setSearchRadius,
  searchCenter,
  activeLocation,
  scope = 'mmr',
  onScopeChange,
}) {
  const cities = ['All', 'Mumbai', 'Thane', 'Navi Mumbai', 'Pune'];
  const connectors = ['All', 'CCS-2', 'Type 2 AC', 'CHAdeMO', 'Bharat AC-001', 'Bharat DC-001'];

  return (
    <div className="bg-slate-900/70 backdrop-blur-md rounded-xl border border-slate-800 p-5 shadow-xl flex flex-col h-[750px]">
      
      {/* Scope Selector: MMR vs All India */}
      <div className="flex items-center justify-between mb-3 bg-slate-800/60 p-1.5 rounded-lg border border-slate-700/80 text-xs">
        <span className="text-[11px] font-semibold text-slate-300 pl-1.5 flex items-center space-x-1.5">
          <span className="w-2 h-2 rounded-full bg-cyan-400 animate-pulse"></span>
          <span>Target Scope:</span>
        </span>
        <div className="flex space-x-1 bg-slate-900/80 p-0.5 rounded-md border border-slate-800">
          <button
            onClick={() => onScopeChange && onScopeChange('mmr')}
            className={`px-2.5 py-1 rounded text-xs font-medium transition cursor-pointer ${
              scope === 'mmr' ? 'bg-emerald-500 text-white shadow-sm font-semibold' : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            MMR (Default)
          </button>
          <button
            onClick={() => onScopeChange && onScopeChange('all')}
            className={`px-2.5 py-1 rounded text-xs font-medium transition cursor-pointer ${
              scope === 'all' ? 'bg-cyan-500 text-white shadow-sm font-semibold' : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            All India (National)
          </button>
        </div>
      </div>
      
      {/* Header & Mode Switcher */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-base font-bold text-white flex items-center space-x-2">
            <span>Charging Stations</span>
            <span className="text-xs bg-slate-800 text-slate-300 px-2 py-0.5 rounded-full border border-slate-700 font-mono">
              {loading ? 'Searching...' : `${stations.length} verified`}
            </span>
          </h3>
          <p className="text-xs text-slate-400">Search, filter, and calculate distances from your location</p>
        </div>

        {/* Spatial Radius vs List Filter Toggle */}
        <div className="flex items-center bg-slate-800/80 p-1 rounded-lg border border-slate-700 text-xs">
          <button
            onClick={() => setIsRadiusMode(false)}
            className={`px-2.5 py-1 rounded font-medium transition cursor-pointer ${
              !isRadiusMode ? 'bg-emerald-500 text-white shadow-sm' : 'text-slate-400 hover:text-white'
            }`}
          >
            All Stations
          </button>
          <button
            onClick={() => setIsRadiusMode(true)}
            className={`px-2.5 py-1 rounded font-medium transition flex items-center space-x-1 cursor-pointer ${
              isRadiusMode ? 'bg-emerald-500 text-white shadow-sm' : 'text-slate-400 hover:text-white'
            }`}
          >
            <Navigation className="w-3 h-3" />
            <span>Nearby Radius</span>
          </button>
        </div>
      </div>

      {/* Spatial Radius Controls if in Radius Mode */}
      {isRadiusMode && (
        <div className="mb-4 bg-emerald-950/30 border border-emerald-500/30 p-3.5 rounded-xl text-xs space-y-2">
          <div className="flex justify-between items-center text-slate-300">
            <span className="font-semibold text-emerald-400 flex items-center space-x-1.5">
              <Navigation className="w-3.5 h-3.5 text-emerald-400" />
              <span>Search Radius Distance:</span>
            </span>
            <span className="font-mono font-bold text-emerald-300 text-sm bg-emerald-900/60 px-2 py-0.5 rounded border border-emerald-500/40">
              {searchRadius} km
            </span>
          </div>

          <input
            id="input-search-radius"
            type="range"
            min="2"
            max="100"
            step="1"
            value={searchRadius}
            onChange={(e) => setSearchRadius(Number(e.target.value))}
            className="w-full accent-emerald-500 cursor-pointer"
          />

          <div className="flex items-center justify-between text-[11px] text-slate-400 pt-1 border-t border-emerald-900/40">
            <span className="truncate pr-2">
              Origin:{' '}
              <strong className="text-white">
                {activeLocation?.name || activeLocation?.displayName || 'Selected Origin'}
              </strong>
            </span>
            <span className="text-emerald-400 text-[10px] shrink-0 font-mono">
              {searchCenter?.lat?.toFixed(3)}, {searchCenter?.lon?.toFixed(3)}
            </span>
          </div>
        </div>
      )}

      {/* Search Bar for filtering station names/operators */}
      <div className="relative mb-3">
        <Search className="w-4 h-4 text-slate-400 absolute left-3 top-3" />
        <input
          type="text"
          placeholder="Filter stations by name, operator, or address..."
          value={filters.search}
          onChange={(e) => onFilterChange('search', e.target.value)}
          className="w-full pl-9 pr-3 py-2 bg-slate-950/70 border border-slate-700/80 rounded-lg text-xs text-white placeholder-slate-500 focus:outline-none focus:border-emerald-500 transition"
        />
      </div>

      {/* Filter Row: City & Connector */}
      <div className="grid grid-cols-2 gap-2 mb-3 text-xs">
        <div>
          <label className="text-[11px] text-slate-400 mb-1 block">City Region</label>
          <select
            value={filters.city}
            onChange={(e) => onFilterChange('city', e.target.value === 'All' ? '' : e.target.value)}
            className="w-full bg-slate-950/70 border border-slate-700 rounded-lg px-2.5 py-1.5 text-white focus:outline-none focus:border-emerald-500"
          >
            {cities.map((c) => (
              <option key={c} value={c}>{c}</option>
            ))}
          </select>
        </div>

        <div>
          <label className="text-[11px] text-slate-400 mb-1 block">Connector Standard</label>
          <select
            value={filters.connector_type}
            onChange={(e) => onFilterChange('connector_type', e.target.value === 'All' ? '' : e.target.value)}
            className="w-full bg-slate-950/70 border border-slate-700 rounded-lg px-2.5 py-1.5 text-white focus:outline-none focus:border-emerald-500"
          >
            {connectors.map((c) => (
              <option key={c} value={c}>{c}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Database Infrastructure Status Header */}
      <div className="flex items-center justify-between mb-3 px-1 text-xs text-slate-300">
        <div className="flex items-center space-x-1.5 text-slate-300 font-medium">
          <span className="w-2 h-2 rounded-full bg-emerald-400"></span>
          <span>PostgreSQL Physical Infrastructure</span>
        </div>
        <span className="text-[10px] text-slate-400 bg-slate-950/80 px-2 py-0.5 rounded border border-slate-800">
          Live telemetry unconfigured
        </span>
      </div>

      {/* Station Cards Scrollable List */}
      <div className="flex-1 overflow-y-auto space-y-2.5 pr-1">
        {loading ? (
          <div className="text-center py-16 px-4 rounded-xl bg-slate-950/40 border border-slate-800/80 my-2">
            <div className="w-8 h-8 border-2 border-emerald-500 border-t-transparent rounded-full animate-spin mx-auto mb-3"></div>
            <h4 className="text-sm font-semibold text-white mb-1">Loading Charging Stations</h4>
            <p className="text-xs text-slate-400">Querying genuine PostgreSQL records...</p>
          </div>
        ) : apiError ? (
          <div className="text-center py-12 px-4 rounded-xl bg-red-950/20 border border-red-500/40 my-2">
            <div className="w-10 h-10 rounded-full bg-red-900/40 border border-red-500/50 flex items-center justify-center mx-auto mb-3 text-red-400">
              <AlertCircle className="w-5 h-5" />
            </div>
            <h4 className="text-sm font-semibold text-white mb-1">Unable to Load Genuine Records</h4>
            <p className="text-xs text-red-300/90 max-w-xs mx-auto mb-4 leading-relaxed">
              {apiError}
            </p>
            {onRetry && (
              <button
                type="button"
                onClick={onRetry}
                className="px-3.5 py-1.5 rounded-lg bg-red-600 hover:bg-red-500 text-white text-xs font-semibold transition cursor-pointer"
              >
                Retry Connection
              </button>
            )}
          </div>
        ) : stations.length === 0 ? (
          <div className="text-center py-10 px-4 rounded-xl bg-slate-950/40 border border-slate-800/80 my-2">
            <div className="w-10 h-10 rounded-full bg-slate-800 flex items-center justify-center mx-auto mb-3 text-slate-400">
              <MapPin className="w-5 h-5 text-amber-400" />
            </div>
            <h4 className="text-sm font-semibold text-white mb-1">No Charging Stations in Radius</h4>
            <p className="text-xs text-slate-400 max-w-xs mx-auto leading-relaxed">
              No EV stations found within <strong className="text-emerald-400">{searchRadius} km</strong> of{' '}
              <strong className="text-white">{activeLocation?.name || activeLocation?.displayName || 'the selected location'}</strong>.
            </p>
            <div className="mt-4 flex items-center justify-center gap-2">
              <button
                type="button"
                onClick={() => setSearchRadius(Math.min(100, searchRadius + 15))}
                className="px-3 py-1.5 rounded-lg bg-emerald-600/80 hover:bg-emerald-600 text-white text-xs font-medium transition cursor-pointer"
              >
                Expand Radius to {Math.min(100, searchRadius + 15)} km
              </button>
              <button
                type="button"
                onClick={() => {
                  onFilterChange('connector_type', 'All');
                  onFilterChange('city', 'All');
                  onFilterChange('search', '');
                }}
                className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs transition cursor-pointer"
              >
                Reset Filters
              </button>
            </div>
          </div>
        ) : (
          stations.map((st) => {
            const isSelected = selectedStationId === st.station_id;
            const powerRating = st.max_power_kw || (st.power_outputs?.length ? st.power_outputs[0] : null);

            return (
              <div
                key={st.station_id}
                onClick={() => onSelectStation(st.station_id)}
                className={`p-3.5 rounded-xl border transition-all cursor-pointer relative overflow-hidden ${
                  isSelected
                    ? 'bg-emerald-950/40 border-emerald-500/80 shadow-md shadow-emerald-500/10'
                    : 'bg-slate-950/50 border-slate-800/80 hover:border-slate-700 hover:bg-slate-800/40'
                }`}
              >
                {/* Station Title & Recorded Ports Badge */}
                <div className="flex items-start justify-between mb-1.5">
                  <div className="pr-2 flex-1">
                    <h4 className="text-sm font-semibold text-white tracking-tight line-clamp-1">
                      {st.station_name}
                    </h4>
                    <p className="text-xs text-slate-400 flex items-center space-x-1 mt-0.5">
                      <MapPin className="w-3 h-3 text-slate-500 shrink-0" />
                      <span className="line-clamp-1">{st.address || `${st.city}, ${st.state}`}</span>
                    </p>
                  </div>

                  <div className="flex flex-col items-end shrink-0 pl-2">
                    <span className="text-[10px] font-bold px-2 py-0.5 rounded-md bg-slate-800/90 text-slate-200 border border-slate-700 font-mono">
                      {st.total_ports} {st.total_ports === 1 ? 'Recorded Port' : 'Recorded Ports'}
                    </span>
                    <span className="text-[9px] text-slate-500 mt-0.5">
                      Live status unavailable
                    </span>
                  </div>
                </div>

                {/* Connector Types & Power Output Badges */}
                <div className="flex flex-wrap items-center gap-1.5 my-2">
                  {st.connector_types && st.connector_types.length > 0 ? (
                    st.connector_types.map((connector) => (
                      <span
                        key={connector}
                        className="text-[10px] px-2 py-0.5 rounded bg-slate-800/90 text-slate-300 border border-slate-700/80 font-medium flex items-center gap-1"
                      >
                        <PlugZap className="w-2.5 h-2.5 text-emerald-400" />
                        {connector}
                      </span>
                    ))
                  ) : (
                    <span className="text-[10px] px-2 py-0.5 rounded bg-slate-800/60 text-slate-400 border border-slate-700/60">
                      Standard Connectors
                    </span>
                  )}

                  {powerRating && (
                    <span className="text-[10px] px-2 py-0.5 rounded bg-sky-950/60 text-sky-400 border border-sky-600/30 font-medium flex items-center gap-1">
                      <Zap className="w-2.5 h-2.5 text-sky-400" />
                      {powerRating} kW Max
                    </span>
                  )}
                </div>

                {/* Operator and Distance Footer */}
                <div className="flex items-center justify-between text-[11px] text-slate-400 pt-2 border-t border-slate-800/60 mt-1.5">
                  <span className="text-slate-300 font-medium">{st.operator_name}</span>
                  {st.distance_km !== null && st.distance_km !== undefined ? (
                    <span className="font-mono text-emerald-400 font-semibold flex items-center gap-1" title="Straight-line Haversine geodesic distance">
                      <Navigation className="w-3 h-3 text-emerald-400" />
                      {st.distance_km} km (straight-line)
                    </span>
                  ) : (
                    <span className="text-slate-500">{st.city}</span>
                  )}
                </div>
              </div>
            );
          })
        )}
      </div>

    </div>
  );
}
