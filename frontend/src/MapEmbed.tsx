/**
 * Обёртка над MapView для встраивания в произвольную страницу.
 *
 * Принимает язык и apiBase через props (а не через i18n/env),
 * чтобы карта была изолирована от внешнего state-менеджмента.
 *
 * Добавляет кнопку «развернуть на весь экран».
 */
import { useEffect, useState } from "react";
import { Maximize2, Minimize2 } from "lucide-react";
import MapView from "./components/map/MapView";
import { ToponymFilters } from "./api/toponyms";
import { setApiBase } from "./api/toponyms";

export interface MapEmbedProps {
  lang: "ru" | "en";
  apiBase: string;
  mapStyleUrl: string;
  initialCenter: [number, number];
  initialZoom: number;
}

export default function MapEmbed({ lang, apiBase, mapStyleUrl, initialCenter, initialZoom }: MapEmbedProps) {
  const [filters, setFilters] = useState<ToponymFilters>({});
  const [isFullscreen, setIsFullscreen] = useState(false);

  useEffect(() => {
    setApiBase(apiBase);
  }, [apiBase]);

  useEffect(() => {
    if (!isFullscreen) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") setIsFullscreen(false);
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [isFullscreen]);

  useEffect(() => {
    if (isFullscreen) {
      const prev = document.body.style.overflow;
      document.body.style.overflow = "hidden";
      return () => { document.body.style.overflow = prev; };
    }
  }, [isFullscreen]);

  const containerStyle: React.CSSProperties = isFullscreen
    ? {
        position: "fixed",
        inset: 0,
        zIndex: 9999,
        backgroundColor: "#fff",
      }
    : {
        position: "relative",
        width: "100%",
        height: "100%",
        minHeight: 400,
      };

  return (
    <div style={containerStyle}>
      <MapView
        filters={filters}
        onFiltersChange={setFilters}
        lang={lang}
        mapStyleUrl={mapStyleUrl}
        initialCenter={initialCenter}
        initialZoom={initialZoom}
      />
      {/*
        Кнопка fullscreen — правый нижний угол, над attribution.
        Маленькая (24×24, иконка 14px), полупрозрачная — чтобы не отвлекала.
        При hover делается непрозрачной — даём понять, что она кликабельна.
      */}
      <button
        type="button"
        onClick={() => setIsFullscreen(!isFullscreen)}
        title={isFullscreen ? "Свернуть (Esc)" : "Развернуть на весь экран"}
        className="map-fullscreen-btn"
        style={{
          position: "absolute",
          bottom: 34,
          right: 10,
          zIndex: 100,
          width: 24,
          height: 24,
          padding: 0,
          background: "rgba(255, 255, 255, 0.85)",
          border: "1px solid rgba(0, 0, 0, 0.1)",
          borderRadius: 4,
          cursor: "pointer",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          color: "#555",
          transition: "background 0.15s, color 0.15s, border-color 0.15s",
        }}
        onMouseEnter={(e) => {
          const t = e.currentTarget;
          t.style.background = "rgba(255, 255, 255, 1)";
          t.style.borderColor = "rgba(0, 0, 0, 0.25)";
          t.style.color = "#000";
        }}
        onMouseLeave={(e) => {
          const t = e.currentTarget;
          t.style.background = "rgba(255, 255, 255, 0.85)";
          t.style.borderColor = "rgba(0, 0, 0, 0.1)";
          t.style.color = "#555";
        }}
        aria-label={isFullscreen ? "Свернуть карту" : "Развернуть карту"}
      >
        {isFullscreen ? <Minimize2 size={14} /> : <Maximize2 size={14} />}
      </button>
    </div>
  );
}
