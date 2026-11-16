// Static-mode aggregations against a hand-written export. Run: npm test (Node's own test runner).
import assert from 'node:assert/strict';
import { test } from 'node:test';
import { createStaticApi } from '../src/static.ts';
import { LA, fixture } from './fixture.ts';

const loads: string[] = [];
const api = createStaticApi(async <T,>(path: string) => {
  loads.push(path);
  if (!(path in fixture)) throw new Error(`missing ${path}`);
  return structuredClone(fixture[path]) as T;
});
const CA = { stateCode: 6 };
const years = { from: 2023, to: 2024 };

test('states: sums the years in range, sorted by deaths', async () => {
  assert.deepEqual(await api.states({ from: 2020, to: 2024 }), [
    { state_code: 48, name: 'Texas', crashes: 20, deaths: 22 },
    { state_code: 6, name: 'California', crashes: 16, deaths: 19 },  // max(name), as in SQL
  ]);
  assert.deepEqual((await api.states({ from: 2024, to: 2024 })).map(s => s.crashes), [20, 5]);
});

test('counties: skips crashes with no county and builds the FIPS', async () => {
  assert.deepEqual(await api.counties(CA, years), [
    { county_code: 37, fips: '06037', name: 'Los Angeles', crashes: 5, deaths: 5 },
    { county_code: 73, fips: '06073', name: 'San Diego', crashes: 1, deaths: 3 },
  ]);
});

test('cities: averages located crashes only', async () => {
  const rows = await api.cities(CA, years);
  assert.deepEqual(rows.map(c => [c.name, c.county_code, c.crashes, c.deaths]), [['LOS ANGELES', 37, 3, 4], ['SAN DIEGO', 73, 1, 3], ['PASADENA', 37, 2, 1]]);
  assert.ok(Math.abs(rows[0].latitude! - 34.055) < 1e-9);
  assert.deepEqual((await api.cities({ stateCode: 6, countyCode: 73 }, years)).map(c => c.name), ['SAN DIEGO']);
});

test('summary: roads, flags and hours', async () => {
  const s = await api.summary(CA, years);
  assert.deepEqual(s.roads, [
    { road_route: 'I-5', name: 'I-5', crashes: 3, deaths: 4, speeding_crashes: 2, drinking_crashes: 1, non_motorist_crashes: 1 },
    { road_route: 'SR-163', name: 'SR-163', crashes: 1, deaths: 3, speeding_crashes: 0, drinking_crashes: 1, non_motorist_crashes: 0 },
    { road_route: 'MAIN ST', name: 'Main St', crashes: 2, deaths: 1, speeding_crashes: 0, drinking_crashes: 0, non_motorist_crashes: 0 },  // tie: greater name
  ]);
  assert.deepEqual(s.factors, { total_crashes: 6, total_deaths: 8, flags: [{ flag_id: 'speed', crashes: 2 }, { flag_id: 'dui', crashes: 1 }, { flag_id: 'ped', crashes: 1 }] });
  assert.equal(s.hours.length, 24);
  assert.deepEqual(s.hours.filter(h => h.crashes).map(h => [h.hour, h.crashes]), [[8, 2], [12, 2], [23, 1]]);
  assert.equal((await api.summary({ stateCode: 6, city: 'PASADENA' }, years)).factors.total_crashes, 2);
  assert.equal((await api.summary(CA, { from: 2020, to: 2022 })).factors.total_crashes, 1);
});

test('crashes: located only, newest first, then by id', async () => {
  const rows = await api.crashes({ stateCode: 6, countyCode: 37 }, years);
  assert.deepEqual(rows.map(c => c.id), ['A2', 'A6', 'A7', 'A1']);
  assert.deepEqual(rows[3].flags, ['speed', 'ped']);
});

test('recent summary, US view: totals, with located count from the grid', async () => {
  assert.deepEqual(await api.recentSummary({ kind: 'years', from: 2025, to: 2026 }), [
    { source: 'chp', kind: 'live', label: 'California Highway Patrol incidents', count: 150, killed: null, injured: null, first: '2025-01-01T00:00:00', last: '2026-11-16T19:00:00', with_coordinates: 110 },
    { source: 'lacity', kind: 'record', label: 'Los Angeles crash reports', count: 50, killed: 2, injured: 35, first: '2025-01-02T10:00:00', last: '2026-10-01T10:00:00', with_coordinates: 43 },
  ]);
  assert.deepEqual(await api.recentSummary({ kind: 'years', from: 2020, to: 2024 }), []);
});

test('recent summary, area: grid cells in the box; first/last stay source-wide', async () => {
  const rows = await api.recentSummary({ kind: 'years', from: 2025, to: 2026 }, LA);
  assert.deepEqual(rows.map(r => [r.source, r.count, r.killed, r.injured, r.with_coordinates, r.first]), [
    ['chp', 80, null, null, 80, '2025-01-01T00:00:00'], ['lacity', 43, 2, 29, 43, '2025-01-02T10:00:00']]);
  assert.deepEqual(await api.recentSummary({ kind: 'years', from: 2026, to: 2026 }, [-80, 30, -79, 31]), []);
});

test('recent points: tiles overlapping the box, filtered to box and years', async () => {
  const rows = await api.recentPoints({ kind: 'years', from: 2025, to: 2026 }, LA);
  assert.deepEqual(rows.map(p => [p.id, p.kind]), [['r1', 'record'], ['c1', 'live'], ['2', 'record']]);
  assert.deepEqual((await api.recentPoints({ kind: 'years', from: 2026, to: 2026 }, LA)).map(p => p.id), ['r1', 'c1']);
  loads.length = 0;
  assert.deepEqual(await api.recentPoints({ kind: 'years', from: 2020, to: 2024 }, LA), []);
  assert.ok(!loads.some(p => p.startsWith('recent/tiles')), 'no tiles loaded for years before dots_since');
});

test('live: summary as is for the US, recomputed from points for a box', async () => {
  const live = { kind: 'live' } as const;
  assert.equal((await api.recentSummary(live))[0].count, 3);
  assert.deepEqual(await api.recentSummary(live, LA), [
    { source: 'chp', kind: 'live', label: 'California Highway Patrol incidents', count: 1, killed: null, injured: null, first: '2026-11-16T10:00:00', last: '2026-11-16T10:00:00', with_coordinates: 1 }]);
  assert.deepEqual((await api.recentPoints(live, LA)).map(p => p.id), ['L1']);
  assert.deepEqual((await api.recentPoints(live, [-125, 30, -110, 42])).map(p => p.id), ['L2', 'L1']);
});

test('points are capped at 3000 per kind, newest first', async () => {
  const point = (i: number, kind: 'record' | 'live') => ({ source: kind === 'live' ? 'chp' : 'lacity', kind, id: `${kind}${i}`, time: `2026-11-16T${String(i % 24).padStart(2, '0')}:00:${String(i % 60).padStart(2, '0')}`,
    lat: 34, lon: -118.3, killed: null, injured: null, road: null, category: 'crash', type: null });
  const many = createStaticApi(async <T,>(path: string) => (path === 'live/last24h.json'
    ? { summary: [], points: [...Array.from({ length: 3100 }, (_, i) => point(i, 'live')), point(0, 'record')] } : fixture[path]) as T);
  const rows = await many.recentPoints({ kind: 'live' }, LA);
  assert.equal(rows.filter(p => p.kind === 'live').length, 3000);
  assert.equal(rows.filter(p => p.kind === 'record').length, 1);
  assert.ok(rows.every((p, i) => i === 0 || rows[i - 1].time >= p.time));
});
