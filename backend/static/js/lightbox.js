/**
 * Lightbox для фотогалереи.
 *
 * Активируется на любых .gallery-grid контейнерах на странице.
 * Не требует зависимостей.
 *
 * Поддерживает:
 * - клик по превью → открытие
 * - стрелки ← → на клавиатуре, Esc для выхода
 * - свайпы на тач-устройствах
 * - кнопка "Слайдшоу" → авто-переключение раз в N мс (data-slideshow-interval)
 * - history.pushState — назад в браузере закрывает lightbox, не уходя со страницы
 * - prefetch следующего и предыдущего фото для плавности
 */
(function () {
    'use strict';

    var lightbox = document.getElementById('lightbox');
    if (!lightbox) return;

    var imgEl = lightbox.querySelector('.lightbox__image');
    var captionEl = lightbox.querySelector('.lightbox__caption');
    var counterEl = lightbox.querySelector('.lightbox__counter');
    var btnClose = lightbox.querySelector('.lightbox__btn--close');
    var btnPrev = lightbox.querySelector('.lightbox__btn--prev');
    var btnNext = lightbox.querySelector('.lightbox__btn--next');
    var btnSlideshow = lightbox.querySelector('.lightbox__btn--slideshow');

    // Все галереи на странице. На сайте обычно одна, но мало ли.
    var galleries = Array.prototype.map.call(
        document.querySelectorAll('[data-gallery]'),
        function (root) {
            return {
                root: root,
                items: Array.prototype.map.call(
                    root.querySelectorAll('.gallery-grid__item'),
                    function (a) {
                        return {
                            src: a.dataset.fullSrc,
                            caption: a.dataset.caption || ''
                        };
                    }
                ),
                slideshowInterval: parseInt(root.dataset.slideshowInterval, 10) || 4000
            };
        }
    );

    if (galleries.length === 0) return;

    var state = {
        gallery: null,    // {items, slideshowInterval}
        index: 0,
        isOpen: false,
        slideshowTimer: null
    };

    // ─── Открытие / закрытие ────────────────────────────────────────

    function open(gallery, index) {
        state.gallery = gallery;
        state.index = index;
        state.isOpen = true;
        lightbox.hidden = false;
        document.body.classList.add('lightbox-open');
        render();

        // history-state, чтобы Back закрывал lightbox
        history.pushState({ lightbox: true }, '', '');
    }

    function close() {
        if (!state.isOpen) return;
        stopSlideshow();
        state.isOpen = false;
        lightbox.hidden = true;
        document.body.classList.remove('lightbox-open');
        imgEl.src = '';  // освобождаем память

        // Снимаем history-state, если мы его поставили
        if (history.state && history.state.lightbox) {
            history.back();
        }
    }

    // ─── Навигация ──────────────────────────────────────────────────

    function next() {
        if (!state.gallery) return;
        state.index = (state.index + 1) % state.gallery.items.length;
        render();
    }

    function prev() {
        if (!state.gallery) return;
        state.index = (state.index - 1 + state.gallery.items.length) % state.gallery.items.length;
        render();
    }

    function render() {
        var item = state.gallery.items[state.index];
        imgEl.src = item.src;
        imgEl.alt = item.caption || '';
        captionEl.textContent = item.caption || '';
        counterEl.textContent = (state.index + 1) + ' / ' + state.gallery.items.length;

        // Prefetch соседних фото — браузер положит в кеш, переключение мгновенное
        prefetch((state.index + 1) % state.gallery.items.length);
        prefetch((state.index - 1 + state.gallery.items.length) % state.gallery.items.length);
    }

    function prefetch(idx) {
        var item = state.gallery.items[idx];
        if (!item) return;
        var img = new Image();
        img.src = item.src;
    }

    // ─── Слайдшоу ───────────────────────────────────────────────────

    function toggleSlideshow() {
        if (state.slideshowTimer) {
            stopSlideshow();
        } else {
            startSlideshow();
        }
    }

    function startSlideshow() {
        stopSlideshow();
        state.slideshowTimer = setInterval(next, state.gallery.slideshowInterval);
        btnSlideshow.classList.add('is-playing');
        btnSlideshow.textContent = '⏸';
        btnSlideshow.setAttribute('aria-label', btnSlideshow.dataset.labelPause);
    }

    function stopSlideshow() {
        if (state.slideshowTimer) {
            clearInterval(state.slideshowTimer);
            state.slideshowTimer = null;
        }
        btnSlideshow.classList.remove('is-playing');
        btnSlideshow.textContent = '▶';
        btnSlideshow.setAttribute('aria-label', btnSlideshow.dataset.labelPlay);
    }

    // ─── Подвешиваем обработчики ────────────────────────────────────

    galleries.forEach(function (gallery) {
        gallery.root.addEventListener('click', function (e) {
            var link = e.target.closest('.gallery-grid__item');
            if (!link) return;
            e.preventDefault();
            var idx = parseInt(link.dataset.index, 10) || 0;
            open(gallery, idx);
        });
    });

    btnClose.addEventListener('click', close);
    btnPrev.addEventListener('click', function () { stopSlideshow(); prev(); });
    btnNext.addEventListener('click', function () { stopSlideshow(); next(); });
    btnSlideshow.addEventListener('click', toggleSlideshow);

    // Клик на фон (но не на кнопки/фото) — закрывает
    lightbox.addEventListener('click', function (e) {
        if (e.target === lightbox || e.target.classList.contains('lightbox__stage')) {
            close();
        }
    });

    // Клавиатура
    document.addEventListener('keydown', function (e) {
        if (!state.isOpen) return;
        if (e.key === 'Escape') close();
        else if (e.key === 'ArrowRight') { stopSlideshow(); next(); }
        else if (e.key === 'ArrowLeft') { stopSlideshow(); prev(); }
        else if (e.key === ' ') { e.preventDefault(); toggleSlideshow(); }
    });

    // Свайпы на тач-устройствах
    var touchStartX = null;
    lightbox.addEventListener('touchstart', function (e) {
        if (e.touches.length === 1) {
            touchStartX = e.touches[0].clientX;
        }
    }, { passive: true });

    lightbox.addEventListener('touchend', function (e) {
        if (touchStartX === null) return;
        var dx = e.changedTouches[0].clientX - touchStartX;
        touchStartX = null;
        if (Math.abs(dx) < 50) return;  // слишком короткий свайп
        stopSlideshow();
        if (dx > 0) prev(); else next();
    });

    // Back в браузере закрывает lightbox
    window.addEventListener('popstate', function () {
        if (state.isOpen) {
            // Не вызываем close() через history.back, чтобы не зациклиться —
            // просто разворачиваем UI
            stopSlideshow();
            state.isOpen = false;
            lightbox.hidden = true;
            document.body.classList.remove('lightbox-open');
            imgEl.src = '';
        }
    });
})();
