// Friends: filter the friends list as you type. Each card carries data-name and data-username.
(function () {
    'use strict';

    var input = document.getElementById('friendSearch');
    var grid = document.getElementById('friendsGrid');
    if (!input || !grid) return;

    var cards = Array.prototype.slice.call(grid.querySelectorAll('.ee-person-card'));

    input.addEventListener('input', function () {
        var query = input.value.trim().toLowerCase();
        cards.forEach(function (card) {
            var text = (card.dataset.name || '') + ' ' + (card.dataset.username || '');
            card.hidden = query !== '' && text.indexOf(query) === -1;
        });
    });
})();
