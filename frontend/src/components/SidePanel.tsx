import { useState } from 'react';
import { Bar, BarChart, ResponsiveContainer, Tooltip, XAxis } from 'recharts';
import type { CityRow, Coverage, CountyRow, FlagDef, RecentSource, Selection, StateRow, Summary, TimeRange } from '../api';
import { FARS_FIRST, FARS_LAST, FIRST_YEAR, THIS_YEAR, ago, farsYears, fmt, parseTime } from '../api';
import type { Meta } from '../static';
import { COLORS, titleCase } from './CrashMap';

const YEARS = Array.from({ length: THIS_YEAR - FIRST_YEAR + 1 }, (_, i) => THIS_YEAR - i);

type Props = {
  selection: Selection;
  range: TimeRange;
  fars: { from: number; to: number } | null;
  recent: RecentSource[];
  recentPoints: number;
  dataMeta: Meta | null;  // set in static mode only
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
    {sel.stateCode !== undefined && <nav className="crumbs">
      <button onClick={() => p.onSelect({})} disabled={sel.stateCode === undefined}>United States</button>
      {sel.stateName && <><span>›</span><button onClick={() => p.onSelect({ stateCode: sel.stateCode, stateName: sel.stateName })} disabled={!inArea}>{sel.stateName}</button></>}
      {inArea && <><span>›</span><b>{place}</b></>}
    </nav>}

    <div className="head">
      <h1>{place}</h1>
    </div>
    {p.dataMeta && <p className="muted">Data as of {when(p.dataMeta.generated_at)}</p>}

    <TimeControls range={p.range} onRange={p.onRange} />

    {p.fars ? <>
      <h2 className="block-title">Fatal crashes, {p.fars.from === p.fars.to ? p.fars.from : `${p.fars.from}–${p.fars.to}`} <small>NHTSA FARS · all US</small></h2>
      <div className="stats">
        <div><strong>{fmt(totals.deaths)}</strong><span>people killed</span></div>
        <div><strong>{fmt(areaCrashes)}</strong><span>fatal crashes</span></div>
      </div>
    </> : null}

    <RecentSection key={place} recent={p.recent} range={p.range} shownPoints={p.recentPoints} dataMeta={p.dataMeta} inArea={inArea} atUS={sel.stateCode === undefined} onSource={p.onSource} />

    {p.loading &&<p className="muted">Loading…</p>}

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
const when = (iso: string) => new Date(iso).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' });
const sum = (rows: { crashes: number; deaths: number }[]) => rows.reduce((t, r) => ({ crashes: t.crashes + r.crashes, deaths: t.deaths + r.deaths }), { crashes: 0, deaths: 0 });


type Preset = { label: string; range: TimeRange };

const PRESETS: Preset[] = [
  { label: 'Last 24 hours', range: { kind: 'live' } },
  { label: `${THIS_YEAR} so far`, range: { kind: 'years', from: THIS_YEAR, to: THIS_YEAR } },
  { label: String(THIS_YEAR - 1), range: { kind: 'years', from: THIS_YEAR - 1, to: THIS_YEAR - 1 } },
  { label: `Since ${FARS_FIRST}`, range: { kind: 'years', from: FARS_FIRST, to: THIS_YEAR } },
];

const sameRange = (a: TimeRange, b: TimeRange) =>
  a.kind === b.kind && (a.kind === 'live' || (b.kind === 'years' && a.from === b.from && a.to === b.to));

const span = (from: number, to: number) => (from === to ? String(from) : `${from}–${to}`);

/** Presets for the common questions, Custom for anything else, and a small timeline that shows
 *  which kind of data each year has, so picking 2026 and losing the death totals is no surprise. */
function TimeControls({ range, onRange }: { range: TimeRange; onRange: (r: TimeRange) => void }) {
  const preset = PRESETS.find(pr => sameRange(pr.range, range));
  const [custom, setCustom] = useState(!preset);
  const years = range.kind === 'years' ? range : { from: FARS_FIRST, to: THIS_YEAR };
  const setYears = (from: number, to: number) => onRange({ kind: 'years', from: Math.min(from, to), to: Math.max(from, to) });
  const fars = farsYears(range);

  // Timeline geometry: one slot per year from FIRST_YEAR to THIS_YEAR.
  const count = THIS_YEAR - FIRST_YEAR + 1;
  const pos = (year: number) => `${(100 * (year - FIRST_YEAR)) / count}%`;
  const width = (from: number, to: number) => `${(100 * (to - from + 1)) / count}%`;

  let status: string;
  if (range.kind === 'live') status = 'Live incident reports and police reports from the last 24 hours. Death totals are not available this recent.';
  else if (!fars) status = `Deaths: none yet for ${span(range.from, range.to)} (nationwide data ends ${FARS_LAST}). Showing local police reports only.`;
  else if (fars.from === range.from && fars.to === range.to) status = `Deaths for ${span(fars.from, fars.to)}, plus local police reports where they exist.`;
  else status = `Deaths for ${span(fars.from, fars.to)} (the newest nationwide data), plus local police reports for ${span(range.from, range.to)} where they exist.`;

  return <div className="time">
    <div className="presets" role="group" aria-label="Time range">
      {PRESETS.map(pr => <button key={pr.label} className={!custom && preset === pr ? 'on' : ''}
        onClick={() => { setCustom(false); onRange(pr.range); }}>
        {pr.range.kind === 'live' && <span className="dot" />}{pr.label}
      </button>)}
      <button className={custom ? 'on' : ''} onClick={() => { setCustom(true); if (range.kind === 'live') onRange({ kind: 'years', ...years }); }}>Custom</button>
    </div>

    {custom && <div className="custom">
      <label>From <select value={years.from} onChange={e => setYears(Number(e.target.value), years.to)}>
        {YEARS.map(y => <option key={y} value={y}>{y}</option>)}</select></label>
      <label>to <select value={years.to} onChange={e => setYears(years.from, Number(e.target.value))}>
        {YEARS.map(y => <option key={y} value={y}>{y}</option>)}</select></label>
    </div>}

    {range.kind === 'years' && <div className="timeline" aria-hidden>
      <div className="track">
        <span className="label">Deaths, all US</span>
        <div className="lane"><i className="fars" style={{ left: pos(FARS_FIRST), width: width(FARS_FIRST, FARS_LAST) }} />
          <b className="sel" style={{ left: pos(range.from), width: width(range.from, range.to) }} /></div>
      </div>
      <div className="track">
        <span className="label">Police reports, local</span>
        <div className="lane"><i className="local" style={{ left: pos(FIRST_YEAR), width: width(FIRST_YEAR, THIS_YEAR) }} />
          <b className="sel" style={{ left: pos(range.from), width: width(range.from, range.to) }} /></div>
      </div>
      <div className="ticks">
        {[FIRST_YEAR, FARS_FIRST, THIS_YEAR].map(y => <span key={y} style={{ left: `calc(${pos(y)} + ${50 / count}%)` }}>{y}</span>)}
      </div>
    </div>}

    <p className="status">{status}</p>
  </div>;
}

const SHOWN_SOURCES = 4;

function RecentSection({ recent, range, shownPoints, dataMeta, inArea, atUS, onSource }: { recent: RecentSource[]; range: TimeRange; shownPoints: number; dataMeta: Meta | null; inArea: boolean; atUS: boolean; onSource: (s: string) => void }) {
  const [showAll, setShowAll] = useState(false);
  if (!recent.length) return null;
  // Nationally there are ~50 sources; listing them all buried everything below.
  const collapsible = recent.length > SHOWN_SOURCES + 1;
  const rows = collapsible && !showAll ? recent.slice(0, SHOWN_SOURCES) : recent;
  const live = range.kind === 'live';
  // Static exports keep dots only for the last dot_days; counts still cover every year.
  const dotsCut = dataMeta && range.kind === 'years' && `${range.from}-01-01` < dataMeta.dots_since && (inArea || shownPoints > 0);
  return <section className="recent">
    <h2>{live ? 'Reported in the last 24 hours' : 'Newer & local data'}</h2>
    {dataMeta && live && <p className="muted">Last 24 hours before {when(dataMeta.generated_at)}.</p>}
    {!atUS && <p className="muted">Counted inside the rectangle around this area, so it can include a little of its neighbours.</p>}
    <ul>
      {rows.map(r => {
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
    {collapsible && <button className="more" onClick={() => setShowAll(!showAll)}>
      {showAll ? 'Show fewer' : `Show all ${recent.length} sources`}</button>}
    {(inArea || live) && shownPoints > 0 && <p className="muted">Showing the newest {fmt(shownPoints)} with a location on the map.</p>}
    {!inArea && !live && !atUS && !shownPoints && <p className="muted">Open a county or city to see these as dots.</p>}
    {dotsCut && <p className="muted">Dots: {dataMeta.dot_days === 365 ? 'last 12 months' : `last ${dataMeta.dot_days} days`} only; counts cover the whole range.</p>}
    <p className="muted">Crash reports are filed police reports with injury counts. Live incidents are first reports from dispatch and traffic systems: minutes old but unverified.</p>
  </section>;
}
