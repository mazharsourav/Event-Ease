// Comments: reply forms, likes and deletes for an event or venue thread.
// The thread root is <section data-ee-comments data-like-url="/events/comment/0/like/" data-delete-url="...">;
// the "0" in each URL is replaced by the comment's id. Buttons carry data-action="reply|cancel|like|delete".
(function () {
    'use strict';

    var root = document.querySelector('[data-ee-comments]');
    if (!root) return;

    var likeUrl = root.dataset.likeUrl;
    var deleteUrl = root.dataset.deleteUrl;
    var signedIn = root.dataset.signedIn === 'true';

    function urlFor(template, id) {
        return template.replace(/\/0\//, '/' + id + '/');
    }

    function csrfToken() {
        var field = document.querySelector('[name=csrfmiddlewaretoken]');
        if (field) return field.value;
        var match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
        return match ? decodeURIComponent(match[1]) : '';
    }

    function post(url) {
        return fetch(url, {
            method: 'POST',
            credentials: 'same-origin',
            headers: { 'X-CSRFToken': csrfToken(), 'Content-Type': 'application/json' }
        }).then(function (response) { return response.json(); });
    }

    function toggleReply(id, show) {
        var form = document.getElementById('reply-form-' + id);
        if (!form) return;
        form.hidden = !show;
        if (show) {
            var field = form.querySelector('textarea');
            if (field) field.focus();
        }
    }

    function like(button) {
        if (!signedIn) {
            window.location.href = root.dataset.loginUrl;
            return;
        }
        var id = button.dataset.id;
        var count = button.querySelector('[data-like-count]');
        button.setAttribute('aria-busy', 'true');

        post(urlFor(likeUrl, id))
            .then(function (data) {
                if (!data.success) return;
                button.dataset.liked = String(data.is_liked);
                button.setAttribute('aria-pressed', String(data.is_liked));
                if (count) count.textContent = data.like_count;
            })
            .catch(function () { /* the count stays as it was */ })
            .then(function () { button.removeAttribute('aria-busy'); });
    }

    function remove(button) {
        var message = 'Delete this comment? This also deletes every reply to it.';
        if (!window.confirm(message)) return;
        var item = button.closest('.ee-comment-item');

        post(urlFor(deleteUrl, button.dataset.id))
            .then(function (data) {
                if (data.success && item) item.remove();
                else window.alert(data.error || 'The comment could not be deleted.');
            })
            .catch(function () { window.alert('The comment could not be deleted. Please try again.'); });
    }

    root.addEventListener('click', function (event) {
        var button = event.target.closest('[data-action]');
        if (!button || !root.contains(button)) return;

        switch (button.dataset.action) {
            case 'reply': toggleReply(button.dataset.id, true); break;
            case 'cancel': toggleReply(button.dataset.id, false); break;
            case 'like': like(button); break;
            case 'delete': remove(button); break;
        }
    });

    if (window.location.hash === '#comments') {
        root.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
})();
