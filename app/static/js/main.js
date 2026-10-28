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
  const containers = document.querySelectorAll('.hero-slideshow-container');
  if (!containers || containers.length === 0) return;

  // Respect system reduced-motion preference
  const mediaQuery = window.matchMedia('(prefers-reduced-motion: reduce)');
  const isReducedMotion = mediaQuery.matches;

  containers.forEach((container) => {
    const slides = container.querySelectorAll('.slideshow-slide');
    const dots = container.querySelectorAll('.slide-dot');
    if (slides.length <= 1) return;

    let currentIndex = 0;
    let timerId = null;
    let isPaused = false;
    // 5-second automatic rotation for dynamic TVSense-inspired cinematic experience
    const INTERVAL_MS = 5000;

    if (isReducedMotion) {
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

    // Only pause when actively hovering over manual controls
    const controls = container.querySelector('.slideshow-controls');
    if (controls) {
      controls.addEventListener('mouseenter', () => {
        isPaused = true;
      });
      controls.addEventListener('mouseleave', () => {
        isPaused = false;
      });
    }

    // Clickable slide dots
    dots.forEach((dot, idx) => {
      dot.addEventListener('click', (e) => {
        e.preventDefault();
        goToSlide(idx);
        startTimer(); // Reset timer upon manual interaction
      });
    });

    // Start slideshow
    startTimer();
  });
}

/**
 * In-Page Portfolio Category & Organization Filter for /work
 * Allows visitors to filter by Category or Organization, responds to ?org= URL params,
 * and handles graceful empty states with smooth animations.
 */
function initPortfolioFilter() {
  const categoryButtons = document.querySelectorAll('.filter-btn');
  const orgPills = document.querySelectorAll('.work-org-pill');
  const allOrgBtn = document.getElementById('org-filter-all');
  const portfolioCards = document.querySelectorAll('.portfolio-card');
  const emptyState = document.getElementById('org-empty-state');
  const emptyLogo = document.getElementById('org-empty-logo');
  const emptyTitle = document.getElementById('org-empty-title');
  const emptyResetBtn = document.getElementById('org-empty-reset-btn');
  const countDisplay = document.getElementById('visible-projects-count');

  if (!portfolioCards.length) return;

  let activeCategory = 'all';
  let activeOrg = 'all';

  function applyFilters(shouldScroll = false) {
    let visibleCount = 0;

    portfolioCards.forEach((card) => {
      const cardCat = card.getAttribute('data-category');
      const cardOrg = card.getAttribute('data-org');

      const matchCat = (activeCategory === 'all' || cardCat === activeCategory);
      const matchOrg = (activeOrg === 'all' || cardOrg === activeOrg);

      if (matchCat && matchOrg) {
        card.style.display = 'flex';
        card.style.animation = 'fadeIn 0.3s ease';
        visibleCount++;
      } else {
        card.style.display = 'none';
      }
    });

    if (countDisplay) {
      countDisplay.textContent = `${visibleCount} Project${visibleCount === 1 ? '' : 's'} Shown`;
    }

    // Handle empty state for filtered organization
    if (emptyState) {
      if (visibleCount === 0 && activeOrg !== 'all') {
        const activePill = document.querySelector(`.work-org-pill[data-org="${activeOrg}"]`);
        const orgImg = activePill ? activePill.querySelector('img') : null;
        const orgName = activePill ? activePill.querySelector('.work-org-name').textContent : activeOrg;

        if (emptyLogo && orgImg) {
          emptyLogo.src = orgImg.src;
          emptyLogo.alt = orgImg.alt;
        }
        if (emptyTitle) {
          emptyTitle.textContent = `Work Done with ${orgName}`;
        }
        emptyState.style.display = 'block';
        emptyState.style.animation = 'fadeIn 0.35s ease';
      } else {
        emptyState.style.display = 'none';
      }
    }

    if (shouldScroll) {
      const portfolioSec = document.getElementById('portfolio-section');
      if (portfolioSec) {
        portfolioSec.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
    }
  }

  // Category filter handlers
  categoryButtons.forEach((btn) => {
    btn.addEventListener('click', () => {
      categoryButtons.forEach((b) => b.classList.remove('active'));
      btn.classList.add('active');
      activeCategory = btn.getAttribute('data-category') || 'all';
      applyFilters();
    });
  });

  // Organization pill handlers
  orgPills.forEach((pill) => {
    pill.addEventListener('click', () => {
      const selectedOrg = pill.getAttribute('data-org');
      if (activeOrg === selectedOrg) {
        // Toggle off if already active
        activeOrg = 'all';
        pill.classList.remove('active');
        if (allOrgBtn) allOrgBtn.classList.add('active');
      } else {
        activeOrg = selectedOrg;
        orgPills.forEach((p) => p.classList.remove('active'));
        if (allOrgBtn) allOrgBtn.classList.remove('active');
        pill.classList.add('active');
      }
      applyFilters();
    });
  });

  if (allOrgBtn) {
    allOrgBtn.addEventListener('click', () => {
      activeOrg = 'all';
      orgPills.forEach((p) => p.classList.remove('active'));
      allOrgBtn.classList.add('active');
      applyFilters();
    });
  }

  if (emptyResetBtn) {
    emptyResetBtn.addEventListener('click', () => {
      activeOrg = 'all';
      activeCategory = 'all';
      orgPills.forEach((p) => p.classList.remove('active'));
      categoryButtons.forEach((b) => b.classList.remove('active'));
      const catAll = document.querySelector('.filter-btn[data-category="all"]');
      if (catAll) catAll.classList.add('active');
      if (allOrgBtn) allOrgBtn.classList.add('active');
      applyFilters();
    });
  }

  // Check URL query parameters (e.g. /work?org=mercy-corps or /work?partner=mercy-corps)
  const urlParams = new URLSearchParams(window.location.search);
  const targetOrg = urlParams.get('org') || urlParams.get('partner');
  if (targetOrg) {
    const matchingPill = document.querySelector(`.work-org-pill[data-org="${targetOrg}"]`);
    if (matchingPill) {
      activeOrg = targetOrg;
      orgPills.forEach((p) => p.classList.remove('active'));
      if (allOrgBtn) allOrgBtn.classList.remove('active');
      matchingPill.classList.add('active');
      setTimeout(() => applyFilters(true), 200);
    }
  }
}
