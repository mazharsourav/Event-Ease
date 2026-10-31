// Venue booking: a live price estimate from the chosen dates.
// The form carries the rates: [data-ee-estimate data-hourly="2500" data-daily="18000"].
(function () {
    'use strict';

    var form = document.querySelector('[data-ee-estimate]');
    if (!form) return;

    var start = form.querySelector('[name="start_date"]');
    var end = form.querySelector('[name="end_date"]');
    var amount = document.querySelector('[data-estimate-amount]');
    var note = document.querySelector('[data-estimate-note]');
    if (!start || !end || !amount || !note) return;

    var hourly = parseFloat(form.dataset.hourly) || 0;
    var daily = parseFloat(form.dataset.daily) || 0;
    var HOUR = 60 * 60 * 1000;
    var DEFAULT_NOTE = 'Choose your dates to see an estimate. The owner confirms the final price.';

    function money(value) {
        return '৳' + Math.round(value).toLocaleString('en-US');
    }

    function update() {
        var from = new Date(start.value);
        var to = new Date(end.value);
        var hours = (to - from) / HOUR;

        if (isNaN(hours) || hours <= 0) {
            amount.textContent = '—';
            note.textContent = DEFAULT_NOTE;
            return;
        }
        if (hourly > 0) {
            amount.textContent = money(hourly * hours);
            note.textContent = hours.toFixed(1).replace(/\.0$/, '') + ' hours at ' + money(hourly) + ' an hour. The owner confirms the final price.';
        } else if (daily > 0) {
            var days = Math.max(1, Math.ceil(hours / 24));
            amount.textContent = money(daily * days);
            note.textContent = days + ' day' + (days > 1 ? 's' : '') + ' at ' + money(daily) + ' a day. The owner confirms the final price.';
        } else {
            amount.textContent = 'Ask';
            note.textContent = 'This venue quotes a price on request.';
        }
    }

    start.addEventListener('change', update);
    end.addEventListener('change', update);
    update();
})();
