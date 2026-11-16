import { Bar, BarChart, ResponsiveContainer, Tooltip, XAxis } from 'recharts';
import type { CityRow, CountyRow, FlagDef, Selection, StateRow, Summary } from '../api';
import { fmt } from '../api';
import { titleCase } from './CrashMap';

const YEARS = [2024, 2023, 2022, 2021, 2020];

type Props = {
  selection: Selection;
  states: StateRow[];
  counties: CountyRow[];
  cities: CityRow[];
  summary: Summary | null;
  flagNames: Record<string, FlagDef>;
  loading: boolean;
  shownCrashes: number;
  selectedRoad: string | null;
  onSelect: (s: Selection) => void;
  onRoad: (road: string | null) => void;
};

export function SidePanel(p: Props) {
  const { selection: sel } = p;
  const inArea = sel.countyCode !== undefined || !!sel.city;
  const totals = sel.stateCode === undefined
    ? sum(p.states)
    : { crashes: p.summary?.factors.total_crashes ?? 0, deaths: p.summary?.factors.total_deaths ?? 0 };
  const areaCrashes = totals.crashes;
  const place = sel.city ? titleCase(sel.city) : sel.countyName ? `${titleCase(sel.countyName)} County` : sel.stateName ?? 'United States';

  return <aside className="panel-side">
    <nav className="crumbs">
      <button onClick={() => p.onSelect({ year: sel.year })} disabled={sel.stateCode === undefined}>United States</button>
      {sel.stateName && <><span>›</span><button onClick={() => p.onSelect({ year: sel.year, stateCode: sel.stateCode, stateName: sel.stateName })} disabled={!inArea}>{sel.stateName}</button></>}
      {inArea && <><span>›</span><b>{place}</b></>}
    </nav>

    <div className="head">
      <h1>{place}</h1>
      <select value={sel.year ?? ''} onChange={e => p.onSelect({ ...sel, year: e.target.value ? Number(e.target.value) : undefined })} aria-label="Year">
        <option value="">2020–2024</option>
        {YEARS.map(y => <option key={y} value={y}>{y}</option>)}
      </select>
    </div>

    <div className="stats">
      <div><strong>{fmt(totals.deaths)}</strong><span>people killed</span></div>
      <div><strong>{fmt(areaCrashes)}</strong><span>fatal crashes</span></div>
    </div>

    {p.loading && <p className="muted">Loading…</p>}

    {sel.stateCode === undefined && <Ranked title="States with the most deaths" hint="Click a state on the map or below."
      rows={p.states.slice(0, 12).map(s => ({ key: String(s.state_code), label: s.name, value: s.deaths, onClick: () => p.onSelect({ year: sel.year, stateCode: s.state_code, stateName: s.name }) }))} />}

    {sel.stateCode !== undefined && !inArea && <>
      <Ranked title="Cities with the most deaths" hint="Crashes outside city limits are counted in their county only."
        rows={p.cities.slice(0, 10).map(c => ({ key: c.name, label: titleCase(c.name), value: c.deaths, onClick: () => p.onSelect({ ...sel, city: c.name }) }))} />
      <Ranked title="Counties with the most deaths"
        rows={p.counties.slice(0, 10).map(c => ({ key: c.fips, label: titleCase(c.name), value: c.deaths, onClick: () => p.onSelect({ ...sel, countyCode: c.county_code, countyName: c.name }) }))} />
    </>}

    {p.summary && sel.stateCode !== undefined && <>
      <section>
        <h2>Roads with the most deaths</h2>
        {inArea && <p className="muted">Click a road to highlight its crashes on the map.</p>}
        <ol className="roads">
          {p.summary.roads.map(r => <li key={r.road_route}>
            <button className={p.selectedRoad === r.road_route ? 'on' : ''} disabled={!inArea}
              onClick={() => p.onRoad(p.selectedRoad === r.road_route ? null : r.road_route)}>
              <span className="road-name">{r.road_route}{r.name.toUpperCase() !== r.road_route && <small>as recorded: {r.name}</small>}</span>
              <span className="road-num">{fmt(r.deaths)} killed · {fmt(r.crashes)} crashes</span>
              <span className="road-tags">
                {r.speeding_crashes > 0 && <em>{pct(r.speeding_crashes, r.crashes)} speeding</em>}
                {r.drinking_crashes > 0 && <em>{pct(r.drinking_crashes, r.crashes)} drinking driver</em>}
                {r.non_motorist_crashes > 0 && <em>{pct(r.non_motorist_crashes, r.crashes)} pedestrian/cyclist</em>}
              </span>
            </button>
          </li>)}
        </ol>
        {p.summary.roads.length === 0 && <p className="muted">No named roads recorded here.</p>}
      </section>

      <section>
        <h2>What was recorded</h2>
        <div className="bars">
          {p.summary.factors.flags.filter(f => p.flagNames[f.flag_id]).map(f => <div key={f.flag_id} className="bar-row" title={p.flagNames[f.flag_id].description}>
            <span>{p.flagNames[f.flag_id].name}</span>
            <div className="bar"><i style={{ width: `${(100 * f.crashes) / Math.max(areaCrashes, 1)}%` }} /></div>
            <b>{pct(f.crashes, areaCrashes)}</b>
          </div>)}
        </div>
      </section>

      <section>
        <h2>Time of day</h2>
        <ResponsiveContainer width="100%" height={120}>
          <BarChart data={p.summary.hours} margin={{ top: 4, right: 0, left: 0, bottom: 0 }}>
            <XAxis dataKey="hour" tickFormatter={h => (h % 6 === 0 ? `${h}:00` : '')} interval={0} tick={{ fill: '#8fa1b8', fontSize: 11 }} axisLine={false} tickLine={false} />
            <Tooltip cursor={{ fill: '#1e293b' }} contentStyle={{ background: '#0b1120', border: '1px solid #334155' }}
              labelFormatter={h => `${h}:00–${h}:59`} formatter={v => [`${fmt(Number(v))} crashes`, '']} />
            <Bar dataKey="crashes" fill="#38bdf8" radius={[2, 2, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </section>
    </>}

    {inArea && p.shownCrashes > 0 && <p className="muted">{fmt(p.shownCrashes)} crashes with a known location are shown on the map. Click a dot for details.</p>}

    <p className="caveat">
      Source: NHTSA FARS, every US crash where someone died within 30 days. These are totals, not rates:
      busy roads and big places show more deaths partly because more people travel there.
      Flags record what police reported, not proven causes.
    </p>
  </aside>;
}

function Ranked({ title, hint, rows }: { title: string; hint?: string; rows: { key: string; label: string; value: number; onClick: () => void }[] }) {
  const max = Math.max(1, ...rows.map(r => r.value));
  return <section>
    <h2>{title}</h2>
    {hint && <p className="muted">{hint}</p>}
    <ol className="ranked">
      {rows.map(r => <li key={r.key}><button onClick={r.onClick}>
        <span>{r.label}</span><div className="bar"><i style={{ width: `${(100 * r.value) / max}%` }} /></div><b>{fmt(r.value)}</b>
      </button></li>)}
    </ol>
  </section>;
}

const pct = (part: number, whole: number) => `${Math.round((100 * part) / Math.max(whole, 1))}%`;
const sum = (rows: { crashes: number; deaths: number }[]) => rows.reduce((t, r) => ({ crashes: t.crashes + r.crashes, deaths: t.deaths + r.deaths }), { crashes: 0, deaths: 0 });
