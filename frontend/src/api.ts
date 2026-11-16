export const API = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';

export type Selection = { stateCode?: number; stateName?: string; countyCode?: number; countyName?: string; city?: string; year?: number };

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

function query(sel: Selection, extra: Record<string, string | number | undefined> = {}) {
  const params = new URLSearchParams();
  const add = (k: string, v: string | number | undefined) => { if (v !== undefined && v !== '') params.set(k, String(v)); };
  add('state_code', sel.stateCode);
  add('county_code', sel.countyCode);
  add('city', sel.city);
  add('year_from', sel.year);
  add('year_to', sel.year);
  Object.entries(extra).forEach(([k, v]) => add(k, v));
  return params.toString();
}

async function get<T>(path: string): Promise<T> {
  const response = await fetch(`${API}${path}`);
  if (!response.ok) throw new Error(`Request failed (${response.status})`);
  return response.json();
}

export const api = {
  flags: () => get<FlagDef[]>('/api/risk-flags?counts=false'),
  states: (sel: Selection) => get<StateRow[]>(`/api/map/states?${query({ year: sel.year })}`),
  counties: (sel: Selection) => get<CountyRow[]>(`/api/map/counties?${query({ stateCode: sel.stateCode, year: sel.year })}`),
  cities: (sel: Selection) => get<CityRow[]>(`/api/map/cities?${query({ stateCode: sel.stateCode, countyCode: sel.countyCode, year: sel.year }, { limit: 25 })}`),
  summary: (sel: Selection) => get<Summary>(`/api/map/summary?${query(sel, { road_limit: 10 })}`),
  crashes: (sel: Selection) => get<CrashPoint[]>(`/api/map/crashes?${query(sel, { limit: 10000 })}`),
};

export const fmt = (n: number) => n.toLocaleString();
