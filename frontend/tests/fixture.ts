// A tiny hand-written export in the format of docs/STATIC_SITE.md, keyed by path under data/.
const crash = (id: string, year: number, county: number | null, lat: number | null, lon: number | null, date: string | null, hour: number | null, deaths: number,
  roadName: string | null, route: string | null, city: string | null, flags: string[], speeding = 0, drinking = 0, nonMotorist = 0) =>
  [id, year, county, lat, lon, date, hour, deaths, roadName, route, city, 'Dark', 'Clear', 'Pedestrian', flags, speeding, drinking, nonMotorist];

export const LA: [number, number, number, number] = [-118.7, 33.7, -118.1, 34.4];

export const fixture: Record<string, unknown> = {
  'meta.json': {
    generated_at: '2026-11-16T20:00:00Z', fars_years: [2020, 2021, 2022, 2023, 2024], recent_years: [2025, 2026], dot_days: 365,
    dots_since: '2025-11-16T20:00:00', grid_deg: 0.05, tile_deg: 1, tile_cap: 2000, tiles: ['-119_34', '-123_37'],
  },
  'flags.json': [
    { id: 'speed', name: 'Speeding', description: 'A driver was speeding', source: 'fars', category: 'behavior' },
    { id: 'dui', name: 'Drinking driver', description: 'A driver had been drinking', source: 'fars', category: 'behavior' },
    { id: 'ped', name: 'Pedestrian', description: 'A pedestrian was killed', source: 'fars', category: 'people' },
  ],
  'coverage.json': [
    { source: 'chp', kind: 'live', label: 'California Highway Patrol incidents', states: [6], bbox: [-124.5, 32.5, -114.1, 42.0] },
    { source: 'lacity', kind: 'record', label: 'Los Angeles crash reports', states: [6], bbox: [-118.7, 33.7, -118.1, 34.4] },
  ],
  'fars/states.json': [[6, 'California', 2023, 10, 12], [6, 'California', 2024, 5, 6], [6, 'CALIFORNIA', 2020, 1, 1], [48, 'Texas', 2024, 20, 22]],
  'fars/06.json': {
    counties: { '37': 'Los Angeles', '73': 'San Diego' },
    crashes: [
      crash('A1', 2024, 37, 34.05, -118.25, '2024-05-01', 8, 2, 'I-5 FWY', 'I-5', 'LOS ANGELES', ['speed', 'ped'], 1, 0, 1),
      crash('A2', 2024, 37, 34.06, -118.24, '2024-07-01', 8, 1, 'I-5', 'I-5', 'LOS ANGELES', ['speed'], 1, 1, 0),
      crash('A3', 2023, 37, null, null, '2023-02-01', null, 1, 'I-5', 'I-5', 'LOS ANGELES', []),
      crash('A4', 2024, 73, 32.7, -117.1, '2024-01-01', 23, 3, 'SR-163', 'SR-163', 'SAN DIEGO', ['dui'], 0, 1, 0),
      crash('A5', 2022, null, 36.0, -119.0, null, 5, 1, null, null, null, []),
      crash('A6', 2024, 37, 34.0, -118.3, '2024-07-01', 12, 1, 'MAIN ST', 'MAIN ST', 'PASADENA', []),
      crash('A7', 2024, 37, 34.01, -118.31, '2024-07-01', 12, 0, 'Main St', 'MAIN ST', 'PASADENA', []),
    ],
  },
  'recent/totals.json': [
    ['chp', 2025, 100, null, null, '2025-01-01T00:00:00', '2025-12-31T23:00:00'],
    ['chp', 2026, 50, null, null, '2026-01-01T01:00:00', '2026-11-16T19:00:00'],
    ['lacity', 2025, 40, 2, 30, '2025-01-02T10:00:00', '2025-12-30T10:00:00'],
    ['lacity', 2026, 10, 0, 5, '2026-01-03T10:00:00', '2026-10-01T10:00:00'],
  ],
  // Cell (-2366, 681) is about -118.3, 34.05 (inside LA); (-2450, 755) is about -122.5, 37.75.
  'recent/grid-2025.json': { sources: ['chp', 'lacity'], cells: [[0, -2366, 681, 60, null, null], [0, -2450, 755, 30, null, null], [1, -2366, 681, 35, 2, 25]] },
  'recent/grid-2026.json': { sources: ['chp', 'lacity'], cells: [[0, -2366, 681, 20, null, null], [1, -2366, 681, 8, 0, 4]] },
  'recent/tiles/-119_34.json': [
    ['lacity', 'r1', '2026-10-01T10:00:00', 34.05, -118.25, 0, 1, 'MAIN ST', 'crash', 'Rear end'],
    ['chp', 'c1', '2026-09-01T12:00:00', 34.06, -118.26, null, null, 'I-5', 'crash', '1183'],
    ['lacity', 'r0', '2025-12-01T10:00:00', 34.5, -118.9, 0, 0, null, 'crash', null],
    ['lacity', 2, '2025-12-01T09:00:00', 34.0, -118.3, 1, 0, 'FIGUEROA ST', 'crash', null],
  ],
  'recent/tiles/-123_37.json': [['chp', 'c2', '2026-08-01T12:00:00', 37.75, -122.45, null, null, 'US-101', 'crash', '1183']],
  'live/last24h.json': {
    summary: [{ source: 'chp', kind: 'live', label: 'California Highway Patrol incidents', count: 3, killed: null, injured: null,
      first: '2026-11-16T09:00:00', last: '2026-11-16T12:00:00', with_coordinates: 2 }],
    points: [
      { source: 'chp', kind: 'live', id: 'L1', time: '2026-11-16T10:00:00', lat: 34.05, lon: -118.25, killed: null, injured: null, road: 'I-5', category: 'crash', type: '1183' },
      { source: 'chp', kind: 'live', id: 'L2', time: '2026-11-16T12:00:00', lat: 37.75, lon: -122.45, killed: null, injured: null, road: 'US-101', category: 'hazard', type: '1125' },
    ],
  },
};
