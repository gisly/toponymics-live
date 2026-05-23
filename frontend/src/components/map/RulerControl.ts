/**
 * Линейка для MapLibre — кастомный IControl, измеряющий расстояние по точкам.
 *
 * UX:
 * - Кнопка-тогл в углу карты (рядом с NavigationControl).
 * - В активном режиме: курсор crosshair, клики ставят точки, линия рисуется
 *   между ними по большому кругу (геодезически, через turf/length).
 * - Двойной клик завершает линию (отключает режим, но линия остаётся).
 * - Повторное нажатие кнопки — отключает режим. Линия остаётся видимой.
 * - Иконка "корзина" появляется рядом, когда есть что стирать.
 *
 * Подключение в MapView:
 *
 *   import { RulerControl } from "./RulerControl";
 *   ...
 *   map.addControl(new RulerControl({ lang: "ru" }), "top-right");
 *
 * Зависимости: @turf/length, @turf/helpers — лёгкие, ~30 КБ суммарно.
 */
import maplibregl, { IControl, Map as MapLibreMap, MapMouseEvent } from "maplibre-gl";
import length from "@turf/length";
import { lineString, point as turfPoint } from "@turf/helpers";

const SOURCE_LINE = "ruler-line";
const SOURCE_POINTS = "ruler-points";
const SOURCE_LABEL = "ruler-label";
const LAYER_LINE = "ruler-line-layer";
const LAYER_POINTS = "ruler-points-layer";
const LAYER_LABEL = "ruler-label-layer";

type Lang = "ru" | "en";

interface Strings {
  enable: string;     // tooltip "Включить линейку"
  disable: string;    // tooltip "Выключить линейку"
  clear: string;      // tooltip "Очистить"
  km: string;         // "км"
  m: string;          // "м"
  hint: string;       // подсказка пользователю
}

const STRINGS: Record<Lang, Strings> = {
  ru: {
    enable: "Измерить расстояние",
    disable: "Завершить измерение",
    clear: "Очистить",
    km: "км",
    m: "м",
    hint: "Кликайте, чтобы добавить точки. Двойной клик — завершить.",
  },
  en: {
    enable: "Measure distance",
    disable: "Finish measuring",
    clear: "Clear",
    km: "km",
    m: "m",
    hint: "Click to add points. Double-click to finish.",
  },
};

export interface RulerControlOptions {
  lang?: Lang;
  lineColor?: string;
  pointColor?: string;
}

export class RulerControl implements IControl {
  private map: MapLibreMap | null = null;
  private container: HTMLDivElement | null = null;
  private btnToggle: HTMLButtonElement | null = null;
  private btnClear: HTMLButtonElement | null = null;
  private hintEl: HTMLDivElement | null = null;

  private active = false;
  private points: [number, number][] = [];   // [lng, lat]
  private prevCursor = "";

  private readonly lang: Lang;
  private readonly lineColor: string;
  private readonly pointColor: string;

  // Bind-ы, чтобы можно было снять обработчики
  private readonly onMapClick: (e: MapMouseEvent) => void;
  private readonly onMapDblClick: (e: MapMouseEvent) => void;

  constructor(opts: RulerControlOptions = {}) {
    this.lang = opts.lang === "en" ? "en" : "ru";
    this.lineColor = opts.lineColor || "#d97757";  // эвенкийский акцентный
    this.pointColor = opts.pointColor || "#d97757";
    this.onMapClick = this.handleMapClick.bind(this);
    this.onMapDblClick = this.handleMapDblClick.bind(this);
  }

  // ─── IControl interface ─────────────────────────────────────────────

  onAdd(map: MapLibreMap): HTMLElement {
    this.map = map;

    const container = document.createElement("div");
    container.className = "maplibregl-ctrl maplibregl-ctrl-group";
    container.style.display = "flex";
    container.style.flexDirection = "column";

    // Кнопка-тогл
    const btnToggle = document.createElement("button");
    btnToggle.type = "button";
    btnToggle.title = STRINGS[this.lang].enable;
    btnToggle.setAttribute("aria-label", STRINGS[this.lang].enable);
    btnToggle.innerHTML = RULER_ICON_SVG;
    btnToggle.style.cursor = "pointer";
    btnToggle.addEventListener("click", () => this.toggle());
    container.appendChild(btnToggle);

    // Кнопка очистки — изначально скрыта
    const btnClear = document.createElement("button");
    btnClear.type = "button";
    btnClear.title = STRINGS[this.lang].clear;
    btnClear.setAttribute("aria-label", STRINGS[this.lang].clear);
    btnClear.innerHTML = TRASH_ICON_SVG;
    btnClear.style.cursor = "pointer";
    btnClear.style.display = "none";
    btnClear.addEventListener("click", () => this.clear());
    container.appendChild(btnClear);

    this.container = container;
    this.btnToggle = btnToggle;
    this.btnClear = btnClear;

    // Готовим источники и слои, как только карта загрузилась
    if (map.isStyleLoaded()) {
      this.ensureLayers();
    } else {
      map.once("load", () => this.ensureLayers());
    }
    // На случай смены стиля — перестилизация слоёв
    map.on("styledata", this.ensureLayersIfMissing);

    return container;
  }

  onRemove(): void {
    if (!this.map) return;
    this.deactivate();
    this.map.off("styledata", this.ensureLayersIfMissing);
    this.removeLayers();
    this.container?.parentNode?.removeChild(this.container);
    this.container = null;
    this.map = null;
  }

  // ─── Поведение ─────────────────────────────────────────────────────

  private toggle(): void {
    if (this.active) this.deactivate();
    else this.activate();
  }

  private activate(): void {
    if (!this.map || this.active) return;
    this.active = true;

    const canvas = this.map.getCanvas();
    this.prevCursor = canvas.style.cursor;
    canvas.style.cursor = "crosshair";

    this.map.on("click", this.onMapClick);
    this.map.on("dblclick", this.onMapDblClick);
    // Отключаем стандартный zoom-on-dblclick на время измерения
    this.map.doubleClickZoom.disable();

    if (this.btnToggle) {
      this.btnToggle.title = STRINGS[this.lang].disable;
      this.btnToggle.setAttribute("aria-label", STRINGS[this.lang].disable);
      this.btnToggle.style.background = "#fef3c7";  // мягкая подсветка
    }
    this.showHint();
  }

  private deactivate(): void {
    if (!this.map || !this.active) return;
    this.active = false;

    const canvas = this.map.getCanvas();
    canvas.style.cursor = this.prevCursor;

    this.map.off("click", this.onMapClick);
    this.map.off("dblclick", this.onMapDblClick);
    this.map.doubleClickZoom.enable();

    if (this.btnToggle) {
      this.btnToggle.title = STRINGS[this.lang].enable;
      this.btnToggle.setAttribute("aria-label", STRINGS[this.lang].enable);
      this.btnToggle.style.background = "";
    }
    this.hideHint();
  }

  private clear(): void {
    this.points = [];
    this.updateGeometry();
    this.updateClearButton();
  }

  private handleMapClick(e: MapMouseEvent): void {
    // Игнорируем клик, если он на топониме (чтобы не перекрывать выбор точки).
    // Если хочется наоборот — убери этот блок.
    const features = this.map!.queryRenderedFeatures(e.point, {
      layers: ["toponyms-circles"],
    });
    if (features.length > 0) {
      // Клик по топониму — пропускаем как точку линейки, чтобы открылся попап.
      return;
    }

    this.points.push([e.lngLat.lng, e.lngLat.lat]);
    this.updateGeometry();
    this.updateClearButton();
  }

  private handleMapDblClick(e: MapMouseEvent): void {
    // Двойной клик — завершить. Точка от него уже добавилась в первом click,
    // отдельно добавлять не нужно.
    e.preventDefault();
    this.deactivate();
  }

  // ─── Подсказка пользователю ────────────────────────────────────────

  private showHint(): void {
    if (!this.map || this.hintEl) return;
    const mapContainer = this.map.getContainer();
    const hint = document.createElement("div");
    hint.textContent = STRINGS[this.lang].hint;
    hint.style.cssText = `
      position: absolute;
      top: 12px;
      left: 50%;
      transform: translateX(-50%);
      background: rgba(0, 0, 0, 0.75);
      color: white;
      padding: 6px 12px;
      border-radius: 4px;
      font-size: 13px;
      z-index: 5;
      pointer-events: none;
      white-space: nowrap;
    `;
    mapContainer.appendChild(hint);
    this.hintEl = hint;
  }

  private hideHint(): void {
    this.hintEl?.parentNode?.removeChild(this.hintEl);
    this.hintEl = null;
  }

  // ─── Геометрия ─────────────────────────────────────────────────────

  private ensureLayers(): void {
    if (!this.map) return;
    const map = this.map;

    if (!map.getSource(SOURCE_POINTS)) {
      map.addSource(SOURCE_POINTS, {
        type: "geojson",
        data: { type: "FeatureCollection", features: [] },
      });
    }
    if (!map.getSource(SOURCE_LINE)) {
      map.addSource(SOURCE_LINE, {
        type: "geojson",
        data: { type: "FeatureCollection", features: [] },
      });
    }
    if (!map.getSource(SOURCE_LABEL)) {
      map.addSource(SOURCE_LABEL, {
        type: "geojson",
        data: { type: "FeatureCollection", features: [] },
      });
    }

    if (!map.getLayer(LAYER_LINE)) {
      map.addLayer({
        id: LAYER_LINE,
        type: "line",
        source: SOURCE_LINE,
        paint: {
          "line-color": this.lineColor,
          "line-width": 2.5,
          "line-dasharray": [2, 1],
        },
      });
    }
    if (!map.getLayer(LAYER_POINTS)) {
      map.addLayer({
        id: LAYER_POINTS,
        type: "circle",
        source: SOURCE_POINTS,
        paint: {
          "circle-radius": 5,
          "circle-color": "#ffffff",
          "circle-stroke-color": this.pointColor,
          "circle-stroke-width": 2.5,
        },
      });
    }
    if (!map.getLayer(LAYER_LABEL)) {
      map.addLayer({
        id: LAYER_LABEL,
        type: "symbol",
        source: SOURCE_LABEL,
        layout: {
          "text-field": ["get", "label"],
          "text-font": ["Noto Sans Regular"],
          "text-size": 13,
          "text-offset": [0, -1.4],
          "text-anchor": "bottom",
          "text-allow-overlap": true,
          "text-ignore-placement": true,
        },
        paint: {
          "text-color": "#1c1917",
          "text-halo-color": "#ffffff",
          "text-halo-width": 2.5,
        },
      });
    }

    // Восстанавливаем данные, если они уже были (например, после смены стиля)
    this.updateGeometry();
  }

  // Стрелочная функция, чтобы можно было снять с .off()
  private ensureLayersIfMissing = (): void => {
    if (!this.map) return;
    // При смене стиля все user-добавленные слои стираются.
    // Если линейка нарисована — заново всё создаём.
    if (!this.map.getLayer(LAYER_LINE)) {
      this.ensureLayers();
    }
  };

  private removeLayers(): void {
    if (!this.map) return;
    const map = this.map;
    for (const layer of [LAYER_LABEL, LAYER_POINTS, LAYER_LINE]) {
      if (map.getLayer(layer)) map.removeLayer(layer);
    }
    for (const src of [SOURCE_LABEL, SOURCE_POINTS, SOURCE_LINE]) {
      if (map.getSource(src)) map.removeSource(src);
    }
  }

  private updateGeometry(): void {
    if (!this.map) return;
    const map = this.map;

    const pointsSrc = map.getSource(SOURCE_POINTS) as maplibregl.GeoJSONSource | undefined;
    const lineSrc = map.getSource(SOURCE_LINE) as maplibregl.GeoJSONSource | undefined;
    const labelSrc = map.getSource(SOURCE_LABEL) as maplibregl.GeoJSONSource | undefined;

    if (!pointsSrc || !lineSrc || !labelSrc) return;

    pointsSrc.setData({
      type: "FeatureCollection",
      features: this.points.map((c) => turfPoint(c)),
    });

    if (this.points.length < 2) {
      lineSrc.setData({ type: "FeatureCollection", features: [] });
      labelSrc.setData({ type: "FeatureCollection", features: [] });
      return;
    }

    const line = lineString(this.points);
    lineSrc.setData({ type: "FeatureCollection", features: [line] });

    // turf/length считает по большому кругу в км — то, что нужно для Сибири
    const km = length(line, { units: "kilometers" });
    const last = this.points[this.points.length - 1];
    labelSrc.setData({
      type: "FeatureCollection",
      features: [{
        type: "Feature",
        geometry: { type: "Point", coordinates: last },
        properties: { label: formatDistance(km, this.lang) },
      }],
    });
  }

  private updateClearButton(): void {
    if (!this.btnClear) return;
    this.btnClear.style.display = this.points.length > 0 ? "block" : "none";
  }
}

// ─── Утилиты ────────────────────────────────────────────────────────

function formatDistance(km: number, lang: Lang): string {
  const s = STRINGS[lang];
  if (km < 1) {
    return `${Math.round(km * 1000)} ${s.m}`;
  }
  if (km < 100) {
    return `${km.toFixed(2)} ${s.km}`;
  }
  // Большие расстояния — округляем до целых
  return `${Math.round(km).toLocaleString(lang === "ru" ? "ru-RU" : "en-US")} ${s.km}`;
}

// ─── Иконки ─────────────────────────────────────────────────────────
// SVG вшиваем в код, чтобы не зависеть от внешних ассетов.
// Размер 18×18 в стиле lucide-react, под кнопку MapLibre (29×29).

const RULER_ICON_SVG = `
<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24"
     fill="none" stroke="currentColor" stroke-width="2"
     stroke-linecap="round" stroke-linejoin="round"
     style="display: inline-block; vertical-align: middle;">
  <path d="M21.3 8.7 8.7 21.3a2.41 2.41 0 0 1-3.4 0l-2.6-2.6a2.41 2.41 0 0 1 0-3.4L15.3 2.7a2.41 2.41 0 0 1 3.4 0l2.6 2.6a2.41 2.41 0 0 1 0 3.4Z"/>
  <path d="m7.5 10.5 2 2"/>
  <path d="m10.5 7.5 2 2"/>
  <path d="m13.5 4.5 2 2"/>
  <path d="m4.5 13.5 2 2"/>
</svg>
`;

const TRASH_ICON_SVG = `
<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24"
     fill="none" stroke="currentColor" stroke-width="2"
     stroke-linecap="round" stroke-linejoin="round"
     style="display: inline-block; vertical-align: middle;">
  <path d="M3 6h18"/>
  <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/>
  <path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
</svg>
`;
