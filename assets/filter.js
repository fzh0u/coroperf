const filters = document.querySelector(".filters");
const query = document.getElementById("query");
const state = document.getElementById("state");
const origin = document.getElementById("origin");
const count = document.getElementById("results-count");
const rows = Array.from(document.querySelectorAll("#case-rows tr"), row => ({
  row,
  search: row.textContent.toLowerCase().replace(/\s+/g, " "),
}));

function filterIssues() {
  const terms = query.value.trim().toLowerCase().split(/\s+/).filter(Boolean);
  let matches = 0;
  for (const { row, search } of rows) {
    const visible = terms.every(term => search.includes(term)) &&
      (!state.value || state.value === row.dataset.state) &&
      (!origin.value || origin.value === row.dataset.reviewed);
    row.hidden = !visible;
    if (visible) matches += 1;
  }
  count.textContent = matches ? `${matches} of ${rows.length} issues` : "No issues match these filters";
}

filters.hidden = false;
filters.addEventListener("input", filterIssues);
window.addEventListener("pageshow", filterIssues);
