/**
 * API client для общения с Django backend.
 */
const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";
async function fetchJSON(path) {
    const res = await fetch(`${API_BASE}${path}`, { credentials: "include" });
    if (!res.ok) {
        throw new Error(`API ${path} → ${res.status}`);
    }
    return res.json();
}
export const api = {
    toponymsGeoJSON: () => fetchJSON("/api/toponyms/geojson/"),
    toponymDetail: (id) => fetchJSON(`/api/toponyms/${id}/`),
    regions: () => fetchJSON("/api/regions/"),
    featureTypes: () => fetchJSON("/api/feature-types/"),
};
