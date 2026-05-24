import { useEffect, useState } from "react";
import { X, User, Map as MapIcon, Languages, Expand } from "lucide-react";
import { fetchToponymDetail, ToponymDetail, getApiBase } from "../../api/toponyms";
import ImageLightbox from "./ImageLightbox";

interface Props {
  id: number;
  onClose: () => void;
}

/**
 * Превращает относительный путь от Django (/media/...) в абсолютный URL.
 * Если уже абсолютный (http://...) — возвращает как есть.
 * Если apiBase пустой (Wagtail-режим, тот же origin) — относительный путь
 * браузер сам отрезолвит правильно.
 */
function resolveMediaUrl(path: string | null): string | null {
  if (!path) return null;
  if (path.startsWith("http://") || path.startsWith("https://")) return path;
  const base = getApiBase() || "";
  // Убираем trailing slash у base и leading slash у path, чтобы не получить //
  return base.replace(/\/$/, "") + (path.startsWith("/") ? path : "/" + path);
}

export default function ToponymPopup({ id, onClose }: Props) {
  const [data, setData] = useState<ToponymDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lightboxOpen, setLightboxOpen] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setData(null);
    fetchToponymDetail(id)
      .then(d => { if (!cancelled) { setData(d); setLoading(false); } })
      .catch(e => { if (!cancelled) { setError(String(e)); setLoading(false); } });
    return () => { cancelled = true; };
  }, [id]);

  // URL скана: приоритет — загруженный файл, fallback — внешняя ссылка
  const mapImageUrl = data?.historical_map
    ? (resolveMediaUrl(data.historical_map.scanned_image) || data.historical_map.image_link || null)
    : null;

  return (
    <>
      <div className="absolute top-4 right-16 w-96 max-h-[calc(100vh-140px)] overflow-y-auto bg-white rounded-md shadow-xl border border-stone-200">
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
            className="shrink-0 w-7 h-7 -mr-1 -mt-0.5 rounded-full flex items-center justify-center text-stone-500 hover:text-stone-900 hover:bg-stone-100 transition-colors"
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
                {data.historical_map.author && (
                  <div className="text-stone-600 text-xs mt-0.5">
                    Автор: {data.historical_map.author.full_name}
                  </div>
                )}
                {data.number_on_map && (
                  <div className="text-stone-500 text-xs">
                    Номер на карте: <span className="font-mono font-medium text-stone-700">{data.number_on_map}</span>
                  </div>
                )}

                {/* Превью скана карты */}
                {mapImageUrl && (
                  <button
                    type="button"
                    onClick={() => setLightboxOpen(true)}
                    className="group relative mt-2 block w-full overflow-hidden rounded border border-stone-200 bg-stone-100 hover:border-stone-400 transition-colors"
                    style={{ aspectRatio: "4 / 3" }}
                    aria-label="Открыть карту в полный размер"
                  >
                    <img
                      src={mapImageUrl}
                      alt={`Рукописная карта: ${data.historical_map.area_name_ru}`}
                      loading="lazy"
                      className="w-full h-full object-cover"
                    />
                    {/* Иконка "увеличить" в углу — появляется при ховере */}
                    <span className="absolute bottom-2 right-2 bg-black/60 text-white rounded p-1.5 opacity-0 group-hover:opacity-100 transition-opacity">
                      <Expand size={14} />
                    </span>
                  </button>
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

      {/* Lightbox — открывается по клику на превью карты */}
      {lightboxOpen && mapImageUrl && data?.historical_map && (
        <ImageLightbox
          src={mapImageUrl}
          alt={`Рукописная карта: ${data.historical_map.area_name_ru}`}
          caption={
            [
              data.historical_map.area_name_ru,
              data.historical_map.author?.full_name && `Автор: ${data.historical_map.author.full_name}`,
              data.number_on_map && `Номер на карте: ${data.number_on_map}`,
            ].filter(Boolean).join(" · ")
          }
          onClose={() => setLightboxOpen(false)}
        />
      )}
    </>
  );
}
