/**
 * Canventory - Settings Page JavaScript
 * Handles email notifications, password changes, and email changes
 */

import { showToast } from '../toast.js';

// ============================================
// Email Notification Toggle
// ============================================

let emailEnabled = false;

export function initEmailToggle(initialState) {
    emailEnabled = initialState;
}

export async function toggleEmailNotifications() {
    const newState = !emailEnabled;

    try {
        const response = await fetch('/web/settings/notifications', {
            method: 'POST',
            credentials: 'include',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ enabled: newState }),
        });

        const result = await response.json();

        if (result.success) {
            emailEnabled = newState;
            updateEmailUI(newState);
            showToast(newState ? 'Email notifications enabled!' : 'Email notifications disabled', 'success');
        } else {
            showToast(result.message || 'Failed to update email settings', 'error');
        }
    } catch (error) {
        showToast('Failed to update email settings', 'error');
    }
}

function updateEmailUI(enabled) {
    const iconOn = document.getElementById('email-icon-on');
    const iconOff = document.getElementById('email-icon-off');
    const status = document.getElementById('email-status');
    const testRow = document.getElementById('test-email-row');

    if (iconOn && iconOff && status) {
        if (enabled) {
            iconOn.classList.remove('hidden');
            iconOff.classList.add('hidden');
            status.textContent = 'Enabled';
            if (testRow) testRow.classList.remove('hidden');
        } else {
            iconOn.classList.add('hidden');
            iconOff.classList.remove('hidden');
            status.textContent = 'Enable';
            if (testRow) testRow.classList.add('hidden');
        }
    }
}

// ============================================
// Test Email
// ============================================

export async function sendTestEmail() {
    try {
        const response = await fetch('/web/settings/test-email', {
            method: 'POST',
            credentials: 'include',
        });

        const result = await response.json();

        if (result.success) {
            showToast('Test email sent! Check your inbox.', 'success');
        } else {
            showToast(result.message || 'Failed to send test email', 'error');
        }
    } catch (error) {
        showToast('Failed to send test email', 'error');
    }
}

// ============================================
// Change Password
// ============================================

export async function changePassword(event) {
    event.preventDefault();

    const currentPassword = document.getElementById('current-password').value;
    const newPassword = document.getElementById('new-password').value;
    const confirmPassword = document.getElementById('confirm-password').value;

    if (newPassword !== confirmPassword) {
        showToast('New passwords do not match', 'error');
        return;
    }

    if (newPassword.length < 8) {
        showToast('New password must be at least 8 characters', 'error');
        return;
    }

    try {
        const response = await fetch('/web/settings/change-password', {
            method: 'POST',
            credentials: 'include',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                current_password: currentPassword,
                new_password: newPassword,
            }),
        });

        const result = await response.json();

        if (result.success) {
            showToast('Password changed successfully!', 'success');
            document.getElementById('password-form').reset();
        } else {
            showToast(result.message || 'Failed to change password', 'error');
        }
    } catch (error) {
        showToast('Failed to change password', 'error');
    }
}

// ============================================
// Change Email
// ============================================

export async function changeEmail(event) {
    event.preventDefault();

    const newEmail = document.getElementById('new-email').value;
    const password = document.getElementById('email-password').value;

    try {
        const response = await fetch('/web/settings/change-email', {
            method: 'POST',
            credentials: 'include',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                new_email: newEmail,
                password: password,
            }),
        });

        const result = await response.json();

        if (result.success) {
            showToast('Email changed successfully!', 'success');
            document.getElementById('email-form').reset();
            // Update displayed email
            const emailDisplay = document.getElementById('current-email');
            if (emailDisplay) {
                emailDisplay.textContent = result.new_email;
            }
        } else {
            showToast(result.message || 'Failed to change email', 'error');
        }
    } catch (error) {
        showToast('Failed to change email', 'error');
    }
}

// ============================================
// Initialization
// ============================================

function init() {
    // Read initial email state from script tag data attribute
    const scriptTag = document.querySelector('script[src*="pages/settings.js"]');
    if (scriptTag) {
        const emailEnabledAttr = scriptTag.dataset.emailEnabled;
        if (emailEnabledAttr !== undefined) {
            initEmailToggle(emailEnabledAttr === 'true');
        }
    }
}

// Auto-initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
} else {
    init();
}

// Export functions to window for inline onclick/onsubmit handlers in templates
window.toggleEmailNotifications = toggleEmailNotifications;
window.sendTestEmail = sendTestEmail;
window.changePassword = changePassword;
window.changeEmail = changeEmail;
window.initEmailToggle = initEmailToggle;
