// Wallet payment (bKash, Nagad): digits only, the PIN can be shown, and the PIN is only asked for on a wallet.
// The form carries its PIN length: <form id="walletForm" data-pin-length="5">.
(function () {
    'use strict';

    var form = document.getElementById('walletForm');
    if (!form) return;

    var pinLength = parseInt(form.dataset.pinLength, 10) || 5;
    var mobile = form.querySelector('[name="mobile"]');
    var pin = form.querySelector('[name="pin"]');
    var pinField = form.querySelector('[data-pin-field]');
    var toggle = form.querySelector('[data-pin-toggle]');
    var method = document.getElementById('walletMethod');
    var submit = form.querySelector('[data-submit]');

    function digitsOnly(input, max) {
        input.addEventListener('input', function () {
            input.value = input.value.replace(/[^0-9]/g, '').slice(0, max);
        });
    }
    digitsOnly(mobile, 10);
    digitsOnly(pin, pinLength);

    // The first choice is the wallet itself, which needs a PIN; card and bank do not
    function needsPin() {
        var chosen = form.querySelector('input[name="wallet_choice"]:checked');
        return !chosen || chosen.value === 'wallet' || chosen.value === 'account';
    }

    form.querySelectorAll('input[name="wallet_choice"]').forEach(function (radio) {
        radio.addEventListener('change', function () {
            method.value = radio.value;
            var show = needsPin();
            pinField.hidden = !show;
            pin.required = show;
        });
    });
    pin.required = needsPin();

    toggle.addEventListener('click', function () {
        var hidden = pin.type === 'password';
        pin.type = hidden ? 'text' : 'password';
        toggle.textContent = hidden ? 'Hide' : 'Show';
    });

    form.addEventListener('submit', function (event) {
        if (mobile.value.length !== 10 || mobile.value.charAt(0) !== '1') {
            event.preventDefault();
            mobile.setCustomValidity('Enter a 10-digit mobile number that starts with 1.');
            mobile.reportValidity();
            mobile.setCustomValidity('');
            return;
        }
        if (needsPin() && pin.value.length !== pinLength) {
            event.preventDefault();
            pin.setCustomValidity('Enter your ' + pinLength + '-digit PIN.');
            pin.reportValidity();
            pin.setCustomValidity('');
            return;
        }
        submit.disabled = true;
        submit.textContent = 'Processing…';
    });
})();
