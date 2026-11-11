/* Αξιολόγηση: the four steps of «Η διαδικασία, βήμα βήμα» light up one by one while scrolling,
   the same way the «Πότε να απευθυνθείτε» signs do on the therapy pages. Decorative only.
   The active step is the one closest to the middle of the screen, computed on every scroll frame,
   so a fast fling never skips a step (an intersection band would). */
(function () {
  var main = document.querySelector('main.assessment-refined');
  var steps = main && main.querySelector('.assessment-steps');
  if (!steps) return;
  var items = Array.prototype.slice.call(steps.children);
  if (items.length < 2) return;
  main.classList.add('as-on');
  var reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var current = -1, target = -1, walking = false;
  function paint(idx) {
    items.forEach(function (li, i) { li.classList.toggle('is-on', i === idx); li.classList.toggle('is-past', i < idx); });
  }
  /* move one step per frame towards the target, so every step lights up in order even after a jump */
  function walk() {
    walking = false;
    if (current === target) return;
    current += current < target ? 1 : -1;
    paint(current);
    if (current !== target) { walking = true; requestAnimationFrame(walk); }
  }
  function setActive(idx) {
    target = idx;
    if (current === -1) { current = idx; paint(idx); return; }
    if (!walking) walk();
  }
  if (reduce) { current = items.length - 1; paint(current); return; }
  var ticking = false;
  function frame() {
    ticking = false;
    var mid = window.innerHeight / 2;
    var list = steps.getBoundingClientRect();
    if (list.bottom < 0 || list.top > window.innerHeight) return;   /* off screen: keep the last state */
    var best = -1, bestDist = Infinity;
    items.forEach(function (li, i) {
      var r = li.getBoundingClientRect();
      var d = (r.top <= mid && r.bottom >= mid) ? 0 : Math.min(Math.abs(r.top - mid), Math.abs(r.bottom - mid));
      if (d < bestDist) { bestDist = d; best = i; }
    });
    if (best >= 0) setActive(best);
  }
  function onScroll() { if (!ticking) { ticking = true; requestAnimationFrame(frame); } }
  window.addEventListener('scroll', onScroll, { passive: true });
  window.addEventListener('resize', onScroll);
  frame();
})();
