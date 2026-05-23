import { useEffect, useState } from "react";
import { Search, Filter, ChevronDown, ChevronRight } from "lucide-react";
import {
  ToponymFilters, Language, FeatureType, HistoricalMap,
  fetchLanguages, fetchFeatureTypes, fetchHistoricalMaps,
} from "../../api/toponyms";

interface Props {
  filters: ToponymFilters;
  onChange: (f: ToponymFilters) => void;
  toponymCount: number;
  loading: boolean;
}

export default function FiltersSidebar({ filters, onChange, toponymCount, loading }: Props) {
  const [collapsed, setCollapsed] = useState(false);
  const [languages, setLanguages] = useState<Language[]>([]);
  const [featureTypes, setFeatureTypes] = useState<FeatureType[]>([]);
  const [historicalMaps, setHistoricalMaps] = useState<HistoricalMap[]>([]);
  const [searchInput, setSearchInput] = useState(filters.search || "");
  const [showHistoricalMaps, setShowHistoricalMaps] = useState(false);

  useEffect(() => {
    fetchLanguages().then(setLanguages).catch(() => {});
    fetchFeatureTypes().then(setFeatureTypes).catch(() => {});
    fetchHistoricalMaps().then(setHistoricalMaps).catch(() => {});
  }, []);

  // Debounce поиска
  useEffect(() => {
    const t = setTimeout(() => {
      if (searchInput !== (filters.search || "")) {
        onChange({ ...filters, search: searchInput || undefined });
      }
    }, 300);
    return () => clearTimeout(t);
  }, [searchInput]);

  function toggleLanguage(iso: string) {
    const cur = filters.language || [];
    const next = cur.includes(iso) ? cur.filter(x => x !== iso) : [...cur, iso];
    onChange({ ...filters, language: next.length ? next : undefined });
  }

  function toggleFeatureType(code: string) {
    const cur = filters.feature_type || [];
    const next = cur.includes(code) ? cur.filter(x => x !== code) : [...cur, code];
    onChange({ ...filters, feature_type: next.length ? next : undefined });
  }

  function toggleHistoricalMap(id: number) {
    const cur = filters.historical_map || [];
    const next = cur.includes(id) ? cur.filter(x => x !== id) : [...cur, id];
    onChange({ ...filters, historical_map: next.length ? next : undefined });
  }

  function clearAll() {
    setSearchInput("");
    onChange({});
  }

  const hasActive = !!(filters.language?.length || filters.feature_type?.length ||
                      filters.historical_map?.length || filters.search);

  if (collapsed) {
    return (
      <div className="w-12 bg-white border-r border-stone-200 flex flex-col items-center py-3">
        <button
          onClick={() => setCollapsed(false)}
          className="text-stone-600 hover:text-stone-900 p-2"
          aria-label="Открыть фильтры"
        >
          <Filter size={18} />
        </button>
      </div>
    );
  }

  return (
    <div className="w-80 bg-white border-r border-stone-200 flex flex-col h-full overflow-hidden">
      <div className="px-4 py-3 border-b border-stone-200 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Filter size={16} className="text-stone-600" />
          <h2 className="font-semibold text-stone-900">Фильтры</h2>
        </div>
        <button
          onClick={() => setCollapsed(true)}
          className="text-stone-500 hover:text-stone-900 text-sm"
        >
          Свернуть
        </button>
      </div>

      <div className="flex-1 overflow-y-auto px-4 py-3 space-y-4 text-sm">
        {/* Поиск */}
        <div>
          <div className="relative">
            <Search size={16} className="absolute left-2 top-2.5 text-stone-400" />
            <input
              type="text"
              value={searchInput}
              onChange={e => setSearchInput(e.target.value)}
              placeholder="Поиск по имени или переводу"
              className="w-full pl-8 pr-2 py-2 border border-stone-300 rounded text-sm focus:outline-none focus:border-stone-500"
            />
          </div>
        </div>

        {/* Счётчик */}
        <div className="text-xs text-stone-500 -my-2">
          {loading ? "Загрузка…" : `${toponymCount} точек на карте`}
        </div>

        {/* Языки */}
        <div>
          <div className="text-xs uppercase tracking-wide text-stone-500 mb-2">Язык</div>
          <div className="space-y-1">
            {languages.map(lang => {
              const checked = filters.language?.includes(lang.iso) ?? false;
              return (
                <label key={lang.iso} className="flex items-center gap-2 cursor-pointer hover:bg-stone-50 px-1 py-0.5 rounded">
                  <input type="checkbox" checked={checked} onChange={() => toggleLanguage(lang.iso)} />
                  <span className="text-stone-700">{lang.name_ru}</span>
                  <span className="text-xs text-stone-400 ml-auto">{lang.iso}</span>
                </label>
              );
            })}
          </div>
        </div>

        {/* Типы объектов */}
        <div>
          <div className="text-xs uppercase tracking-wide text-stone-500 mb-2">Тип объекта</div>
          <div className="space-y-1">
            {featureTypes.map(ft => {
              const checked = filters.feature_type?.includes(ft.code) ?? false;
              return (
                <label key={ft.code} className="flex items-center gap-2 cursor-pointer hover:bg-stone-50 px-1 py-0.5 rounded">
                  <input type="checkbox" checked={checked} onChange={() => toggleFeatureType(ft.code)} />
                  <span className="text-stone-700">{ft.name_ru}</span>
                </label>
              );
            })}
          </div>
        </div>

        {/* Рукописные карты (collapsible) */}
        <div>
          <button
            onClick={() => setShowHistoricalMaps(s => !s)}
            className="w-full flex items-center justify-between text-xs uppercase tracking-wide text-stone-500 mb-2"
          >
            <span>Рукописная карта ({historicalMaps.length})</span>
            {showHistoricalMaps ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
          </button>
          {showHistoricalMaps && (
            <div className="space-y-1 max-h-60 overflow-y-auto">
              {historicalMaps.map(hm => {
                const checked = filters.historical_map?.includes(hm.id) ?? false;
                return (
                  <label key={hm.id} className="flex items-start gap-2 cursor-pointer hover:bg-stone-50 px-1 py-1 rounded">
                    <input type="checkbox" checked={checked} onChange={() => toggleHistoricalMap(hm.id)} className="mt-0.5" />
                    <div className="flex-1 min-w-0">
                      <div className="text-stone-700 text-xs truncate" title={hm.area_name_ru}>
                        {hm.area_name_ru}
                      </div>
                      <div className="text-stone-400 text-xs">{hm.toponym_count} топонимов</div>
                    </div>
                  </label>
                );
              })}
            </div>
          )}
        </div>
      </div>

      {hasActive && (
        <div className="border-t border-stone-200 px-4 py-2">
          <button
            onClick={clearAll}
            className="text-sm text-stone-600 hover:text-stone-900 underline"
          >
            Сбросить все фильтры
          </button>
        </div>
      )}
    </div>
  );
}
