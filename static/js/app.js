const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];

function toast(msg) {
  const t = $('#toast'); t.textContent = msg; t.classList.add('show');
  clearTimeout(toast._t); toast._t = setTimeout(() => t.classList.remove('show'), 2400);
}

function ctlHTML(id, qty) {
  if (!qty) return `<button class="add-btn" data-id="${id}">ADD</button>`;
  return `<div class="stepper"><button class="minus" data-id="${id}" aria-label="Remove one">−</button>` +
         `<span class="q">${qty}</span><button class="plus" data-id="${id}" aria-label="Add one">+</button></div>`;
}

async function changeCart(id, delta, replace = false) {
  try {
    const r = await fetch('/cart/change', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ item_id: id, delta, replace })
    });
    const d = await r.json();
    if (d.conflict) { return confirm(d.message) ? changeCart(id, delta, true) : null; }
    if (d.error) { toast(d.error); return null; }
    return d;
  } catch (e) { toast('Network error. Is the server running?'); return null; }
}

function updateBar(count, subtotal) {
  const nav = $('#navcount'); if (nav) nav.textContent = count;
  const bar = $('#cartbar');
  if (bar) {
    $('#barcount').textContent = count; $('#barsub').textContent = subtotal;
    bar.classList.toggle('show', count > 0);
  }
}

document.addEventListener('click', async (e) => {
  const b = e.target.closest('.add-btn, .plus, .minus');
  if (!b) return;
  const id = +b.dataset.id, delta = b.classList.contains('minus') ? -1 : 1;
  const d = await changeCart(id, delta);
  if (!d) return;
  if (document.body.dataset.page === 'cart') { location.reload(); return; }
  const box = $(`.ctl[data-id="${id}"]`);
  if (box) box.innerHTML = ctlHTML(id, d.qty);
  updateBar(d.count, d.subtotal);
  if (delta > 0 && d.qty === 1) toast('Added to cart');
});

// veg-only toggle on restaurant page
const veg = $('#vegonly');
if (veg) veg.addEventListener('change', () =>
  $$('.dish').forEach(el => el.classList.toggle('hide', veg.checked && el.dataset.veg !== '1')));

// click a coupon chip to fill the code box
$$('.coupon-chip').forEach(c => c.addEventListener('click', () => {
  $('#couponInput').value = c.dataset.code; $('#couponInput').focus();
}));

// live order tracking (polls every 5 seconds)
const panel = $('#trackPanel');
if (panel && panel.dataset.status !== 'Delivered' && panel.dataset.status !== 'Cancelled') {
  const iv = setInterval(async () => {
    try {
      const d = await (await fetch(`/api/order/${panel.dataset.oid}/status`)).json();
      $$('#track .step').forEach((s, i) => {
        s.classList.toggle('done', i < d.stage || (i === d.stage && d.stage === 3));
        s.classList.toggle('active', i === d.stage && d.stage < 3);
      });
      const badge = $('#statusBadge');
      badge.textContent = d.status; badge.className = 'status s-' + d.status.replace(/ /g, '');
      if (d.status === 'Delivered') {
        $('#eta').textContent = 'Delivered. Enjoy your meal!'; clearInterval(iv);
      }
      if (d.status === 'Cancelled') location.reload();
    } catch (e) { /* ignore */ }
  }, 5000);
}
