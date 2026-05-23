import { useEffect, useRef, useState } from "react";
import maplibregl, { Map as MapLibreMap } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { Protocol } from "pmtiles";
import { useTranslation } from "react-i18next";
import { fetchToponymsGeoJSON, ToponymFilters, ToponymGeoJSON } from "../../api/toponyms";
import ToponymPopup from "./ToponymPopup";
import FiltersSidebar from "./FiltersSidebar";
import { setMapLanguage, MapLanguage } from "./mapLanguage";

const MAP_STYLE_URL = import.meta.env.VITE_MAP_STYLE_URL || "/map-style/toponymics-live.json";

// Регистрируем pmtiles:// протокол в MapLibre один раз на модуль.
// После этого можно в style.json использовать "url": "pmtiles://..."
// и MapLibre сам будет тащить нужные куски через HTTP Range.
const pmtilesProtocol = new Protocol();
maplibregl.addProtocol("pmtiles", pmtilesProtocol.tile);

// Цвета по языку — для слоя точек
const LANGUAGE_COLORS: Record<string, string> = {
  evn: "#d97757",   // тёплый коричнево-оранжевый — эвенкийский в фокусе
  sah: "#5b8a72",   // зелёный — якутский
  ru:  "#5b6f9c",   // приглушённый синий — русский
  ket: "#8b6fad",   // фиолетовый — кетский
  en:  "#888888",   // серый — английский
};

interface Props {
  filters: ToponymFilters;
  onFiltersChange: (f: ToponymFilters) => void;
}

export default function MapView({ filters, onFiltersChange }: Props) {
  const { i18n } = useTranslation();
  // Карта понимает только ru/en. Если в i18n что-то другое — fallback на ru.
  const mapLang: MapLanguage = i18n.language === "en" ? "en" : "ru";

  const mapContainer = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [data, setData] = useState<ToponymGeoJSON | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Загрузка данных при изменении фильтров
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    fetchToponymsGeoJSON(filters)
      .then(d => { if (!cancelled) { setData(d); setLoading(false); } })
      .catch(e => { if (!cancelled) { setError(String(e)); setLoading(false); } });
    return () => { cancelled = true; };
  }, [JSON.stringify(filters)]);

  // Синхронизация языка подписей карты с i18n.
  // setMapLanguage сам подождёт загрузки стиля если ещё не загрузился.
  useEffect(() => {
    if (mapRef.current) {
      setMapLanguage(mapRef.current, mapLang);
    }
  }, [mapLang]);

  // Инициализация карты (один раз)
  useEffect(() => {
    if (!mapContainer.current || mapRef.current) return;

    const map = new maplibregl.Map({
      container: mapContainer.current,
      style: MAP_STYLE_URL,
      center: [110, 62],  // центр Сибири/Эвенкии
      zoom: 4,
      minZoom: 2,
      maxZoom: 17,
      attributionControl: false,
    });

    map.addControl(new maplibregl.NavigationControl({ visualizePitch: false }), "top-right");
    map.addControl(new maplibregl.ScaleControl({ unit: "metric" }), "bottom-left");
    map.addControl(
      new maplibregl.AttributionControl({
        compact: true,
        customAttribution: "Топонимы: проект «Toponymics Live» | Тайлы: © OpenStreetMap, OpenFreeMap",
      }),
      "bottom-right",
    );

    map.on("load", () => {
      // Сразу применяем актуальный язык (стиль грузится с русскими подписями по умолчанию,
      // если язык EN — мгновенно подменяем после загрузки).
      setMapLanguage(map, mapLang);

      // Источник для топонимов — пока пустой, обновим из effect ниже
      map.addSource("toponyms", {
        type: "geojson",
        data: { type: "FeatureCollection", features: [] },
      });

      // Слой кружков
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

      // Слой подписей — только на больших зумах
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

      // Обработчики кликов
      map.on("click", "toponyms-circles", (e) => {
        const f = e.features?.[0];
        if (!f) return;
        const id = f.properties?.id as number;
        setSelectedId(id);
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
    };
  }, []);

  // Обновление данных в слое
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !data) return;
    const updateSource = () => {
      const src = map.getSource("toponyms") as maplibregl.GeoJSONSource | undefined;
      if (src) src.setData(data);
    };
    if (map.loaded()) updateSource();
    else map.once("load", updateSource);
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
