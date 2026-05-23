import { useState } from "react";
import MapView from "../components/map/MapView";
import { ToponymFilters } from "../api/toponyms";

export default function MapPage() {
  const [filters, setFilters] = useState<ToponymFilters>({});
  return (
    <div
      style={{
        position: "absolute",
        top: 60,          // под шапкой
        left: 0,
        right: 0,
        bottom: 0,
        display: "flex",
      }}
    >
      <MapView filters={filters} onFiltersChange={setFilters} />
    </div>
  );
}
