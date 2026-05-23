/**
 * Утилита для переключения языка подписей на MapLibre карте без перезагрузки стиля.
 *
 * Идея:
 * 1. В стиле карты для подписей используется паттерн ["coalesce", ["get", "name:ru"], ["get", "name"]].
 * 2. При смене языка мы проходим по всем слоям и подменяем "name:ru" → "name:en" (и наоборот).
 * 3. Карта обновляет подписи без моргания, источник данных тот же.
 *
 * Это позволяет иметь ОДИН файл стиля, а не плодить копии для каждого языка.
 */
import type { Map as MapLibreMap, LayerSpecification } from "maplibre-gl";

export type MapLanguage = "ru" | "en";

/**
 * Меняет имя поля в expression рекурсивно.
 * Например, ["coalesce", ["get", "name:ru"], ["get", "name"]] с (oldName="name:ru", newName="name:en")
 * становится ["coalesce", ["get", "name:en"], ["get", "name"]].
 */
function replaceFieldInExpression(
  expr: unknown,
  oldName: string,
  newName: string
): unknown {
  if (!Array.isArray(expr)) return expr;

  // Случай ["get", "name:ru"] → ["get", "name:en"]
  if (expr.length === 2 && expr[0] === "get" && expr[1] === oldName) {
    return ["get", newName];
  }

  // Рекурсивно обрабатываем все элементы массива (это может быть вложенный expression)
  return expr.map((item) => replaceFieldInExpression(item, oldName, newName));
}

/**
 * Меняет язык подписей на всех слоях карты, у которых text-field содержит
 * обращение к "name:ru" или "name:en". Безопасно для слоёв без подписей.
 */
export function setMapLanguage(map: MapLibreMap, lang: MapLanguage): void {
  if (!map.isStyleLoaded()) {
    // Если стиль ещё не загрузился — подождём событие.
    map.once("styledata", () => setMapLanguage(map, lang));
    return;
  }

  const oldName = lang === "en" ? "name:ru" : "name:en";
  const newName = lang === "en" ? "name:en" : "name:ru";

  const style = map.getStyle();
  if (!style.layers) return;

  for (const layer of style.layers as LayerSpecification[]) {
    // У символьных слоёв (symbol) бывает text-field. У остальных нет — пропускаем.
    if (layer.type !== "symbol") continue;
    const layout = layer.layout;
    if (!layout || !("text-field" in layout)) continue;

    const oldField = layout["text-field"];
    const newField = replaceFieldInExpression(oldField, oldName, newName);

    // setLayoutProperty принимает Expression, но типизация в maplibre строгая —
    // приходится приводить, потому что getStyle() возвращает уже сериализованный JSON.
    map.setLayoutProperty(layer.id, "text-field", newField as never);
  }
}
