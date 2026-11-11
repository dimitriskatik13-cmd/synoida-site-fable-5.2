/* ΣΥΝΟΙΔΑ: κοινή συμπεριφορά όλων των σελίδων.
   1. ενεργό στοιχείο μενού   2. μενού κινητού   3. μενού «Θεραπείες» (υπολογιστής)   4. λίστες τηλεφώνων
   4β. κεφαλίδα και κάτω μπάρα   4γ. φωτογραφία που ταξιδεύει στη μετάβαση   5. εμφάνιση ενοτήτων στην κύλιση   6. πρόοδος κύλισης (--hdr, data-progress)   7. μετρητής
   Χωρίς JavaScript η σελίδα είναι πλήρης. Με ρύθμιση «μείωση κίνησης» τίποτα δεν κινείται. */
(function () {
  'use strict';

  var reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var clamp01 = function (v) { return Math.min(Math.max(v, 0), 1); };

  /* ---------- 1. ενεργό στοιχείο μενού: η σελίδα δηλώνει το όνομά της στο <body data-page> ---------- */
  var page = document.body.getAttribute('data-page');
  document.querySelectorAll('[data-nav="' + page + '"]').forEach(function (el) { el.classList.add('nav-active'); });

  /* ---------- 2. μενού κινητού ---------- */
  var navToggle = document.getElementById('navToggle');
  var mobileMenu = document.getElementById('mobileMenu');
  var iconOpen = document.getElementById('navOpen');
  var iconClose = document.getElementById('navClose');

  function setMobileMenu(open) {
    mobileMenu.classList.toggle('hidden', !open);
    iconOpen.classList.toggle('hidden', open);
    iconClose.classList.toggle('hidden', !open);
    navToggle.setAttribute('aria-expanded', String(open));
    document.documentElement.classList.toggle('menu-open', open);      // η σελίδα από πίσω δεν κυλά
  }
  navToggle.addEventListener('click', function () { setMobileMenu(mobileMenu.classList.contains('hidden')); });
  mobileMenu.querySelectorAll('a').forEach(function (a) {
    a.addEventListener('click', function () { setMobileMenu(false); });
  });

  var therapiesBtn = document.getElementById('mTherapiesBtn');
  var therapiesSub = document.getElementById('mTherapiesSub');
  var therapiesChevron = document.getElementById('mTherapiesChevron');
  therapiesBtn.addEventListener('click', function () {
    var open = therapiesSub.classList.toggle('hidden') === false;
    therapiesSub.classList.toggle('flex', open);
    therapiesChevron.classList.toggle('rotate-180', open);
    therapiesBtn.setAttribute('aria-expanded', String(open));
  });

  /* ---------- 3. μενού «Θεραπείες» στον υπολογιστή: ανοίγει με CSS, εδώ ενημερώνεται μόνο το aria-expanded ---------- */
  var dropdown = document.querySelector('nav .group');
  var dropdownTrigger = dropdown && dropdown.querySelector('[aria-haspopup]');
  if (dropdown && dropdownTrigger) {
    ['mouseenter', 'focusin'].forEach(function (type) {
      dropdown.addEventListener(type, function () { dropdownTrigger.setAttribute('aria-expanded', 'true'); });
    });
    ['mouseleave', 'focusout'].forEach(function (type) {
      dropdown.addEventListener(type, function () {
        if (!dropdown.matches(':hover') && !dropdown.contains(document.activeElement)) dropdownTrigger.setAttribute('aria-expanded', 'false');
      });
    });
  }

  /* ---------- 4. λίστες τηλεφώνων (<details class="phones">): κλείνουν με κλικ έξω και με Escape ---------- */
  function closePhones(except) {
    document.querySelectorAll('details.phones[open]').forEach(function (d) {
      if (!except || !d.contains(except)) d.removeAttribute('open');
    });
  }
  document.addEventListener('click', function (e) { closePhones(e.target); });

  document.addEventListener('keydown', function (e) {
    if (e.key !== 'Escape') return;
    closePhones(null);
    if (!mobileMenu.classList.contains('hidden')) { setMobileMenu(false); navToggle.focus(); return; }
    if (dropdown && dropdown.contains(document.activeElement)) {
      document.activeElement.blur();
      dropdownTrigger.setAttribute('aria-expanded', 'false');
    }
  });

  /* ---------- 4β. Αρχική στο κινητό: η κάτω μπάρα εμφανίζεται όταν το κουμπί του hero βγει από την οθόνη ---------- */
  var callbar = document.querySelector('.callbar');
  var heroCta = document.querySelector('[data-callbar-after]');      // υπάρχει μόνο στην Αρχική
  if (heroCta && callbar && 'IntersectionObserver' in window) {
    new IntersectionObserver(function (entries) {
      var show = !entries[0].isIntersecting;
      document.body.classList.toggle('callbar-on', show);
      callbar.inert = !show && window.matchMedia('(max-width:1023px)').matches;
    }).observe(heroCta);
  } else {
    document.body.classList.add('callbar-on');
  }

  /* ---------- 4β2. «Μετάβαση στο περιεχόμενο»: δίνει εστίαση στο <main> (δουλεύει και στο 404, όπου οι σύνδεσμοι έχουν <base>) ---------- */
  var skipLink = document.querySelector('a[href="#main"]');
  var mainEl = document.getElementById('main');
  if (skipLink && mainEl) {
    skipLink.addEventListener('click', function (e) {
      e.preventDefault();
      mainEl.setAttribute('tabindex', '-1');
      mainEl.focus();
      mainEl.scrollIntoView();
    });
  }

  /* ---------- 4γ. μετάβαση σελίδας: η φωτογραφία της θεραπείας που πατήθηκε «ταξιδεύει» στο κάδρο της σελίδας της ---------- */
  document.addEventListener('click', function (e) {
    var link = e.target.closest && e.target.closest('a[href^="treatment-"]');
    if (!link) return;
    document.querySelectorAll('[data-tx]').forEach(function (el) { el.style.viewTransitionName = ''; el.removeAttribute('data-tx'); });
    var photo = Array.prototype.filter.call(link.querySelectorAll('img'), function (im) { return im.offsetWidth > 0; })[0];
    if (!photo && link.closest('.hx-index')) {            // Αρχική σε υπολογιστή: η φωτογραφία είναι στο κάδρο προεπισκόπησης
      photo = Array.prototype.filter.call(document.querySelectorAll('.hx-preview img'), function (im) { return im.offsetWidth > 0; })[0];
    }
    if (photo) { photo.style.viewTransitionName = 'tx-photo'; photo.setAttribute('data-tx', ''); }
  });
  window.addEventListener('pageshow', function () {       // επιστροφή με «πίσω»: καθαρίζει το όνομα για να μη μείνει διπλό
    document.querySelectorAll('[data-tx]').forEach(function (el) { el.style.viewTransitionName = ''; el.removeAttribute('data-tx'); });
  });

  /* ---------- 5. εμφάνιση ενοτήτων (.reveal) όταν μπαίνουν στην οθόνη ---------- */
  var reveals = document.querySelectorAll('.reveal');
  if (reduceMotion || !('IntersectionObserver' in window)) {
    reveals.forEach(function (el) { el.classList.add('in'); });
  } else {
    var revealObserver = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) { entry.target.classList.add('in'); revealObserver.unobserve(entry.target); }
      });
    }, { threshold: 0.02, rootMargin: '0px 0px 10% 0px' });
    reveals.forEach(function (el) { revealObserver.observe(el); });
    window.addEventListener('load', function () {      // ό,τι φαίνεται ήδη στο πρώτο άνοιγμα εμφανίζεται αμέσως
      reveals.forEach(function (el) { if (el.getBoundingClientRect().top < window.innerHeight) el.classList.add('in'); });
    });
  }

  /* ---------- 6. πρόοδος κύλισης. Το ύψος της κεφαλίδας γράφεται στο --hdr (το χρησιμοποιεί το CSS για κολλημένα στοιχεία και άγκυρες). ---------- */
  var header = document.querySelector('header');
  var progressEls = Array.prototype.slice.call(document.querySelectorAll('[data-progress]'));
  var ticking = false;

  function measureHeader() {
    document.documentElement.style.setProperty('--hdr', (header ? header.offsetHeight : 72) + 'px');
  }

  /* data-progress="αρχή τέλος": πρόοδος 0 έως 1 καθώς το στοιχείο περνά από την οθόνη (--p). Προεπιλογή 0.85 και 0.6.
     Γράφει μόνο μεταβλητές CSS, δεν αλλάζει διάταξη. */
  function frame() {
    ticking = false;
    var vh = window.innerHeight;
    for (var i = 0; i < progressEls.length; i++) {
      var el = progressEls[i], rect = el.getBoundingClientRect();
      var parts = (el.getAttribute('data-progress') || '').split(/\s+/);
      var start = parseFloat(parts[0]); if (isNaN(start)) start = 0.85;
      var end = parseFloat(parts[1]); if (isNaN(end)) end = 0.6;
      el.style.setProperty('--p', clamp01((vh * start - rect.top) / (vh * (start - end) + rect.height)).toFixed(3));
    }
  }

  function onScroll() {
    if (!ticking) { ticking = true; requestAnimationFrame(frame); }
  }

  /* Κάθε παιδί με data-at μαθαίνει σε ποιο ύψος της λίστας βρίσκεται (--at, 0 έως 1), για να «ανάβει» με τη σειρά. */
  function measureItems() {
    progressEls.forEach(function (list) {
      var listRect = list.getBoundingClientRect();
      if (listRect.height < 1) return;
      Array.prototype.forEach.call(list.querySelectorAll('[data-at]'), function (item) {
        var r = item.getBoundingClientRect();
        item.style.setProperty('--at', ((r.top + r.height / 2 - listRect.top) / listRect.height).toFixed(3));
      });
    });
  }

  measureHeader();
  window.addEventListener('resize', measureHeader);
  window.addEventListener('load', measureHeader);
  if (progressEls.length) measureItems();
  if (progressEls.length && !reduceMotion) {
    frame();
    window.addEventListener('resize', function () { measureItems(); frame(); });
    window.addEventListener('load', function () { measureItems(); frame(); });
    window.addEventListener('scroll', onScroll, { passive: true });
  }

  /* ---------- 7. μετρητής (data-count): μετρά μέχρι τον αριθμό όταν φανεί. Το HTML έχει ήδη τον τελικό αριθμό. ---------- */
  var counters = document.querySelectorAll('[data-count]');
  if (counters.length && !reduceMotion && 'IntersectionObserver' in window) {
    var countObserver = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (!entry.isIntersecting) return;
        countObserver.unobserve(entry.target);
        var el = entry.target;
        var target = parseInt(el.getAttribute('data-count'), 10) || 0;
        var duration = parseInt(el.getAttribute('data-count-ms'), 10) || 2600;
        var startTime = null;
        function step(now) {
          if (startTime === null) startTime = now;
          var q = Math.min((now - startTime) / duration, 1);
          q = 1 - Math.pow(1 - q, 3);                     // επιβράδυνση προς το τέλος
          el.textContent = String(Math.round(target * q));
          if (q < 1) requestAnimationFrame(step);
        }
        requestAnimationFrame(step);
      });
    }, { threshold: 0.5 });
    counters.forEach(function (el) { el.textContent = '0'; countObserver.observe(el); });
  }
})();
