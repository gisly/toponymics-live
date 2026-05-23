import { useState } from "react";
import { useTranslation } from "react-i18next";
import MapView from "../components/map/MapView";
import { ToponymFilters } from "../api/toponyms";

export default function MapPage() {
  const { i18n } = useTranslation();
  const lang = i18n.language === "en" ? "en" : "ru";
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
      <MapView filters={filters} onFiltersChange={setFilters} lang={lang} />
    </div>
  );
}
