import { Bar, BarChart, ResponsiveContainer, Tooltip, XAxis } from 'recharts';
import type { CityRow, Coverage, CountyRow, FlagDef, RecentSource, Selection, StateRow, Summary, TimeRange } from '../api';
import { FARS_FIRST, FARS_LAST, FIRST_YEAR, THIS_YEAR, ago, fmt, parseTime } from '../api';
import { COLORS, titleCase } from './CrashMap';

const YEARS = Array.from({ length: THIS_YEAR - FIRST_YEAR + 1 }, (_, i) => THIS_YEAR - i);

type Props = {
  selection: Selection;
  range: TimeRange;
  fars: { from: number; to: number } | null;
  recent: RecentSource[];
  recentPoints: number;
  coverage: Coverage[];
  onRange: (r: TimeRange) => void;
  onSource: (source: string) => void;
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
      <button onClick={() => p.onSelect({})} disabled={sel.stateCode === undefined}>United States</button>
      {sel.stateName && <><span>›</span><button onClick={() => p.onSelect({ stateCode: sel.stateCode, stateName: sel.stateName })} disabled={!inArea}>{sel.stateName}</button></>}
      {inArea && <><span>›</span><b>{place}</b></>}
    </nav>

    <div className="head">
      <h1>{place}</h1>
    </div>

    <TimeControls range={p.range} onRange={p.onRange} />

    <RecentSection recent={p.recent} range={p.range} shownPoints={p.recentPoints} inArea={inArea} atUS={sel.stateCode === undefined} onSource={p.onSource} />

    {p.fars ? <>
      <h2 className="block-title">Fatal crashes, {p.fars.from === p.fars.to ? p.fars.from : `${p.fars.from}–${p.fars.to}`} <small>NHTSA FARS · all US</small></h2>
      <div className="stats">
        <div><strong>{fmt(totals.deaths)}</strong><span>people killed</span></div>
        <div><strong>{fmt(areaCrashes)}</strong><span>fatal crashes</span></div>
      </div>
    </> : <p className="note">
      Nationwide fatal-crash data (NHTSA FARS) is published about 1.5 years late, so it covers {FARS_FIRST}–{FARS_LAST} here.
      {p.range.kind === 'live' ? ' Live mode shows incident reports from the last 24 hours instead.' : ' For later years the map shows city crash reports and live incident feeds where they exist (outlined in blue).'}
    </p>}

    {p.loading && <p className="muted">Loading…</p>}

    {p.fars && sel.stateCode === undefined && <Ranked title="States with the most deaths" hint="Click a state on the map or below."
      rows={p.states.slice(0, 12).map(s => ({ key: String(s.state_code), label: s.name, value: s.deaths, onClick: () => p.onSelect({ stateCode: s.state_code, stateName: s.name }) }))} />}

    {p.fars && sel.stateCode !== undefined && !inArea && <>
      <Ranked title="Cities with the most deaths" hint="Crashes outside city limits are counted in their county only."
        rows={p.cities.slice(0, 10).map(c => ({ key: c.name, label: titleCase(c.name), value: c.deaths, onClick: () => p.onSelect({ ...sel, city: c.name }) }))} />
      <Ranked title="Counties with the most deaths"
        rows={p.counties.slice(0, 10).map(c => ({ key: c.fips, label: titleCase(c.name), value: c.deaths, onClick: () => p.onSelect({ ...sel, countyCode: c.county_code, countyName: c.name }) }))} />
    </>}

    {p.fars && p.summary && sel.stateCode !== undefined && <>
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


function TimeControls({ range, onRange }: { range: TimeRange; onRange: (r: TimeRange) => void }) {
  const years = range.kind === 'years' ? range : { from: FARS_FIRST, to: THIS_YEAR };
  const setYears = (from: number, to: number) => onRange({ kind: 'years', from: Math.min(from, to), to: Math.max(from, to) });
  return <div className="time">
    <label>From <select value={years.from} disabled={range.kind === 'live'} onChange={e => setYears(Number(e.target.value), years.to)}>
      {YEARS.map(y => <option key={y} value={y}>{y}</option>)}</select></label>
    <label>to <select value={years.to} disabled={range.kind === 'live'} onChange={e => setYears(years.from, Number(e.target.value))}>
      {YEARS.map(y => <option key={y} value={y}>{y}</option>)}</select></label>
    <button className={range.kind === 'live' ? 'live on' : 'live'} onClick={() => onRange(range.kind === 'live' ? { kind: 'years', from: FARS_FIRST, to: THIS_YEAR } : { kind: 'live' })}>
      <span className="dot" /> Last 24 hours
    </button>
  </div>;
}

function RecentSection({ recent, range, shownPoints, inArea, atUS, onSource }: { recent: RecentSource[]; range: TimeRange; shownPoints: number; inArea: boolean; atUS: boolean; onSource: (s: string) => void }) {
  if (!recent.length) return null;
  const live = range.kind === 'live';
  return <section className="recent">
    <h2>{live ? 'Reported in the last 24 hours' : 'Newer & local data'}</h2>
    {!atUS && <p className="muted">Counted inside the rectangle around this area, so it can include a little of its neighbours.</p>}
    <ul>
      {recent.map(r => {
        const last = r.last ? parseTime({ time: r.last, kind: r.kind }) : null;
        const body = <>
          <i style={{ background: r.kind === 'live' ? COLORS.live : COLORS.record }} />
          <div>
            <b>{r.label}</b>
            <span>{fmt(r.count)} {r.kind === 'live' ? (live ? 'incidents' : 'crashes reported (live feed)') : 'police crash reports'}
              {r.kind === 'record' && r.killed ? ` · ${fmt(r.killed)} killed` : ''}{r.kind === 'record' && r.injured ? ` · ${fmt(r.injured)} injured` : ''}</span>
            {last && <span className="muted">latest {r.kind === 'live' ? ago(last) : last.toLocaleDateString(undefined, { dateStyle: 'medium' })}</span>}
          </div>
        </>;
        return <li key={r.source}>{atUS ? <button onClick={() => onSource(r.source)} title="Zoom to this area">{body}</button> : <div className="row">{body}</div>}</li>;
      })}
    </ul>
    {(inArea || live) && shownPoints > 0 && <p className="muted">Showing the newest {fmt(shownPoints)} with a location on the map.</p>}
    {!inArea && !live && !atUS && !shownPoints && <p className="muted">Open a county or city to see these as dots.</p>}
    <p className="muted">Crash reports are filed police reports with injury counts. Live incidents are first reports from dispatch and traffic systems: minutes old but unverified.</p>
  </section>;
}
