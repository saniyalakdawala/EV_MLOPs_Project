import React, { useState } from 'react';
import { X, BatteryCharging, Zap, History, Play, Square, AlertCircle, ShieldAlert, CheckCircle2 } from 'lucide-react';
import { startChargingSession, endChargingSession, fetchPortHistory } from '../api';

export default function StationDetailModal({ station, onClose, onSessionUpdated }) {
  const [loadingPortId, setLoadingPortId] = useState(null);
  const [actionError, setActionError] = useState(null);
  const [successMsg, setSuccessMsg] = useState(null);
  const [viewingPortHistory, setViewingPortHistory] = useState(null);
  const [portHistoryLogs, setPortHistoryLogs] = useState([]);
  const [historyLoading, setHistoryLoading] = useState(false);

  if (!station) return null;

  // Handle Starting a Session
  const handleStartSession = async (portId) => {
    setActionError(null);
    setSuccessMsg(null);
    setLoadingPortId(portId);

    try {
      const userDriver = `DRIVER_${Math.floor(1000 + Math.random() * 9000)}`;
      const res = await startChargingSession(portId, userDriver);
      setSuccessMsg(`Session started successfully! Session ID: ${res.session_id.substring(0, 8)}... Port is now locked & IN_USE.`);
      if (onSessionUpdated) onSessionUpdated();
    } catch (err) {
      setActionError(err.message);
    } finally {
      setLoadingPortId(null);
    }
  };

  // Handle Ending a Session (find active session on this port or end)
  const handleEndSession = async (portId) => {
    setActionError(null);
    setSuccessMsg(null);
    setLoadingPortId(portId);

    try {
      // Find active session for this port
      const historyRes = await fetchPortHistory(portId);
      const kwhMetered = Number((Math.random() * 25 + 10).toFixed(2));
      // To terminate, fetch active sessions via central API client
      const activeSessions = await fetchSessionHistory({ session_status: 'ACTIVE' });
      const matchingActive = activeSessions.find(s => s.port_id === portId);

      if (matchingActive) {
        await endChargingSession(matchingActive.session_id, kwhMetered);
        setSuccessMsg(`Session ended cleanly! Delivered ${kwhMetered} kWh. Port released to AVAILABLE.`);
        if (onSessionUpdated) onSessionUpdated();
      } else {
        // Direct port status reset via backend if needed
        setActionError('No active session found matching this port.');
      }
    } catch (err) {
      setActionError(err.message);
    } finally {
      setLoadingPortId(null);
    }
  };

  // Inspect Port Audit History
  const handleViewPortHistory = async (portId) => {
    setViewingPortHistory(portId);
    setHistoryLoading(true);
    try {
      const data = await fetchPortHistory(portId);
      setPortHistoryLogs(data);
    } catch (err) {
      console.error(err);
    } finally {
      setHistoryLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm">
      <div className="bg-slate-900 border border-slate-700/80 rounded-2xl w-full max-w-3xl overflow-hidden shadow-2xl flex flex-col max-h-[90vh]">
        
        {/* Modal Header */}
        <div className="p-5 border-b border-slate-800 flex items-start justify-between bg-slate-950/40">
          <div>
            <div className="flex items-center space-x-2">
              <span className="text-xs bg-emerald-500/20 text-emerald-400 font-semibold px-2 py-0.5 rounded-full border border-emerald-500/30">
                {station.operator_name}
              </span>
              <span className="text-xs text-slate-400 font-mono">ID: #{station.station_id}</span>
            </div>
            <h2 className="text-xl font-bold text-white mt-1">{station.station_name}</h2>
            <p className="text-xs text-slate-400 mt-0.5">{station.address} • {station.city}, {station.state}</p>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-white transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Alerts & Messages */}
        {actionError && (
          <div className="mx-5 mt-4 p-3 rounded-lg bg-red-950/50 border border-red-500/50 text-red-300 text-xs flex items-center space-x-2">
            <AlertCircle className="w-4 h-4 shrink-0 text-red-400" />
            <span>{actionError}</span>
          </div>
        )}

        {successMsg && (
          <div className="mx-5 mt-4 p-3 rounded-lg bg-emerald-950/50 border border-emerald-500/50 text-emerald-300 text-xs flex items-center space-x-2">
            <CheckCircle2 className="w-4 h-4 shrink-0 text-emerald-400" />
            <span>{successMsg}</span>
          </div>
        )}

        {/* Modal Body: Ports List */}
        <div className="p-5 overflow-y-auto flex-1 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-bold text-slate-200 uppercase tracking-wider">
              Physical Dispenser Ports ({station.ports?.length || 0})
            </h3>
            <span className="text-xs text-slate-400 flex items-center space-x-1.5">
              <span className="text-slate-300 font-semibold">{station.ports?.length || 0} Recorded</span>
              <span className="text-slate-600">•</span>
              <span className="text-[10px] text-slate-400 bg-slate-950 px-2 py-0.5 rounded border border-slate-800">
                Live availability unavailable
              </span>
            </span>
          </div>

          <div className="bg-slate-950/60 border border-slate-800/80 rounded-lg p-2.5 text-[11px] text-slate-400 flex items-center justify-between">
            <span>Dispensers and ratings verified from database records.</span>
            <span className="text-slate-500 text-[10px] italic">Session actions below simulate ADBMS ACID transactions</span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5">
            {station.ports?.map((port) => {
              const isAvail = port.status === 'AVAILABLE';
              const isInUse = port.status === 'IN_USE';
              const isLoading = loadingPortId === port.port_id;

              return (
                <div
                  key={port.port_id}
                  className={`p-4 rounded-xl border transition-all ${
                    isAvail
                      ? 'bg-slate-950/60 border-slate-800 hover:border-slate-700'
                      : isInUse
                      ? 'bg-amber-950/20 border-amber-500/30'
                      : 'bg-slate-950/40 border-slate-800'
                  }`}
                >
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-xs font-mono font-bold text-slate-300">
                      Port #{port.port_number} (ID: {port.port_id})
                    </span>
                    <span
                      className={`text-[10px] font-bold px-2 py-0.5 rounded-full border ${
                        isInUse
                          ? 'bg-amber-500/20 text-amber-400 border-amber-500/30 animate-pulse'
                          : isAvail
                          ? 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30'
                          : 'bg-slate-800 text-slate-400 border-slate-700'
                      }`}
                    >
                      {isInUse ? 'IN_USE (Test Session)' : isAvail ? 'RECORDED' : port.status}
                    </span>
                  </div>

                  <div className="space-y-1 mb-3 text-xs">
                    <div className="flex justify-between text-slate-400">
                      <span>Connector:</span>
                      <strong className="text-white">{port.connector_type}</strong>
                    </div>
                    <div className="flex justify-between text-slate-400">
                      <span>Rated Capacity:</span>
                      <strong className="text-emerald-400 font-mono">{port.power_kw} kW</strong>
                    </div>
                  </div>

                  {/* Actions for this Port */}
                  <div className="flex items-center space-x-2 pt-2 border-t border-slate-800/80">
                    {isAvail && (
                      <button
                        onClick={() => handleStartSession(port.port_id)}
                        disabled={isLoading}
                        className="flex-1 py-1.5 px-3 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-semibold text-xs transition flex items-center justify-center space-x-1.5 shadow-md shadow-emerald-600/20"
                      >
                        <Play className="w-3.5 h-3.5 fill-current" />
                        <span>{isLoading ? 'Locking...' : 'Start Charging'}</span>
                      </button>
                    )}

                    {isInUse && (
                      <button
                        onClick={() => handleEndSession(port.port_id)}
                        disabled={isLoading}
                        className="flex-1 py-1.5 px-3 rounded-lg bg-amber-600 hover:bg-amber-500 text-white font-semibold text-xs transition flex items-center justify-center space-x-1.5"
                      >
                        <Square className="w-3.5 h-3.5 fill-current" />
                        <span>{isLoading ? 'Releasing...' : 'End Charging'}</span>
                      </button>
                    )}

                    <button
                      onClick={() => handleViewPortHistory(port.port_id)}
                      className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 transition"
                      title="View temporal status change audit log"
                    >
                      <History className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Temporal Audit Log Drawer if selected */}
          {viewingPortHistory && (
            <div className="mt-5 p-4 rounded-xl bg-slate-950 border border-slate-800 text-xs">
              <div className="flex items-center justify-between mb-3">
                <span className="font-bold text-slate-300 flex items-center space-x-2">
                  <History className="w-4 h-4 text-emerald-400" />
                  <span>Temporal Audit Log: Port #{viewingPortHistory} (station_status_history)</span>
                </span>
                <button
                  onClick={() => setViewingPortHistory(null)}
                  className="text-slate-500 hover:text-slate-300"
                >
                  Close
                </button>
              </div>

              {historyLoading ? (
                <div className="py-4 text-center text-slate-500">Loading audit history...</div>
              ) : portHistoryLogs.length === 0 ? (
                <div className="py-4 text-center text-slate-500">No transition history logged yet.</div>
              ) : (
                <div className="space-y-2 max-h-48 overflow-y-auto">
                  {portHistoryLogs.map((log) => (
                    <div key={log.history_id} className="p-2.5 rounded-lg bg-slate-900 border border-slate-800 flex items-center justify-between">
                      <div>
                        <div className="flex items-center space-x-2">
                          <span className="text-slate-400 font-mono">{log.old_status || 'INIT'}</span>
                          <span className="text-emerald-400 font-bold">&rarr;</span>
                          <span className="font-bold text-white">{log.new_status}</span>
                        </div>
                        <p className="text-[11px] text-slate-400 mt-0.5">{log.reason || 'Status update'}</p>
                      </div>
                      <span className="text-[10px] text-slate-500 font-mono">
                        {new Date(log.changed_at).toLocaleTimeString()}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

        </div>

        {/* Modal Footer */}
        <div className="p-4 border-t border-slate-800 bg-slate-950/60 flex items-center justify-between text-xs text-slate-400">
          <span>Coordinates: {station.latitude}, {station.longitude} (WGS-84)</span>
          <button
            onClick={onClose}
            className="px-4 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 transition"
          >
            Close
          </button>
        </div>

      </div>
    </div>
  );
}
