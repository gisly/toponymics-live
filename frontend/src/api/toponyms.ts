const API_BASE = import.meta.env.VITE_API_BASE_URL || "";

export interface Language {
  iso: string;
  name_ru: string;
  name_en: string;
  name_native: string;
}

export interface FeatureType {
  code: string;
  name_ru: string;
  name_en: string;
  icon: string;
  default_color: string;
  sort_order: number;
}

export interface HistoricalMap {
  id: number;
  area_name_ru: string;
  area_name_en: string;
  author: { id: number; full_name: string; comment: string } | null;
  collector: { id: number; full_name: string; comment: string } | null;
  is_archive: boolean;
  scanned_image: string | null;
  image_link: string;
  toponym_count: number;
}

export interface ToponymGeoFeature {
  type: "Feature";
  id: number;
  geometry: { type: "Point"; coordinates: [number, number] };
  properties: {
    id: number;
    place_id: number;
    name: string;
    name_latin: string;
    language: string;
    feature_type: string | null;
    feature_color: string | null;
    translation_ru: string;
    is_approximate: boolean;
    historical_map_id: number | null;
  };
}

export interface ToponymGeoJSON {
  type: "FeatureCollection";
  features: ToponymGeoFeature[];
}

export interface ToponymDetail {
  id: number;
  name: string;
  name_latin: string;
  name_ipa: string;
  language: Language;
  feature_type: FeatureType | null;
  translation_ru: string;
  translation_en: string;
  motivation: { id: number; short_name_ru: string; short_name_en: string } | null;
  motivation_comment: string;
  linguistic_means: string;
  informant: { id: number; full_name: string; comment: string } | null;
  historical_map: HistoricalMap | null;
  number_on_map: string;
  alternative_forms: string[];
  latitude: number | null;
  longitude: number | null;
  is_coordinates_approximate: boolean;
  location_comment: string;
  other_names: Array<{ id: number; name: string; language: string; translation_ru: string }>;
}

export interface ToponymFilters {
  language?: string[];
  feature_type?: string[];
  historical_map?: number[];
  search?: string;
  bbox?: [number, number, number, number];  // west,south,east,north
}

function buildQuery(filters: ToponymFilters): string {
  const params = new URLSearchParams();
  if (filters.language?.length) params.set("language", filters.language.join(","));
  if (filters.feature_type?.length) params.set("feature_type", filters.feature_type.join(","));
  if (filters.historical_map?.length) params.set("historical_map", filters.historical_map.join(","));
  if (filters.search) params.set("search", filters.search);
  if (filters.bbox) params.set("bbox", filters.bbox.join(","));
  return params.toString();
}

export async function fetchToponymsGeoJSON(filters: ToponymFilters = {}): Promise<ToponymGeoJSON> {
  const qs = buildQuery(filters);
  const url = `${API_BASE}/api/toponyms/geojson/${qs ? `?${qs}` : ""}`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export async function fetchToponymDetail(id: number): Promise<ToponymDetail> {
  const res = await fetch(`${API_BASE}/api/toponyms/${id}/`);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export async function fetchLanguages(): Promise<Language[]> {
  const res = await fetch(`${API_BASE}/api/languages/`);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  const data = await res.json();
  return data.results || data;
}

export async function fetchFeatureTypes(): Promise<FeatureType[]> {
  const res = await fetch(`${API_BASE}/api/feature-types/`);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  const data = await res.json();
  return data.results || data;
}

export async function fetchHistoricalMaps(): Promise<HistoricalMap[]> {
  const res = await fetch(`${API_BASE}/api/historical-maps/`);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  const data = await res.json();
  return data.results || data;
}
