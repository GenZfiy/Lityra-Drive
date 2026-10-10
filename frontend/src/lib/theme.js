// Platform theme (light | dark). Persisted per browser; applied by toggling the
// `.dark` class on <html>, which flips the CSS color tokens in index.css.
const KEY = "lare_theme";

export function getTheme() {
  return localStorage.getItem(KEY) === "dark" ? "dark" : "light";
}

export function applyTheme(t) {
  document.documentElement.classList.toggle("dark", t === "dark");
}

export function setTheme(t) {
  localStorage.setItem(KEY, t);
  applyTheme(t);
}

export function initTheme() {
  applyTheme(getTheme());
}

export function toggleTheme() {
  const next = getTheme() === "dark" ? "light" : "dark";
  setTheme(next);
  return next;
}
