const filters = document.querySelector(".filters");
const query = document.getElementById("query");
const kind = document.getElementById("kind");
const trackerStatus = document.getElementById("tracker-status");
const scope = document.getElementById("scope");
const count = document.getElementById("results-count");
const { format, empty } = count.dataset;

function normalize(value) {
  return value.toLowerCase().replace(/[#\s]+/g, " ").trim();
}

const rows = Array.from(document.querySelectorAll("#case-rows tr"), row => ({
  row,
  search: normalize(row.textContent + " " + row.dataset.titleAlt),
}));

function filterIssues() {
  const terms = normalize(query.value).split(" ").filter(Boolean);
  let matches = 0;
  for (const { row, search } of rows) {
    const visible = terms.every(term => search.includes(term)) &&
      (!kind.value || kind.value === row.dataset.kind) &&
      (!trackerStatus.value || trackerStatus.value === row.dataset.trackerStatus) &&
      (!scope.value || scope.value === row.dataset.scope);
    row.hidden = !visible;
    if (visible) matches += 1;
  }
  count.textContent = matches ? format.replace("{matches}", matches).replace("{total}", rows.length) : empty;
}

filters.hidden = false;
filters.addEventListener("input", filterIssues);
window.addEventListener("pageshow", filterIssues);
