// Profile: check the chosen photo and show it in place before the form is sent.
(function () {
    'use strict';

    var input = document.getElementById('avatar');
    var preview = document.getElementById('avatarPreview');
    if (!input || !preview) return;

    var MAX_BYTES = 5 * 1024 * 1024;

    input.addEventListener('change', function () {
        var file = input.files && input.files[0];
        if (!file) return;

        if (file.size > MAX_BYTES) {
            input.value = '';
            input.setCustomValidity('Choose a photo under 5 MB.');
            input.reportValidity();
            input.setCustomValidity('');
            return;
        }
        if (file.type.indexOf('image/') !== 0) {
            input.value = '';
            input.setCustomValidity('Choose an image file.');
            input.reportValidity();
            input.setCustomValidity('');
            return;
        }

        var reader = new FileReader();
        reader.onload = function (event) {
            var image = document.createElement('img');
            image.src = event.target.result;
            image.alt = 'Preview of your new photo';
            preview.textContent = '';
            preview.appendChild(image);
        };
        reader.readAsDataURL(file);
    });
})();
