/**
 * Точка входа для встраивания карты в любую HTML-страницу
 * (в нашем случае — в Wagtail-страницу /platform/).
 *
 * Использование на HTML-стороне:
 *
 *   <div id="map-root"
 *        data-lang="ru"
 *        data-api-base=""
 *        data-map-style-url="/map-style/toponymics-live.json"></div>
 *   <link rel="stylesheet" href="/static/map/toponymics-map.css" />
 *   <script src="/static/map/toponymics-map.umd.js"></script>
 *   <script>
 *     window.ToponymicsMap.mount('map-root');
 *   </script>
 *
 * Здесь нет react-router (роутингом занимается Wagtail/Django),
 * нет i18n React-провайдера (язык приходит через data-атрибут).
 */
import { StrictMode } from "react";
import { createRoot, Root } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import MapEmbed from "./MapEmbed";
import "./index.css";

export interface MountOptions {
  /** Язык подписей: 'ru' (по умолчанию) или 'en'. Берётся из data-lang, если не передан. */
  lang?: "ru" | "en";
  /**
   * Базовый URL Django API. По умолчанию пусто (тот же origin что и страница).
   * Можно переопределить через data-api-base.
   */
  apiBase?: string;
  /**
   * URL JSON-стиля MapLibre. По умолчанию "/map-style/toponymics-live.json".
   * Сервер должен подменить в нём {PMTILES_URL} на актуальный путь к pmtiles.
   * Можно переопределить через data-map-style-url.
   */
  mapStyleUrl?: string;
  /** Начальный центр карты [долгота, широта]. По умолчанию [110, 62] — центр Эвенкии. */
  initialCenter?: [number, number];
  /** Начальный зум. По умолчанию 4. */
  initialZoom?: number;
}

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 60_000,
      refetchOnWindowFocus: false,
    },
  },
});

// Храним смонтированные корни, чтобы не плодить дубликаты при повторных mount() на тот же элемент
const mountedRoots = new Map<string, Root>();

/**
 * Монтирует React-карту в DOM-элемент с указанным id.
 * Опции можно передать программно или через data-атрибуты на элементе.
 */
function mount(elementId: string, options: MountOptions = {}): void {
  const container = document.getElementById(elementId);
  if (!container) {
    console.error(`[ToponymicsMap] Element with id="${elementId}" not found`);
    return;
  }

  // Если уже смонтировано — перемонтируем с новыми опциями
  if (mountedRoots.has(elementId)) {
    mountedRoots.get(elementId)!.unmount();
    mountedRoots.delete(elementId);
  }

  // Опции из data-атрибутов имеют меньший приоритет чем переданные в коде
  const dataLang = container.dataset.lang as "ru" | "en" | undefined;
  const dataApiBase = container.dataset.apiBase;
  const dataMapStyleUrl = container.dataset.mapStyleUrl;
  const dataInitialZoom = container.dataset.initialZoom;
  const dataInitialCenter = container.dataset.initialCenter;

  const lang = options.lang || dataLang || "ru";
  const apiBase = options.apiBase ?? dataApiBase ?? "";
  const mapStyleUrl =
    options.mapStyleUrl ?? dataMapStyleUrl ?? "/map-style/toponymics-live.json";
  const initialZoom = options.initialZoom ?? (dataInitialZoom ? Number(dataInitialZoom) : 4);
  const initialCenter: [number, number] = options.initialCenter ?? (
    dataInitialCenter
      ? (dataInitialCenter.split(",").map(Number) as [number, number])
      : [110, 62]
  );

  const root = createRoot(container);
  mountedRoots.set(elementId, root);

  root.render(
    <StrictMode>
      <QueryClientProvider client={queryClient}>
        <MapEmbed
          lang={lang}
          apiBase={apiBase}
          mapStyleUrl={mapStyleUrl}
          initialCenter={initialCenter}
          initialZoom={initialZoom}
        />
      </QueryClientProvider>
    </StrictMode>,
  );
}

/** Размонтирует ранее смонтированный экземпляр. */
function unmount(elementId: string): void {
  const root = mountedRoots.get(elementId);
  if (root) {
    root.unmount();
    mountedRoots.delete(elementId);
  }
}

/**
 * Меняет язык подписей у уже смонтированного экземпляра.
 * Если хочешь только подписи без перемонтирования — используй этот метод.
 */
function setLanguage(elementId: string, lang: "ru" | "en"): void {
  // Простейший способ — перемонтировать с новым lang.
  // MapEmbed.tsx сам обновит карту через mapLanguage.ts когда поменяется prop.
  const container = document.getElementById(elementId);
  if (!container) return;
  mount(elementId, { lang });
}

// Экспорт в глобальный объект — так UMD-бандл будет видим как window.ToponymicsMap
const ToponymicsMap = { mount, unmount, setLanguage };
export default ToponymicsMap;
