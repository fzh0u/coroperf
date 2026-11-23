const languageSwitch = document.getElementById("language-switch");
const alternate = languageSwitch.getAttribute("href");

function revealFragment(hash, scroll) {
  const target = document.getElementById(hash.slice(1));
  if (!target) return;
  let details = target.closest("details");
  if (details) {
    while (details) {
      details.open = true;
      details = details.parentElement.closest("details");
    }
    if (scroll) target.scrollIntoView();
  }
}

function followFragment() {
  languageSwitch.setAttribute("href", alternate + location.hash);
  revealFragment(location.hash, true);
}

window.addEventListener("pageshow", followFragment);
window.addEventListener("hashchange", followFragment);
languageSwitch.addEventListener("click", () => languageSwitch.setAttribute("href", alternate + location.hash));
document.addEventListener("click", event => {
  const link = event.target.closest("a[href^='#']");
  if (link) revealFragment(link.hash, link.hash === location.hash);
});
