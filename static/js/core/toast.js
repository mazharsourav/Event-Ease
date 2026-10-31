// Toasts: Django messages fade out on their own, or when dismissed.
(function () {
    'use strict';

    var container = document.querySelector('.ee-toasts');
    if (!container) return;

    var VISIBLE_MS = 6000;
    var ERROR_VISIBLE_MS = 10000;
    var FADE_MS = 300;

    function dismiss(toast) {
        if (!toast.isConnected || toast.classList.contains('is-leaving')) return;
        toast.classList.add('is-leaving');
        setTimeout(function () { toast.remove(); }, FADE_MS);
    }

    container.querySelectorAll('.ee-toast').forEach(function (toast) {
        var isError = toast.classList.contains('ee-toast--error');
        setTimeout(function () { dismiss(toast); }, isError ? ERROR_VISIBLE_MS : VISIBLE_MS);
    });

    container.addEventListener('click', function (event) {
        var close = event.target.closest('.ee-toast-close');
        if (close) dismiss(close.closest('.ee-toast'));
    });
})();
