/**
 * Canventory - Admin Page JavaScript
 * Handles emoji picker, category modals, and drag-drop reordering
 */

// ============================================
// Emoji Picker
// ============================================

let activePickerContainer = null;

function initEmojiPickers() {
    const toggleButtons = document.querySelectorAll('.emoji-picker-toggle');

    toggleButtons.forEach(button => {
        const targetId = button.dataset.target;
        const input = document.getElementById(targetId);
        const container = document.getElementById('emoji-picker-' + targetId);
        const picker = container?.querySelector('emoji-picker');

        if (!container || !picker || !input) return;

        // Toggle picker on button click
        button.addEventListener('click', (e) => {
            e.stopPropagation();

            // Close any other open picker
            if (activePickerContainer && activePickerContainer !== container) {
                activePickerContainer.classList.remove('active');
            }

            // Toggle this picker
            container.classList.toggle('active');
            activePickerContainer = container.classList.contains('active') ? container : null;
        });

        // Handle emoji selection
        picker.addEventListener('emoji-click', (e) => {
            input.value = e.detail.unicode;
            container.classList.remove('active');
            activePickerContainer = null;

            // Update toggle button to show selected emoji
            button.textContent = e.detail.unicode;
        });
    });

    // Close picker when clicking outside
    document.addEventListener('click', (e) => {
        if (activePickerContainer && !activePickerContainer.contains(e.target)) {
            const toggle = activePickerContainer.previousElementSibling;
            if (!toggle || !toggle.contains(e.target)) {
                activePickerContainer.classList.remove('active');
                activePickerContainer = null;
            }
        }
    });

    // Close picker on escape
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && activePickerContainer) {
            activePickerContainer.classList.remove('active');
            activePickerContainer = null;
        }
    });
}

// ============================================
// Category Modals
// ============================================

export function openEditCategoryModal(id, label, icon) {
    document.getElementById('edit-category-form').action = '/web/admin/categories/' + id + '/update';
    document.getElementById('edit-cat-icon').value = icon;
    document.getElementById('edit-cat-label').value = label;

    // Update the emoji picker toggle to show current icon
    const editToggle = document.querySelector('[data-target="edit-cat-icon"]');
    if (editToggle) {
        editToggle.textContent = icon;
    }

    document.getElementById('edit-category-modal').style.display = 'flex';
}

export function closeEditCategoryModal() {
    document.getElementById('edit-category-modal').style.display = 'none';
    // Close any open emoji picker in the modal
    const editPicker = document.getElementById('emoji-picker-edit-cat-icon');
    if (editPicker) {
        editPicker.classList.remove('active');
    }
}

export function openDeleteCategoryModal(id, label, itemCount) {
    document.getElementById('delete-category-form').action = '/web/admin/categories/' + id + '/delete';
    document.getElementById('delete-cat-name').textContent = label;
    document.getElementById('delete-item-count').textContent = itemCount;
    document.getElementById('delete-force-checkbox').checked = false;
    document.getElementById('delete-cat-submit').disabled = true;
    document.getElementById('delete-category-modal').style.display = 'flex';
}

export function closeDeleteCategoryModal() {
    document.getElementById('delete-category-modal').style.display = 'none';
}

function initCategoryModals() {
    // Close modals on escape key
    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape') {
            closeEditCategoryModal();
            closeDeleteCategoryModal();
        }
    });

    // Handle force delete checkbox
    const forceCheckbox = document.getElementById('delete-force-checkbox');
    const deleteSubmit = document.getElementById('delete-cat-submit');
    if (forceCheckbox && deleteSubmit) {
        forceCheckbox.addEventListener('change', function () {
            deleteSubmit.disabled = !this.checked;
        });
    }
}

// ============================================
// Drag and Drop Category Reordering
// ============================================

function initCategoryDragDrop() {
    const tbody = document.getElementById('categories-tbody');
    if (!tbody) return;

    let draggedRow = null;

    function clearDragClasses() {
        tbody.querySelectorAll('tr').forEach(row => {
            row.classList.remove('drag-over-top', 'drag-over-bottom');
        });
    }

    function getDropPosition(e, targetRow) {
        const rect = targetRow.getBoundingClientRect();
        const midpoint = rect.top + rect.height / 2;
        return e.clientY < midpoint ? 'before' : 'after';
    }

    tbody.addEventListener('dragstart', function (e) {
        if (e.target.tagName === 'TR') {
            draggedRow = e.target;
            e.target.classList.add('dragging');
            e.dataTransfer.effectAllowed = 'move';
            e.dataTransfer.setData('text/plain', '');
        }
    });

    tbody.addEventListener('dragend', function (e) {
        if (e.target.tagName === 'TR') {
            e.target.classList.remove('dragging');
            draggedRow = null;
            clearDragClasses();
        }
    });

    tbody.addEventListener('dragover', function (e) {
        e.preventDefault();
        e.dataTransfer.dropEffect = 'move';

        const targetRow = e.target.closest('tr');
        if (targetRow && targetRow !== draggedRow) {
            clearDragClasses();
            const position = getDropPosition(e, targetRow);
            if (position === 'before') {
                targetRow.classList.add('drag-over-top');
            } else {
                targetRow.classList.add('drag-over-bottom');
            }
        }
    });

    tbody.addEventListener('dragleave', function (e) {
        const targetRow = e.target.closest('tr');
        if (targetRow) {
            targetRow.classList.remove('drag-over-top', 'drag-over-bottom');
        }
    });

    tbody.addEventListener('drop', function (e) {
        e.preventDefault();

        const targetRow = e.target.closest('tr');
        if (targetRow && draggedRow && targetRow !== draggedRow) {
            const position = getDropPosition(e, targetRow);

            if (position === 'after') {
                targetRow.parentNode.insertBefore(draggedRow, targetRow.nextSibling);
            } else {
                targetRow.parentNode.insertBefore(draggedRow, targetRow);
            }

            // Save the new order
            saveCategoryOrder();
        }

        clearDragClasses();
    });

    function saveCategoryOrder() {
        const rows = tbody.querySelectorAll('tr[data-category-id]');
        const order = Array.from(rows).map((row, index) => ({
            id: parseInt(row.dataset.categoryId),
            sort_order: index
        }));

        fetch('/web/admin/categories/reorder', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ categories: order })
        })
            .then(response => {
                if (!response.ok) {
                    console.error('Failed to save category order');
                }
            })
            .catch(error => {
                console.error('Error saving category order:', error);
            });
    }
}

// ============================================
// Initialization
// ============================================

export function init() {
    initEmojiPickers();
    initCategoryModals();
    initCategoryDragDrop();
}

// Auto-initialize when DOM is ready
document.addEventListener('DOMContentLoaded', init);

// Export functions to window for inline onclick handlers in templates
window.openEditCategoryModal = openEditCategoryModal;
window.closeEditCategoryModal = closeEditCategoryModal;
window.openDeleteCategoryModal = openDeleteCategoryModal;
window.closeDeleteCategoryModal = closeDeleteCategoryModal;
