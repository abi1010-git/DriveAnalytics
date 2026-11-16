// DriveAnalytics: click a state, then a county or city, to see where people died in crashes,
// which roads had the most deaths, and what police recorded about those crashes.
import React, { useEffect, useMemo, useState } from 'react';
import { createRoot } from 'react-dom/client';
import type { CityRow, CountyRow, CrashPoint, FlagDef, Selection, StateRow, Summary } from './api';
import { API, api } from './api';
import { CrashMap } from './components/CrashMap';
import { SidePanel } from './components/SidePanel';
import type { Boundary } from './geo';
import { loadCounties, loadStates } from './geo';
import './style.css';

function App() {
  const [selection, setSelection] = useState<Selection>({});
  const [flags, setFlags] = useState<FlagDef[]>([]);
  const [stateFeatures, setStateFeatures] = useState<Boundary[]>([]);
  const [countyFeatures, setCountyFeatures] = useState<Boundary[]>([]);
  const [states, setStates] = useState<StateRow[]>([]);
  const [counties, setCounties] = useState<CountyRow[]>([]);
  const [cities, setCities] = useState<CityRow[]>([]);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [crashes, setCrashes] = useState<CrashPoint[]>([]);
  const [selectedRoad, setSelectedRoad] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fail = (reason: unknown) => setError(reason instanceof Error ? reason.message : 'Unable to load data');

  useEffect(() => {
    api.flags().then(setFlags).catch(fail);
    loadStates().then(setStateFeatures).catch(fail);
  }, []);

  // Load whatever the current level needs. A newer selection cancels older responses.
  useEffect(() => {
    let current = true;
    const keep = <T,>(set: (v: T) => void) => (v: T) => { if (current) set(v); };
    const inArea = selection.countyCode !== undefined || !!selection.city;
    setLoading(true);
    setError(null);
    setSelectedRoad(null);
    setSummary(null);
    setCrashes([]);
    const jobs: Promise<unknown>[] = [];
    if (selection.stateCode === undefined) {
      jobs.push(api.states(selection).then(keep(setStates)));
    } else {
      jobs.push(loadCounties().then(keep(setCountyFeatures)));
      jobs.push(api.counties(selection).then(keep(setCounties)));
      jobs.push(api.summary(selection).then(keep(setSummary)));
      if (!inArea) jobs.push(api.cities(selection).then(keep(setCities)));
      if (inArea) jobs.push(api.crashes(selection).then(keep(setCrashes)));
    }
    Promise.all(jobs).catch(e => current && fail(e)).finally(() => current && setLoading(false));
    return () => { current = false; };
  }, [selection]);

  const flagNames = useMemo(() => Object.fromEntries(flags.filter(f => f.source === 'fars').map(f => [f.id, f])), [flags]);

  return <div className="app">
    <div className="map-wrap">
      <CrashMap selection={selection} stateFeatures={stateFeatures} countyFeatures={countyFeatures} states={states} counties={counties}
        cities={cities} crashes={crashes} flagNames={flagNames} selectedRoad={selectedRoad}
        onState={(stateCode, stateName) => setSelection({ year: selection.year, stateCode, stateName })}
        onCounty={(countyCode, countyName) => setSelection({ year: selection.year, stateCode: selection.stateCode, stateName: selection.stateName, countyCode, countyName })}
        onCity={city => setSelection({ year: selection.year, stateCode: selection.stateCode, stateName: selection.stateName, city })} />
      {error && <div className="error">Could not load data from <code>{API}</code>: {error}</div>}
    </div>
    <SidePanel selection={selection} states={states} counties={counties} cities={cities} summary={summary} flagNames={flagNames}
      loading={loading} shownCrashes={crashes.length} selectedRoad={selectedRoad} onSelect={setSelection} onRoad={setSelectedRoad} />
  </div>;
}

createRoot(document.getElementById('root')!).render(<React.StrictMode><App /></React.StrictMode>);
