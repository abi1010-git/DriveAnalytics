import React, { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid, ResponsiveContainer } from 'recharts';
import './style.css';

const API = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';
type Event = { id:number; vehicle_id:number; timestamp:string; event_type:string; severity:string; software_version:string; route_id:string; description:string };
type Summary = { total_vehicles:number; total_safety_events:number; hard_braking_count:number; sensor_failure_count:number; events_by_severity:Record<string,number>; events_by_event_type:Record<string,number>; events_by_software_version:Record<string,number> };
type FleetSummary = { vehicle_id:number; telemetry_record_count:number; average_speed:number; max_speed:number; hard_braking_count:number; rapid_acceleration_count:number; sensor_failure_count:number };
const chart = (values:Record<string,number>) => Object.entries(values).map(([name,value]) => ({ name, value }));

function App() {
  const [summary,setSummary] = useState<Summary|null>(null), [events,setEvents] = useState<Event[]>([]), [fleet,setFleet] = useState<FleetSummary[]>([]), [selected,setSelected] = useState<Event|null>(null), [severity,setSeverity] = useState(''), [error,setError] = useState<string|null>(null);
  const load = () => {
    setError(null); setSummary(null);
    const json = (response:Response) => { if (!response.ok) throw Error(`Request failed (${response.status})`); return response.json(); };
    Promise.all([fetch(`${API}/api/metrics/summary`).then(json), fetch(`${API}/api/events`).then(json), fetch(`${API}/api/analytics/fleet-summary`).then(json)])
      .then(([metrics, eventRows, fleetRows]) => { setSummary(metrics); setEvents(eventRows); setFleet(fleetRows); })
      .catch(reason => setError(reason instanceof Error ? reason.message : 'Unable to load analytics'));
  };
  useEffect(load, []);
  const shown = events.filter(event => !severity || event.severity === severity);
  return <main>
    <header><div><span className="eyebrow">SAFEDRIVE / ENGINEERING ANALYTICS</span><h1>Safety operations console</h1><p>Simulated fleet telemetry and event intelligence.</p></div><span className="badge">● SYNTHETIC DATA</span></header>
    {error ? <section><p>Unable to load analytics from <code>{API}</code>: {error}</p><button onClick={load}>Retry</button></section> : !summary ? <p>Loading analytics…</p> : <>
      <section className="cards">{[['Fleet vehicles',summary.total_vehicles],['Safety events',summary.total_safety_events],['Critical events',summary.events_by_severity.CRITICAL||0],['Hard braking',summary.hard_braking_count],['Sensor failures',summary.sensor_failure_count]].map(([name,value]) => <article key={String(name)}><small>{name}</small><strong>{value}</strong><span>Current dataset</span></article>)}</section>
      <section className="charts"><Panel title="Events by severity"><BarChart data={chart(summary.events_by_severity)}><CartesianGrid strokeDasharray="3 3"/><XAxis dataKey="name"/><YAxis/><Tooltip/><Bar dataKey="value" fill="#f59e0b"/></BarChart></Panel><Panel title="Event type distribution"><BarChart data={chart(summary.events_by_event_type)}><CartesianGrid strokeDasharray="3 3"/><XAxis dataKey="name" angle={-18} textAnchor="end" height={55}/><YAxis/><Tooltip/><Bar dataKey="value" fill="#38bdf8"/></BarChart></Panel><Panel title="Software versions"><BarChart data={chart(summary.events_by_software_version)}><CartesianGrid strokeDasharray="3 3"/><XAxis dataKey="name"/><YAxis/><Tooltip/><Bar dataKey="value" fill="#a78bfa"/></BarChart></Panel></section>
      <section className="spark-summary"><div className="section-head"><div><span className="eyebrow">PYSPARK BATCH SUMMARY</span><h2>Fleet telemetry health</h2></div><span className="badge">AGGREGATE DATA</span></div>{fleet.length ? <table><thead><tr><th>Vehicle</th><th>Records</th><th>Avg speed</th><th>Max speed</th><th>Sensor failures</th></tr></thead><tbody>{fleet.slice(0,10).map(row => <tr key={row.vehicle_id}><td>SD-{String(row.vehicle_id).padStart(3,'0')}</td><td>{row.telemetry_record_count.toLocaleString()}</td><td>{row.average_speed.toFixed(1)} mph</td><td>{row.max_speed.toFixed(1)} mph</td><td>{row.sensor_failure_count}</td></tr>)}</tbody></table> : <p>Run the PySpark pipeline to populate aggregate summaries.</p>}</section>
      <section className="investigate"><div className="section-head"><div><span className="eyebrow">EVENT INVESTIGATION</span><h2>Recent safety events</h2></div><select value={severity} onChange={event => setSeverity(event.target.value)}><option value="">All severities</option>{['LOW','MEDIUM','HIGH','CRITICAL'].map(value => <option key={value}>{value}</option>)}</select></div><table><thead><tr><th>Timestamp</th><th>Vehicle</th><th>Event type</th><th>Severity</th><th>Version</th><th>Route</th></tr></thead><tbody>{shown.slice(0,100).map(event => <tr key={event.id} onClick={() => setSelected(event)}><td>{new Date(event.timestamp).toLocaleString()}</td><td>SD-{String(event.vehicle_id).padStart(3,'0')}</td><td>{event.event_type}</td><td><span className={'severity '+event.severity.toLowerCase()}>{event.severity}</span></td><td>{event.software_version}</td><td>{event.route_id}</td></tr>)}</tbody></table></section>
    </>}
    {selected && <aside><button onClick={() => setSelected(null)}>×</button><span className="eyebrow">EVENT {selected.id}</span><h2>{selected.event_type}</h2><p>{selected.description}</p><dl><dt>Severity</dt><dd>{selected.severity}</dd><dt>Vehicle</dt><dd>SD-{String(selected.vehicle_id).padStart(3,'0')}</dd><dt>Timestamp</dt><dd>{new Date(selected.timestamp).toLocaleString()}</dd><dt>Route / Version</dt><dd>{selected.route_id} / {selected.software_version}</dd></dl><div className="telemetry-note">Nearby telemetry is available through <code>/api/events/{selected.id}</code>.</div></aside>}
  </main>;
}
function Panel({ title, children }: { title:string; children:any }) { return <article className="panel"><h3>{title}</h3><ResponsiveContainer width="100%" height={220}>{children}</ResponsiveContainer></article>; }
createRoot(document.getElementById('root')!).render(<App/>);
