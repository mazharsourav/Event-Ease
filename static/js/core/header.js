// Site header: the hairline under the bar once content scrolls beneath it,
// and closing the small-screen menu when you click elsewhere, press Escape or pick a link.
(function () {
    'use strict';

    var nav = document.querySelector('.ee-nav');
    if (!nav) return;

    var STUCK_AFTER = 8;
    function updateStuck() {
        nav.classList.toggle('is-stuck', window.scrollY > STUCK_AFTER);
    }
    window.addEventListener('scroll', updateStuck, { passive: true });
    updateStuck();

    var menu = nav.querySelector('.ee-menu');
    if (!menu) return;

    document.addEventListener('click', function (event) {
        if (menu.open && !menu.contains(event.target)) menu.open = false;
    });
    menu.addEventListener('click', function (event) {
        if (event.target.closest('a')) menu.open = false;
    });
    document.addEventListener('keydown', function (event) {
        if (event.key === 'Escape' && menu.open) {
            menu.open = false;
            menu.querySelector('summary').focus();
        }
    });
})();
