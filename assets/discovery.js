(() => {
  const rows = Array.from(document.querySelectorAll('[data-candidate]'));
  const container = document.getElementById('discovery-rows');
  if (!container) return;
  const zh = document.documentElement.lang === 'zh-CN';
  const controls = Object.fromEntries(['search', 'domain', 'status', 'state', 'order'].map(name => [name, document.getElementById(`discovery-${name}`)]));
  const count = document.getElementById('discovery-count');
  const previous = document.getElementById('discovery-previous');
  const next = document.getElementById('discovery-next');
  const pageLabel = document.getElementById('discovery-page');
  let page = 0;
  const size = 30;
  const texts = new Map(rows.map(row => [row, row.textContent.toLocaleLowerCase()]));
  function update() {
    const term = controls.search.value.toLocaleLowerCase().trim();
    const filtered = rows.filter(row => (!term || texts.get(row).includes(term)) && ['domain', 'status', 'state'].every(key => !controls[key].value || row.dataset[key] === controls[key].value));
    filtered.sort((a, b) => controls.order.value === 'heat' ? Number(b.dataset.heat) - Number(a.dataset.heat) : Number(a.dataset.rank) - Number(b.dataset.rank) || Number(b.dataset.heat) - Number(a.dataset.heat));
    const pages = Math.max(1, Math.ceil(filtered.length / size));
    page = Math.min(page, pages - 1);
    rows.forEach(row => { row.hidden = true; });
    filtered.slice(page * size, (page + 1) * size).forEach(row => { row.hidden = false; container.appendChild(row); });
    count.textContent = zh ? `${filtered.length} 条命中；共 ${rows.length} 条` : `${filtered.length} matches of ${rows.length} search hits`;
    pageLabel.textContent = zh ? `第 ${page + 1} / ${pages} 页` : `Page ${page + 1} of ${pages}`;
    previous.disabled = page === 0;
    next.disabled = page + 1 === pages;
  }
  Object.values(controls).forEach(control => control.addEventListener('input', () => { page = 0; update(); }));
  previous.addEventListener('click', () => { page--; update(); });
  next.addEventListener('click', () => { page++; update(); });
  document.querySelector('.discovery-pager').hidden = false;
  update();
})();
