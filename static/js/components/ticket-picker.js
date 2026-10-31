// Ticket picker: quantity steppers per ticket tier, a running total, and a limit on tickets per order.
//
// Markup (see templates/events/detail/_ticket_card.html and templates/events/event_booking_form.html):
//   [data-ee-tickets data-max-tickets="6" data-book-url="...">     the container (a card or the whole form)
//     [data-tier] > input[data-qty data-category-id data-price data-max] + [data-step="up|down"]
//   [data-total-amount] [data-total-count]                           anywhere on the page, updated live
//   [data-checkout]                                                  on the event page: goes to data-book-url
// Inside a <form>, submitting with no tickets is stopped and [data-ticket-error] is shown.
(function () {
    'use strict';

    var picker = document.querySelector('[data-ee-tickets]');
    if (!picker) return;

    var MAX = parseInt(picker.dataset.maxTickets, 10) || 6;
    var bookUrl = picker.dataset.bookUrl;
    var inputs = Array.prototype.slice.call(picker.querySelectorAll('[data-qty]'));
    var amounts = document.querySelectorAll('[data-total-amount]');
    var counts = document.querySelectorAll('[data-total-count]');
    var checkout = document.querySelectorAll('[data-checkout]');
    var error = document.querySelector('[data-ticket-error]');

    function quantity(input) {
        return Math.max(0, parseInt(input.value, 10) || 0);
    }

    function money(value) {
        return '৳' + value.toLocaleString('en-US', { maximumFractionDigits: 0 });
    }

    function totalTickets() {
        return inputs.reduce(function (sum, input) { return sum + quantity(input); }, 0);
    }

    function update() {
        var tickets = 0;
        var total = 0;
        inputs.forEach(function (input) {
            var qty = quantity(input);
            tickets += qty;
            total += qty * (parseFloat(input.dataset.price) || 0);
        });

        inputs.forEach(function (input) {
            var qty = quantity(input);
            var available = parseInt(input.dataset.max, 10) || 0;
            var room = Math.min(available, MAX - tickets + qty);
            var row = input.closest('[data-tier]');
            input.max = room;
            row.querySelector('[data-step="up"]').disabled = qty >= room;
            row.querySelector('[data-step="down"]').disabled = qty <= 0;
        });

        amounts.forEach(function (node) { node.textContent = money(total); });
        counts.forEach(function (node) { node.textContent = tickets + ' of ' + MAX + ' tickets'; });
        checkout.forEach(function (button) { button.disabled = tickets === 0 || tickets > MAX; });
        if (error && tickets > 0) error.hidden = true;
    }

    function set(input, value) {
        var max = parseInt(input.max, 10);
        input.value = Math.max(0, Math.min(isNaN(max) ? value : max, value));
        update();
    }

    inputs.forEach(function (input) {
        input.addEventListener('input', function () { set(input, quantity(input)); });
        input.addEventListener('keydown', function (event) {
            if (['-', '+', 'e', 'E', '.'].indexOf(event.key) !== -1) event.preventDefault();
        });
    });

    picker.addEventListener('click', function (event) {
        var step = event.target.closest('[data-step]');
        if (!step) return;
        var input = step.closest('[data-tier]').querySelector('[data-qty]');
        set(input, quantity(input) + (step.dataset.step === 'up' ? 1 : -1));
    });

    if (bookUrl) {
        checkout.forEach(function (button) {
            button.addEventListener('click', function () {
                var params = new URLSearchParams();
                inputs.forEach(function (input) {
                    var qty = quantity(input);
                    if (qty > 0) params.append('quantity_' + input.dataset.categoryId, qty);
                });
                window.location.href = bookUrl + '?' + params.toString();
            });
        });
    }

    var form = picker.closest('form') || (picker.matches('form') ? picker : null);
    if (form) {
        form.addEventListener('submit', function (event) {
            var tickets = totalTickets();
            if (tickets > 0 && tickets <= MAX) return;
            event.preventDefault();
            if (error) {
                error.hidden = false;
                error.scrollIntoView({ behavior: 'smooth', block: 'center' });
            }
        });
    }

    update();
})();
