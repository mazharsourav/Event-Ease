// Gallery: choosing a thumbnail swaps the large photo. Left and right arrows step through the photos.
// Markup: [data-ee-gallery] > [data-gallery-image] + [data-gallery-caption] + buttons[data-src][data-caption].
(function () {
    'use strict';

    document.querySelectorAll('[data-ee-gallery]').forEach(function (gallery) {
        var image = gallery.querySelector('[data-gallery-image]');
        var caption = gallery.querySelector('[data-gallery-caption]');
        var thumbs = Array.prototype.slice.call(gallery.querySelectorAll('[data-src]'));
        if (!image || thumbs.length < 2) return;

        var index = 0;

        function show(next) {
            index = (next + thumbs.length) % thumbs.length;
            var thumb = thumbs[index];
            image.src = thumb.dataset.src;
            image.alt = thumb.dataset.alt || '';
            if (caption) caption.textContent = thumb.dataset.caption || '';
            thumbs.forEach(function (other) {
                if (other === thumb) other.setAttribute('aria-current', 'true');
                else other.removeAttribute('aria-current');
            });
        }

        thumbs.forEach(function (thumb, position) {
            thumb.addEventListener('click', function () { show(position); });
        });

        gallery.addEventListener('keydown', function (event) {
            if (event.key === 'ArrowRight') { event.preventDefault(); show(index + 1); thumbs[index].focus(); }
            else if (event.key === 'ArrowLeft') { event.preventDefault(); show(index - 1); thumbs[index].focus(); }
        });
    });
})();
