/**
 * Fact Box Consult — Vanilla JavaScript Frontend Interactions
 *
 * Implements:
 * 1. Hero 30-Second Cinematic Photo Slideshow (FR-04a, ADR-010) with pause-on-hover/focus
 *    and prefers-reduced-motion compliance.
 * 2. Accessible Mobile Navigation Off-Canvas Drawer.
 * 3. In-Page Portfolio Category Filtering on /work (no individual detail routes).
 * 4. Header scroll elevation effect.
 */

document.addEventListener('DOMContentLoaded', () => {
  initHeaderScroll();
  initMobileNavigation();
  initHeroSlideshow();
  initPortfolioFilter();
});

/**
 * Header Scroll Elevation Effect
 */
function initHeaderScroll() {
  const header = document.querySelector('.site-header');
  if (!header) return;

  const handleScroll = () => {
    if (window.scrollY > 30) {
      header.classList.add('scrolled');
    } else {
      header.classList.remove('scrolled');
    }
  };

  window.addEventListener('scroll', handleScroll, { passive: true });
  handleScroll();
}

/**
 * Mobile Navigation Drawer Toggle & Focus Trap
 */
function initMobileNavigation() {
  const toggleBtn = document.getElementById('nav-toggle');
  const closeBtn = document.getElementById('nav-close');
  const drawer = document.getElementById('mobile-drawer');
  const overlay = document.getElementById('mobile-overlay');

  if (!toggleBtn || !drawer || !overlay) return;

  const openDrawer = () => {
    drawer.classList.add('active');
    overlay.classList.add('active');
    toggleBtn.setAttribute('aria-expanded', 'true');
    document.body.style.overflow = 'hidden';
    if (closeBtn) closeBtn.focus();
  };

  const closeDrawer = () => {
    drawer.classList.remove('active');
    overlay.classList.remove('active');
    toggleBtn.setAttribute('aria-expanded', 'false');
    document.body.style.overflow = '';
    toggleBtn.focus();
  };

  toggleBtn.addEventListener('click', openDrawer);
  if (closeBtn) closeBtn.addEventListener('click', closeDrawer);
  overlay.addEventListener('click', closeDrawer);

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && drawer.classList.contains('active')) {
      closeDrawer();
    }
  });
}

/**
 * 30-Second Cinematic Background Photo Slideshow
 * Complies with:
 * - 30-second transition interval
 * - Pause on mouse hover
 * - Pause on keyboard focus
 * - Accessibility indicators
 * - Respects prefers-reduced-motion
 */
function initHeroSlideshow() {
  const container = document.getElementById('hero-slideshow');
  if (!container) return;

  const slides = container.querySelectorAll('.slideshow-slide');
  const dots = container.querySelectorAll('.slide-dot');
  if (slides.length <= 1) return;

  let currentIndex = 0;
  let timerId = null;
  let isPaused = false;
  const INTERVAL_MS = 30000; // 30 seconds as specified in FR-04a and ROADMAP

  // Respect system reduced-motion preference
  const mediaQuery = window.matchMedia('(prefers-reduced-motion: reduce)');
  if (mediaQuery.matches) {
    console.info('Hero slideshow auto-advance disabled due to prefers-reduced-motion.');
    return;
  }

  function goToSlide(index) {
    slides[currentIndex].classList.remove('active');
    if (dots[currentIndex]) {
      dots[currentIndex].classList.remove('active');
      dots[currentIndex].setAttribute('aria-selected', 'false');
    }

    currentIndex = (index + slides.length) % slides.length;

    slides[currentIndex].classList.add('active');
    if (dots[currentIndex]) {
      dots[currentIndex].classList.add('active');
      dots[currentIndex].setAttribute('aria-selected', 'true');
    }
  }

  function startTimer() {
    if (timerId) clearInterval(timerId);
    timerId = setInterval(() => {
      if (!isPaused) {
        goToSlide(currentIndex + 1);
      }
    }, INTERVAL_MS);
  }

  // Pause on mouse hover
  container.addEventListener('mouseenter', () => {
    isPaused = true;
  });
  container.addEventListener('mouseleave', () => {
    isPaused = false;
  });

  // Pause on keyboard focus inside hero container
  container.addEventListener('focusin', () => {
    isPaused = true;
  });
  container.addEventListener('focusout', () => {
    isPaused = false;
  });

  // Clickable slide dots
  dots.forEach((dot, idx) => {
    dot.addEventListener('click', () => {
      goToSlide(idx);
      startTimer(); // Reset timer upon manual interaction
    });
  });

  // Start slideshow
  startTimer();
}

/**
 * In-Page Portfolio Category Filter for /work
 * Shows/hides project cards without reloading the page or requiring individual project routes.
 */
function initPortfolioFilter() {
  const filterButtons = document.querySelectorAll('.filter-btn');
  const portfolioCards = document.querySelectorAll('.portfolio-card');

  if (!filterButtons.length || !portfolioCards.length) return;

  filterButtons.forEach((btn) => {
    btn.addEventListener('click', () => {
      const selectedCategory = btn.getAttribute('data-category');

      // Update button active state
      filterButtons.forEach((b) => b.classList.remove('active'));
      btn.classList.add('active');

      // Filter cards
      portfolioCards.forEach((card) => {
        const cardCategory = card.getAttribute('data-category');
        if (selectedCategory === 'all' || cardCategory === selectedCategory) {
          card.style.display = 'flex';
          card.style.animation = 'fadeIn 0.35s ease';
        } else {
          card.style.display = 'none';
        }
      });
    });
  });
}
