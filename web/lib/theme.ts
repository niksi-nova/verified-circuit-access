export const THEME_STORAGE_KEY = "braille-press:theme";

export type Theme = "light" | "dark";

export function applyTheme(theme: Theme | "system"): void {
  const root = document.documentElement;
  if (theme === "system") {
    root.removeAttribute("data-theme");
    window.localStorage.removeItem(THEME_STORAGE_KEY);
  } else {
    root.setAttribute("data-theme", theme);
    window.localStorage.setItem(THEME_STORAGE_KEY, theme);
  }
}

export function readStoredTheme(): Theme | "system" {
  try {
    const stored = window.localStorage.getItem(THEME_STORAGE_KEY);
    return stored === "light" || stored === "dark" ? stored : "system";
  } catch {
    return "system";
  }
}

/** Inlined verbatim into a <script> tag by ThemeInitScript; must not
 * reference any module-scope binding (it runs before hydration, outside
 * this module's scope). Kept here only so both copies can be compared. */
export const THEME_INIT_SOURCE = `
(function () {
  try {
    var stored = window.localStorage.getItem("${THEME_STORAGE_KEY}");
    if (stored === "light" || stored === "dark") {
      document.documentElement.setAttribute("data-theme", stored);
    }
  } catch (e) {}
})();
`;
