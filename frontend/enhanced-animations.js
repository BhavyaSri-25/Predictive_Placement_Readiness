// Enhanced Animations and Interactions
document.addEventListener('DOMContentLoaded', function() {
    
    // Initialize scroll reveal animations
    initScrollReveal();
    
    // Initialize enhanced button interactions
    initButtonAnimations();
    
    // Initialize form animations
    initFormAnimations();
    
    // Initialize loading animations
    initLoadingAnimations();
    
    // Initialize micro-interactions
    initMicroInteractions();
    
});

// Scroll Reveal Animation
function initScrollReveal() {
    const observerOptions = {
        threshold: 0.1,
        rootMargin: '0px 0px -50px 0px'
    };
    
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('revealed');
            }
        });
    }, observerOptions);
    
    // Observe elements with scroll-reveal class
    document.querySelectorAll('.scroll-reveal').forEach(el => {
        observer.observe(el);
    });
}

// Enhanced Button Animations
function initButtonAnimations() {
    document.querySelectorAll('.btn-animated').forEach(btn => {
        // Ripple effect on click
        btn.addEventListener('click', function(e) {
            const ripple = document.createElement('span');
            const rect = this.getBoundingClientRect();
            const size = Math.max(rect.width, rect.height);
            const x = e.clientX - rect.left - size / 2;
            const y = e.clientY - rect.top - size / 2;
            
            ripple.style.cssText = `
                position: absolute;
                width: ${size}px;
                height: ${size}px;
                left: ${x}px;
                top: ${y}px;
                border-radius: 50%;
                background: rgba(255, 255, 255, 0.4);
                transform: scale(0);
                animation: ripple 0.6s ease-out;
                pointer-events: none;
                z-index: 1;
            `;
            
            this.appendChild(ripple);
            setTimeout(() => ripple.remove(), 600);
        });
        
        // Enhanced hover effects
        btn.addEventListener('mouseenter', function() {
            this.style.transform = 'translateY(-3px) scale(1.02)';
        });
        
        btn.addEventListener('mouseleave', function() {
            this.style.transform = 'translateY(0) scale(1)';
        });
    });
}

// Enhanced Form Animations
function initFormAnimations() {
    document.querySelectorAll('.input-animated').forEach(input => {
        // Focus animations
        input.addEventListener('focus', function() {
            this.parentElement.classList.add('input-focused');
        });
        
        input.addEventListener('blur', function() {
            this.parentElement.classList.remove('input-focused');
        });
        
        // Typing animation
        input.addEventListener('input', function() {
            this.classList.add('typing');
            clearTimeout(this.typingTimer);
            this.typingTimer = setTimeout(() => {
                this.classList.remove('typing');
            }, 500);
        });
    });
}

// Loading Animations
function initLoadingAnimations() {
    // Simulate loading states for dynamic content
    document.querySelectorAll('[data-loading]').forEach(element => {
        element.classList.add('loading-shimmer');
        
        // Remove loading after specified time or when content loads
        const loadTime = element.dataset.loading || 1000;
        setTimeout(() => {
            element.classList.remove('loading-shimmer');
            element.classList.add('fade-in');
        }, loadTime);
    });
}

// Micro-interactions
function initMicroInteractions() {
    // Add hover effects to interactive elements
    document.querySelectorAll('.interactive').forEach(element => {
        element.addEventListener('mouseenter', function() {
            this.style.transform = 'translateY(-2px)';
        });
        
        element.addEventListener('mouseleave', function() {
            this.style.transform = 'translateY(0)';
        });
    });
    
    // Enhanced card interactions
    document.querySelectorAll('.card-animated').forEach(card => {
        card.addEventListener('mouseenter', function() {
            this.style.transform = 'translateY(-8px) scale(1.02)';
        });
        
        card.addEventListener('mouseleave', function() {
            this.style.transform = 'translateY(0) scale(1)';
        });
    });
}

// Progress Bar Animations
function animateProgressBar(element, targetWidth, duration = 1000) {
    const fill = element.querySelector('.progress-fill-animated');
    if (!fill) return;
    
    let start = 0;
    const startTime = performance.now();
    
    function animate(currentTime) {
        const elapsed = currentTime - startTime;
        const progress = Math.min(elapsed / duration, 1);
        
        const currentWidth = start + (targetWidth - start) * easeOutCubic(progress);
        fill.style.width = currentWidth + '%';
        
        if (progress < 1) {
            requestAnimationFrame(animate);
        }
    }
    
    requestAnimationFrame(animate);
}

// Easing function
function easeOutCubic(t) {
    return 1 - Math.pow(1 - t, 3);
}

// Counter Animation
function animateCounter(element, target, duration = 1000) {
    let start = 0;
    const startTime = performance.now();
    
    function animate(currentTime) {
        const elapsed = currentTime - startTime;
        const progress = Math.min(elapsed / duration, 1);
        
        const current = start + (target - start) * easeOutCubic(progress);
        element.textContent = Math.round(current);
        
        if (progress < 1) {
            requestAnimationFrame(animate);
        }
    }
    
    requestAnimationFrame(animate);
}

// Stagger Animation for lists
function staggerAnimation(elements, delay = 100) {
    elements.forEach((element, index) => {
        setTimeout(() => {
            element.classList.add('fade-in');
        }, index * delay);
    });
}

// Add CSS for ripple effect
const rippleCSS = `
@keyframes ripple {
    to {
        transform: scale(2);
        opacity: 0;
    }
}

.typing {
    border-color: #667eea !important;
    box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1) !important;
}

.input-focused {
    transform: scale(1.02);
}
`;

// Inject CSS
const style = document.createElement('style');
style.textContent = rippleCSS;
document.head.appendChild(style);

// Export functions for use in other scripts
window.AnimationUtils = {
    animateProgressBar,
    animateCounter,
    staggerAnimation,
    easeOutCubic
};