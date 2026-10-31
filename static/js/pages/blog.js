// Blog: reaction buttons. A [data-react] button posts its data-type to its data-url and the page reflects the answer.
// Buttons that share a [data-react-group] act like a radio group: choosing one clears the others.
// Without JavaScript the buttons do nothing, and the post page still reads fine.
(function () {
    'use strict';

    function csrfToken() {
        var match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
        if (match) return decodeURIComponent(match[1]);
        var field = document.querySelector('[name=csrfmiddlewaretoken]');
        return field ? field.value : '';
    }

    function apply(button, data) {
        var scope = button.closest('[data-react-group]') || button;
        var buttons = scope.matches('[data-react]') ? [scope] : scope.querySelectorAll('[data-react]');

        Array.prototype.forEach.call(buttons, function (other) {
            var on = data.status === 'success' && other.dataset.type === data.reaction_type;
            other.setAttribute('aria-pressed', String(on));
        });
        Array.prototype.forEach.call(scope.querySelectorAll('[data-react-count]'), function (count) {
            count.textContent = data.reactions_count;
        });
    }

    document.addEventListener('click', function (event) {
        var button = event.target.closest('[data-react]');
        if (!button) return;

        button.setAttribute('aria-busy', 'true');
        fetch(button.dataset.url, {
            method: 'POST',
            credentials: 'same-origin',
            headers: { 'X-CSRFToken': csrfToken(), 'Content-Type': 'application/x-www-form-urlencoded' },
            body: 'reaction_type=' + encodeURIComponent(button.dataset.type)
        })
            .then(function (response) { return response.json(); })
            .then(function (data) {
                if (data.status === 'success' || data.status === 'removed') apply(button, data);
            })
            .catch(function () { /* the count stays as it was */ })
            .then(function () { button.removeAttribute('aria-busy'); });
    });
})();
