// Static mode (GitHub Pages): the same functions as `api`, computed in the browser from the JSON
// files `python -m pipeline export` writes. File format and semantics: docs/STATIC_SITE.md.
// Type-only import, so api.ts can import this module without a runtime cycle.
import type { BBox, CityRow, CountyRow, Coverage, CrashPoint, FlagDef, RecentPoint, RecentSource, RoadRow, Selection, StateRow, Summary, TimeRange } from './api';

export type Meta = {
  generated_at: string; fars_years: number[]; recent_years: number[]; dot_days: number; dots_since: string;
  grid_deg: number; tile_deg: number; tile_cap: number; tiles: string[];
};
type Years = { from: number; to: number };
type StateYear = [state_code: number, name: string, year: number, crashes: number, deaths: number];
type FarsRow = [id: string, year: number, county_code: number | null, lat: number | null, lon: number | null, date: string | null, hour: number | null,
  deaths: number | null, road_name: string | null, road_route: string | null, city_name: string | null, light_condition: string | null,
  weather: string | null, first_harmful_event: string | null, flags: string[], speeding: number, drinking: number, non_motorist: number];
type FarsState = { counties: Record<string, string>; crashes: FarsRow[] };
type Total = [source: string, year: number, count: number, killed: number | null, injured: number | null, first: string | null, last: string | null];
type Grid = { sources: string[]; cells: [source: number, x: number, y: number, count: number, killed: number | null, injured: number | null][] };
type TileRow = [source: string, id: string | number, time: string, lat: number, lon: number, killed: number | null, injured: number | null,
  road: string | null, category: string, type: string | null];
type Live = { summary: RecentSource[]; points: RecentPoint[] };

export type Load = <T>(path: string) => Promise<T>;

const POINTS_PER_KIND = 3000;  // the API's per-table limit for /api/recent/points
const CRASH_LIMIT = 10000;     // what the app asks /api/map/crashes for
const cmp = (a: string | null, b: string | null) => (a === b ? 0 : a === null ? -1 : b === null ? 1 : a < b ? -1 : 1);
const inBox = (lon: number, lat: number, [w, s, e, n]: BBox) => lon >= w && lon <= e && lat >= s && lat <= n;
const addNullable = (a: number | null, b: number | null) => (b === null ? a : (a ?? 0) + b);

/** Newest first, at most POINTS_PER_KIND of each kind (record / live), like the API. */
function newestPerKind(points: RecentPoint[]): RecentPoint[] {
  const seen = { record: 0, live: 0 };
  return [...points].sort((a, b) => cmp(b.time, a.time)).filter(p => ++seen[p.kind] <= POINTS_PER_KIND);
}

export function createStaticApi(load: Load) {
  const meta = () => load<Meta>('meta.json');
  const coverage = () => load<Coverage[]>('coverage.json');
  const kindOf = (cov: Coverage[]) => {
    const bySource = new Map(cov.map(c => [c.source, c]));
    return (source: string, fallback: 'record' | 'live' = 'record') => ({ kind: bySource.get(source)?.kind ?? fallback, label: bySource.get(source)?.label ?? source });
  };

  /** The state's FARS crashes, filtered like map_queries.Area (county, city, years). */
  async function farsRows(sel: Selection, years: Years) {
    if (sel.stateCode === undefined) throw new Error('This view needs a state in static mode');
    const file = await load<FarsState>(`fars/${String(sel.stateCode).padStart(2, '0')}.json`);
    const rows = file.crashes.filter(r => r[1] >= years.from && r[1] <= years.to
      && (sel.countyCode === undefined || r[2] === sel.countyCode) && (!sel.city || r[10] === sel.city));
    return { file, rows };
  }

  async function states(years: Years): Promise<StateRow[]> {
    const out = new Map<number, StateRow>();
    for (const [code, name, year, crashes, deaths] of await load<StateYear[]>('fars/states.json')) {
      if (year < years.from || year > years.to) continue;
      const row = out.get(code) ?? { state_code: code, name, crashes: 0, deaths: 0 };
      out.set(code, { ...row, name: cmp(name, row.name) > 0 ? name : row.name, crashes: row.crashes + crashes, deaths: row.deaths + deaths });
    }
    return [...out.values()].sort((a, b) => b.deaths - a.deaths);
  }

  async function counties(sel: Selection, years: Years): Promise<CountyRow[]> {
    const { file, rows } = await farsRows({ stateCode: sel.stateCode }, years);
    const out = new Map<number, CountyRow>();
    for (const r of rows) {
      if (r[2] === null) continue;
      const row = out.get(r[2]) ?? { county_code: r[2], fips: String(sel.stateCode).padStart(2, '0') + String(r[2]).padStart(3, '0'), name: file.counties[String(r[2])] ?? '', crashes: 0, deaths: 0 };
      row.crashes++; row.deaths += r[7] ?? 0;
      out.set(r[2], row);
    }
    return [...out.values()].sort((a, b) => b.deaths - a.deaths);
  }

  async function cities(sel: Selection, years: Years): Promise<CityRow[]> {
    const { rows } = await farsRows({ stateCode: sel.stateCode, countyCode: sel.countyCode }, years);
    const out = new Map<string, CityRow & { lat: number[]; lon: number[] }>();
    for (const r of rows) {
      if (r[10] === null) continue;
      const row = out.get(r[10]) ?? { name: r[10], county_code: -1, crashes: 0, deaths: 0, latitude: null, longitude: null, lat: [], lon: [] };
      row.county_code = Math.max(row.county_code, r[2] ?? -1); row.crashes++; row.deaths += r[7] ?? 0;
      if (r[3] !== null) row.lat.push(r[3]);  // SQL avg skips nulls, column by column
      if (r[4] !== null) row.lon.push(r[4]);
      out.set(r[10], row);
    }
    const avg = (v: number[]) => (v.length ? v.reduce((a, b) => a + b, 0) / v.length : null);
    return [...out.values()].sort((a, b) => b.deaths - a.deaths || b.crashes - a.crashes).slice(0, 25)
      .map(({ lat, lon, ...row }) => ({ ...row, latitude: avg(lat), longitude: avg(lon) }));
  }

  async function summary(sel: Selection, years: Years): Promise<Summary> {
    const { rows } = await farsRows(sel, years);
    const roads = new Map<string, RoadRow & { names: Map<string | null, number> }>();
    const flags = new Map<string, number>();
    const hours = Array.from({ length: 24 }, (_, hour) => ({ hour, crashes: 0 }));
    let deaths = 0;
    for (const r of rows) {
      deaths += r[7] ?? 0;
      r[14].forEach(f => flags.set(f, (flags.get(f) ?? 0) + 1));
      if (r[6] !== null && hours[r[6]]) hours[r[6]].crashes++;
      if (r[9] === null) continue;
      const road = roads.get(r[9]) ?? { road_route: r[9], name: r[9], crashes: 0, deaths: 0, speeding_crashes: 0, drinking_crashes: 0, non_motorist_crashes: 0, names: new Map() };
      road.crashes++; road.deaths += r[7] ?? 0;
      road.speeding_crashes += r[15]; road.drinking_crashes += r[16]; road.non_motorist_crashes += r[17];
      road.names.set(r[8], (road.names.get(r[8]) ?? 0) + 1);
      roads.set(r[9], road);
    }
    const top = [...roads.values()].sort((a, b) => b.deaths - a.deaths || b.crashes - a.crashes || cmp(a.road_route, b.road_route)).slice(0, 10);
    return {
      roads: top.map(({ names, ...road }) => {
        // Most common spelling; ties go to the greater name (map_queries compares (count, name)).
        const [name] = [...names].reduce((best, cur) => (cur[1] > best[1] || (cur[1] === best[1] && cmp(cur[0], best[0]) > 0) ? cur : best));
        return { ...road, name: name ?? road.road_route };
      }),
      factors: { total_crashes: rows.length, total_deaths: deaths, flags: [...flags].sort((a, b) => b[1] - a[1] || cmp(a[0], b[0])).map(([flag_id, crashes]) => ({ flag_id, crashes })) },
      hours,
    };
  }

  async function crashes(sel: Selection, years: Years): Promise<CrashPoint[]> {
    const { rows } = await farsRows(sel, years);
    return rows.filter(r => r[3] !== null && r[4] !== null)
      .sort((a, b) => (a[5] === b[5] ? 0 : a[5] === null ? 1 : b[5] === null ? -1 : cmp(b[5], a[5])) || cmp(a[0], b[0]))
      .slice(0, CRASH_LIMIT)
      .map(r => ({ id: r[0], latitude: r[3]!, longitude: r[4]!, date: r[5], hour: r[6], deaths: r[7] ?? 0, road_name: r[8], road_route: r[9], city_name: r[10],
        light_condition: r[11], weather: r[12], first_harmful_event: r[13], flags: r[14] }));
  }

  async function recentSummary(range: TimeRange, bbox?: BBox): Promise<RecentSource[]> {
    if (range.kind === 'live') {
      const live = await load<Live>('live/last24h.json');
      if (!bbox) return live.summary;
      const out = new Map<string, RecentSource>();
      const known = new Map(live.summary.map(s => [s.source, { kind: s.kind, label: s.label }]));
      const info = kindOf(await coverage());
      for (const p of live.points) {
        if (!inBox(p.lon, p.lat, bbox)) continue;
        const row = out.get(p.source) ?? { source: p.source, ...(known.get(p.source) ?? info(p.source, p.kind)), count: 0, killed: null, injured: null, first: null, last: null, with_coordinates: 0 };
        out.set(p.source, { ...row, count: row.count + 1, with_coordinates: row.with_coordinates + 1, killed: addNullable(row.killed, p.killed), injured: addNullable(row.injured, p.injured),
          first: row.first === null || p.time < row.first ? p.time : row.first, last: row.last === null || p.time > row.last ? p.time : row.last });
      }
      return [...out.values()].sort((a, b) => b.count - a.count);
    }
    const [m, totals, info] = await Promise.all([meta(), load<Total[]>('recent/totals.json'), coverage().then(kindOf)]);
    const years = m.recent_years.filter(y => y >= range.from && y <= range.to);
    const grids = await Promise.all(years.map(y => load<Grid>(`recent/grid-${y}.json`)));
    const out = new Map<string, RecentSource>();
    const reports = new Map<string, { killed: boolean; injured: boolean }>();
    for (const [source, year, count, killed, injured, first, last] of totals) {
      if (year < range.from || year > range.to) continue;
      const row = out.get(source) ?? { source, ...info(source), count: 0, killed: null, injured: null, first: null, last: null, with_coordinates: 0 };
      const rep = reports.get(source) ?? { killed: false, injured: false };
      reports.set(source, { killed: rep.killed || killed !== null, injured: rep.injured || injured !== null });
      out.set(source, { ...row, first: first !== null && (row.first === null || first < row.first) ? first : row.first, last: last !== null && (row.last === null || last > row.last) ? last : row.last,
        // The US view counts every row from totals; an area counts its grid cells below.
        ...(bbox ? {} : { count: row.count + count, killed: addNullable(row.killed, killed), injured: addNullable(row.injured, injured) }) });
    }
    const g = m.grid_deg, box = bbox && [Math.floor(bbox[0] / g), Math.floor(bbox[1] / g), Math.floor(bbox[2] / g), Math.floor(bbox[3] / g)];
    const cells = new Map<string, { count: number; killed: number; injured: number }>();
    for (const grid of grids) for (const [i, x, y, count, killed, injured] of grid.cells) {
      if (box && (x < box[0] || x > box[2] || y < box[1] || y > box[3])) continue;
      const c = cells.get(grid.sources[i]) ?? { count: 0, killed: 0, injured: 0 };
      cells.set(grid.sources[i], { count: c.count + count, killed: c.killed + (killed ?? 0), injured: c.injured + (injured ?? 0) });
    }
    for (const [source, row] of out) {
      const c = cells.get(source) ?? { count: 0, killed: 0, injured: 0 }, rep = reports.get(source)!;
      out.set(source, bbox
        ? { ...row, count: c.count, killed: rep.killed ? c.killed : null, injured: rep.injured ? c.injured : null, with_coordinates: c.count }
        : { ...row, with_coordinates: c.count });
    }
    return [...out.values()].filter(r => r.count > 0).sort((a, b) => b.count - a.count);
  }

  async function recentPoints(range: TimeRange, bbox: BBox): Promise<RecentPoint[]> {
    if (range.kind === 'live') return newestPerKind((await load<Live>('live/last24h.json')).points.filter(p => inBox(p.lon, p.lat, bbox)));
    const [m, info] = await Promise.all([meta(), coverage().then(kindOf)]);
    const start = `${range.from}-01-01`, end = `${range.to + 1}-01-01`;
    if (end <= m.dots_since.slice(0, 10)) return [];  // no dots kept before dots_since
    const t = m.tile_deg, [x0, y0, x1, y1] = [bbox[0] / t, bbox[1] / t, bbox[2] / t, bbox[3] / t].map(Math.floor);
    const keys = m.tiles.filter(k => { const [x, y] = k.split('_').map(Number); return x >= x0 && x <= x1 && y >= y0 && y <= y1; });
    const tiles = await Promise.all(keys.map(k => load<TileRow[]>(`recent/tiles/${k}.json`)));
    const out: RecentPoint[] = [];
    for (const tile of tiles) for (const [source, id, time, lat, lon, killed, injured, road, category, type] of tile) {
      if (time >= start && time < end && inBox(lon, lat, bbox)) out.push({ source, kind: info(source).kind, id: String(id), time, lat, lon, killed, injured, road, category, type });
    }
    return newestPerKind(out);
  }

  return {
    flags: () => load<FlagDef[]>('flags.json'),
    states, counties, cities, summary, crashes, coverage, recentSummary, recentPoints, meta,
  };
}

// One fetch per file per page load; a failed fetch is forgotten so a later call can retry.
const cache = new Map<string, Promise<unknown>>();
function fetchJson<T>(path: string): Promise<T> {
  if (!cache.has(path)) {
    const request = fetch(`${import.meta.env.BASE_URL}data/${path}`).then(r => {
      if (!r.ok) throw new Error(`Could not load ${path} (${r.status})`);
      return r.json();
    });
    request.catch(() => cache.delete(path));
    cache.set(path, request);
  }
  return cache.get(path) as Promise<T>;
}

export const staticApi = createStaticApi(fetchJson);
export const meta = staticApi.meta;
