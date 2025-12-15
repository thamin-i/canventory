/**
 * Canventory - Modal System
 * Reusable modal dialogs for alerts, confirms, and delete confirmations
 */

export const Modal = {
  overlay: null,
  container: null,
  resolvePromise: null,

  init() {
    this.overlay = document.getElementById("modal-overlay");
    this.container = document.getElementById("modal-container");

    if (!this.overlay) return;

    // Close on overlay click (outside modal)
    this.overlay.addEventListener("click", (e) => {
      if (e.target === this.overlay) {
        this.close(false);
      }
    });

    // Close on Escape key
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && this.overlay.classList.contains("active")) {
        this.close(false);
      }
    });
  },

  show(options) {
    const {
      type = "info",
      icon = null,
      title = "Notice",
      subtitle = "",
      message = "",
      buttons = [{ text: "OK", type: "primary", value: true }],
    } = options;

    // Set icon
    const iconEl = document.getElementById("modal-icon");
    const icons = {
      info: "💬",
      success: "✅",
      warning: "⚠️",
      danger: "🗑️",
    };
    iconEl.textContent = icon || icons[type] || "💬";
    iconEl.className = `modal-icon ${type}`;

    // Set title and subtitle
    document.getElementById("modal-title").textContent = title;
    const subtitleEl = document.getElementById("modal-subtitle");
    subtitleEl.textContent = subtitle;
    subtitleEl.style.display = subtitle ? "block" : "none";

    // Set message
    document.getElementById("modal-message").textContent = message;

    // Create buttons
    const footerEl = document.getElementById("modal-footer");
    footerEl.innerHTML = "";

    buttons.forEach((btn) => {
      const buttonEl = document.createElement("button");
      buttonEl.className = `btn btn-${btn.type || "secondary"}`;
      buttonEl.textContent = btn.text;
      buttonEl.addEventListener("click", () => this.close(btn.value));

      // Auto-focus the primary button
      if (btn.type === "primary" || btn.type === "danger") {
        setTimeout(() => buttonEl.focus(), 100);
      }

      footerEl.appendChild(buttonEl);
    });

    // Show modal
    this.overlay.classList.add("active");
    document.body.style.overflow = "hidden";

    return new Promise((resolve) => {
      this.resolvePromise = resolve;
    });
  },

  close(value) {
    this.overlay.classList.remove("active");
    document.body.style.overflow = "";

    if (this.resolvePromise) {
      this.resolvePromise(value);
      this.resolvePromise = null;
    }
  },

  // Convenience methods
  alert(message, options = {}) {
    return this.show({
      type: options.type || "info",
      icon: options.icon,
      title: options.title || "Notice",
      subtitle: options.subtitle || "",
      message: message,
      buttons: [{ text: "OK", type: "primary", value: true }],
    });
  },

  confirm(message, options = {}) {
    return this.show({
      type: options.type || "warning",
      icon: options.icon,
      title: options.title || "Confirm",
      subtitle: options.subtitle || "",
      message: message,
      buttons: [
        {
          text: options.cancelText || "Cancel",
          type: "secondary",
          value: false,
        },
        {
          text: options.confirmText || "Confirm",
          type: options.confirmType || "primary",
          value: true,
        },
      ],
    });
  },

  confirmDelete(itemName, options = {}) {
    return this.show({
      type: "danger",
      icon: "🗑️",
      title: options.title || "Delete Item",
      subtitle: itemName,
      message:
        options.message ||
        "This action cannot be undone. Are you sure you want to proceed?",
      buttons: [
        { text: "Cancel", type: "secondary", value: false },
        { text: "Delete", type: "danger", value: true },
      ],
    });
  },
};

// Make Modal globally available for inline scripts in templates
window.Modal = Modal;

/**
 * Initialize delete confirmation handlers for forms with data-confirm attribute
 */
export function initDeleteConfirmations() {
  document.querySelectorAll("form[data-confirm]").forEach((form) => {
    form.addEventListener("submit", async function (e) {
      e.preventDefault();

      const itemName = this.dataset.confirmItem || "this item";
      const confirmType = this.dataset.confirmType || "delete";

      let confirmed = false;

      if (confirmType === "delete") {
        confirmed = await Modal.confirmDelete(itemName);
      } else if (confirmType === "user-delete") {
        confirmed = await Modal.confirmDelete(itemName, {
          title: "Delete User",
          message:
            "This will permanently remove the user and all their data. This cannot be undone.",
        });
      } else {
        confirmed = await Modal.confirm(this.dataset.confirm, {
          type: "warning",
        });
      }

      if (confirmed) {
        this.submit();
      }
    });
  });
}
