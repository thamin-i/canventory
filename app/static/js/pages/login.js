/**
 * Canventory - Login Page JavaScript
 * Handles authentication tabs (login/register)
 */

// ============================================
// Auth Tabs
// ============================================

function initAuthTabs() {
    const tabButtons = document.querySelectorAll('.tab-btn');
    const authForms = document.querySelectorAll('.auth-form');

    if (tabButtons.length === 0) return;

    tabButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            const tab = btn.dataset.tab;

            // Update active tab button
            tabButtons.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');

            // Show corresponding form
            authForms.forEach(form => form.classList.remove('active'));
            const targetForm = document.getElementById(`${tab}-form`);
            if (targetForm) {
                targetForm.classList.add('active');
            }
        });
    });
}

// ============================================
// Initialization
// ============================================

export function init() {
    initAuthTabs();
}

// Auto-initialize when DOM is ready
document.addEventListener('DOMContentLoaded', init);
