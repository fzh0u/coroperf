(() => {
  const controls = document.getElementById('batch-controls');
  const count = document.getElementById('batch-count');
  if (!controls || !count) return;
  const search = document.getElementById('batch-search');
  const repository = document.getElementById('batch-repository');
  const status = document.getElementById('batch-status');
  const rows = Array.from(document.querySelectorAll('[data-batch-review]'));
  const texts = new Map(rows.map(row => [row, `${row.textContent} ${row.dataset.repository}`.toLocaleLowerCase()]));
  const zh = document.documentElement.lang === 'zh-CN';
  function update() {
    const term = search.value.trim().toLocaleLowerCase();
    let shown = 0;
    rows.forEach(row => {
      const match = (!term || texts.get(row).includes(term)) &&
        (!repository.value || row.dataset.repository === repository.value) &&
        (!status.value || row.dataset.status === status.value);
      row.hidden = !match;
      if (match) shown += 1;
    });
    count.textContent = zh ? `显示 ${shown} / ${rows.length} 项结论` : `Showing ${shown} / ${rows.length} reviews`;
  }
  search.addEventListener('input', update);
  repository.addEventListener('change', update);
  status.addEventListener('change', update);
  controls.hidden = false;
  update();
})();
