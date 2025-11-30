// ===== Event Management System - Enhanced JavaScript =====

// Configuration
const CONFIG = {
    ALERT_TIMEOUT: 5000,
    ANIMATION_DELAY: 150,
    DEBOUNCE_DELAY: 300
};

// Utility Functions
const utils = {
    // Debounce function for performance
    debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    },

    // Format date to readable string
    formatDate(dateString) {
        const options = { 
            year: 'numeric', 
            month: 'long', 
            day: 'numeric',
            weekday: 'long'
        };
        return new Date(dateString).toLocaleDateString('en-US', options);
    },

    // Show loading state
    showLoading(element) {
        element.classList.add('loading');
        element.disabled = true;
    },

    // Hide loading state
    hideLoading(element) {
        element.classList.remove('loading');
        element.disabled = false;
    },

    // Copy to clipboard
    async copyToClipboard(text) {
        try {
            await navigator.clipboard.writeText(text);
            this.showToast('Copied to clipboard!', 'success');
        } catch (err) {
            console.error('Failed to copy: ', err);
        }
    },

    // Show toast notification
    showToast(message, type = 'info') {
        const toast = document.createElement('div');
        toast.className = `alert alert-${type} alert-dismissible fade show position-fixed`;
        toast.style.cssText = `
            top: 20px;
            right: 20px;
            z-index: 9999;
            min-width: 300px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        `;
        toast.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;
        document.body.appendChild(toast);
        setTimeout(() => toast.remove(), 3000);
    }
};

// Main Application Class
class EventManagementApp {
    constructor() {
        this.init();
    }

    init() {
        this.setupEventListeners();
        this.autoDismissAlerts();
        this.setupPasswordToggles();
        this.setupFormValidation();
        this.setupAnimations();
        this.setupStatsCounter();
        this.setupSmoothScrolling();
    }

    // Setup all event listeners
    setupEventListeners() {
        // Navbar scroll effect
        window.addEventListener('scroll', utils.debounce(() => {
            const navbar = document.querySelector('.navbar');
            if (window.scrollY > 100) {
                navbar.style.background = 'rgba(67, 97, 238, 0.95)';
                navbar.style.backdropFilter = 'blur(10px)';
            } else {
                navbar.style.background = '';
                navbar.style.backdropFilter = '';
            }
        }, CONFIG.DEBOUNCE_DELAY));

        // Card hover effects
        document.addEventListener('DOMContentLoaded', () => {
            const cards = document.querySelectorAll('.card');
            cards.forEach(card => {
                card.addEventListener('mouseenter', () => {
                    card.style.transform = 'translateY(-8px)';
                });
                card.addEventListener('mouseleave', () => {
                    card.style.transform = 'translateY(0)';
                });
            });
        });

        // Form submission enhancements
        document.addEventListener('submit', (e) => {
            const form = e.target;
            if (form.classList.contains('needs-validation')) {
                this.handleFormSubmission(form, e);
            }
        });
    }

    // Auto-dismiss alerts with enhanced animation
    autoDismissAlerts() {
        document.addEventListener('DOMContentLoaded', () => {
            const alerts = document.querySelectorAll('.alert:not(.alert-permanent)');
            alerts.forEach(alert => {
                const bsAlert = new bootstrap.Alert(alert);
                
                setTimeout(() => {
                    alert.style.opacity = '0';
                    alert.style.transform = 'translateX(100%)';
                    setTimeout(() => bsAlert.close(), 300);
                }, CONFIG.ALERT_TIMEOUT);
            });
        });
    }

    // Password visibility toggle
    setupPasswordToggles() {
        document.addEventListener('click', (e) => {
            if (e.target.closest('#togglePassword')) {
                const button = e.target.closest('#togglePassword');
                const passwordInput = document.getElementById('password');
                const icon = button.querySelector('i');
                
                if (passwordInput.type === 'password') {
                    passwordInput.type = 'text';
                    icon.className = 'fas fa-eye-slash';
                    button.setAttribute('aria-label', 'Hide password');
                } else {
                    passwordInput.type = 'password';
                    icon.className = 'fas fa-eye';
                    button.setAttribute('aria-label', 'Show password');
                }
            }
        });
    }

    // Enhanced form validation
    setupFormValidation() {
        const forms = document.querySelectorAll('.needs-validation');
        forms.forEach(form => {
            form.addEventListener('submit', (e) => {
                if (!form.checkValidity()) {
                    e.preventDefault();
                    e.stopPropagation();
                    
                    // Add shake animation to invalid fields
                    const invalidFields = form.querySelectorAll(':invalid');
                    invalidFields.forEach(field => {
                        field.classList.add('is-invalid');
                        field.style.animation = 'shake 0.5s ease-in-out';
                        setTimeout(() => field.style.animation = '', 500);
                    });
                }
                form.classList.add('was-validated');
            }, false);

            // Real-time validation
            form.querySelectorAll('input, select, textarea').forEach(input => {
                input.addEventListener('input', () => {
                    if (input.checkValidity()) {
                        input.classList.remove('is-invalid');
                        input.classList.add('is-valid');
                    } else {
                        input.classList.remove('is-valid');
                        input.classList.add('is-invalid');
                    }
                });
            });
        });
    }

    // Handle form submission with loading states
    handleFormSubmission(form, e) {
        const submitButton = form.querySelector('button[type="submit"]');
        if (submitButton) {
            utils.showLoading(submitButton);
            
            // Simulate API call delay for better UX
            setTimeout(() => {
                utils.hideLoading(submitButton);
            }, 1000);
        }
    }

    // Setup animations
    setupAnimations() {
        // Intersection Observer for scroll animations
        const observerOptions = {
            threshold: 0.1,
            rootMargin: '0px 0px -50px 0px'
        };

        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    entry.target.style.animation = `fadeInUp 0.6s ease-out ${entry.target.dataset.delay || '0s'} forwards`;
                    observer.unobserve(entry.target);
                }
            });
        }, observerOptions);

        // Observe elements for animation
        document.addEventListener('DOMContentLoaded', () => {
            const animatedElements = document.querySelectorAll('.card, .feature-card, .stat-item');
            animatedElements.forEach((el, index) => {
                el.style.opacity = '0';
                el.style.transform = 'translateY(30px)';
                el.dataset.delay = `${index * 0.1}s`;
                observer.observe(el);
            });
        });
    }

    // Animated stats counter
    setupStatsCounter() {
        const statsSection = document.querySelector('.bg-light');
        if (!statsSection) return;

        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    this.animateStats();
                    observer.unobserve(entry.target);
                }
            });
        }, { threshold: 0.5 });

        observer.observe(statsSection);
    }

    animateStats() {
        const counters = document.querySelectorAll('[id$="Count"]');
        counters.forEach(counter => {
            const target = parseInt(counter.textContent);
            let current = 0;
            const increment = target / 60; // 2 second animation
            const timer = setInterval(() => {
                current += increment;
                if (current >= target) {
                    counter.textContent = target + '+';
                    clearInterval(timer);
                } else {
                    counter.textContent = Math.floor(current) + '+';
                }
            }, 33); // ~30fps
        });
    }

    // Smooth scrolling for anchor links
    setupSmoothScrolling() {
        document.addEventListener('click', (e) => {
            if (e.target.matches('a[href^="#"]')) {
                e.preventDefault();
                const target = document.querySelector(e.target.getAttribute('href'));
                if (target) {
                    target.scrollIntoView({
                        behavior: 'smooth',
                        block: 'start'
                    });
                }
            }
    });
    }

    // QR Code functionality
    setupQRCodeScanner() {
        // This would integrate with a QR scanning library
        console.log('QR Code scanner setup ready');
    }

    // Event registration handler
    handleEventRegistration(eventId) {
        // Add any pre-registration logic here
        console.log(`Registering for event: ${eventId}`);
    }
}

// Shake animation for invalid form fields
const shakeKeyframes = `
@keyframes shake {
    0%, 100% { transform: translateX(0); }
    25% { transform: translateX(-5px); }
    75% { transform: translateX(5px); }
}
`;

// Add shake animation to styles
const style = document.createElement('style');
style.textContent = shakeKeyframes;
document.head.appendChild(style);

// Initialize the application when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.eventApp = new EventManagementApp();
    
    // Add any additional initialization here
    console.log('Event Management System initialized');
});

// Export for module usage (if needed)
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { EventManagementApp, utils };
}