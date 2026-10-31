// Dropdown: draws the list of every <select> inside an .ee-field, in place of the operating system's list.
// The real <select> stays in the form (visually hidden) and remains the source of truth for submission,
// so forms still work without JavaScript. Styles: css/components/dropdown.css.
(function () {
    'use strict';

    var selects = document.querySelectorAll('.ee-field select');
    if (!selects.length) return;

    var dropdowns = [];

    function closeOthers(except) {
        dropdowns.forEach(function (dropdown) {
            if (dropdown !== except) dropdown.close(false);
        });
    }

    selects.forEach(function (select, index) {
        var field = select.closest('.ee-field');
        var caption = field.querySelector(':scope > span');
        if (!caption) return;

        var captionId = 'ee-select-label-' + index;
        var buttonId = 'ee-select-btn-' + index;
        caption.id = captionId;

        var button = document.createElement('button');
        button.type = 'button';
        button.id = buttonId;
        button.className = 'ee-select-btn';
        button.setAttribute('aria-haspopup', 'listbox');
        button.setAttribute('aria-expanded', 'false');
        button.setAttribute('aria-labelledby', captionId + ' ' + buttonId);

        var menu = document.createElement('ul');
        menu.className = 'ee-select-menu';
        menu.setAttribute('role', 'listbox');
        menu.setAttribute('aria-labelledby', captionId);
        menu.hidden = true;

        var items = Array.prototype.map.call(select.options, function (option) {
            var item = document.createElement('li');
            item.className = 'ee-select-opt';
            item.setAttribute('role', 'option');
            item.tabIndex = -1;
            item.dataset.value = option.value;
            item.textContent = option.textContent;
            menu.appendChild(item);
            return item;
        });

        function sync() {
            var current = select.options[select.selectedIndex];
            button.textContent = current ? current.textContent : '';
            items.forEach(function (item) {
                item.setAttribute('aria-selected', String(item.dataset.value === select.value));
            });
        }

        function open() {
            closeOthers(dropdown);
            menu.hidden = false;
            button.setAttribute('aria-expanded', 'true');
            var selected = items.filter(function (item) {
                return item.getAttribute('aria-selected') === 'true';
            })[0];
            (selected || items[0]).focus();
        }

        function close(returnFocus) {
            if (menu.hidden) return;
            menu.hidden = true;
            button.setAttribute('aria-expanded', 'false');
            if (returnFocus) button.focus();
        }

        function choose(item) {
            select.value = item.dataset.value;
            select.dispatchEvent(new Event('change', { bubbles: true }));
            sync();
            close(true);
        }

        var dropdown = { close: close };
        dropdowns.push(dropdown);

        select.classList.add('ee-select-native');
        select.tabIndex = -1;
        select.setAttribute('aria-hidden', 'true');
        select.after(button, menu);
        sync();

        // Clicking anywhere on the field, including its caption, toggles the list
        field.addEventListener('click', function (event) {
            if (menu.contains(event.target)) return;
            event.preventDefault();
            if (menu.hidden) open(); else close(false);
        });

        menu.addEventListener('click', function (event) {
            event.preventDefault();
            var item = event.target.closest('.ee-select-opt');
            if (item) choose(item);
        });

        button.addEventListener('keydown', function (event) {
            if (['ArrowDown', 'ArrowUp', 'Enter', ' '].indexOf(event.key) === -1) return;
            event.preventDefault();
            if (menu.hidden) open();
        });

        menu.addEventListener('keydown', function (event) {
            var at = items.indexOf(document.activeElement);
            switch (event.key) {
                case 'ArrowDown':
                    event.preventDefault();
                    items[Math.min(at + 1, items.length - 1)].focus();
                    break;
                case 'ArrowUp':
                    event.preventDefault();
                    items[Math.max(at - 1, 0)].focus();
                    break;
                case 'Home':
                    event.preventDefault();
                    items[0].focus();
                    break;
                case 'End':
                    event.preventDefault();
                    items[items.length - 1].focus();
                    break;
                case 'Enter':
                case ' ':
                    event.preventDefault();
                    if (at > -1) choose(items[at]);
                    break;
                case 'Escape':
                    event.preventDefault();
                    close(true);
                    break;
                case 'Tab':
                    close(false);
                    break;
                default:
                    if (event.key.length === 1) focusByTyping(event.key, at);
            }
        });

        // Typing a letter jumps to the next option that starts with it
        function focusByTyping(key, at) {
            var typed = key.toLowerCase();
            var ordered = items.slice(at + 1).concat(items.slice(0, at + 1));
            var hit = ordered.filter(function (item) {
                return item.textContent.trim().toLowerCase().indexOf(typed) === 0;
            })[0];
            if (hit) hit.focus();
        }
    });

    document.addEventListener('click', function (event) {
        if (!event.target.closest('.ee-field')) closeOthers(null);
    });
})();
