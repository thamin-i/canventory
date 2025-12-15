/**
 * Canventory - UI Components
 * Image upload, burger menu, and other UI interactions
 */

import { Modal } from "./modal.js";

/**
 * Initialize image upload with size validation
 */
export function initImageUpload() {
  const imageInput = document.getElementById("image");
  if (imageInput) {
    imageInput.addEventListener("change", function (e) {
      const file = e.target.files[0];
      if (file && file.size > 5 * 1024 * 1024) {
        Modal.alert(
          "The image you selected exceeds the 5MB size limit. Please choose a smaller file.",
          {
            type: "warning",
            icon: "📸",
            title: "Image Too Large",
          }
        );
        e.target.value = "";
      }
    });
  }
}

/**
 * Initialize burger menu for mobile navigation
 */
export function initBurgerMenu() {
  const burgerBtn = document.getElementById("burger-menu-btn");
  const dropdown = document.getElementById("header-dropdown");

  if (!burgerBtn || !dropdown) return;

  burgerBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    const isOpen = dropdown.classList.contains("open");

    if (isOpen) {
      dropdown.classList.remove("open");
      burgerBtn.classList.remove("open");
      burgerBtn.setAttribute("aria-label", "Open menu");
    } else {
      dropdown.classList.add("open");
      burgerBtn.classList.add("open");
      burgerBtn.setAttribute("aria-label", "Close menu");
    }
  });

  // Close dropdown when clicking outside
  document.addEventListener("click", (e) => {
    if (!burgerBtn.contains(e.target) && !dropdown.contains(e.target)) {
      dropdown.classList.remove("open");
      burgerBtn.classList.remove("open");
      burgerBtn.setAttribute("aria-label", "Open menu");
    }
  });

  // Close dropdown on escape key
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && dropdown.classList.contains("open")) {
      dropdown.classList.remove("open");
      burgerBtn.classList.remove("open");
      burgerBtn.setAttribute("aria-label", "Open menu");
    }
  });
}
