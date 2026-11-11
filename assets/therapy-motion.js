/* Σελίδες θεραπειών: ο μετρητής της ενότητας «Πότε να απευθυνθείτε».
   Το σημείο που διαβάζεται φωτίζεται και ένας μετρητής «03 / 06» με μπάρα δείχνει πού βρίσκεται ο αναγνώστης:
   στον υπολογιστή μέσα στην κολλημένη αριστερή στήλη, στο κινητό ως λεπτή μπάρα κάτω από την κεφαλίδα.
   Μόνο διακοσμητικό: χωρίς JavaScript η λίστα φαίνεται ολόκληρη. Με «μείωση κίνησης» δεν τρέχει καθόλου.
   Όλη η υπόλοιπη κίνηση της σελίδας (εμφάνιση, γραμμή βημάτων, φωτογραφία τίτλου) είναι CSS. */
(function () {
  var main = document.querySelector('main.pg-therapy');
  var list = main && main.querySelector('.pg-signs-list');
  if (!list || window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
  var items = Array.prototype.slice.call(list.children);
  var total = items.length;
  if (total < 2) return;

  function pad(n) { return String(n).padStart(2, '0'); }

  /* ένας μετρητής: <b>03</b><i>/ 06</i><em><u></u></em> */
  function makeCounter(cls) {
    var box = document.createElement('div');
    box.className = cls;
    box.setAttribute('aria-hidden', 'true');
    box.innerHTML = '<span><b>01</b><i>/ ' + pad(total) + '</i></span><em><u></u></em>';
    return box;
  }
  var counters = [];
  var intro = main.querySelector('.pg-signs-intro');
  if (intro) {                                             // υπολογιστής: πριν από τον σύνδεσμο της αριστερής στήλης
    var side = makeCounter('pg-count');
    intro.insertBefore(side, intro.querySelector('.signs-cta'));
    counters.push(side);
  }
  var bar = makeCounter('pg-countbar');                    // κινητό: κολλημένη μπάρα πάνω από τη λίστα
  list.parentNode.insertBefore(bar, list);
  counters.push(bar);
  main.classList.add('tm-on');

  /* η μπάρα του κινητού κολλά ακριβώς κάτω από την κεφαλίδα */
  var header = document.querySelector('.site-header');
  function measure() { if (header) main.style.setProperty('--pg-hdr', header.offsetHeight + 'px'); }

  var current = -1;
  function paint(idx) {
    if (idx === current) return;
    current = idx;
    items.forEach(function (li, i) { li.classList.toggle('is-on', i === idx); });
    counters.forEach(function (c) {
      c.querySelector('b').textContent = pad(idx + 1);
      c.querySelector('u').style.transform = 'scaleX(' + ((idx + 1) / total).toFixed(3) + ')';
    });
  }

  /* ενεργό είναι το σημείο που βρίσκεται πιο κοντά στη μέση της οθόνης· ελέγχεται σε κάθε καρέ κύλισης */
  var ticking = false;
  function frame() {
    ticking = false;
    var vh = window.innerHeight, box = list.getBoundingClientRect();
    if (box.bottom < 0 || box.top > vh) return;            // εκτός οθόνης: μένει η τελευταία κατάσταση
    var mid = vh / 2, best = 0, bestDist = Infinity;
    items.forEach(function (li, i) {
      var r = li.getBoundingClientRect();
      var d = (r.top <= mid && r.bottom >= mid) ? 0 : Math.min(Math.abs(r.top - mid), Math.abs(r.bottom - mid));
      if (d < bestDist) { bestDist = d; best = i; }
    });
    paint(best);
  }
  function onScroll() { if (!ticking) { ticking = true; requestAnimationFrame(frame); } }
  window.addEventListener('scroll', onScroll, { passive: true });
  window.addEventListener('resize', function () { measure(); onScroll(); });
  measure();
  paint(0);
  frame();
})();
