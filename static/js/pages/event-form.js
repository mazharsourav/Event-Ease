// Event form: the price field follows "free event", and ticket tiers can be added and removed.
//
// Tiers: [data-tiers data-prefix="tickets" data-max="5"] holds [data-tier-list], a <template data-tier-template>
// whose field names contain __prefix__, and the [data-add-tier] button. Removing a tier ticks its DELETE box and
// hides it, so the form indexes stay in step with the formset's TOTAL_FORMS.
(function () {
    'use strict';

    // ---------- Free event ----------
    var free = document.querySelector('[name="is_free"]');
    var price = document.querySelector('[name="ticket_price"]');
    var priceRow = document.querySelector('[data-price-row]');
    var tiers = document.querySelector('[data-tiers]');

    function syncFree() {
        if (!free || !price) return;
        var isFree = free.checked;
        price.disabled = isFree;
        price.required = !isFree;
        if (isFree) price.value = '0.00';
        else if (price.value === '0.00') price.value = '';
        if (priceRow) priceRow.hidden = isFree;
        if (tiers) {
            tiers.hidden = isFree;
            // Hidden tiers must not be sent, or a free event would be saved as paid
            tiers.querySelectorAll('input, select, textarea').forEach(function (control) {
                if (!/-(TOTAL|INITIAL|MIN_NUM|MAX_NUM)_FORMS$/.test(control.name)) control.disabled = isFree;
            });
        }
    }
    if (free) {
        free.addEventListener('change', syncFree);
        syncFree();
    }

    // A disabled price is not sent, which would fail the form; send the zero instead
    var form = document.getElementById('eventForm');
    if (form && price) {
        form.addEventListener('submit', function () {
            if (free && free.checked) price.disabled = false;
        });
    }

    // ---------- Ticket tiers ----------
    if (!tiers) return;

    var prefix = tiers.dataset.prefix;
    var max = parseInt(tiers.dataset.max, 10) || 5;
    var list = tiers.querySelector('[data-tier-list]');
    var template = tiers.querySelector('[data-tier-template]');
    var add = tiers.querySelector('[data-add-tier]');
    var total = document.getElementById('id_' + prefix + '-TOTAL_FORMS');
    if (!list || !template || !add || !total) return;

    function visible() {
        return Array.prototype.filter.call(list.querySelectorAll('[data-tier-form]'), function (node) { return !node.hidden; });
    }

    function number() {
        visible().forEach(function (node, position) {
            var legend = node.querySelector('legend');
            if (legend) legend.textContent = 'Ticket tier ' + (position + 1);
        });
        add.disabled = visible().length >= max;
        add.textContent = add.disabled ? 'Maximum of ' + max + ' tiers' : 'Add a tier';
    }

    add.addEventListener('click', function () {
        if (visible().length >= max) return;
        var index = parseInt(total.value, 10) || 0;
        var html = template.innerHTML.replace(/__prefix__/g, String(index));
        list.insertAdjacentHTML('beforeend', html);
        total.value = index + 1;
        number();
        var fresh = list.lastElementChild;
        var first = fresh && fresh.querySelector('input');
        if (first) first.focus();
    });

    list.addEventListener('click', function (event) {
        var remove = event.target.closest('[data-remove-tier]');
        if (!remove) return;
        var node = remove.closest('[data-tier-form]');
        var del = node.querySelector('input[name$="-DELETE"]');
        if (del) del.checked = true;
        node.hidden = true;
        number();
    });

    number();
})();
