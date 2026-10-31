(() => {
  'use strict';
  const state = { products: [], cart: [] };
  const API = String(window.THREEDS_API_BASE || '').replace(/\/$/, '');
  const money = p => new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(p / 100);
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const shapeByKind = {};
  document.querySelectorAll('.product-card').forEach(card => {
    const id = card.querySelector('[data-add]')?.dataset.add;
    const svg = card.querySelector('.product-visual svg');
    if (id && svg) shapeByKind[id] = svg.outerHTML;
  });
  const legacyShapes = Object.values(shapeByKind);

  function loadCart() {
    try { state.cart = JSON.parse(localStorage.getItem('threeds-cart-v1') || '[]'); } catch { state.cart = []; }
    if (!Array.isArray(state.cart)) state.cart = [];
  }
  function saveCart() { localStorage.setItem('threeds-cart-v1', JSON.stringify(state.cart)); }
  function product(id) { return state.products.find(p => p.id === id); }
  function toast(message) {
    const el = document.querySelector('#toast'); if (!el) return;
    el.textContent = message; el.classList.add('show'); clearTimeout(toast.timer); toast.timer = setTimeout(() => el.classList.remove('show'), 2600);
  }
  function visual(p, i) {
    if (p.image_url) return `<img src="${esc(p.image_url)}" alt="${esc(p.name)}" style="width:85%;height:93%;object-fit:contain;filter:drop-shadow(1px 19px 13px #32253d29)">`;
    return legacyShapes[['lamp','vase','planter','gift','figure','moon'].indexOf(p.illustration_key)] || legacyShapes[i % legacyShapes.length] || '';
  }
  function renderCatalog() {
    const grid = document.querySelector('#productGrid'); if (!grid) return;
    grid.textContent = '';
    state.products.forEach((p, i) => {
      const article = document.createElement('article');
      article.className = 'product-card reveal visible'; article.dataset.cat = p.category?.slug || 'other';
      const draft = !p.price_verified || !p.allow_checkout;
      article.innerHTML = `<div class="product-visual" role="button" tabindex="0"><span class="product-badge">✳ ${p.featured ? 'STUDIO FAVOURITE' : 'MADE WITH CARE'}</span>${visual(p, i)}<button class="product-add" aria-label="Add ${esc(p.name)}">+</button></div><div class="product-data"><div class="product-data-top"><div><h3>${esc(p.name)}</h3><small>${esc(p.short_description)}</small></div><div class="price">${p.price_paise == null ? 'Ask us' : money(p.price_paise)}<i>${draft ? 'draft price' : 'confirmed price'}</i></div></div></div>`;
      const open = () => showQuickView(p, i);
      article.querySelector('.product-visual').addEventListener('click', e => { if (!e.target.closest('.product-add')) open(); });
      article.querySelector('.product-visual').addEventListener('keydown', e => { if (e.key === 'Enter') open(); });
      article.querySelector('.product-add').addEventListener('click', e => { e.stopPropagation(); add(p); });
      grid.append(article);
    });
  }
  function showQuickView(p, i) {
    document.querySelector('#modalImage').innerHTML = visual(p, i);
    document.querySelector('#modalTitle').textContent = p.name;
    document.querySelector('#modalDescription').textContent = p.description || p.short_description;
    document.querySelector('#modalPrice').textContent = p.price_paise == null ? 'Price on request' : `${money(p.price_paise)}${p.price_verified ? '' : ' · draft'}`;
    const button = document.querySelector('#modalAdd'); button.dataset.liveProduct = p.id; button.textContent = p.allow_checkout && p.price_verified ? '♡ Add to my little bag ↗' : 'Price awaiting confirmation';
    document.querySelector('#overlay').classList.add('show'); document.querySelector('#modal').classList.add('show'); document.body.classList.add('no-scroll');
  }
  function add(p, personalization = '') {
    if (!p.allow_checkout || !p.price_verified || p.price_paise == null) return toast('This price is still a draft — please ask the exhibition team.');
    const found = state.cart.find(x => x.product_id === p.id && x.personalization === personalization);
    if (found) found.quantity += 1; else state.cart.push({ product_id: p.id, quantity: 1, personalization });
    saveCart(); renderCart(); toast(`♡ ${p.name} added to your little bag`);
  }
  function renderCart() {
    state.cart = state.cart.filter(x => product(x.product_id));
    const count = state.cart.reduce((n, x) => n + x.quantity, 0);
    document.querySelector('#bagCount').textContent = count;
    document.querySelector('#cartTotal').textContent = money(state.cart.reduce((n, x) => n + product(x.product_id).price_paise * x.quantity, 0));
    const holder = document.querySelector('#drawerItems'); holder.textContent = '';
    if (!count) { holder.innerHTML = '<div class="empty"><span class="empty-star">✳</span><h3>Nothing in here... yet!</h3><p>Your future favourite little things are waiting.</p></div>'; return; }
    state.cart.forEach((item, index) => {
      const p = product(item.product_id), row = document.createElement('div'); row.className = 'cart-item';
      row.innerHTML = `<div class="cart-thumbnail">${visual(p, state.products.indexOf(p))}</div><div class="cart-info"><strong>${esc(p.name)}</strong><small>${esc(item.personalization || 'A little something special')}</small><div class="cart-line"><div class="qty"><button aria-label="Decrease">−</button><span>${item.quantity}</span><button aria-label="Increase">+</button></div><span class="cart-price">${money(p.price_paise * item.quantity)}</span></div></div>`;
      const buttons = row.querySelectorAll('.qty button');
      buttons[0].addEventListener('click', () => change(index, -1)); buttons[1].addEventListener('click', () => change(index, 1)); holder.append(row);
    });
  }
  function change(index, amount) { state.cart[index].quantity += amount; if (state.cart[index].quantity <= 0) state.cart.splice(index, 1); saveCart(); renderCart(); }
  function bindLiveControls() {
    document.querySelector('#modalAdd')?.addEventListener('click', e => { const p = product(e.currentTarget.dataset.liveProduct); if (p) add(p); }, true);
    document.querySelector('#giftAdd')?.addEventListener('click', e => {
      e.stopImmediatePropagation(); const p = state.products.find(x => x.slug === 'just-for-you-plaque');
      if (p) add(p, `${document.querySelector('#giftName').value.trim() || 'Your name'} · ${document.querySelector('.person-button.active')?.dataset.person || 'You'}`);
    }, true);
  }
  async function start() {
    document.head.insertAdjacentHTML('beforeend', '<style>.brand-control,.brand-settings{display:none!important}.product-data small{display:block;line-height:1.45;max-width:230px}.product-visual>img{transition:transform .6s cubic-bezier(.2,.8,.2,1)}.product-card:hover .product-visual>img{transform:scale(1.08) rotate(-2deg)}</style>');
    loadCart(); bindLiveControls();
    try {
      const apiHeaders = API ? { 'ngrok-skip-browser-warning': 'true' } : {};
      const [products, categories, settings] = await Promise.all(['/api/products','/api/categories','/api/site-settings'].map(url => fetch(API + url, { headers: apiHeaders }).then(r => { if (!r.ok) throw Error(); return r.json(); })));
      state.products = products;
      const filters = document.querySelector('#filters'); filters.textContent = '';
      [{ slug: 'all', name: 'Everything ✳' }, ...categories].forEach((c, i) => { const b = document.createElement('button'); b.className = `chip${i ? '' : ' active'}`; b.textContent = c.name; b.addEventListener('click', () => { filters.querySelectorAll('.chip').forEach(x => x.classList.toggle('active', x === b)); document.querySelectorAll('.product-card').forEach(card => card.classList.toggle('hidden', c.slug !== 'all' && card.dataset.cat !== c.slug)); }); filters.append(b); });
      document.documentElement.style.setProperty('--primary', settings.primary_color); document.documentElement.style.setProperty('--warm', settings.secondary_color); document.documentElement.style.setProperty('--bg', settings.background_color); document.documentElement.style.setProperty('--ink', settings.text_color);
      if (settings.logo_url) { const img = document.querySelector('#brandImage'); img.src = settings.logo_url; img.style.display = 'block'; document.querySelector('#brandFallback').style.display = 'none'; }
      const note = document.querySelector('.topnote'); if (note) note.textContent = settings.banner;
      renderCatalog(); renderCart();
      if (API) document.querySelectorAll('a[href="checkout.html"]').forEach(link => link.addEventListener('click', async event => { event.preventDefault(); try { const response = await fetch(API + '/api/guest-cart-handoff', { method: 'POST', headers: { 'Content-Type': 'application/json', 'ngrok-skip-browser-warning': 'true' }, body: JSON.stringify({ items: state.cart }) }); if (!response.ok) throw Error(); const handoff = await response.json(); location.href = `${API}/checkout?handoff=${encodeURIComponent(handoff.handoff)}`; } catch { toast('Cross-site checkout is unavailable. Please open the exhibition QR store.'); } }));
    } catch { state.products = []; renderCart(); toast('Ordering temporarily unavailable — please speak to our exhibition team.'); }
  }
  start();
})();
