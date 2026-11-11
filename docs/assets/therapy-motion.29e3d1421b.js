/* Therapy pages: calm, editorial depth and guidance in the specialty colour (no decorative shapes).
   1. Hero: the photo settles slowly and moves slower than the words; a short rule in the specialty colour draws under the title.
   2. «Πότε να απευθυνθείτε» told as a sequence: signs light up one by one, a fixed counter «03 / 06» with a bar.
   3. Domains: the row being read gets its number in the specialty colour (colour only, nothing moves).
   4. Dark «how it works»: the photo opens from the bottom like a curtain; without a photo, the step rules draw in.
   5. Section titles rise word by word.
   Decorative only. Without JS the page is complete; with reduced motion nothing moves (states are shown settled). */
(function () {
  var main = document.querySelector('main.specialty-refined, main.speech-refined');
  if (!main || !('IntersectionObserver' in window)) return;
  var reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var accent = (getComputedStyle(main).getPropertyValue('--specialty-color') || '').trim() || '#8DC63F';
  main.style.setProperty('--accent', accent);
  main.classList.add('tm-on');

  function el(tag, cls, attrs) { var e = document.createElement(tag); if (cls) e.className = cls; if (attrs) for (var k in attrs) e.setAttribute(k, attrs[k]); return e; }
  function clamp(x, a, b) { return Math.min(Math.max(x, a), b); }

  /* ---- 1. hero: calm depth and a rule in the specialty colour ---- */
  var hero = main.querySelector('.specialty-hero, .speech-hero');
  var heroBox = hero && hero.firstElementChild;
  var heroCopy = heroBox && heroBox.querySelector('.reveal');
  if (heroCopy) {
    heroCopy.classList.add('tm-hero-copy');
    var h1 = heroCopy.querySelector('h1');
    if (h1) h1.insertAdjacentElement('afterend', el('span', 'tm-rule', { 'aria-hidden': 'true' }));
  }

  /* ---- 2. «Πότε» as a sequence ---- */
  var steps = main.querySelector('.specialty-signs-list, .speech-observations');
  var counter = null, bar = null, total = 0, signsFrame = null;
  if (steps) {
    var items = Array.prototype.slice.call(steps.children);
    total = items.length;
    steps.classList.add('tm-steps');
    var intro = steps.parentElement.querySelector('.specialty-signs-intro, .speech-concerns-intro');
    if (intro && total > 1) {
      var prog = el('div', 'tm-progress', { 'aria-hidden': 'true' });
      counter = el('span', 'tm-count'); counter.innerHTML = '<b>01</b><i>/ ' + String(total).padStart(2, '0') + '</i>';
      bar = el('span', 'tm-bar'); bar.appendChild(el('em'));
      prog.appendChild(counter); prog.appendChild(bar);
      var cta = intro.querySelector('.signs-cta');
      intro.insertBefore(prog, cta || null);
    }
    var currentSign = -1, targetSign = -1, walking = false;
    var paintSign = function (idx) {
      items.forEach(function (li, i) { li.classList.toggle('is-on', i === idx); li.classList.toggle('is-past', i < idx); });
      if (counter) counter.firstChild.textContent = String(idx + 1).padStart(2, '0');
      if (bar) bar.firstChild.style.transform = 'scaleX(' + ((idx + 1) / total).toFixed(3) + ')';
    };
    /* one sign per frame towards the target, so every sign lights up in order even after a jump */
    var walkSign = function () {
      walking = false;
      if (currentSign === targetSign) return;
      currentSign += currentSign < targetSign ? 1 : -1;
      paintSign(currentSign);
      if (currentSign !== targetSign) { walking = true; requestAnimationFrame(walkSign); }
    };
    var setActive = function (idx) {
      targetSign = idx;
      if (currentSign === -1) { currentSign = idx; paintSign(idx); return; }
      if (!walking) walkSign();
    };
    /* the active sign is the one closest to the middle of the screen, checked on every scroll frame,
       so a fast fling never skips one (an intersection band could, especially in Safari) */
    signsFrame = function () {
      var mid = window.innerHeight / 2, box = steps.getBoundingClientRect();
      if (box.bottom < 0 || box.top > window.innerHeight) return;
      var best = -1, bestDist = Infinity;
      items.forEach(function (li, i) {
        var r = li.getBoundingClientRect();
        var d = (r.top <= mid && r.bottom >= mid) ? 0 : Math.min(Math.abs(r.top - mid), Math.abs(r.bottom - mid));
        if (d < bestDist) { bestDist = d; best = i; }
      });
      if (best >= 0) setActive(best);
    };
    if (reduce) setActive(total - 1);
  }

  /* ---- 3. domains: the row being read takes the specialty colour ---- */
  var rows = Array.prototype.slice.call(main.querySelectorAll('.specialty-domains > li, .speech-area-list > li'));
  if (rows.length) {
    var dio = new IntersectionObserver(function (en) {
      en.forEach(function (e) { e.target.classList.toggle('is-on', e.isIntersecting); });
    }, { rootMargin: '-40% 0px -40% 0px' });
    rows.forEach(function (r) { r.classList.add('tm-row'); dio.observe(r); });
  }

  /* ---- 4. dark section: the photo opens like a curtain, or the step rules draw in ---- */
  var photos = Array.prototype.slice.call(main.querySelectorAll('.specialty-dark .specialty-photo, .speech-practice .speech-photo'));
  var pio = new IntersectionObserver(function (en) {
    en.forEach(function (e) { if (e.isIntersecting) { e.target.classList.add('tm-in'); pio.unobserve(e.target); } });
  }, { threshold: 0.3 });
  photos.forEach(function (f) { f.classList.add('tm-curtain'); if (reduce) f.classList.add('tm-in'); else pio.observe(f); });
  var lists = Array.prototype.slice.call(main.querySelectorAll('.specialty-process-list, .speech-practice-points'));
  var lio = new IntersectionObserver(function (en) {
    en.forEach(function (e) { if (e.isIntersecting) { e.target.classList.add('tm-in'); lio.unobserve(e.target); } });
  }, { threshold: 0.25 });
  lists.forEach(function (l) { l.classList.add('tm-rules'); Array.prototype.forEach.call(l.children, function (c, i) { c.style.setProperty('--k', i); }); lio.observe(l); });

  /* ---- 5. section titles rise word by word ---- */
  function splitWords(node, counter) {
    Array.prototype.slice.call(node.childNodes).forEach(function (n) {
      if (n.nodeType === 3) {
        var parts = n.textContent.split(/(\s+)/), frag = document.createDocumentFragment();
        parts.forEach(function (p) {
          if (!p) return;
          if (/^\s+$/.test(p)) { frag.appendChild(document.createTextNode(p)); return; }
          var w = el('span', 'tm-w'); w.textContent = p; w.style.setProperty('--w', counter.i++); frag.appendChild(w);
        });
        n.parentNode.replaceChild(frag, n);
      } else if (n.nodeType === 1) splitWords(n, counter);
    });
  }
  var heads = Array.prototype.slice.call(main.querySelectorAll('section:not(.specialty-hero):not(.speech-hero) h2'));
  if (!reduce) {
    var hio = new IntersectionObserver(function (en) {
      en.forEach(function (e) { if (e.isIntersecting) { e.target.classList.add('tm-show'); hio.unobserve(e.target); } });
    }, { threshold: 0.5 });
    heads.forEach(function (h) { splitWords(h, { i: 0 }); h.classList.add('tm-words'); hio.observe(h); });
  }

  /* ---- one scroll loop for the depth effects ---- */
  if (reduce) return;
  var ticking = false;
  function frame() {
    ticking = false;
    if (signsFrame) signsFrame();
    var vh = window.innerHeight;
    if (hero) {
      var r = hero.getBoundingClientRect();
      if (r.bottom > 0 && r.top < vh) {
        var p = clamp(-r.top / r.height, 0, 1);
        hero.style.setProperty('--hp', p.toFixed(3));
      }
    }
  }
  function onScroll() { if (!ticking) { ticking = true; requestAnimationFrame(frame); } }
  window.addEventListener('scroll', onScroll, { passive: true });
  window.addEventListener('resize', onScroll);
  frame();
})();
