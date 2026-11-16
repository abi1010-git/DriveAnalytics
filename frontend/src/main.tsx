// Phase 1 page: shows what real data is loaded and how often each risk flag occurs.
// The map, address search, rankings and trends arrive in Phase 3.
import React, { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import './style.css';

const API = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';

type FarsYear = { year: number; crashes: number; fatalities: number };
type Datasets = {
  fars: { name: string; coverage: string; years: FarsYear[]; last_loaded: string | null };
  nyc: { name: string; coverage: string; crashes: number; with_coordinates: number; first_crash: string | null; last_crash: string | null; last_loaded: string | null };
};
type Flag = { id: string; name: string; description: string; source: 'fars' | 'nyc'; category: string; crashes_flagged: number };

const fmt = (n: number) => n.toLocaleString();
const day = (iso: string | null) => (iso ? new Date(iso).toLocaleDateString() : '—');

function App() {
  const [data, setData] = useState<Datasets | null>(null);
  const [flags, setFlags] = useState<Flag[]>([]);
  const [error, setError] = useState<string | null>(null);

  const load = () => {
    setError(null);
    const json = (r: Response) => { if (!r.ok) throw Error(`Request failed (${r.status})`); return r.json(); };
    Promise.all([fetch(`${API}/api/datasets`).then(json), fetch(`${API}/api/risk-flags`).then(json)])
      .then(([datasets, flagRows]) => { setData(datasets); setFlags(flagRows); })
      .catch(reason => setError(reason instanceof Error ? reason.message : 'Unable to load data'));
  };
  useEffect(load, []);

  if (error) return <main><p>Could not reach the API at <code>{API}</code>: {error}</p><button onClick={load}>Retry</button></main>;
  if (!data) return <main><p>Loading…</p></main>;

  const farsTotal = data.fars.years.reduce((sum, y) => sum + y.crashes, 0);
  const farsDeaths = data.fars.years.reduce((sum, y) => sum + y.fatalities, 0);
  const years = data.fars.years.map(y => y.year);
  return <main>
    <header>
      <div><span className="eyebrow">DRIVEANALYTICS</span><h1>US crash data explorer</h1>
        <p>Real crash records from NHTSA (every fatal US crash) and NYC Open Data (every police-reported crash in New York City).</p></div>
      <span className="badge">PHASE 1 · DATA LOADED</span>
    </header>

    <section className="cards">
      <article><small>US fatal crashes</small><strong>{fmt(farsTotal)}</strong><span>{years.length ? `${years[0]}–${years[years.length - 1]}` : 'not loaded'}</span></article>
      <article><small>People killed (US)</small><strong>{fmt(farsDeaths)}</strong><span>FARS</span></article>
      <article><small>NYC crashes</small><strong>{fmt(data.nyc.crashes)}</strong><span>{day(data.nyc.first_crash)} – {day(data.nyc.last_crash)}</span></article>
      <article><small>NYC crashes with a location</small><strong>{data.nyc.crashes ? `${Math.round(100 * data.nyc.with_coordinates / data.nyc.crashes)}%` : '—'}</strong><span>{fmt(data.nyc.with_coordinates)} mappable</span></article>
    </section>

    <section className="charts one">
      <article className="panel"><h3>Fatal crashes per year, United States (FARS)</h3>
        <ResponsiveContainer width="100%" height={240}>
          <BarChart data={data.fars.years}><CartesianGrid strokeDasharray="3 3" /><XAxis dataKey="year" /><YAxis /><Tooltip formatter={v => fmt(Number(v))} /><Bar dataKey="crashes" name="Fatal crashes" fill="#38bdf8" /></BarChart>
        </ResponsiveContainer>
      </article>
    </section>

    {(['fars', 'nyc'] as const).map(source => <section className="investigate" key={source}>
      <div className="section-head"><div><span className="eyebrow">RISK FLAGS · {source === 'fars' ? 'US FATAL CRASHES' : 'NEW YORK CITY'}</span>
        <h2>What was recorded about these crashes</h2></div></div>
      <table><thead><tr><th>Flag</th><th>Category</th><th>Crashes</th><th>How it is defined</th></tr></thead>
        <tbody>{flags.filter(f => f.source === source).sort((a, b) => b.crashes_flagged - a.crashes_flagged).map(f =>
          <tr key={f.id}><td>{f.name}</td><td>{f.category.replace(/_/g, ' ')}</td><td>{fmt(f.crashes_flagged)}</td><td className="muted">{f.description}</td></tr>)}</tbody></table>
    </section>)}

    <p className="footnote">A flag records what police reported about a crash; it does not establish cause. Sources: NHTSA FARS national files; NYC Open Data dataset h9gi-nx95.</p>
  </main>;
}

createRoot(document.getElementById('root')!).render(<App />);
