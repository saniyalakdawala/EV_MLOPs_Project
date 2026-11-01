import React, { useState, useEffect } from 'react';
import { History, Zap, CheckCircle2, Clock, Filter, RefreshCw } from 'lucide-react';
import { fetchSessionHistory } from '../api';

export default function SessionHistoryView() {
  const [sessions, setSessions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState('');

  const loadSessions = async () => {
    setLoading(true);
    try {
      const data = await fetchSessionHistory({ session_status: statusFilter, limit: 100 });
      setSessions(data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadSessions();
  }, [statusFilter]);

  const activeCount = sessions.filter(s => s.session_status === 'ACTIVE').length;
  const totalKwh = sessions.reduce((acc, s) => acc + (s.energy_kwh || 0), 0);

  return (
    <div className="bg-slate-900/70 backdrop-blur-md rounded-2xl border border-slate-800 p-6 shadow-xl space-y-5">
      
      {/* View Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-lg font-bold text-white flex items-center space-x-2">
            <History className="w-5 h-5 text-emerald-400" />
            <span>Operational Charging Session Logs</span>
          </h2>
          <p className="text-xs text-slate-400">
            Chronological audit of charging transactions, energy consumption, and dispenser allocations.
          </p>
        </div>

        {/* Filter and Refresh */}
        <div className="flex items-center space-x-3 text-xs">
          <div className="flex items-center space-x-1.5 bg-slate-950/80 px-2.5 py-1.5 rounded-lg border border-slate-700">
            <Filter className="w-3.5 h-3.5 text-slate-400" />
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="bg-transparent text-white focus:outline-none"
            >
              <option value="">All Statuses</option>
              <option value="ACTIVE">Active Sessions</option>
              <option value="COMPLETED">Completed Sessions</option>
            </select>
          </div>

          <button
            onClick={loadSessions}
            className="p-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white transition"
            title="Reload session records"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin text-emerald-400' : ''}`} />
          </button>
        </div>
      </div>

      {/* Mini KPI summary */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <div className="bg-slate-950/60 p-3.5 rounded-xl border border-slate-800">
          <span className="text-[11px] font-semibold text-slate-400">Visible Sessions</span>
          <div className="text-xl font-bold text-white mt-1">{sessions.length}</div>
        </div>
        <div className="bg-slate-950/60 p-3.5 rounded-xl border border-slate-800">
          <span className="text-[11px] font-semibold text-emerald-400">Currently Active</span>
          <div className="text-xl font-bold text-emerald-300 mt-1">{activeCount}</div>
        </div>
        <div className="bg-slate-950/60 p-3.5 rounded-xl border border-slate-800">
          <span className="text-[11px] font-semibold text-amber-400">Total Metered Energy</span>
          <div className="text-xl font-bold text-amber-300 mt-1">{totalKwh.toFixed(1)} kWh</div>
        </div>
      </div>

      {/* Sessions Table */}
      <div className="overflow-x-auto rounded-xl border border-slate-800">
        <table className="w-full text-left text-xs">
          <thead className="bg-slate-950/80 text-slate-400 border-b border-slate-800 uppercase tracking-wider text-[10px]">
            <tr>
              <th className="py-3 px-4">Session UUID</th>
              <th className="py-3 px-4">Port ID</th>
              <th className="py-3 px-4">Driver Identifier</th>
              <th className="py-3 px-4">Start Time</th>
              <th className="py-3 px-4">End Time</th>
              <th className="py-3 px-4">Energy (kWh)</th>
              <th className="py-3 px-4">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/60 bg-slate-900/40 font-mono">
            {loading ? (
              <tr>
                <td colSpan="7" className="py-8 text-center text-slate-500 font-sans">
                  Querying charging_sessions table...
                </td>
              </tr>
            ) : sessions.length === 0 ? (
              <tr>
                <td colSpan="7" className="py-8 text-center text-slate-500 font-sans">
                  No session records found matching filter.
                </td>
              </tr>
            ) : (
              sessions.map((sess) => {
                const isActive = sess.session_status === 'ACTIVE';
                return (
                  <tr key={sess.session_id} className="hover:bg-slate-800/40 transition">
                    <td className="py-3 px-4 font-semibold text-slate-300">
                      {sess.session_id.substring(0, 8)}...
                    </td>
                    <td className="py-3 px-4 text-emerald-400">
                      Port #{sess.port_id}
                    </td>
                    <td className="py-3 px-4 text-slate-200">
                      {sess.user_identifier}
                    </td>
                    <td className="py-3 px-4 text-slate-400">
                      {new Date(sess.start_time).toLocaleString()}
                    </td>
                    <td className="py-3 px-4 text-slate-400">
                      {sess.end_time ? new Date(sess.end_time).toLocaleString() : '— In Progress —'}
                    </td>
                    <td className="py-3 px-4 font-bold text-white">
                      {sess.energy_kwh > 0 ? `${sess.energy_kwh} kWh` : '0.00 kWh'}
                    </td>
                    <td className="py-3 px-4">
                      <span
                        className={`text-[10px] font-bold px-2 py-0.5 rounded-full border ${
                          isActive
                            ? 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30 animate-pulse'
                            : 'bg-slate-800 text-slate-400 border-slate-700'
                        }`}
                      >
                        {sess.session_status}
                      </span>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

    </div>
  );
}
