/**
 * API client для общения с Django backend.
 */

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export interface Toponym {
  id: number;
  name_ru: string;
  name_evn_cyrillic: string;
  name_evn_latin: string;
  name_en: string;
  feature_type: number;
  region: number;
  latitude: string;
  longitude: string;
  confidence: "high" | "medium" | "low" | "unknown";
}

export interface ToponymGeoJSON {
  type: "FeatureCollection";
  features: Array<{
    type: "Feature";
    geometry: { type: "Point"; coordinates: [number, number] };
    properties: {
      id: number;
      name_ru: string;
      name_evn_cyrillic: string;
      name_evn_latin: string;
      feature_type_id: number;
      region_id: number;
      confidence: string;
    };
  }>;
}

export interface Region {
  id: number;
  name: string;
  slug: string;
  description: string;
  bbox: [number, number, number, number] | null;
}

export interface FeatureType {
  id: number;
  code: string;
  name: string;
  icon: string;
  default_color: string;
  sort_order: number;
}

async function fetchJSON<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { credentials: "include" });
  if (!res.ok) {
    throw new Error(`API ${path} → ${res.status}`);
  }
  return res.json();
}

export const api = {
  toponymsGeoJSON: () => fetchJSON<ToponymGeoJSON>("/api/toponyms/geojson/"),
  toponymDetail: (id: number) => fetchJSON<Toponym>(`/api/toponyms/${id}/`),
  regions: () => fetchJSON<{ results: Region[] }>("/api/regions/"),
  featureTypes: () => fetchJSON<{ results: FeatureType[] }>("/api/feature-types/"),
};
