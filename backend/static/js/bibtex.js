/**
 * Превращает оставшиеся от старого WordPress-шорткода bibtex-блоки в
 * аккуратные раскрывающиеся секции с кнопкой "Скопировать".
 *
 * Импорт из WordPress оставил очень грязный HTML:
 * - Маркер "bibtex" может быть в <p>, а само содержимое — голым текстом
 *   внутри <li> (без обёртки в элемент).
 * - Маркер "свернуть" иногда вложен в невалидную пару <p><p>...</p></p>,
 *   которую браузер раскручивает в странные конструкции.
 * - У части записей конечный маркер "свернуть" вообще отсутствует — bibtex
 *   "повис".
 *
 * Алгоритм:
 * 1. Ищем элементы с textContent === "bibtex" — это start-маркеры.
 * 2. Для каждого находим ближайший <li> (или другой "запись-контейнер") —
 *    в нём всё bibtex-содержимое и финальный маркер.
 * 3. Внутри этого контейнера итерируемся по дочерним узлам (включая
 *    текстовые), начиная сразу после start-маркера. Собираем всё до:
 *    - элемента с textContent === "свернуть" (нашли пару → отрезаем),
 *    - или конца контейнера (не нашли пару → берём до конца).
 * 4. Заменяем собранное на <details> с кнопкой "Скопировать".
 *
 * Идемпотентность: уже обработанные блоки помечаются классом, повторный
 * запуск ничего не сломает.
 */
(function () {
    'use strict';

    var START_RX = /^\s*bibtex\s*$/i;
    var END_RX = /^\s*(свернуть|collapse)\s*$/i;

    /**
     * Возвращает true, если узел — элемент с маленьким текстом,
     * матчящимся regex (start-маркер или end-маркер).
     */
    function isMarker(node, rx) {
        if (!node || node.nodeType !== 1) return false;
        if (node.dataset && node.dataset.bibtexProcessed) return false;
        var text = node.textContent || '';
        if (text.length > 30) return false;
        return rx.test(text);
    }

    /**
     * Поднимается от node до ближайшего LI (или article, section), который
     * считаем "контейнером одной библиографической записи".
     */
    function findRecordContainer(node) {
        var el = node.parentNode;
        while (el && el !== document.body) {
            if (el.nodeType === 1 && /^(LI|ARTICLE|SECTION)$/i.test(el.tagName)) {
                return el;
            }
            el = el.parentNode;
        }
        // Фоллбэк — родитель start-маркера
        return node.parentNode;
    }

    /**
     * Внутри record-контейнера собирает все узлы (элементы + текст) между
     * start-маркером и end-маркером (или до конца контейнера, если end не
     * найден).
     *
     * Возвращает {nodes: [...], endNode: HTMLElement|null}.
     * nodes — узлы для удаления и для извлечения текста.
     * endNode — сам end-маркер (тоже подлежит удалению), либо null.
     */
    function collectBetween(container, startMarker) {
        var nodes = [];
        var endNode = null;
        var foundStart = false;
        // walker по всем дочерним узлам контейнера (на любой глубине), в
        // document-order. NodeFilter.SHOW_ALL = 0xFFFFFFFF.
        var walker = document.createTreeWalker(container, NodeFilter.SHOW_ALL, null);
        var node = walker.nextNode();
        while (node) {
            if (!foundStart) {
                if (node === startMarker) {
                    foundStart = true;
                    // дальше будем собирать
                }
                node = walker.nextNode();
                continue;
            }
            // Пропускаем узлы, которые являются ПОТОМКАМИ start-маркера
            // (внутри него тоже идёт обход).
            if (startMarker.contains(node)) {
                node = walker.nextNode();
                continue;
            }
            // Проверяем, не end-маркер ли это (или его потомок)
            if (node.nodeType === 1 && isMarker(node, END_RX)) {
                endNode = node;
                break;
            }
            // Если это текст внутри элемента, который САМ является end-маркером,
            // тоже останавливаемся (но обработаем ниже на следующей итерации
            // через цикл уже не дойдём — node === end-marker уже найдено).
            nodes.push(node);
            node = walker.nextNode();
        }
        return { nodes: nodes, endNode: endNode };
    }

    /**
     * Извлекает чистый bibtex-текст из собранных узлов.
     * Берёт текст из элементов и текстовых узлов, схлопывает пробелы,
     * убирает пустые строки. Элементы-предки текстовых узлов не дублируем:
     * берём только текстовые узлы и элементы без детей (но без потомков),
     * чтобы не получить текст дважды.
     */
    function extractText(nodes) {
        // Возьмём только текстовые узлы (NodeType 3). Их .nodeValue даст
        // весь нужный текст без дублирования.
        var parts = [];
        nodes.forEach(function (n) {
            if (n.nodeType === 3) {
                parts.push(n.nodeValue);
            }
        });
        var text = parts.join('').replace(/\u00A0/g, ' ').trim();
        // Нормализуем переводы строк: больше двух подряд → два
        text = text.replace(/\n\s*\n\s*\n+/g, '\n\n');
        return text;
    }

    /**
     * Удаляет собранные узлы и end-маркер из DOM. Аккуратно: текстовые
     * узлы удаляются напрямую, элементы — вместе с их поддеревом.
     */
    function removeCollected(nodes, endNode) {
        // Собираем уникальные элементы верхнего уровня, чтобы не пытаться
        // удалить уже удалённый текстовый узел внутри удалённого элемента.
        // Идея: удаляем узлы по убыванию глубины — сначала самые глубокие.
        var seen = new Set();
        var toRemove = [];
        nodes.forEach(function (n) {
            if (seen.has(n)) return;
            seen.add(n);
            toRemove.push(n);
        });
        // Сортируем: сначала текстовые узлы (они "листовые") и глубоко
        // вложенные элементы, потом верхние.
        toRemove.sort(function (a, b) {
            return depth(b) - depth(a);
        });
        toRemove.forEach(function (n) {
            if (n.parentNode) n.parentNode.removeChild(n);
        });
        if (endNode && endNode.parentNode) {
            endNode.parentNode.removeChild(endNode);
        }
    }

    function depth(node) {
        var d = 0;
        var el = node;
        while (el && el.parentNode) {
            d++;
            el = el.parentNode;
        }
        return d;
    }

    function buildDetails(bibtexText) {
        var details = document.createElement('details');
        details.className = 'bibtex-block';

        var summary = document.createElement('summary');
        summary.textContent = 'BibTeX';
        details.appendChild(summary);

        var pre = document.createElement('pre');
        pre.className = 'bibtex-block__code';
        pre.textContent = bibtexText;
        details.appendChild(pre);

        var btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'bibtex-block__copy';
        btn.textContent = 'Скопировать';
        btn.addEventListener('click', function (e) {
            e.preventDefault();
            copyToClipboard(bibtexText).then(function (ok) {
                btn.textContent = ok ? 'Скопировано ✓' : 'Не удалось';
                setTimeout(function () { btn.textContent = 'Скопировать'; }, 1500);
            });
        });
        details.appendChild(btn);

        details.dataset.bibtexProcessed = '1';
        return details;
    }

    function copyToClipboard(text) {
        if (navigator.clipboard && navigator.clipboard.writeText) {
            return navigator.clipboard.writeText(text).then(
                function () { return true; },
                function () { return fallbackCopy(text); }
            );
        }
        return Promise.resolve(fallbackCopy(text));
    }

    function fallbackCopy(text) {
        try {
            var ta = document.createElement('textarea');
            ta.value = text;
            ta.setAttribute('readonly', '');
            ta.style.position = 'fixed';
            ta.style.opacity = '0';
            document.body.appendChild(ta);
            ta.select();
            var ok = document.execCommand('copy');
            document.body.removeChild(ta);
            return ok;
        } catch (e) {
            return false;
        }
    }

    function init() {
        // Ищем все start-маркеры на странице
        var candidates = document.querySelectorAll('p, li, div, span');
        var starts = [];
        Array.prototype.forEach.call(candidates, function (el) {
            if (isMarker(el, START_RX)) starts.push(el);
        });

        starts.forEach(function (startMarker) {
            // Если start-маркер уже удалён предыдущей итерацией — пропускаем
            if (!startMarker.isConnected) return;

            var container = findRecordContainer(startMarker);
            var collected = collectBetween(container, startMarker);
            var bibtexText = extractText(collected.nodes);

            if (!bibtexText) {
                // Нет содержимого — просто удалим start (и end если есть),
                // чтобы он не торчал.
                if (startMarker.parentNode) startMarker.parentNode.removeChild(startMarker);
                if (collected.endNode && collected.endNode.parentNode) {
                    collected.endNode.parentNode.removeChild(collected.endNode);
                }
                return;
            }

            var details = buildDetails(bibtexText);
            startMarker.parentNode.insertBefore(details, startMarker);

            // Удаляем оригинальные узлы (содержимое + end-маркер) и сам start
            removeCollected(collected.nodes, collected.endNode);
            if (startMarker.parentNode) startMarker.parentNode.removeChild(startMarker);
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
