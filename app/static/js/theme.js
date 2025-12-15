/**
 * Canventory - Theme Management
 * Handles light/dark mode toggle and persistence
 */

export const ThemeManager = {
  STORAGE_KEY: "canventory_theme",

  init() {
    // Load saved theme or detect system preference
    const savedTheme = localStorage.getItem(this.STORAGE_KEY);
    if (savedTheme) {
      this.setTheme(savedTheme);
    } else if (window.matchMedia("(prefers-color-scheme: dark)").matches) {
      this.setTheme("dark");
    } else {
      this.setTheme("light");
    }

    // Listen for system theme changes
    window
      .matchMedia("(prefers-color-scheme: dark)")
      .addEventListener("change", (e) => {
        if (!localStorage.getItem(this.STORAGE_KEY)) {
          this.setTheme(e.matches ? "dark" : "light");
        }
      });
  },

  setTheme(theme) {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem(this.STORAGE_KEY, theme);

    // Update meta theme-color for mobile browsers
    const metaThemeColor = document.querySelector('meta[name="theme-color"]');
    if (metaThemeColor) {
      metaThemeColor.setAttribute(
        "content",
        theme === "dark" ? "#1a1815" : "#faf6f0"
      );
    }
  },

  toggle() {
    const currentTheme =
      document.documentElement.getAttribute("data-theme") || "light";
    const newTheme = currentTheme === "dark" ? "light" : "dark";
    this.setTheme(newTheme);
  },

  getCurrentTheme() {
    return document.documentElement.getAttribute("data-theme") || "light";
  },
};

// Make ThemeManager globally available for inline onclick handlers
window.ThemeManager = ThemeManager;

/**
 * Initialize theme toggle buttons
 */
export function initThemeToggle() {
  const toggleButtons = document.querySelectorAll(".theme-toggle");
  toggleButtons.forEach((btn) => {
    btn.addEventListener("click", () => {
      ThemeManager.toggle();
    });
  });
}
