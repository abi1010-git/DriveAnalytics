import { staticApi } from './static';

export const API = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';
// Built for GitHub Pages: read exported JSON files instead of calling the API (see static.ts).
export const STATIC = import.meta.env.VITE_STATIC === '1';

// Where on the map we are. Time is separate (TimeRange) so changing one never resets the other.
export type Selection = { stateCode?: number; stateName?: string; countyCode?: number; countyName?: string; city?: string };

// FARS (fatal crashes) is published ~1.5 years late; this project loads these years.
export const FARS_FIRST = 2020;
export const FARS_LAST = 2024;
export const FIRST_YEAR = 2012;  // NYC records start July 2012
export const THIS_YEAR = new Date().getFullYear();

export type TimeRange = { kind: 'years'; from: number; to: number } | { kind: 'live' };

/** The part of the range FARS covers, or null when it covers none of it. */
export function farsYears(range: TimeRange): { from: number; to: number } | null {
  if (range.kind === 'live') return null;
  const from = Math.max(range.from, FARS_FIRST), to = Math.min(range.to, FARS_LAST);
  return from <= to ? { from, to } : null;
}

export function rangeWindow(range: TimeRange): { start: string; end?: string } {
  if (range.kind === 'live') return { start: new Date(Date.now() - 24 * 3600 * 1000).toISOString() };
  return { start: `${range.from}-01-01`, end: `${range.to + 1}-01-01` };
}

export type BBox = [number, number, number, number];  // min_lon, min_lat, max_lon, max_lat

export type StateRow = { state_code: number; name: string; crashes: number; deaths: number };
export type CountyRow = { county_code: number; fips: string; name: string; crashes: number; deaths: number };
export type CityRow = { name: string; county_code: number; crashes: number; deaths: number; latitude: number | null; longitude: number | null };
export type RoadRow = { road_route: string; name: string; crashes: number; deaths: number; speeding_crashes: number; drinking_crashes: number; non_motorist_crashes: number };
export type Summary = { roads: RoadRow[]; factors: { total_crashes: number; total_deaths: number; flags: { flag_id: string; crashes: number }[] }; hours: { hour: number; crashes: number }[] };
export type CrashPoint = {
  id: string; latitude: number; longitude: number; date: string | null; hour: number | null; deaths: number;
  road_name: string | null; road_route: string | null; city_name: string | null; light_condition: string | null; weather: string | null;
  first_harmful_event: string | null; flags: string[];
};
export type FlagDef = { id: string; name: string; description: string; source: 'fars' | 'nyc'; category: string };

function query(sel: Selection & { years?: { from: number; to: number } | null }, extra: Record<string, string | number | undefined> = {}) {
  const params = new URLSearchParams();
  const add = (k: string, v: string | number | undefined) => { if (v !== undefined && v !== '') params.set(k, String(v)); };
  add('state_code', sel.stateCode);
  add('county_code', sel.countyCode);
  add('city', sel.city);
  add('year_from', sel.years?.from);
  add('year_to', sel.years?.to);
  Object.entries(extra).forEach(([k, v]) => add(k, v));
  return params.toString();
}

async function get<T>(path: string): Promise<T> {
  const response = await fetch(`${API}${path}`);
  if (!response.ok) throw new Error(`Request failed (${response.status})`);
  return response.json();
}

type Years = { from: number; to: number };

export type RecentSource = { source: string; kind: 'record' | 'live'; label: string; count: number; killed: number | null; injured: number | null; first: string | null; last: string | null; with_coordinates: number };
export type RecentPoint = { source: string; kind: 'record' | 'live'; id: string; time: string; lat: number; lon: number; killed: number | null; injured: number | null; road: string | null; category: string; type: string | null };
export type Coverage = { source: string; kind: 'record' | 'live'; label: string; states: number[]; bbox: BBox };

function recentQuery(range: TimeRange, bbox?: BBox, extra: Record<string, string | number> = {}) {
  const w = rangeWindow(range);
  const params = new URLSearchParams({ start: w.start, ...(w.end ? { end: w.end } : {}), ...Object.fromEntries(Object.entries(extra).map(([k, v]) => [k, String(v)])) });
  if (bbox) params.set('bbox', bbox.map(v => v.toFixed(5)).join(','));
  return params.toString();
}

const httpApi = {
  flags: () => get<FlagDef[]>('/api/risk-flags?counts=false'),
  states: (years: Years) => get<StateRow[]>(`/api/map/states?${query({ years })}`),
  counties: (sel: Selection, years: Years) => get<CountyRow[]>(`/api/map/counties?${query({ stateCode: sel.stateCode, years })}`),
  cities: (sel: Selection, years: Years) => get<CityRow[]>(`/api/map/cities?${query({ stateCode: sel.stateCode, countyCode: sel.countyCode, years }, { limit: 25 })}`),
  summary: (sel: Selection, years: Years) => get<Summary>(`/api/map/summary?${query({ ...sel, years }, { road_limit: 10 })}`),
  crashes: (sel: Selection, years: Years) => get<CrashPoint[]>(`/api/map/crashes?${query({ ...sel, years }, { limit: 10000 })}`),
  coverage: () => get<Coverage[]>('/api/recent/coverage'),
  recentSummary: (range: TimeRange, bbox?: BBox) => get<RecentSource[]>(`/api/recent/summary?${recentQuery(range, bbox, range.kind === 'live' ? { all_incidents: 'true' } : {})}`),
  recentPoints: (range: TimeRange, bbox: BBox) => get<RecentPoint[]>(`/api/recent/points?${recentQuery(range, bbox, { limit: 3000, ...(range.kind === 'live' ? { all_incidents: 'true' } : {}) })}`),
};

export const api: typeof httpApi = STATIC ? staticApi : httpApi;

/** Live feeds store UTC; city crash reports store the city's local time. */
export function parseTime(point: { time: string; kind: 'record' | 'live' }): Date {
  return new Date(point.kind === 'live' && !/[zZ+]/.test(point.time.slice(19)) ? point.time + 'Z' : point.time);
}

export function ago(date: Date): string {
  const minutes = Math.round((Date.now() - date.getTime()) / 60000);
  if (minutes < 1) return 'just now';
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 48) return `${hours} h ago`;
  return `${Math.round(hours / 24)} days ago`;
}

export const fmt = (n: number) => n.toLocaleString();
