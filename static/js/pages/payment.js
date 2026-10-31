// Payment page: bKash and Nagad have their own screens; the other methods post this form.
// Quick pay (demo) marks the booking paid through the quick-pay endpoint.
(function () {
    'use strict';

    var form = document.getElementById('paymentForm');
    if (!form) return;

    form.addEventListener('submit', function (event) {
        var chosen = form.querySelector('input[name="payment_method"]:checked');
        if (!chosen) return;
        var target = { bkash: form.dataset.bkashUrl, nagad: form.dataset.nagadUrl }[chosen.value];
        if (target) {
            event.preventDefault();
            window.location.href = target;
        }
    });

    var quickPay = document.getElementById('quickPay');
    if (!quickPay) return;

    function csrfToken() {
        var field = form.querySelector('[name=csrfmiddlewaretoken]');
        return field ? field.value : '';
    }

    quickPay.addEventListener('click', function () {
        if (!window.confirm('Mark this booking as paid straight away? (Demo only)')) return;
        quickPay.disabled = true;

        fetch(quickPay.dataset.url, {
            method: 'POST',
            credentials: 'same-origin',
            headers: { 'X-CSRFToken': csrfToken(), 'Content-Type': 'application/json' }
        })
            .then(function (response) { return response.json(); })
            .then(function (data) {
                if (data.success) {
                    window.location.href = quickPay.dataset.next;
                } else {
                    quickPay.disabled = false;
                    window.alert(data.message || 'The payment could not be completed.');
                }
            })
            .catch(function () {
                quickPay.disabled = false;
                window.alert('Something went wrong during the payment. Please try again.');
            });
    });
})();
