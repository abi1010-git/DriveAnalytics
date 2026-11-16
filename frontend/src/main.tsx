// DriveAnalytics: click a state, then a county or city, to see where people were hurt or killed
// in crashes, which roads had the most deaths, and what was recorded about those crashes.
// Fatal crashes nationwide come from FARS (to 2024); newer data comes from city crash reports
// and live incident feeds where they exist.
import L from 'leaflet';
import React, { useEffect, useMemo, useState } from 'react';
import { createRoot } from 'react-dom/client';
import type { BBox, CityRow, CountyRow, Coverage, CrashPoint, FlagDef, RecentPoint, RecentSource, Selection, StateRow, Summary, TimeRange } from './api';
import { API, FARS_FIRST, THIS_YEAR, api, farsYears } from './api';
import { CrashMap, Legend } from './components/CrashMap';
import { SidePanel } from './components/SidePanel';
import type { Boundary } from './geo';
import { loadCounties, loadStates } from './geo';
import './style.css';

const US_BBOX: BBox = [-179.9, 17.5, -64.5, 71.5];

function boundsToBBox(bounds: L.LatLngBounds, pad = 0): BBox {
  return [bounds.getWest() - pad, bounds.getSouth() - pad, bounds.getEast() + pad, bounds.getNorth() + pad];
}

function App() {
  const [selection, setSelection] = useState<Selection>({});
  const [range, setRange] = useState<TimeRange>({ kind: 'years', from: FARS_FIRST, to: THIS_YEAR });
  const [flags, setFlags] = useState<FlagDef[]>([]);
  const [coverage, setCoverage] = useState<Coverage[]>([]);
  const [stateFeatures, setStateFeatures] = useState<Boundary[]>([]);
  const [countyFeatures, setCountyFeatures] = useState<Boundary[]>([]);
  const [states, setStates] = useState<StateRow[]>([]);
  const [counties, setCounties] = useState<CountyRow[]>([]);
  const [cities, setCities] = useState<CityRow[]>([]);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [crashes, setCrashes] = useState<CrashPoint[]>([]);
  const [recent, setRecent] = useState<RecentSource[]>([]);
  const [recentPoints, setRecentPoints] = useState<RecentPoint[]>([]);
  const [selectedRoad, setSelectedRoad] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fail = (reason: unknown) => setError(reason instanceof Error ? reason.message : 'Unable to load data');
  const fars = farsYears(range);
  const inArea = selection.countyCode !== undefined || !!selection.city;

  useEffect(() => {
    api.flags().then(setFlags).catch(fail);
    api.coverage().then(setCoverage).catch(fail);
    loadStates().then(setStateFeatures).catch(fail);
  }, []);

  // FARS (fatal crashes, to 2024) for the current place and the part of the range it covers.
  useEffect(() => {
    let current = true;
    const keep = <T,>(set: (v: T) => void) => (v: T) => { if (current) set(v); };
    setLoading(true);
    setError(null);
    setSelectedRoad(null);
    setSummary(null);
    setCrashes([]);
    const jobs: Promise<unknown>[] = [];
    if (selection.stateCode !== undefined) jobs.push(loadCounties().then(keep(setCountyFeatures)));
    if (!fars) {
      setStates([]); setCounties([]); setCities([]);
    } else if (selection.stateCode === undefined) {
      jobs.push(api.states(fars).then(keep(setStates)));
    } else {
      jobs.push(api.counties(selection, fars).then(keep(setCounties)));
      jobs.push(api.summary(selection, fars).then(keep(setSummary)));
      if (!inArea) jobs.push(api.cities(selection, fars).then(keep(setCities)));
      if (inArea) jobs.push(api.crashes(selection, fars).then(keep(setCrashes)));
    }
    Promise.all(jobs).catch(e => current && fail(e)).finally(() => current && setLoading(false));
    return () => { current = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selection, fars?.from, fars?.to]);

  // The area on screen as a bounding box, for the recent-data queries.
  const bbox = useMemo<BBox | null>(() => {
    if (selection.stateCode === undefined) return null;
    const prefix = String(selection.stateCode).padStart(2, '0');
    if (selection.countyCode !== undefined) {
      const county = countyFeatures.find(f => f.id === prefix + String(selection.countyCode).padStart(3, '0'));
      return county ? boundsToBBox(L.geoJSON(county).getBounds()) : null;
    }
    if (selection.city) {
      if (crashes.length) return boundsToBBox(L.latLngBounds(crashes.map(c => [c.latitude, c.longitude] as [number, number])), 0.02);
      const city = cities.find(c => c.name === selection.city);
      return city?.latitude != null ? [city.longitude! - 0.15, city.latitude - 0.12, city.longitude! + 0.15, city.latitude + 0.12] : null;
    }
    const state = stateFeatures.find(f => Number(f.id) === selection.stateCode);
    return state ? (selection.stateCode === 2 ? [-179.9, 51, -129.9, 71.5] : boundsToBBox(L.geoJSON(state).getBounds())) : null;
  }, [selection, countyFeatures, stateFeatures, crashes, cities]);

  // Newer-than-FARS data: per-source counts for the area, and points when zoomed into one.
  // Dots once zoomed into a county/city; in live mode everywhere; and statewide when FARS has nothing for the range.
  const wantPoints = inArea || range.kind === 'live' || (!fars && selection.stateCode !== undefined);
  const rangeKey = range.kind === 'live' ? 'live' : `${range.from}-${range.to}`;
  useEffect(() => {
    let current = true;
    const box = bbox ?? undefined;
    if (selection.stateCode !== undefined && !box) return;  // wait for boundaries
    api.recentSummary(range, box).then(rows => current && setRecent(rows)).catch(e => current && fail(e));
    if (wantPoints) api.recentPoints(range, box ?? US_BBOX).then(rows => current && setRecentPoints(rows)).catch(e => current && fail(e));
    else setRecentPoints([]);
    return () => { current = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [bbox?.join(','), rangeKey, wantPoints, selection.stateCode]);

  // Live mode refreshes itself every 5 minutes.
  useEffect(() => {
    if (range.kind !== 'live') return;
    const timer = window.setInterval(() => setRange({ kind: 'live' }), 5 * 60 * 1000);
    return () => window.clearInterval(timer);
  }, [range.kind]);

  const flagNames = useMemo(() => Object.fromEntries(flags.filter(f => f.source === 'fars').map(f => [f.id, f])), [flags]);
  const recentStates = useMemo(() => {
    const out = new Map<number, string[]>();
    coverage.forEach(c => c.states.forEach(s => out.set(s, [...(out.get(s) ?? []), c.label])));
    return out;
  }, [coverage]);

  return <div className="app">
    <div className="map-wrap">
      <CrashMap selection={selection} farsActive={!!fars} stateFeatures={stateFeatures} countyFeatures={countyFeatures} states={states} counties={counties}
        cities={cities} crashes={crashes} recentPoints={recentPoints} recentStates={recentStates} coverage={coverage} flagNames={flagNames} selectedRoad={selectedRoad}
        onState={(stateCode, stateName) => setSelection({ stateCode, stateName })}
        onCounty={(countyCode, countyName) => setSelection({ stateCode: selection.stateCode, stateName: selection.stateName, countyCode, countyName })}
        onCity={city => setSelection({ stateCode: selection.stateCode, stateName: selection.stateName, city })} />
      <Legend showFatal={!!fars && inArea} showRecords={recentPoints.some(r => r.kind === 'record')} showLive={recentPoints.some(r => r.kind === 'live')} />
      {error && <div className="error">Could not load data from <code>{API}</code>: {error}</div>}
    </div>
    <SidePanel selection={selection} range={range} fars={fars} states={states} counties={counties} cities={cities} summary={summary}
      recent={recent} recentPoints={recentPoints.length} coverage={coverage} flagNames={flagNames} loading={loading} shownCrashes={crashes.length}
      selectedRoad={selectedRoad} onSelect={setSelection} onRange={setRange} onRoad={setSelectedRoad}
      onSource={source => {
        const state = coverage.find(c => c.source === source)?.states[0];
        const feature = stateFeatures.find(f => Number(f.id) === state);
        if (state !== undefined) setSelection({ stateCode: state, stateName: feature?.properties.name });
      }} />
  </div>;
}

createRoot(document.getElementById('root')!).render(<React.StrictMode><App /></React.StrictMode>);
