function showSuccessMessage(message) {
    const alert = document.getElementById('successAlert');
    const messageElement = document.getElementById('successMessage');
    messageElement.textContent = message;
    alert.classList.remove('hidden');
    // Auto hide after 3 seconds
    setTimeout(hideSuccessMessage, 3000);
}

function hideSuccessMessage() {
    const alert = document.getElementById('successAlert');
    alert.classList.add('hidden');
}
function showModal(modalId) {
    document.getElementById(modalId).classList.remove('hidden');
    document.body.style.overflow = 'hidden';
}

function hideModal(modalId) {
    document.getElementById(modalId).classList.add('hidden');
    document.body.style.overflow = 'auto';
}
document.addEventListener('DOMContentLoaded', function() {

    // Mobile menu toggle
    const menuBtn = document.getElementById('menuBtn');
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('overlay');

    if (menuBtn) {
        menuBtn.addEventListener('click', function() {
            sidebar.classList.toggle('active');
            overlay.classList.toggle('hidden');
        });
    }

    if (overlay) {
        overlay.addEventListener('click', function() {
            sidebar.classList.remove('active');
            overlay.classList.add('hidden');
        });
    }

    // Character counter for quick message
    const textarea = document.querySelector('textarea');
    const charCount = document.getElementById('charCount');

    if (textarea && charCount) {
        textarea.addEventListener('input', function() {
            const count = this.value.length;
            charCount.textContent = count;
        });
    }
    
});