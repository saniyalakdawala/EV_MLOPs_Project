import React, { useEffect, useMemo, useState } from 'react';
import { AlertTriangle, BrainCircuit, RefreshCw, TrendingUp } from 'lucide-react';
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { fetchForecastEvaluation, fetchForecastModelInfo, requestForecast } from '../api';

export default function ForecastPanel() {
  const [model, setModel] = useState(null);
  const [evaluation, setEvaluation] = useState(null);
  const [siteId, setSiteId] = useState('');
  const [horizon, setHorizon] = useState(24);
  const [forecasts, setForecasts] = useState([]);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  const loadModel = async () => {
    try {
      const [info, scores] = await Promise.all([fetchForecastModelInfo(), fetchForecastEvaluation()]);
      setModel(info); setEvaluation(scores); setSiteId((current) => current || info.site_ids?.[0] || ''); setError(null);
    } catch (err) { setModel(null); setEvaluation(null); setError(err.message); }
  };
  useEffect(() => {
    let mounted = true;
    Promise.all([fetchForecastModelInfo(), fetchForecastEvaluation()]).then(([info, scores]) => {
      if (!mounted) return;
      setModel(info); setEvaluation(scores); setSiteId(info.site_ids?.[0] || '');
    }).catch((err) => { if (mounted) { setModel(null); setEvaluation(null); setError(err.message); } });
    return () => { mounted = false; };
  }, []);

  const runForecast = async () => {
    if (!model || !siteId) return;
    setLoading(true); setError(null);
    try {
      const result = await requestForecast({ site_id: siteId, forecast_origin: model.latest_observed_hour, horizon_hours: Number(horizon) });
      setForecasts(result.forecasts);
    } catch (err) { setError(err.message); setForecasts([]); }
    finally { setLoading(false); }
  };

  const chartRows = useMemo(() => forecasts.map((row) => ({ ...row, label: new Date(row.timestamp).toLocaleString([], { weekday: 'short', hour: 'numeric', day: 'numeric', timeZone: model?.timezone || undefined }) })), [forecasts, model?.timezone]);
  const score = evaluation?.held_out_test_metrics?.[evaluation.selected_model];

  return (
    <section className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="flex items-center gap-2 text-xl font-bold text-white"><TrendingUp className="h-5 w-5 text-cyan-400" />Charging Demand Forecast</h2>
          <p className="mt-1 text-sm text-slate-400">Hourly session-arrival-associated energy, grouped by site local time.</p>
        </div>
        <button onClick={loadModel} className="flex items-center gap-2 rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-slate-200 hover:bg-slate-700"><RefreshCw className="h-4 w-4" />Refresh model</button>
      </div>

      {!model ? (
        <div className="rounded-2xl border border-amber-700/50 bg-amber-950/30 p-6 text-amber-100">
          <div className="flex items-start gap-3"><AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-amber-300" /><div><h3 className="font-semibold">A trained model is not available</h3><p className="mt-1 text-sm text-amber-100/80">{error || 'Import eligible session data and train a model to enable forecasts.'} The existing VoltGrid session seed is simulated and is not used for training.</p><p className="mt-3 text-xs text-amber-100/70">No forecast, actual performance, or live demand feed is being shown.</p></div></div>
        </div>
      ) : (
        <>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
            {[['Selected model', model.model_name], ['Last trained (UTC)', model.trained_at_utc ? new Date(model.trained_at_utc).toLocaleString() : 'Unavailable'], ['Model version', model.model_version], ['Data provenance', model.provenance], ['Held-out test MAE', score ? `${score.mae.toFixed(2)} kWh` : 'Unavailable']].map(([label, value]) => <div key={label} className="rounded-xl border border-slate-800 bg-slate-900/70 p-4"><p className="text-xs uppercase tracking-wide text-slate-400">{label}</p><p className="mt-2 truncate font-semibold text-white" title={String(value)}>{value}</p></div>)}
          </div>
          {String(model.provenance).toUpperCase().startsWith('SYNTHETIC') && <div className="rounded-lg border border-amber-700/50 bg-amber-950/30 px-4 py-3 text-sm text-amber-200">Synthetic plumbing demonstration only. These results do not represent genuine charging demand.</div>}
          <div className="flex flex-wrap items-end gap-3 rounded-2xl border border-slate-800 bg-slate-900/70 p-4">
            <label className="grid gap-1 text-xs text-slate-400">Site<select value={siteId} onChange={(event) => setSiteId(event.target.value)} className="min-w-48 rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-white">{model.site_ids?.map((id) => <option key={id} value={id}>{id}</option>)}</select></label>
            <label className="grid gap-1 text-xs text-slate-400">Horizon<select value={horizon} onChange={(event) => setHorizon(event.target.value)} className="rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-white">{[6, 12, 24, 48, 72, 168].map((h) => <option key={h} value={h}>{h} hours</option>)}</select></label>
            <button disabled={loading} onClick={runForecast} className="flex items-center gap-2 rounded-lg bg-cyan-600 px-4 py-2 text-sm font-semibold text-white hover:bg-cyan-500 disabled:opacity-50"><BrainCircuit className="h-4 w-4" />{loading ? 'Forecasting…' : 'Generate forecast'}</button>
            <span className="text-xs text-slate-500">Origin: latest complete observed hour ({model.latest_observed_hour})</span>
          </div>
          {error && <p role="alert" className="rounded-lg border border-rose-800 bg-rose-950/40 px-4 py-3 text-sm text-rose-200">{error}</p>}
          {chartRows.length ? <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-4"><h3 className="mb-4 font-semibold text-white">Forecasted energy (kWh)</h3><div className="h-80"><ResponsiveContainer width="100%" height="100%"><LineChart data={chartRows}><CartesianGrid strokeDasharray="3 3" stroke="#334155" /><XAxis dataKey="label" tick={{ fill: '#94a3b8', fontSize: 11 }} minTickGap={20} /><YAxis tick={{ fill: '#94a3b8', fontSize: 11 }} unit=" kWh" /><Tooltip contentStyle={{ background: '#0f172a', border: '1px solid #334155', borderRadius: 8 }} formatter={(value) => [`${Number(value).toFixed(2)} kWh`, 'Forecast']} /><Line type="monotone" dataKey="predicted_kwh" stroke="#22d3ee" strokeWidth={2} dot={false} /></LineChart></ResponsiveContainer></div><p className="mt-3 text-xs text-slate-500">Forecast only; actual future observations are not yet available. No uncertainty interval is estimated by this model.</p></div> : <div className="rounded-2xl border border-dashed border-slate-700 p-10 text-center text-sm text-slate-400">Choose a site and generate a forecast. Model evaluation uses a separate chronological held-out test period.</div>}
          {evaluation && <details className="rounded-xl border border-slate-800 bg-slate-900/50 p-4"><summary className="cursor-pointer text-sm font-medium text-slate-200">Model comparison details</summary><pre className="mt-3 overflow-auto text-xs text-slate-400">{JSON.stringify({ validation: evaluation.validation_metrics, held_out_test: evaluation.held_out_test_metrics, per_site_test: evaluation.per_site_test_metrics }, null, 2)}</pre></details>}
        </>
      )}
    </section>
  );
}
