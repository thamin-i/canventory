/**
 * Canventory - Main Application Entry Point
 *
 * ES6 Module that imports and initializes all components:
 * - theme.js   : Theme management (light/dark mode)
 * - toast.js   : Toast notification system
 * - modal.js   : Modal dialogs and confirmations
 * - ui.js      : UI components (burger menu, image upload)
 */

import { ThemeManager, initThemeToggle } from "./theme.js";
import { showToast } from "./toast.js";
import { Modal, initDeleteConfirmations } from "./modal.js";
import { initBurgerMenu, initImageUpload } from "./ui.js";

// ============================================
// Initialization
// ============================================

document.addEventListener("DOMContentLoaded", function () {
  // Initialize theme
  ThemeManager.init();

  // Initialize modal system
  Modal.init();

  // Initialize theme toggle buttons
  initThemeToggle();

  // Initialize image upload validation
  initImageUpload();

  // Initialize burger menu
  initBurgerMenu();

  // Initialize delete confirmation handlers
  initDeleteConfirmations();
});
