// Conversation: start at the newest message, grow the box as you type, send with Enter (Shift+Enter for a new line).
(function () {
    'use strict';

    var area = document.getElementById('messagesArea');
    var input = document.getElementById('messageInput');
    var form = document.getElementById('messageForm');
    if (!area || !input || !form) return;

    area.scrollTop = area.scrollHeight;

    input.addEventListener('input', function () {
        input.style.height = 'auto';
        input.style.height = Math.min(input.scrollHeight, 120) + 'px';
    });

    input.addEventListener('keydown', function (event) {
        if (event.key === 'Enter' && !event.shiftKey) {
            event.preventDefault();
            if (input.value.trim()) form.submit();
        }
    });

    form.addEventListener('submit', function (event) {
        if (!input.value.trim()) event.preventDefault();
    });
})();
