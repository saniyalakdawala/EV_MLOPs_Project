import React from 'react';
import { MapPin, BatteryCharging, Zap, HardDrive, ShieldCheck } from 'lucide-react';

export default function OverviewCards({ stats, dbaStats }) {
  if (!stats) return null;

  const cards = [
    {
      title: 'Charging Stations',
      value: stats.total_stations?.toLocaleString() || '0',
      subtitle: `${stats.maharashtra_stations || 0} in Maharashtra (${stats.mumbai_metro_stations || 0} Mumbai MMR)`,
      icon: MapPin,
      gradient: 'from-blue-600/20 to-cyan-600/10',
      borderColor: 'border-blue-500/30',
      textColor: 'text-blue-400',
    },
    {
      title: 'Recorded Charging Ports',
      value: `${stats.total_ports?.toLocaleString() || '0'} Ports`,
      subtitle: `${stats.total_stations?.toLocaleString() || 0} physical stations • Live telemetry unavailable`,
      icon: BatteryCharging,
      gradient: 'from-emerald-600/20 to-teal-600/10',
      borderColor: 'border-emerald-500/30',
      textColor: 'text-emerald-400',
    },
    {
      title: 'Active Charging Sessions',
      value: stats.active_sessions?.toLocaleString() || '0',
      subtitle: `${stats.total_energy_delivered_kwh?.toLocaleString() || '0'} kWh total energy delivered`,
      icon: Zap,
      gradient: 'from-amber-600/20 to-orange-600/10',
      borderColor: 'border-amber-500/30',
      textColor: 'text-amber-400',
    },
    {
      title: 'DBA Buffer Cache Hit Ratio',
      value: `${dbaStats?.cache_hit_percentage || 99.9}%`,
      subtitle: `Total DB footprint: ${dbaStats?.total_size || '11 MB'}`,
      icon: HardDrive,
      gradient: 'from-purple-600/20 to-indigo-600/10',
      borderColor: 'border-purple-500/30',
      textColor: 'text-purple-400',
    },
  ];

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
      {cards.map((card, idx) => {
        const Icon = card.icon;
        return (
          <div
            key={idx}
            className={`bg-slate-900/60 backdrop-blur-md rounded-xl p-5 border ${card.borderColor} bg-gradient-to-br ${card.gradient} shadow-lg relative overflow-hidden transition-all hover:translate-y-[-2px]`}
          >
            <div className="flex items-center justify-between mb-3">
              <span className="text-xs uppercase tracking-wider font-semibold text-slate-400">{card.title}</span>
              <div className={`p-2 rounded-lg bg-slate-800/80 ${card.textColor}`}>
                <Icon className="w-5 h-5" />
              </div>
            </div>
            <div className="text-2xl font-bold text-white mb-1 tracking-tight">{card.value}</div>
            <p className="text-xs text-slate-400">{card.subtitle}</p>
          </div>
        );
      })}
    </div>
  );
}
