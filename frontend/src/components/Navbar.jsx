import React from 'react';
import { Zap, Database, MapPin, Activity, History, TrendingUp } from 'lucide-react';

export default function Navbar({ activeTab, setActiveTab, onRefresh, isRefreshing }) {
  const tabs = [
    { id: 'map', label: 'GIS Map & Stations', icon: MapPin },
    { id: 'sessions', label: 'Charging Sessions', icon: History },
    { id: 'forecast', label: 'Demand Forecast', icon: TrendingUp },
    { id: 'dba', label: 'DBA Operations & Health', icon: Database },
  ];

  return (
    <header className="sticky top-0 z-50 bg-slate-900/90 backdrop-blur-md border-b border-slate-800">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          
          {/* Logo & Project Title */}
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-emerald-600 to-cyan-500 flex items-center justify-center shadow-lg shadow-emerald-500/20">
              <Zap className="w-6 h-6 text-white" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <span className="font-bold text-lg text-white tracking-tight">VoltGrid Mumbai</span>
                <span className="text-xs bg-emerald-500/20 text-emerald-400 font-medium px-2 py-0.5 rounded-full border border-emerald-500/30">
                  GIS, DBA & Forecasting
                </span>
              </div>
              <p className="text-xs text-slate-400 hidden sm:block">Smart EV Infrastructure & Demand Forecasting</p>
            </div>
          </div>

          {/* Navigation Tabs */}
          <nav className="flex space-x-1 sm:space-x-2">
            {tabs.map((tab) => {
              const Icon = tab.icon;
              const isActive = activeTab === tab.id;
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`flex items-center space-x-2 px-3 py-2 rounded-lg text-sm font-medium transition-all ${
                    isActive
                      ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/40 shadow-sm shadow-emerald-500/10'
                      : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/60'
                  }`}
                >
                  <Icon className="w-4 h-4" />
                  <span className="hidden md:inline">{tab.label}</span>
                </button>
              );
            })}
          </nav>

          {/* Status Indicator & Refresh */}
          <div className="flex items-center space-x-3">
            <div className="hidden lg:flex items-center space-x-2 bg-slate-800/80 px-2.5 py-1.5 rounded-lg border border-slate-700/60 text-xs">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
              <span className="text-slate-300 font-mono">DB: ev_db (Port 5432)</span>
            </div>
            <button
              onClick={onRefresh}
              disabled={isRefreshing}
              className="p-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white transition border border-slate-700 text-xs flex items-center space-x-1"
              title="Refresh database state"
            >
              <Activity className={`w-4 h-4 ${isRefreshing ? 'animate-spin text-emerald-400' : ''}`} />
              <span className="hidden sm:inline">Refresh</span>
            </button>
          </div>

        </div>
      </div>
    </header>
  );
}
