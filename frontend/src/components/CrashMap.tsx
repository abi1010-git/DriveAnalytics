import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { useEffect, useMemo } from 'react';
import { CircleMarker, GeoJSON, MapContainer, Pane, Popup, TileLayer, Tooltip, useMap } from 'react-leaflet';
import type { CityRow, CountyRow, Coverage, CrashPoint, FlagDef, RecentPoint, Selection, StateRow } from '../api';
import { ago, fmt, parseTime } from '../api';
import type { Boundary } from '../geo';

// Sequential scale: darker = fewer deaths, brighter = more. Buckets are quantiles of the
// areas currently on screen, so each level (states, or one state's counties) uses its own range.
const SCALE = ['#3a2430', '#5e2a32', '#8a3331', '#b8452c', '#e0632a', '#f79a3e'];
const US_BOUNDS: L.LatLngBoundsExpression = [[24.4, -125], [49.5, -66.9]];
const ALASKA_BOUNDS: L.LatLngBoundsExpression = [[51, -179.9], [71.5, -129.9]];  // the Aleutians cross 180°

function quantileColor(values: number[]) {
  const sorted = [...values].sort((a, b) => a - b);
  const cuts = SCALE.slice(1).map((_, i) => sorted[Math.floor(((i + 1) / SCALE.length) * (sorted.length - 1))] ?? 0);
  return (v: number) => SCALE[cuts.filter(c => v > c).length];
}

// GeoJSON layers in react-leaflet don't restyle when their data changes, so each layer's key
// includes a cheap fingerprint of the numbers it shows.
const total = (rows: { deaths: number; crashes: number }[]) => rows.reduce((t, r) => t + r.deaths * 7 + r.crashes, 0);

function FitBounds({ bounds }: { bounds: L.LatLngBoundsExpression | null }) {
  const map = useMap();
  useEffect(() => { if (bounds) map.flyToBounds(bounds, { padding: [24, 24], duration: 0.8 }); }, [map, bounds]);
  return null;
}

// Dot colours, also used by the legend: each kind of data looks different on purpose.
export const COLORS = { fatal: '#ef4444', record: '#38bdf8', live: '#c084fc', city: '#e2e8f0' };

type Props = {
  selection: Selection;
  farsActive: boolean;
  recentPoints: RecentPoint[];
  recentStates: Map<number, string[]>;
  coverage: Coverage[];
  stateFeatures: Boundary[];
  countyFeatures: Boundary[];
  states: StateRow[];
  counties: CountyRow[];
  cities: CityRow[];
  crashes: CrashPoint[];
  flagNames: Record<string, FlagDef>;
  selectedRoad: string | null;
  onState: (code: number, name: string) => void;
  onCounty: (code: number, name: string) => void;
  onCity: (name: string) => void;
};

export function CrashMap(p: Props) {
  const { selection } = p;
  // The map prefers canvas for the many shaded areas, but a canvas in the points pane would
  // cover the whole map and swallow clicks meant for the counties below it. SVG lets clicks on
  // empty space through (and runs the live-incident pulse animation, which canvas can't).
  const pointsRenderer = useMemo(() => L.svg({ pane: 'points' }), []);
  const inArea = selection.countyCode !== undefined || !!selection.city;

  const stateLayer = useMemo(() => {
    if (selection.stateCode !== undefined) return null;
    const byCode = new Map(p.states.map(s => [s.state_code, s]));
    const color = quantileColor(p.states.map(s => s.deaths));
    // Every state is drawn so it stays clickable even when FARS has no data for the range.
    const features = p.stateFeatures.filter(f => Number(f.id) <= 56);
    return { features, byCode, color, version: total(p.states) + (p.farsActive ? 1 : 0) + p.recentStates.size };
  }, [p.states, p.stateFeatures, selection.stateCode, p.farsActive, p.recentStates]);

  const countyLayer = useMemo(() => {
    if (selection.stateCode === undefined) return null;
    const prefix = String(selection.stateCode).padStart(2, '0');
    const byFips = new Map(p.counties.map(c => [c.fips, c]));
    const color = quantileColor(p.counties.map(c => c.deaths));
    const features = p.countyFeatures.filter(f => String(f.id).startsWith(prefix));
    return { features, byFips, color, prefix, version: total(p.counties) };
  }, [p.counties, p.countyFeatures, selection.stateCode]);

  const bounds = useMemo<L.LatLngBoundsExpression | null>(() => {
    if (selection.stateCode === undefined) return US_BOUNDS;
    if (selection.city && p.crashes.length) return L.latLngBounds(p.crashes.map(c => [c.latitude, c.longitude] as [number, number]));
    if (selection.countyCode !== undefined && countyLayer) {
      const fips = countyLayer.prefix + String(selection.countyCode).padStart(3, '0');
      const county = countyLayer.features.find(f => f.id === fips);
      if (county) return L.geoJSON(county).getBounds();
    }
    if (selection.city) return null;  // wait for crash points
    if (selection.stateCode === 2) return ALASKA_BOUNDS;
    const state = p.stateFeatures.find(f => Number(f.id) === selection.stateCode);
    return state ? L.geoJSON(state).getBounds() : null;
  }, [selection, p.crashes, countyLayer, p.stateFeatures]);

  const roadBounds = useMemo(() => {
    const hits = p.selectedRoad ? p.crashes.filter(c => c.road_route === p.selectedRoad) : [];
    return hits.length ? L.latLngBounds(hits.map(c => [c.latitude, c.longitude] as [number, number])) : null;
  }, [p.selectedRoad, p.crashes]);

  return <MapContainer bounds={US_BOUNDS} className="map" zoomSnap={0.25} preferCanvas>
    {/* OpenStreetMap's own tiles need no key but are meant for light use; a hosted deploy should
        switch to a tile provider with an account. CSS (.dark-tiles) turns them dark to match the app. */}
    <TileLayer
      url="https://tile.openstreetmap.org/{z}/{x}/{y}.png" className="dark-tiles"
      attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
      maxZoom={19} />
    <FitBounds bounds={roadBounds ?? bounds} />

    {stateLayer && <GeoJSON key={`states-${stateLayer.features.length}-${stateLayer.version}`} data={{ type: 'FeatureCollection', features: stateLayer.features } as GeoJSON.FeatureCollection}
      style={f => {
        const row = stateLayer.byCode.get(Number(f?.id));
        const recent = p.recentStates.has(Number(f?.id));
        const edge = !p.farsActive && recent ? { color: COLORS.record, weight: 2 } : { color: '#0b1120', weight: 1 };
        return { fillColor: row ? stateLayer.color(row.deaths) : '#1e293b', fillOpacity: row ? 0.75 : 0.55, ...edge };
      }}
      onEachFeature={(f, layer) => {
        const code = Number(f.id);
        const row = stateLayer.byCode.get(code);
        const name = row?.name ?? (f.properties as { name: string }).name;
        const sources = p.recentStates.get(code);
        const fars = row ? `${fmt(row.deaths)} deaths · ${fmt(row.crashes)} fatal crashes (FARS)` : p.farsActive ? 'No FARS data' : 'FARS covers 2020–2024 only';
        layer.bindTooltip(`<b>${name}</b><br>${fars}${sources ? `<br><span style="color:${COLORS.record}">Newer data: ${sources.join(', ')}</span>` : ''}`, { sticky: true });
        const base = (layer as L.Path).options;
        layer.on({ click: () => p.onState(code, name), mouseover: e => e.target.setStyle({ weight: 2.5, color: '#f4f7fb' }), mouseout: e => e.target.setStyle({ weight: base.weight, color: base.color }) });
      }} />}

    {countyLayer && <GeoJSON key={`counties-${selection.stateCode}-${selection.countyCode}-${selection.city}-${countyLayer.features.length}-${countyLayer.version}`}
      data={{ type: 'FeatureCollection', features: countyLayer.features } as GeoJSON.FeatureCollection}
      style={f => {
        const fips = String(f?.id);
        const selected = selection.countyCode !== undefined && fips === countyLayer.prefix + String(selection.countyCode).padStart(3, '0');
        const deaths = countyLayer.byFips.get(fips)?.deaths ?? 0;
        return inArea
          ? { fillOpacity: selected ? 0.04 : 0.35, fillColor: '#0b1120', color: selected ? '#f4f7fb' : '#475569', weight: selected ? 2 : 0.6 }
          : { fillColor: deaths ? countyLayer.color(deaths) : '#1e293b', fillOpacity: 0.7, color: '#0b1120', weight: 0.6 };
      }}
      onEachFeature={(f, layer) => {
        const fips = String(f.id);
        const row = countyLayer.byFips.get(fips);
        const name = row?.name ?? (f.properties as { name: string }).name;
        layer.bindTooltip(`<b>${name}</b><br>${row ? `${fmt(row.deaths)} deaths · ${fmt(row.crashes)} fatal crashes` : 'No fatal crashes recorded'}`, { sticky: true });
        layer.on({ click: () => p.onCounty(Number(fips.slice(2)), name) });
      }} />}

    {/* Points get their own pane so they always draw above the shaded areas. */}
    <Pane name="points" style={{ zIndex: 450 }}>
    {selection.stateCode !== undefined && !inArea && p.cities.filter(c => c.latitude !== null).map(c =>
      <CircleMarker renderer={pointsRenderer} key={c.name} center={[c.latitude!, c.longitude!]} radius={3 + Math.sqrt(c.deaths) / 2.5}
        pathOptions={{ color: '#0b1120', weight: 1, fillColor: COLORS.city, fillOpacity: 0.8 }} eventHandlers={{ click: () => p.onCity(c.name) }}>
        <Tooltip pane="tooltipPane">{titleCase(c.name)}: {fmt(c.deaths)} deaths</Tooltip>
      </CircleMarker>)}

    {inArea && p.crashes.map(c => {
      const dimmed = p.selectedRoad !== null && c.road_route !== p.selectedRoad;
      return <CircleMarker renderer={pointsRenderer} key={c.id} center={[c.latitude, c.longitude]} radius={3 + 2 * Math.min(c.deaths, 4)}
        pathOptions={{ color: dimmed ? '#334155' : '#fecaca', weight: dimmed ? 0.5 : 1, fillColor: dimmed ? '#334155' : '#ef4444', fillOpacity: dimmed ? 0.35 : 0.8 }}>
        <Popup pane="popupPane"><CrashDetails crash={c} flagNames={p.flagNames} /></Popup>
      </CircleMarker>;
    })}

    {p.recentPoints.map(r => {
      const live = r.kind === 'live';
      const hurt = (r.killed ?? 0) * 3 + Math.min(r.injured ?? 0, 3);
      return <CircleMarker renderer={pointsRenderer} key={`${r.source}-${r.id}`} center={[r.lat, r.lon]} radius={live ? 5 : 2.5 + hurt}
        pathOptions={{ color: live ? '#f5d0fe' : '#bae6fd', weight: live ? 1 : 0.5, fillColor: live ? COLORS.live : COLORS.record,
          fillOpacity: live ? 0.85 : 0.55, opacity: live ? 1 : 0.6, className: live && r.category === 'crash' ? 'pulse' : undefined }}>
        <Popup pane="popupPane"><RecentDetails point={r} label={p.coverage.find(c => c.source === r.source)?.label ?? r.source} /></Popup>
      </CircleMarker>;
    })}
    </Pane>
  </MapContainer>;
}

function CrashDetails({ crash, flagNames }: { crash: CrashPoint; flagNames: Record<string, FlagDef> }) {
  const when = [crash.date ? new Date(crash.date + 'T00:00').toLocaleDateString(undefined, { dateStyle: 'medium' }) : 'Date unknown',
    crash.hour !== null ? `${crash.hour}:00–${crash.hour}:59` : null].filter(Boolean).join(', ');
  return <div className="crash-popup">
    <strong>{crash.deaths} {crash.deaths === 1 ? 'death' : 'deaths'}</strong>
    <div>{when}</div>
    <div>{[crash.road_name, crash.city_name && titleCase(crash.city_name)].filter(Boolean).join(' · ') || 'Road not recorded'}</div>
    <div className="muted">{[crash.light_condition, crash.weather, crash.first_harmful_event && `hit: ${crash.first_harmful_event}`].filter(Boolean).join(' · ')}</div>
    {crash.flags.length > 0 && <div className="chips">{crash.flags.map(f => <span key={f} className="chip">{flagNames[f]?.name ?? f}</span>)}</div>}
  </div>;
}

function RecentDetails({ point, label }: { point: RecentPoint; label: string }) {
  const when = parseTime(point);
  const live = point.kind === 'live';
  return <div className="crash-popup">
    <span className={`kind ${point.kind}`}>{live ? 'Live incident report' : 'Police crash report'}</span>
    <strong>{point.type ?? (point.category === 'crash' ? 'Crash' : point.category)}</strong>
    <div>{live ? `${when.toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })} (${ago(when)})` : when.toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })}</div>
    {point.road && <div>{point.road}</div>}
    {!live && <div>{point.killed ? `${point.killed} killed · ` : ''}{point.injured ?? 0} injured</div>}
    <div className="muted">Source: {label}{live ? '. Unverified first report; details may change.' : ''}</div>
  </div>;
}

type LegendProps = { level: 'us' | 'state' | 'area'; shading: string | null; showCities: boolean; showFatal: boolean; showRecords: boolean; showLive: boolean };

/** What the colours and dots mean, plus what to click next. */
export function Legend(p: LegendProps) {
  const hint = p.level === 'us' ? 'Click a state to explore it'
    : p.level === 'state' ? (p.showCities ? 'Click a county, or a city bubble' : 'Click a county')
    : 'Click a dot for details';
  return <div className="legend">
    <span className="hint">{hint}</span>
    {p.shading && <span className="scale">
      <small>{p.shading}</small>
      <span className="ramp">fewer {SCALE.map(c => <i key={c} style={{ background: c }} />)} more</span>
    </span>}
    {p.showCities && <span><i className="ring" style={{ background: COLORS.city }} />City, sized by deaths</span>}
    {p.showFatal && <span><i style={{ background: COLORS.fatal }} />Fatal crash (FARS)</span>}
    {p.showRecords && <span><i style={{ background: COLORS.record }} />Police crash report</span>}
    {p.showLive && <span><i style={{ background: COLORS.live }} />Live incident</span>}
  </div>;
}

export const titleCase = (s: string) => s.toLowerCase().replace(/\b([a-z])/g, m => m.toUpperCase());
