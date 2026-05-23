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

  // Применяем API base сразу при монтировании, до первого запроса
  useEffect(() => {
    setApiBase(apiBase);
  }, [apiBase]);

  // ESC выходит из полноэкранного режима
  useEffect(() => {
    if (!isFullscreen) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") setIsFullscreen(false);
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [isFullscreen]);

  // В fullscreen блокируем прокрутку body, иначе можно случайно прокрутить страницу
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
        minHeight: 400, // минимум на случай если родитель совсем плоский
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
      <button
        type="button"
        onClick={() => setIsFullscreen(!isFullscreen)}
        title={isFullscreen ? "Свернуть (Esc)" : "Развернуть на весь экран"}
        style={{
          position: "absolute",
          top: 12,
          right: 12,
          zIndex: 100,
          background: "white",
          border: "1px solid #d4d4d4",
          borderRadius: 6,
          padding: 8,
          cursor: "pointer",
          boxShadow: "0 2px 6px rgba(0,0,0,0.1)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
        aria-label={isFullscreen ? "Свернуть карту" : "Развернуть карту"}
      >
        {isFullscreen
          ? <Minimize2 size={18} color="#333" />
          : <Maximize2 size={18} color="#333" />
        }
      </button>
    </div>
  );
}
