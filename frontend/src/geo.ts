// US boundaries from the us-atlas package (Census Bureau cartographic boundaries, 1:10m),
// converted from TopoJSON. Feature ids are FIPS codes: "06" for a state, "06037" for a county,
// which match the state_code/county_code columns in FARS.
import type { Feature, FeatureCollection, Geometry } from 'geojson';
import { feature } from 'topojson-client';
import type { GeometryCollection, Topology } from 'topojson-specification';

export type Boundary = Feature<Geometry, { name: string }>;

function toFeatures(topology: Topology, key: string): Boundary[] {
  return (feature(topology, topology.objects[key] as GeometryCollection<{ name: string }>) as FeatureCollection<Geometry, { name: string }>).features;
}

let states: Promise<Boundary[]> | null = null;
let counties: Promise<Boundary[]> | null = null;

export function loadStates() {
  states ??= import('us-atlas/states-10m.json').then(m => toFeatures(m.default as unknown as Topology, 'states'));
  return states;
}

// Counties are ~800 KB, so they are only loaded once someone opens a state.
export function loadCounties() {
  counties ??= import('us-atlas/counties-10m.json').then(m => toFeatures(m.default as unknown as Topology, 'counties'));
  return counties;
}
