let transitionTimer: ReturnType<typeof setTimeout> | undefined;

/** Animate explicit theme changes without animating the saved theme on load. */
export function transitionTheme(dark: boolean) {
  const root = document.documentElement;
  clearTimeout(transitionTimer);

  root.setAttribute("data-theme-transition", "");
  // Commit the transition styles before changing the palette.
  root.getBoundingClientRect();
  transitionTimer = setTimeout(() => root.removeAttribute("data-theme-transition"), 400);

  root.classList.toggle("dark", dark);
  localStorage.setItem("firelens-dark", dark ? "1" : "0");
}
