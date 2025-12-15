/**
 * Canventory - Toast Notifications
 * Displays temporary notification messages
 */

export function showToast(message, type = "success") {
  const container = document.getElementById("toast-container");
  if (!container) return;

  const icons = {
    success: "✅",
    error: "❌",
    warning: "⚠️",
  };

  const toast = document.createElement("div");
  toast.className = `toast ${type}`;
  toast.innerHTML = `
    <span class="toast-icon">${icons[type]}</span>
    <span class="toast-message">${message}</span>
  `;

  container.appendChild(toast);

  // Auto-remove after 5 seconds
  setTimeout(() => {
    toast.remove();
  }, 5000);
}

// Make showToast globally available for inline scripts in templates
window.showToast = showToast;
