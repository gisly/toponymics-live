import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import maplibregl, { Map, Popup } from "maplibre-gl";
import { Protocol } from "pmtiles";
import "maplibre-gl/dist/maplibre-gl.css";

import { api } from "@/api/client";

const STYLE_URL = import.meta.env.VITE_MAP_STYLE_URL || "/map-style/style.json";

// Регистрируем pmtiles протокол один раз на модуль
const pmtilesProtocol = new Protocol();
maplibregl.addProtocol("pmtiles", pmtilesProtocol.tile);

export default function MapPage() {
  const { t } = useTranslation();
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<Map | null>(null);
  const [mapReady, setMapReady] = useState(false);

  // Загружаем топонимы как GeoJSON одним запросом
  const { data: toponyms } = useQuery({
    queryKey: ["toponyms-geojson"],
    queryFn: () => api.toponymsGeoJSON(),
  });

  // Инициализация карты — один раз
  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;

    const map = new maplibregl.Map({
      container: containerRef.current,
      style: STYLE_URL,
      center: [105, 60], // условный центр Сибири — Эвенкия
      zoom: 4,
    });

    map.addControl(new maplibregl.NavigationControl(), "top-right");
    map.addControl(new maplibregl.ScaleControl(), "bottom-left");

    map.on("load", () => {
      setMapReady(true);
    });

    map.on("error", (e) => {
      // Не падаем, если стиль ещё не настроен — просто логируем
      console.warn("MapLibre error:", e?.error?.message || e);
    });

    mapRef.current = map;

    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, []);

  // Когда карта готова и данные загружены — добавляем слой топонимов
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapReady || !toponyms) return;

    const SOURCE_ID = "toponyms";
    const LAYER_ID = "toponyms-circles";
    const LABELS_ID = "toponyms-labels";

    // Если уже есть — обновляем; иначе создаём
    const existingSource = map.getSource(SOURCE_ID) as maplibregl.GeoJSONSource | undefined;
    if (existingSource) {
      existingSource.setData(toponyms as never);
      return;
    }

    map.addSource(SOURCE_ID, { type: "geojson", data: toponyms as never });

    map.addLayer({
      id: LAYER_ID,
      type: "circle",
      source: SOURCE_ID,
      paint: {
        "circle-radius": [
          "interpolate", ["linear"], ["zoom"],
          4, 3,
          12, 8,
        ],
        "circle-color": [
          "match", ["get", "confidence"],
          "high", "#15803d",
          "medium", "#ca8a04",
          "low", "#b91c1c",
          "#737373",
        ],
        "circle-stroke-width": 1.5,
        "circle-stroke-color": "#ffffff",
      },
    });

    map.addLayer({
      id: LABELS_ID,
      type: "symbol",
      source: SOURCE_ID,
      minzoom: 7,
      layout: {
        "text-field": ["coalesce", ["get", "name_ru"], ["get", "name_evn_cyrillic"]],
        "text-font": ["Noto Sans Regular"],
        "text-size": 12,
        "text-offset": [0, 1.2],
        "text-anchor": "top",
      },
      paint: {
        "text-color": "#1c1917",
        "text-halo-color": "#ffffff",
        "text-halo-width": 1.5,
      },
    });

    // Клик по точке → попап
    map.on("click", LAYER_ID, (e) => {
      const f = e.features?.[0];
      if (!f) return;
      const p = f.properties as Record<string, string>;
      const coords = (f.geometry as GeoJSON.Point).coordinates as [number, number];
      const html = `
        <div style="font-family: Inter, sans-serif; min-width: 200px">
          <strong>${escapeHtml(p.name_ru || "—")}</strong><br/>
          <span style="font-family: 'Charis SIL', serif; color: #44403c">
            ${escapeHtml(p.name_evn_cyrillic || "")}
            ${p.name_evn_latin ? ` &middot; ${escapeHtml(p.name_evn_latin)}` : ""}
          </span>
        </div>
      `;
      new Popup({ closeButton: true })
        .setLngLat(coords)
        .setHTML(html)
        .addTo(map);
    });

    map.on("mouseenter", LAYER_ID, () => { map.getCanvas().style.cursor = "pointer"; });
    map.on("mouseleave", LAYER_ID, () => { map.getCanvas().style.cursor = ""; });
  }, [mapReady, toponyms]);

  return (
    <div className="relative w-full" style={{ height: "calc(100vh - 64px)" }}>
      <div ref={containerRef} className="absolute inset-0" />
      {!mapReady && (
        <div className="absolute inset-0 flex items-center justify-center bg-stone-100/80">
          <span className="text-stone-600">{t("map.loading")}</span>
        </div>
      )}
    </div>
  );
}

function escapeHtml(s: string): string {
  return s
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}
