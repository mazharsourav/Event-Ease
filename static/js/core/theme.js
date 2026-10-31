// Theme: light or dark, remembered between visits.
// This file is loaded as the first thing in <body>, so the saved theme is applied before anything paints.
(function () {
    'use strict';

    var STORAGE_KEY = 'darkMode';
    var STORAGE_ON = 'enabled';
    var DARK_CLASS = 'dark-mode';

    function read() {
        try { return localStorage.getItem(STORAGE_KEY) === STORAGE_ON; } catch (e) { return false; }
    }

    function write(isDark) {
        try {
            if (isDark) localStorage.setItem(STORAGE_KEY, STORAGE_ON);
            else localStorage.removeItem(STORAGE_KEY);
        } catch (e) { /* storage blocked: the theme still switches, it just isn't remembered */ }
    }

    var body = document.body;
    if (read()) body.classList.add(DARK_CLASS);

    document.addEventListener('DOMContentLoaded', function () {
        var button = document.getElementById('toggle-mode');
        if (!button) return;

        function reflect() { button.setAttribute('aria-pressed', String(body.classList.contains(DARK_CLASS))); }
        reflect();

        button.addEventListener('click', function () {
            var isDark = body.classList.toggle(DARK_CLASS);
            write(isDark);
            reflect();
        });
    });
})();
