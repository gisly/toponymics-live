import { useEffect, useState } from "react";
import { X, User, Map as MapIcon, Languages } from "lucide-react";
import { fetchToponymDetail, ToponymDetail } from "../../api/toponyms";

interface Props {
  id: number;
  onClose: () => void;
}

export default function ToponymPopup({ id, onClose }: Props) {
  const [data, setData] = useState<ToponymDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setData(null);
    fetchToponymDetail(id)
      .then(d => { if (!cancelled) { setData(d); setLoading(false); } })
      .catch(e => { if (!cancelled) { setError(String(e)); setLoading(false); } });
    return () => { cancelled = true; };
  }, [id]);

  return (
    <div className="absolute top-4 right-4 w-96 max-h-[calc(100vh-140px)] overflow-y-auto bg-white rounded-md shadow-xl border border-stone-200">
      <div className="sticky top-0 bg-white border-b border-stone-200 px-4 py-3 flex items-start justify-between gap-2">
        <div className="flex-1">
          {loading && <div className="text-sm text-stone-500">Загрузка…</div>}
          {error && <div className="text-sm text-red-600">{error}</div>}
          {data && (
            <>
              <div className="text-xl font-semibold text-stone-900 leading-tight">
                {data.name}
              </div>
              {data.name_latin && (
                <div className="text-sm text-stone-600 italic mt-0.5">
                  {data.name_latin}
                  {data.name_ipa && <span className="ml-2">[{data.name_ipa}]</span>}
                </div>
              )}
            </>
          )}
        </div>
        <button
          onClick={onClose}
          className="text-stone-400 hover:text-stone-700 -mr-1 -mt-1"
          aria-label="Закрыть"
        >
          <X size={18} />
        </button>
      </div>

      {data && (
        <div className="px-4 py-3 space-y-3 text-sm">
          {/* Тип объекта + язык */}
          <div className="flex items-center gap-2 text-stone-600 text-xs">
            {data.feature_type && (
              <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-stone-100 rounded">
                {data.feature_type.name_ru}
              </span>
            )}
            <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-stone-100 rounded">
              <Languages size={12} /> {data.language.name_ru}
            </span>
          </div>

          {/* Переводы */}
          {(data.translation_ru || data.translation_en) && (
            <div>
              <div className="text-xs uppercase tracking-wide text-stone-500 mb-1">Перевод</div>
              {data.translation_ru && <div className="text-stone-800">{data.translation_ru}</div>}
              {data.translation_en && <div className="text-stone-600 italic">{data.translation_en}</div>}
            </div>
          )}

          {/* Мотивация и аффикс */}
          {(data.motivation || data.linguistic_means) && (
            <div>
              <div className="text-xs uppercase tracking-wide text-stone-500 mb-1">Лингвистика</div>
              {data.motivation && (
                <div className="text-stone-800">Мотив: {data.motivation.short_name_ru}</div>
              )}
              {data.motivation_comment && (
                <div className="text-stone-600 text-xs mt-0.5">{data.motivation_comment}</div>
              )}
              {data.linguistic_means && (
                <div className="text-stone-700 text-xs mt-1 font-mono">{data.linguistic_means}</div>
              )}
            </div>
          )}

          {/* Другие имена этого же места */}
          {data.other_names.length > 0 && (
            <div>
              <div className="text-xs uppercase tracking-wide text-stone-500 mb-1">
                Другие имена этого места
              </div>
              <ul className="space-y-0.5">
                {data.other_names.map(o => (
                  <li key={o.id} className="text-stone-700">
                    <span className="font-medium">{o.name}</span>
                    <span className="text-stone-500 ml-1">({o.language})</span>
                    {o.translation_ru && <span className="text-stone-600 ml-1">— {o.translation_ru}</span>}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Информант */}
          {data.informant && (
            <div>
              <div className="text-xs uppercase tracking-wide text-stone-500 mb-1 flex items-center gap-1">
                <User size={12} /> Информант
              </div>
              <div className="text-stone-800">{data.informant.full_name}</div>
            </div>
          )}

          {/* Рукописная карта */}
          {data.historical_map && (
            <div>
              <div className="text-xs uppercase tracking-wide text-stone-500 mb-1 flex items-center gap-1">
                <MapIcon size={12} /> Рукописная карта
              </div>
              <div className="text-stone-800">{data.historical_map.area_name_ru}</div>
              {data.number_on_map && (
                <div className="text-stone-500 text-xs">Номер на карте: {data.number_on_map}</div>
              )}
            </div>
          )}

          {/* Координаты */}
          {(data.latitude !== null && data.longitude !== null) && (
            <div className="text-xs text-stone-500 pt-2 border-t border-stone-200">
              {data.latitude.toFixed(5)}, {data.longitude.toFixed(5)}
              {data.is_coordinates_approximate && (
                <span className="ml-2 text-amber-600">приблизительно</span>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
