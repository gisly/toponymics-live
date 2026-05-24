import { useEffect, useRef, useState } from "react";
import maplibregl, { Map as MapLibreMap } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { Protocol } from "pmtiles";
import { fetchToponymsGeoJSON, ToponymFilters, ToponymGeoJSON } from "../../api/toponyms";
import ToponymPopup from "./ToponymPopup";
import FiltersSidebar from "./FiltersSidebar";
import { setMapLanguage, MapLanguage } from "./mapLanguage";
import { RulerControl } from "./RulerControl";

const pmtilesProtocol = new Protocol();
maplibregl.addProtocol("pmtiles", pmtilesProtocol.tile);

const LANGUAGE_COLORS: Record<string, string> = {
  evn: "#d97757",
  sah: "#5b8a72",
  ru:  "#5b6f9c",
  ket: "#8b6fad",
  en:  "#888888",
};

interface Props {
  filters: ToponymFilters;
  onFiltersChange: (f: ToponymFilters) => void;
  lang?: MapLanguage;
  mapStyleUrl?: string;
  initialCenter?: [number, number];
  initialZoom?: number;
}

export default function MapView({
  filters,
  onFiltersChange,
  lang = "ru",
  mapStyleUrl,
  initialCenter = [110, 62],
  initialZoom = 4,
}: Props) {
  const mapLang: MapLanguage = lang;

  const mapContainer = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const rulerRef = useRef<RulerControl | null>(null);
  // Готов ли source "toponyms" к приёму данных. Поднимается в map.on("load"),
  // после addSource. Используется как замок: данные не льются раньше, чем
  // source создан.
  const sourceReadyRef = useRef(false);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [data, setData] = useState<ToponymGeoJSON | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    fetchToponymsGeoJSON(filters)
      .then(d => { if (!cancelled) { setData(d); setLoading(false); } })
      .catch(e => { if (!cancelled) { setError(String(e)); setLoading(false); } });
    return () => { cancelled = true; };
  }, [JSON.stringify(filters)]);

  useEffect(() => {
    if (mapRef.current) {
      setMapLanguage(mapRef.current, mapLang);
    }
    if (mapRef.current && rulerRef.current) {
      mapRef.current.removeControl(rulerRef.current);
      const ruler = new RulerControl({ lang: mapLang });
      mapRef.current.addControl(ruler, "top-right");
      rulerRef.current = ruler;
    }
  }, [mapLang]);

  // Закрытие попапа по Esc
  useEffect(() => {
    if (selectedId === null) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") setSelectedId(null);
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [selectedId]);

  useEffect(() => {
    if (!mapContainer.current || mapRef.current) return;

    const map = new maplibregl.Map({
      container: mapContainer.current,
      style: mapStyleUrl || "/map-style/toponymics-live.json",
      center: initialCenter,
      zoom: initialZoom,
      minZoom: 2,
      maxZoom: 17,
      attributionControl: false,
    });

    map.addControl(new maplibregl.NavigationControl({ visualizePitch: false }), "top-right");

    const ruler = new RulerControl({ lang: mapLang });
    map.addControl(ruler, "top-right");
    rulerRef.current = ruler;

    map.addControl(new maplibregl.ScaleControl({ unit: "metric" }), "bottom-left");
    map.addControl(
      new maplibregl.AttributionControl({
        compact: true,
        customAttribution: "Топонимы: проект «Toponymics Live» | Тайлы: © OpenStreetMap, OpenFreeMap",
      }),
      "bottom-right",
    );

    map.on("load", () => {
      setMapLanguage(map, mapLang);

      map.addSource("toponyms", {
        type: "geojson",
        data: { type: "FeatureCollection", features: [] },
      });

      map.addLayer({
        id: "toponyms-circles",
        type: "circle",
        source: "toponyms",
        paint: {
          "circle-radius": [
            "interpolate", ["linear"], ["zoom"],
            2, 2.5,
            6, 4,
            10, 6,
            14, 9,
          ],
          "circle-color": [
            "match",
            ["get", "language"],
            "evn", LANGUAGE_COLORS.evn,
            "sah", LANGUAGE_COLORS.sah,
            "ru",  LANGUAGE_COLORS.ru,
            "ket", LANGUAGE_COLORS.ket,
            "en",  LANGUAGE_COLORS.en,
            "#666666",
          ],
          "circle-stroke-color": "#ffffff",
          "circle-stroke-width": 1.5,
          "circle-opacity": [
            "case",
            ["get", "is_approximate"], 0.5,
            0.9
          ],
        },
      });

      map.addLayer({
        id: "toponyms-labels",
        type: "symbol",
        source: "toponyms",
        minzoom: 8,
        layout: {
          "text-field": ["get", "name"],
          "text-font": ["Noto Sans Regular"],
          "text-size": ["interpolate", ["linear"], ["zoom"], 8, 10, 14, 13],
          "text-anchor": "top",
          "text-offset": [0, 0.8],
          "text-optional": true,
        },
        paint: {
          "text-color": "#222222",
          "text-halo-color": "rgba(255, 255, 255, 0.95)",
          "text-halo-width": 2,
        },
      });

      // Source готов — теперь данные можно лить.
      // Если данные пришли раньше события load, эффект ниже отрисует их сразу,
      // как только увидит, что sourceReadyRef.current стал true.
      sourceReadyRef.current = true;
      // Сразу подсасываем актуальные данные (если они уже были загружены)
      const currentData = dataRef.current;
      if (currentData) {
        const src = map.getSource("toponyms") as maplibregl.GeoJSONSource | undefined;
        if (src) src.setData(currentData);
      }

      // Клик по точке топонима — открыть попап
      map.on("click", "toponyms-circles", (e) => {
        const f = e.features?.[0];
        if (!f) return;
        const id = f.properties?.id as number;
        setSelectedId(id);
      });

      // Клик по пустому месту карты — закрыть попап
      map.on("click", (e) => {
        const features = map.queryRenderedFeatures(e.point, {
          layers: ["toponyms-circles"],
        });
        if (features.length === 0) {
          setSelectedId(null);
        }
      });

      map.on("mouseenter", "toponyms-circles", () => {
        map.getCanvas().style.cursor = "pointer";
      });
      map.on("mouseleave", "toponyms-circles", () => {
        map.getCanvas().style.cursor = "";
      });
    });

    mapRef.current = map;

    return () => {
      map.remove();
      mapRef.current = null;
      rulerRef.current = null;
      sourceReadyRef.current = false;
    };
  }, []);

  // Зеркалим data в ref, чтобы load-колбэк карты мог его прочесть
  // (load-колбэк создан в effect-е с пустыми deps и держит замыкание на
  // старое значение data, поэтому через ref надёжнее).
  const dataRef = useRef<ToponymGeoJSON | null>(null);
  useEffect(() => {
    dataRef.current = data;
  }, [data]);

  // Обновление данных в слое. Триггеры:
  //  - data поменялась (например, фильтры применились)
  //  - source стал готов (происходит ровно один раз, на load)
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !data) return;

    const trySetData = () => {
      // Если source ещё не создан — выходим, событие load его создаст и
      // само заберёт data из dataRef.current.
      if (!sourceReadyRef.current) return;
      const src = map.getSource("toponyms") as maplibregl.GeoJSONSource | undefined;
      if (src) src.setData(data);
    };

    trySetData();
  }, [data]);

  return (
    <div className="relative flex" style={{ width: "100%", height: "100%" }}>
      <FiltersSidebar
        filters={filters}
        onChange={onFiltersChange}
        toponymCount={data?.features.length ?? 0}
        loading={loading}
      />
      <div className="relative" style={{ flex: 1, position: "relative" }}>
        <div
          ref={mapContainer}
          style={{ position: "absolute", top: 0, left: 0, right: 0, bottom: 0 }}
        />
        {error && (
          <div className="absolute top-4 left-1/2 -translate-x-1/2 bg-red-50 border border-red-200 text-red-800 px-4 py-2 rounded shadow text-sm" style={{ zIndex: 10 }}>
            Ошибка загрузки: {error}
          </div>
        )}
        {selectedId && (
          <ToponymPopup
            id={selectedId}
            onClose={() => setSelectedId(null)}
          />
        )}
        <Legend />
      </div>
    </div>
  );
}

function Legend() {
  return (
    <div className="absolute bottom-8 left-4 bg-white/95 backdrop-blur rounded-md shadow-md p-3 text-xs">
      <div className="font-semibold text-stone-800 mb-2">Цвет точки = язык</div>
      <ul className="space-y-1">
        <li className="flex items-center gap-2">
          <span className="w-3 h-3 rounded-full" style={{ background: LANGUAGE_COLORS.evn, border: "1.5px solid white", boxShadow: "0 0 0 0.5px #999" }} />
          <span>Эвенкийский</span>
        </li>
        <li className="flex items-center gap-2">
          <span className="w-3 h-3 rounded-full" style={{ background: LANGUAGE_COLORS.sah, border: "1.5px solid white", boxShadow: "0 0 0 0.5px #999" }} />
          <span>Якутский</span>
        </li>
        <li className="flex items-center gap-2">
          <span className="w-3 h-3 rounded-full" style={{ background: LANGUAGE_COLORS.ru, border: "1.5px solid white", boxShadow: "0 0 0 0.5px #999" }} />
          <span>Русский</span>
        </li>
        <li className="flex items-center gap-2">
          <span className="w-3 h-3 rounded-full" style={{ background: LANGUAGE_COLORS.ket, border: "1.5px solid white", boxShadow: "0 0 0 0.5px #999" }} />
          <span>Кетский</span>
        </li>
        <li className="flex items-center gap-2 text-stone-500 mt-1 pt-1 border-t border-stone-200">
          <span className="w-3 h-3 rounded-full bg-stone-400 opacity-50" />
          <span>Приблизительно</span>
        </li>
      </ul>
    </div>
  );
}
