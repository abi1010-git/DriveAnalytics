import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { useEffect, useMemo } from 'react';
import { CircleMarker, GeoJSON, MapContainer, Pane, Popup, TileLayer, Tooltip, useMap } from 'react-leaflet';
import type { CityRow, CountyRow, CrashPoint, FlagDef, Selection, StateRow } from '../api';
import { fmt } from '../api';
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

type Props = {
  selection: Selection;
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
  const inArea = selection.countyCode !== undefined || !!selection.city;

  const stateLayer = useMemo(() => {
    if (selection.stateCode !== undefined) return null;
    const byCode = new Map(p.states.map(s => [s.state_code, s]));
    const color = quantileColor(p.states.map(s => s.deaths));
    const features = p.stateFeatures.filter(f => byCode.has(Number(f.id)));
    return { features, byCode, color, version: total(p.states) };
  }, [p.states, p.stateFeatures, selection.stateCode]);

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
      style={f => ({ fillColor: stateLayer.color(stateLayer.byCode.get(Number(f?.id))?.deaths ?? 0), fillOpacity: 0.75, color: '#0b1120', weight: 1 })}
      onEachFeature={(f, layer) => {
        const row = stateLayer.byCode.get(Number(f.id))!;
        layer.bindTooltip(`<b>${row.name}</b><br>${fmt(row.deaths)} deaths · ${fmt(row.crashes)} fatal crashes`, { sticky: true });
        layer.on({ click: () => p.onState(row.state_code, row.name), mouseover: e => e.target.setStyle({ weight: 2.5, color: '#f4f7fb' }), mouseout: e => e.target.setStyle({ weight: 1, color: '#0b1120' }) });
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
      <CircleMarker key={c.name} center={[c.latitude!, c.longitude!]} radius={3 + Math.sqrt(c.deaths) / 2.5}
        pathOptions={{ color: '#f4f7fb', weight: 1, fillColor: '#38bdf8', fillOpacity: 0.85 }} eventHandlers={{ click: () => p.onCity(c.name) }}>
        <Tooltip pane="tooltipPane">{titleCase(c.name)}: {fmt(c.deaths)} deaths</Tooltip>
      </CircleMarker>)}

    {inArea && p.crashes.map(c => {
      const dimmed = p.selectedRoad !== null && c.road_route !== p.selectedRoad;
      return <CircleMarker key={c.id} center={[c.latitude, c.longitude]} radius={3 + 2 * Math.min(c.deaths, 4)}
        pathOptions={{ color: dimmed ? '#334155' : '#fecaca', weight: dimmed ? 0.5 : 1, fillColor: dimmed ? '#334155' : '#ef4444', fillOpacity: dimmed ? 0.35 : 0.8 }}>
        <Popup pane="popupPane"><CrashDetails crash={c} flagNames={p.flagNames} /></Popup>
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

export const titleCase = (s: string) => s.toLowerCase().replace(/\b([a-z])/g, m => m.toUpperCase());
