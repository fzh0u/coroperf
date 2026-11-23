const filters = document.querySelector(".filters");
const query = document.getElementById("query");
const kind = document.getElementById("kind");
const caseLanguage = document.getElementById("case-language");
const trackerStatus = document.getElementById("tracker-status");
const contribution = document.getElementById("contribution");
const scope = document.getElementById("scope");
const count = document.getElementById("results-count");
const { format, empty, all } = count.dataset;

function normalize(value) {
  return value.toLowerCase().replace(/[#\s]+/g, " ").trim();
}

const groups = Array.from(document.querySelectorAll("#case-rows .language-group"), group => ({
  group,
  headingCount: group.querySelector("[data-language-count]"),
  rows: Array.from(group.querySelectorAll(".issue-row"), row => ({
    row,
    search: normalize(row.textContent + " " + row.dataset.titleAlt),
  })),
}));
const total = groups.reduce((sum, group) => sum + group.rows.length, 0);

function filterIssues() {
  const terms = normalize(query.value).split(" ").filter(Boolean);
  let matches = 0;
  for (const { group, headingCount, rows } of groups) {
    let groupMatches = 0;
    const languageMatches = !caseLanguage.value || caseLanguage.value === group.dataset.language;
    for (const { row, search } of rows) {
      const visible = languageMatches && terms.every(term => search.includes(term)) &&
        (!kind.value || kind.value === row.dataset.kind) &&
        (!contribution.value || contribution.value === row.dataset.contribution) &&
        (!trackerStatus.value || trackerStatus.value === row.dataset.trackerStatus) &&
        (!scope.value || scope.value === row.dataset.scope);
      row.hidden = !visible;
      if (visible) groupMatches += 1;
    }
    group.hidden = groupMatches === 0;
    headingCount.textContent = headingCount.dataset.format.replace("{count}", groupMatches);
    matches += groupMatches;
  }
  if (matches === total) {
    count.textContent = all;
  } else {
    count.textContent = matches ? format.replace("{matches}", matches).replace("{total}", total) : empty;
  }
}

filters.hidden = false;
filters.addEventListener("input", filterIssues);
window.addEventListener("pageshow", filterIssues);
