// Confirm before a destructive link or button: <a data-confirm="Delete this event?">.
(function () {
    'use strict';

    document.addEventListener('click', function (event) {
        var target = event.target.closest('[data-confirm]');
        if (!target) return;
        if (!window.confirm(target.dataset.confirm)) {
            event.preventDefault();
            event.stopPropagation();
        }
    });
})();
