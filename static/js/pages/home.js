// Home page: the posters on the wall lean toward the cursor.
(function () {
    'use strict';

    var wall = document.querySelector('[data-lean]');
    if (!wall) return;
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    if (!window.matchMedia('(hover: hover)').matches) return;

    var frame = null;
    var target = 0;

    window.addEventListener('pointermove', function (event) {
        // -1 at the left edge of the viewport, 1 at the right
        target = (event.clientX / window.innerWidth) * 2 - 1;
        if (frame) return;
        frame = requestAnimationFrame(function () {
            wall.style.setProperty('--lean', target.toFixed(3));
            frame = null;
        });
    }, { passive: true });
})();
