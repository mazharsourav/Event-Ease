// Tabs: [data-ee-tabs] holds buttons[role=tab][aria-controls="panel-id"] and the panels they control.
// Arrow keys move between tabs. Until this runs every panel stays visible (no-JavaScript fallback).
(function () {
    'use strict';

    document.querySelectorAll('[data-ee-tabs]').forEach(function (root) {
        var tabs = Array.prototype.slice.call(root.querySelectorAll('[role="tab"]'));
        if (!tabs.length) return;

        var panels = tabs.map(function (tab) { return document.getElementById(tab.getAttribute('aria-controls')); });
        root.classList.add('js-tabs');

        function select(index, focus) {
            tabs.forEach(function (tab, position) {
                var on = position === index;
                tab.setAttribute('aria-selected', String(on));
                tab.tabIndex = on ? 0 : -1;
                if (panels[position]) panels[position].hidden = !on;
            });
            if (focus) tabs[index].focus();
        }

        tabs.forEach(function (tab, index) {
            tab.addEventListener('click', function () { select(index, false); });
            tab.addEventListener('keydown', function (event) {
                if (event.key === 'ArrowRight') { event.preventDefault(); select((index + 1) % tabs.length, true); }
                else if (event.key === 'ArrowLeft') { event.preventDefault(); select((index - 1 + tabs.length) % tabs.length, true); }
            });
        });

        var start = tabs.findIndex(function (tab) { return tab.getAttribute('aria-selected') === 'true'; });
        select(start < 0 ? 0 : start, false);
    });
})();
