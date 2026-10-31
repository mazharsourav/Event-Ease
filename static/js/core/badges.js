// Header badges: a dot on the notifications, messages and friends icons when something is waiting.
// Endpoints come from data attributes on [data-ee-badges] (written by templates/includes/site_header.html).
(function () {
    'use strict';

    var root = document.querySelector('[data-ee-badges]');
    if (!root) return;

    var urls = {
        notifications: root.dataset.notificationsUrl,
        social: root.dataset.socialUrl,
        read: {
            notifications: root.dataset.readNotificationsUrl,
            messages: root.dataset.readMessagesUrl,
            friends: root.dataset.readFriendsUrl
        }
    };
    var POLL_MS = 30000;

    function badge(name) {
        return root.querySelector('[data-ee-badge="' + name + '"]');
    }

    function setUnread(name, isUnread) {
        var element = badge(name);
        if (element) element.classList.toggle('has-unread', isUnread);
    }

    function csrfToken() {
        var match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
        return match ? decodeURIComponent(match[1]) : '';
    }

    function getJSON(url) {
        return fetch(url, { credentials: 'same-origin', headers: { Accept: 'application/json' } })
            .then(function (response) {
                if (!response.ok) throw new Error('HTTP ' + response.status);
                return response.json();
            });
    }

    function refresh() {
        if (document.hidden) return;
        getJSON(urls.notifications)
            .then(function (data) { setUnread('notifications', data.count > 0); })
            .catch(function () { /* the dot just keeps its last state */ });
        getJSON(urls.social)
            .then(function (data) {
                setUnread('messages', data.unread_messages > 0);
                setUnread('friends', data.pending_friend_requests > 0);
            })
            .catch(function () {});
    }

    // Opening one of these pages counts as seeing it: tell the server so the dot clears.
    root.addEventListener('click', function (event) {
        var element = event.target.closest('[data-ee-badge]');
        if (!element || !element.classList.contains('has-unread')) return;
        var name = element.dataset.eeBadge;
        var url = urls.read[name];
        if (!url) return;

        // keepalive lets the request finish even though the click navigates away
        fetch(url, {
            method: 'POST',
            credentials: 'same-origin',
            keepalive: true,
            headers: { 'X-CSRFToken': csrfToken(), 'Content-Type': 'application/json' }
        }).then(function (response) {
            if (response.ok) element.classList.remove('has-unread');
        }).catch(function () {});
    });

    document.addEventListener('visibilitychange', refresh);
    setInterval(refresh, POLL_MS);
    refresh();
})();
