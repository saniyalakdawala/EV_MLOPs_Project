import React, { useState, useEffect, useRef } from 'react';
import { Search, Navigation, MapPin, X, Loader2, Compass, AlertCircle, ExternalLink } from 'lucide-react';
import { searchLocations } from '../api';

const QUICK_LANDMARKS = [
  'Bandra West, Mumbai',
  'Andheri Station, Mumbai',
  'Powai, Mumbai',
  'Chhatrapati Shivaji Maharaj International Airport, Mumbai',
  'Bandra Kurla Complex, Mumbai',
  'Nariman Point, Mumbai',
  'Thane West, Mumbai',
  'Vashi, Navi Mumbai'
];

export default function LocationSearchBar({
  onSelectLocation,
  onUseCurrentLocation,
  isLocating,
  activeLocation,
  geoError,
  onDismissGeoError,
}) {
  const [query, setQuery] = useState('');
  const [suggestions, setSuggestions] = useState([]);
  const [isSearching, setIsSearching] = useState(false);
  const [isOpen, setIsOpen] = useState(false);
  const [searchError, setSearchError] = useState(null);
  const [selectedIndex, setSelectedIndex] = useState(-1);

  const containerRef = useRef(null);
  const debounceTimerRef = useRef(null);

  // Close dropdown on click outside
  useEffect(() => {
    function handleClickOutside(e) {
      if (containerRef.current && !containerRef.current.contains(e.target)) {
        setIsOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Debounced search logic - only searches after user pauses typing (>= 350ms, >= 2 chars)
  // Requirement: Do not run station search against arbitrary coordinates while user is still typing.
  useEffect(() => {
    if (debounceTimerRef.current) {
      clearTimeout(debounceTimerRef.current);
    }

    const trimmed = query.trim();
    if (trimmed.length < 2) {
      setSuggestions([]);
      setIsSearching(false);
      setSearchError(null);
      return;
    }

    debounceTimerRef.current = setTimeout(async () => {
      setIsSearching(true);
      setSearchError(null);
      try {
        const results = await searchLocations(trimmed, 6);
        setSuggestions(results);
        setIsOpen(true);
        setSelectedIndex(-1);
      } catch (err) {
        console.error('Geocoding search failed:', err);
        setSearchError(err.message || 'Geocoding request failed. Please check your query or network.');
        setSuggestions([]);
        setIsOpen(true);
      } finally {
        setIsSearching(false);
      }
    }, 380);

    return () => {
      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current);
      }
    };
  }, [query]);

  // Handle picking a suggestion
  const handleSelectSuggestion = (place) => {
    setQuery(place.name || place.display_name);
    setIsOpen(false);
    setSuggestions([]);
    setSearchError(null);

    if (onSelectLocation) {
      onSelectLocation({
        lat: place.latitude,
        lon: place.longitude,
        name: place.name,
        displayName: place.display_name,
        formattedAddress: place.formatted_address,
        source: 'geocoded',
        placeType: place.place_type,
      });
    }
  };

  // Keyboard navigation support
  const handleKeyDown = (e) => {
    if (!isOpen || suggestions.length === 0) return;

    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setSelectedIndex((prev) => (prev < suggestions.length - 1 ? prev + 1 : 0));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setSelectedIndex((prev) => (prev > 0 ? prev - 1 : suggestions.length - 1));
    } else if (e.key === 'Enter') {
      e.preventDefault();
      if (selectedIndex >= 0 && selectedIndex < suggestions.length) {
        handleSelectSuggestion(suggestions[selectedIndex]);
      } else if (suggestions.length > 0) {
        handleSelectSuggestion(suggestions[0]);
      }
    } else if (e.key === 'Escape') {
      setIsOpen(false);
    }
  };

  // Handle quick chip click
  const handleQuickLandmark = (landmarkName) => {
    setQuery(landmarkName);
  };

  return (
    <div ref={containerRef} className="w-full relative space-y-2">
      {/* Search Header Controls */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2">
        
        {/* Option A: Use My Current Location Button */}
        <button
          id="btn-use-current-location"
          type="button"
          onClick={onUseCurrentLocation}
          disabled={isLocating}
          title="Detect GPS coordinates using browser Geolocation API"
          className="shrink-0 flex items-center justify-center space-x-2 px-3.5 py-2.5 rounded-xl bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 active:scale-[0.98] text-white font-semibold text-xs shadow-md shadow-emerald-950/40 border border-emerald-400/40 disabled:opacity-60 transition cursor-pointer"
        >
          {isLocating ? (
            <Loader2 className="w-4 h-4 animate-spin text-white" />
          ) : (
            <Navigation className="w-4 h-4 text-white" />
          )}
          <span>{isLocating ? 'Acquiring GPS...' : 'Use My Current Location'}</span>
        </button>

        {/* Option B: Enter a Location (Searchable Input with Autocomplete) */}
        <div className="relative flex-1">
          <div className="relative flex items-center">
            <Search className="w-4 h-4 text-slate-400 absolute left-3.5 pointer-events-none" />
            <input
              id="input-location-search"
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onFocus={() => {
                if (suggestions.length > 0 || query.trim().length >= 2) {
                  setIsOpen(true);
                }
              }}
              onKeyDown={handleKeyDown}
              placeholder="Search place or address (e.g. Bandra West, Andheri Station, Powai, Airport)..."
              autoComplete="off"
              className="w-full pl-9 pr-9 py-2.5 bg-slate-900/90 border border-slate-700 hover:border-slate-600 focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500/50 rounded-xl text-xs text-white placeholder-slate-400 shadow-inner outline-none transition"
            />
            {isSearching ? (
              <Loader2 className="w-4 h-4 text-emerald-400 animate-spin absolute right-3" />
            ) : query ? (
              <button
                type="button"
                onClick={() => {
                  setQuery('');
                  setSuggestions([]);
                  setIsOpen(false);
                }}
                className="p-1 text-slate-400 hover:text-white absolute right-2.5 rounded-full hover:bg-slate-800 transition"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            ) : null}
          </div>

          {/* Autocomplete Suggestions Dropdown */}
          {isOpen && (
            <div className="absolute left-0 right-0 top-full mt-1.5 bg-slate-900/98 backdrop-blur-xl border border-slate-700/90 rounded-xl shadow-2xl z-50 overflow-hidden max-h-80 overflow-y-auto animate-in fade-in slide-in-from-top-1 duration-150">
              
              {/* Header Note */}
              <div className="px-3.5 py-2 bg-slate-950/60 border-b border-slate-800 text-[11px] text-slate-400 flex items-center justify-between">
                <span>Select matching location to set search origin:</span>
                <span className="text-[10px] text-slate-500">OpenStreetMap Nominatim</span>
              </div>

              {/* Suggestions List */}
              {suggestions.length > 0 ? (
                <ul className="divide-y divide-slate-800/60">
                  {suggestions.map((item, idx) => {
                    const isSelected = selectedIndex === idx;
                    return (
                      <li
                        key={item.place_id || idx}
                        onClick={() => handleSelectSuggestion(item)}
                        onMouseEnter={() => setSelectedIndex(idx)}
                        className={`px-3.5 py-2.5 cursor-pointer transition flex items-start space-x-2.5 ${
                          isSelected
                            ? 'bg-emerald-950/60 text-white'
                            : 'hover:bg-slate-800/60 text-slate-200'
                        }`}
                      >
                        <MapPin className={`w-4 h-4 shrink-0 mt-0.5 ${isSelected ? 'text-emerald-400' : 'text-slate-400'}`} />
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center justify-between gap-2">
                            <span className="font-semibold text-xs text-white truncate">
                              {item.name || item.display_name.split(',')[0]}
                            </span>
                            <span className="text-[10px] font-mono text-emerald-400/90 shrink-0 bg-emerald-950/50 px-1.5 py-0.5 rounded border border-emerald-500/30">
                              {item.latitude.toFixed(4)}, {item.longitude.toFixed(4)}
                            </span>
                          </div>
                          <p className="text-[11px] text-slate-400 truncate mt-0.5">
                            {item.formatted_address || item.display_name}
                          </p>
                        </div>
                      </li>
                    );
                  })}
                </ul>
              ) : searchError ? (
                <div className="p-4 text-center text-xs text-red-300 flex items-center justify-center space-x-2">
                  <AlertCircle className="w-4 h-4 text-red-400 shrink-0" />
                  <span>{searchError}</span>
                </div>
              ) : !isSearching ? (
                <div className="p-4 text-center text-xs text-slate-400">
                  No matching locations found for <strong className="text-white">"{query}"</strong>.
                  <div className="text-[11px] text-slate-500 mt-1">
                    Try checking spelling or picking a landmark shortcut below.
                  </div>
                </div>
              ) : null}

              {/* Attribution Footer */}
              <div className="px-3.5 py-1.5 bg-slate-950/80 border-t border-slate-800/80 text-[10px] text-slate-500 flex items-center justify-between">
                <span>Data © OpenStreetMap contributors, ODbL 1.0</span>
                <span>Select place to retrieve nearby stations</span>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Quick Example Landmarks Chips */}
      <div className="flex items-center space-x-1.5 overflow-x-auto py-0.5 text-[11px] scrollbar-none">
        <span className="text-slate-500 shrink-0 text-[10px] font-medium uppercase tracking-wider">
          Suggestions:
        </span>
        {QUICK_LANDMARKS.map((name) => (
          <button
            key={name}
            type="button"
            onClick={() => handleQuickLandmark(name)}
            className="shrink-0 px-2.5 py-0.5 rounded-full bg-slate-900 hover:bg-slate-800 text-slate-400 hover:text-emerald-300 border border-slate-800 hover:border-slate-700 transition text-[11px] cursor-pointer"
          >
            {name.split(',')[0]}
          </button>
        ))}
      </div>

      {/* Geolocation Error Alert if active */}
      {geoError && (
        <div className="p-3 rounded-xl bg-red-950/80 border border-red-500/60 text-xs text-red-200 flex items-start justify-between gap-2 shadow-lg">
          <div className="flex items-start space-x-2">
            <AlertCircle className="w-4 h-4 text-red-400 shrink-0 mt-0.5" />
            <div>
              <strong className="text-white">Location Access Notice:</strong> {geoError}
            </div>
          </div>
          <button
            type="button"
            onClick={onDismissGeoError}
            className="text-slate-400 hover:text-white p-0.5 rounded"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      )}

      {/* Active Selected Location Banner */}
      {activeLocation && (
        <div className="px-3 py-2 rounded-xl bg-slate-900/80 border border-emerald-500/40 text-xs text-slate-300 flex flex-wrap items-center justify-between gap-2 shadow-sm">
          <div className="flex items-center space-x-2">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
            <span>
              Active Origin:{' '}
              <strong className="text-white">
                {activeLocation.name || activeLocation.displayName || 'Selected Origin'}
              </strong>
            </span>
            <span className="text-emerald-400 font-mono text-[11px]">
              ({activeLocation.lat.toFixed(4)}, {activeLocation.lon.toFixed(4)})
            </span>
          </div>

          <div className="flex items-center space-x-2 text-[10px]">
            <span className="px-2 py-0.5 rounded-full bg-slate-800 text-slate-300 border border-slate-700">
              Source: {activeLocation.source === 'gps' ? 'Browser GPS' : activeLocation.source === 'geocoded' ? 'OpenStreetMap Geocoding' : 'Map Selection'}
            </span>
          </div>
        </div>
      )}

    </div>
  );
}
