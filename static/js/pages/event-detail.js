// Event detail: the registration countdown.
// [data-deadline="<ISO time>"] is written by templates/events/detail/_ticket_card.html.
(function () {
    'use strict';

    var deadlineLabel = document.querySelector('[data-deadline]');
    if (deadlineLabel) {
        var deadline = new Date(deadlineLabel.dataset.deadline);
        var MINUTE = 60 * 1000;
        var HOUR = 60 * MINUTE;
        var DAY = 24 * HOUR;

        var tick = function () {
            var left = deadline - new Date();
            if (isNaN(left)) return;
            if (left <= 0) {
                deadlineLabel.textContent = 'Registration has closed';
                deadlineLabel.dataset.state = 'closed';
                return;
            }
            var days = Math.floor(left / DAY);
            var hours = Math.floor((left % DAY) / HOUR);
            var minutes = Math.floor((left % HOUR) / MINUTE);

            if (days > 0) deadlineLabel.textContent = 'Registration closes in ' + days + 'd ' + hours + 'h';
            else deadlineLabel.textContent = 'Registration closes in ' + hours + 'h ' + minutes + 'm';
            deadlineLabel.dataset.state = days === 0 && hours === 0 && minutes <= 30 ? 'urgent' : 'open';
        };
        tick();
        setInterval(tick, 30 * 1000);
    }
})();
