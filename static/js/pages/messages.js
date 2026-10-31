// Messages: a two-pane chat. The list of conversations is on the left; picking one loads its messages,
// polls for new ones every few seconds, and lets you send text and files.
//
// The root carries its endpoints: [data-ee-chat data-user-id data-messages-url data-send-url data-send-files-url],
// where data-messages-url has a 0 in place of the other person's id.
(function () {
    'use strict';

    var root = document.querySelector('[data-ee-chat]');
    if (!root) return;

    var POLL_MS = 3000;
    var NEAR_BOTTOM_PX = 60;

    var me = parseInt(root.dataset.userId, 10);
    var el = {
        people: root.querySelectorAll('[data-chat-user]'),
        search: document.getElementById('chatSearch'),
        empty: root.querySelector('[data-chat-empty]'),
        open: root.querySelector('[data-chat-open]'),
        name: root.querySelector('[data-chat-name]'),
        avatar: root.querySelector('[data-chat-avatar]'),
        messages: root.querySelector('[data-chat-messages]'),
        newButton: root.querySelector('[data-chat-new]'),
        form: root.querySelector('[data-chat-form]'),
        input: root.querySelector('[data-chat-input]'),
        file: document.getElementById('chatFile'),
        files: root.querySelector('[data-chat-files]'),
        back: root.querySelector('[data-chat-back]')
    };

    var currentUser = null;
    var timer = null;
    var shown = {};      // ids of the messages already on screen
    var shownCount = 0;

    function csrfToken() {
        var field = root.querySelector('[name=csrfmiddlewaretoken]');
        return field ? field.value : '';
    }

    function messagesUrl(id) {
        return root.dataset.messagesUrl.replace(/\/0\//, '/' + id + '/');
    }

    function initials(name) {
        return name.split(/\s+/).map(function (part) { return part.charAt(0); }).join('').slice(0, 2).toUpperCase();
    }

    function nearBottom() {
        var box = el.messages;
        return box.scrollHeight - box.scrollTop - box.clientHeight < NEAR_BOTTOM_PX;
    }

    function scrollToBottom() {
        el.messages.scrollTop = el.messages.scrollHeight;
        el.newButton.hidden = true;
    }

    // ---------- Rendering ----------
    function fileNode(file, mine) {
        var isImage = file.file_type && file.file_type.indexOf('image/') === 0;
        if (isImage) {
            var button = document.createElement('button');
            button.type = 'button';
            button.className = 'ee-chat-image';
            button.dataset.lightbox = file.url;
            button.setAttribute('aria-label', 'Open photo ' + (file.original_name || ''));
            var image = document.createElement('img');
            image.src = file.url;
            image.alt = file.original_name || 'Photo';
            image.loading = 'lazy';
            button.appendChild(image);
            return button;
        }
        var link = document.createElement('a');
        link.className = 'ee-chat-file';
        link.href = file.url;
        link.target = '_blank';
        link.rel = 'noopener';
        link.download = file.original_name || '';
        var size = file.file_size ? ' (' + (file.file_size / 1024).toFixed(1) + ' KB)' : '';
        link.textContent = (file.original_name || 'Attachment') + size;
        return link;
    }

    function bubble(message) {
        var mine = message.sender === me;
        var hasText = message.content && message.content.trim();
        var hasFiles = message.files && message.files.length;
        if (!hasText && !hasFiles) return null;

        var node = document.createElement('div');
        node.className = 'ee-chat-bubble ' + (mine ? 'is-mine' : 'is-theirs');
        node.dataset.id = message.id;

        if (hasText) {
            var text = document.createElement('p');
            text.textContent = message.content;
            node.appendChild(text);
        }
        if (hasFiles) {
            message.files.forEach(function (file) { node.appendChild(fileNode(file, mine)); });
        }
        var time = document.createElement('time');
        time.dateTime = message.created_at;
        time.textContent = new Date(message.created_at).toLocaleString([], { day: 'numeric', month: 'short', hour: 'numeric', minute: '2-digit' });
        node.appendChild(time);
        return node;
    }

    function render(messages, force) {
        var wasNearBottom = nearBottom();
        var added = 0;
        messages.forEach(function (message) {
            if (shown[message.id]) return;
            var node = bubble(message);
            if (!node) return;
            shown[message.id] = true;
            el.messages.appendChild(node);
            added += 1;
        });
        shownCount += added;

        if (force || wasNearBottom) scrollToBottom();
        else if (added) el.newButton.hidden = false;
    }

    // ---------- Loading ----------
    function load(force) {
        if (!currentUser || document.hidden) return;
        var asked = currentUser;
        fetch(messagesUrl(asked), { credentials: 'same-origin', headers: { Accept: 'application/json' } })
            .then(function (response) { return response.json(); })
            .then(function (data) {
                if (asked !== currentUser || !data.messages) return;
                render(data.messages, force);
            })
            .catch(function () { /* try again on the next poll */ });
    }

    function openChat(button) {
        currentUser = button.dataset.chatUser;
        shown = {};
        shownCount = 0;
        el.messages.textContent = '';

        el.name.textContent = button.dataset.name;
        el.avatar.textContent = '';
        if (button.dataset.avatar) {
            var image = document.createElement('img');
            image.src = button.dataset.avatar;
            image.alt = '';
            el.avatar.appendChild(image);
        } else {
            el.avatar.textContent = button.dataset.initials || initials(button.dataset.name);
        }

        el.people.forEach(function (other) { other.classList.toggle('is-active', other === button); });
        var unread = button.querySelector('.ee-count-badge');
        if (unread) unread.remove();

        el.empty.hidden = true;
        el.open.hidden = false;
        root.classList.add('is-chat-open');

        load(true);
        clearInterval(timer);
        timer = setInterval(function () { load(false); }, POLL_MS);
        el.input.focus();
    }

    // ---------- Sending ----------
    function afterSend(data) {
        if (!data.success) return;
        el.input.value = '';
        el.input.style.height = '';
        el.file.value = '';
        renderFiles();
        load(true);
    }

    function send() {
        var content = el.input.value.trim();
        var files = el.file.files;
        if (!currentUser || (!content && !files.length)) return;

        if (files.length) {
            var body = new FormData();
            body.append('receiver_id', currentUser);
            body.append('content', content);
            Array.prototype.forEach.call(files, function (file) { body.append('files', file); });
            fetch(root.dataset.sendFilesUrl, {
                method: 'POST', credentials: 'same-origin', headers: { 'X-CSRFToken': csrfToken() }, body: body
            }).then(function (response) { return response.json(); }).then(afterSend);
            return;
        }

        fetch(root.dataset.sendUrl, {
            method: 'POST',
            credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken() },
            body: JSON.stringify({ receiver_id: currentUser, content: content })
        }).then(function (response) { return response.json(); }).then(afterSend);
    }

    // ---------- Files waiting to be sent ----------
    function renderFiles() {
        var files = Array.prototype.slice.call(el.file.files);
        el.files.textContent = '';
        el.files.hidden = files.length === 0;

        files.forEach(function (file, index) {
            var item = document.createElement('li');
            var label = document.createElement('span');
            label.textContent = file.name + ' (' + (file.size / 1024).toFixed(1) + ' KB)';
            var remove = document.createElement('button');
            remove.type = 'button';
            remove.setAttribute('aria-label', 'Remove ' + file.name);
            remove.textContent = '×';
            remove.addEventListener('click', function () {
                var keep = new DataTransfer();
                files.forEach(function (other, position) { if (position !== index) keep.items.add(other); });
                el.file.files = keep.files;
                renderFiles();
            });
            item.append(label, remove);
            el.files.appendChild(item);
        });
    }

    // ---------- Wiring ----------
    el.people.forEach(function (button) {
        button.addEventListener('click', function () { openChat(button); });
    });

    el.search.addEventListener('input', function () {
        var query = el.search.value.trim().toLowerCase();
        el.people.forEach(function (button) {
            button.closest('li').hidden = query !== '' && button.dataset.name.toLowerCase().indexOf(query) === -1;
        });
    });

    el.form.addEventListener('submit', function (event) {
        event.preventDefault();
        send();
    });
    el.input.addEventListener('keydown', function (event) {
        if (event.key === 'Enter' && !event.shiftKey) {
            event.preventDefault();
            send();
        }
    });
    el.input.addEventListener('input', function () {
        el.input.style.height = 'auto';
        el.input.style.height = Math.min(el.input.scrollHeight, 120) + 'px';
    });
    el.file.addEventListener('change', renderFiles);

    el.newButton.addEventListener('click', scrollToBottom);
    el.messages.addEventListener('scroll', function () {
        if (nearBottom()) el.newButton.hidden = true;
    });
    el.back.addEventListener('click', function () { root.classList.remove('is-chat-open'); });
    document.addEventListener('visibilitychange', function () { if (!document.hidden) load(false); });

    // ?with=<id> opens that conversation straight away
    var wanted = new URLSearchParams(window.location.search).get('with');
    if (wanted) {
        var match = root.querySelector('[data-chat-user="' + wanted + '"]');
        if (match) openChat(match);
    }
})();
