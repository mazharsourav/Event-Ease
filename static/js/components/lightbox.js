// Lightbox: any element with data-lightbox="<image url>" opens that photo large (click handled by delegation,
// so photos added to the page later work too). Escape or a click closes it.
// Other scripts can call window.eeLightbox.open(url, returnFocusTo).
(function () {
    'use strict';

    var overlay = null;
    var image = null;
    var close = null;
    var opener = null;

    function build() {
        overlay = document.createElement('div');
        overlay.className = 'ee-lightbox';
        overlay.hidden = true;
        overlay.setAttribute('role', 'dialog');
        overlay.setAttribute('aria-modal', 'true');
        overlay.setAttribute('aria-label', 'Photo');

        image = document.createElement('img');
        image.alt = '';

        close = document.createElement('button');
        close.type = 'button';
        close.className = 'ee-lightbox-close';
        close.setAttribute('aria-label', 'Close photo');
        close.textContent = '×';

        overlay.append(image, close);
        document.body.appendChild(overlay);

        overlay.addEventListener('click', function (event) {
            if (event.target !== image) hide();
        });
    }

    function open(source, from) {
        if (!overlay) build();
        opener = from || null;
        image.src = source;
        overlay.hidden = false;
        close.focus();
    }

    function hide() {
        if (!overlay || overlay.hidden) return;
        overlay.hidden = true;
        image.removeAttribute('src');
        if (opener) opener.focus();
    }

    document.addEventListener('click', function (event) {
        var trigger = event.target.closest('[data-lightbox]');
        if (trigger) open(trigger.dataset.lightbox, trigger);
    });
    document.addEventListener('keydown', function (event) {
        if (event.key === 'Escape') hide();
    });

    window.eeLightbox = { open: open, close: hide };
})();
