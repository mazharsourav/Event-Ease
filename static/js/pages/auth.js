// Sign up: the two password fields must match before the form is sent.
(function () {
    'use strict';

    var first = document.getElementById('password1');
    var second = document.getElementById('password2');
    if (!first || !second) return;

    function check() {
        second.setCustomValidity(first.value && second.value && first.value !== second.value ? 'The passwords do not match.' : '');
    }
    first.addEventListener('input', check);
    second.addEventListener('input', check);
})();
