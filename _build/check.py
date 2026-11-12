#!/usr/bin/env python3
"""Στατικός έλεγχος του χτισμένου site (docs/). Μόνο βασική Python. Τρέξε τον μετά από κάθε build:

    python3 _build/build.py && python3 _build/check.py

Ελέγχει σε κάθε σελίδα: ισορροπία tags, ένα h1 και σωστή σειρά επικεφαλίδων, περιοχές (main, nav, header, footer),
στόχο του «Μετάβαση στο περιεχόμενο», μοναδικά id, εσωτερικούς συνδέσμους και άγκυρες, εικόνες (alt, διαστάσεις, αρχεία που
υπάρχουν), τίτλο και περιγραφή (μήκος, μοναδικότητα), canonical, Open Graph, δομημένα δεδομένα (JSON-LD), πολιτική
ασφαλείας, ετικέτες σε κουμπιά, καθώς και κανόνες κειμένου του ιδιοκτήτη (χωρίς μεγάλη παύλα, χωρίς τη λέξη «ερώτημα»).
Ελέγχει ακόμη ότι κανένας χαρακτήρας δεν φέρνει επιπλέον αρχείο γραμματοσειράς, το sitemap, το robots και ότι τίποτα εσωτερικό (_build, README) δεν βρίσκεται στον φάκελο δημοσίευσης.
Κωδικός εξόδου 1 αν υπάρχει πρόβλημα.
"""
import collections, json, os, re, sys, urllib.parse
from html.parser import HTMLParser

NO_HERO_IMAGE = ('404.html', 'contact-us.html')   # σελίδες χωρίς φωτογραφία στην πρώτη οθόνη

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DOCS = os.environ.get('SYNOIDA_DOCS') or os.path.join(ROOT, 'docs')   # άλλος φάκελος εξόδου για δοκιμές: SYNOIDA_DOCS=/διαδρομή
VOID = {'meta', 'link', 'img', 'br', 'hr', 'input', 'source', 'area', 'base', 'col', 'embed', 'track', 'wbr'}
SVG = {'svg', 'path', 'circle', 'rect', 'g', 'line', 'polyline', 'polygon', 'ellipse', 'defs', 'use'}
SCHEMA_SPECIALTY = {'SpeechPathology', 'Pediatric', 'Psychiatric', 'Physiotherapy', 'PrimaryCare', 'Neurologic', 'Nursing', 'CommunityHealth'}
BANNED = [('—', 'μεγάλη παύλα (em dash)'), ('ερώτημα', 'η λέξη «ερώτημα»'), ('ερωτήματα', 'η λέξη «ερωτήματα»'), ('Lorem', 'κείμενο γεμίσματος'), ('TODO', 'σημείωση TODO')]


class Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack, self.unclosed, self.stray = [], [], []
        self.heads, self.cur = [], None
        self.imgs, self.links, self.ids = [], [], collections.Counter()
        self.meta, self.title, self.in_title = {}, '', False
        self.ld, self.in_ld, self.ldbuf = [], False, ''
        self.lang, self.text, self.skip = None, [], 0
        self.land = collections.Counter()
        self.controls, self.ctl = [], None
        self.canon, self.handlers, self.csp, self.scripts_inline = None, 0, None, 0
        self.aria_refs, self.css, self.js = [], [], []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag not in VOID and not (tag in SVG and self.rawtag_selfclosing()):
            self.stack.append(tag)
        if a.get('id'):
            self.ids[a['id']] += 1
        self.handlers += sum(1 for k in a if k.startswith('on'))
        for k in ('aria-controls', 'aria-labelledby', 'aria-describedby'):
            if a.get(k):
                self.aria_refs += a[k].split()
        if tag == 'html':
            self.lang = a.get('lang')
        if tag in ('h1', 'h2', 'h3', 'h4', 'h5', 'h6'):
            self.cur = [int(tag[1]), '']
        if tag == 'img':
            self.imgs.append(a)
        if tag == 'a':
            self.links.append(a)
        if tag in ('a', 'button', 'summary'):
            self.ctl = [tag, a, '', False]
        if tag == 'img' and self.ctl and a.get('alt'):
            self.ctl[3] = True
        if tag == 'meta':
            k = a.get('name') or a.get('property') or a.get('http-equiv')
            if k:
                self.meta[k.lower()] = a.get('content', '')
            if (a.get('http-equiv') or '').lower() == 'content-security-policy':
                self.csp = a.get('content', '')
        if tag == 'link':
            rel = a.get('rel') or ''
            if 'canonical' in rel:
                self.canon = a.get('href')
            if 'stylesheet' in rel:
                self.css.append(a.get('href'))
        if tag == 'title':
            self.in_title = True
        if tag == 'script':
            if a.get('type') == 'application/ld+json':
                self.in_ld, self.ldbuf = True, ''
            elif a.get('src'):
                self.js.append(a)
            else:
                self.scripts_inline += 1
            self.skip += 1
        if tag == 'style':
            self.skip += 1
        if tag in ('main', 'nav', 'header', 'footer'):
            self.land[tag] += 1

    def rawtag_selfclosing(self):
        return (self.get_starttag_text() or '').rstrip().endswith('/>')

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in VOID and self.stack and self.stack[-1] == tag:
            self.stack.pop()

    def handle_endtag(self, tag):
        if tag in VOID:
            return
        if tag in self.stack:
            while self.stack and self.stack[-1] != tag:
                self.unclosed.append(self.stack.pop())
            self.stack.pop()
        else:
            self.stray.append(tag)
        if tag in ('h1', 'h2', 'h3', 'h4', 'h5', 'h6') and self.cur:
            self.heads.append((self.cur[0], ' '.join(self.cur[1].split()))); self.cur = None
        if tag in ('a', 'button', 'summary') and self.ctl and self.ctl[0] == tag:
            self.controls.append(self.ctl); self.ctl = None
        if tag == 'title':
            self.in_title = False
        if tag == 'script':
            if self.in_ld:
                self.ld.append(self.ldbuf); self.in_ld = False
            self.skip -= 1
        if tag == 'style':
            self.skip -= 1

    def handle_data(self, d):
        if self.in_title:
            self.title += d
        if self.in_ld:
            self.ldbuf += d
        if self.cur is not None:
            self.cur[1] += d
        if self.ctl is not None:
            self.ctl[2] += d
        if self.skip == 0 and d.strip():
            self.text.append(d.strip())


def main():
    pages_meta = json.load(open(os.path.join(HERE, 'pages.json'), encoding='utf-8'))
    problems, notes = [], []
    P = {}
    for name in pages_meta:
        path = os.path.join(DOCS, name)
        if not os.path.exists(path):
            problems.append('%s: δεν έχει χτιστεί' % name); continue
        raw = open(path, encoding='utf-8').read()
        x = Page(); x.feed(raw); x.raw = raw; P[name] = x
    titles, descs = collections.Counter(), collections.Counter()
    for name, x in P.items():
        def bad(msg):
            problems.append('%-28s %s' % (name, msg))
        if x.unclosed or x.stray or x.stack:
            bad('tags που δεν κλείνουν σωστά: ανοιχτά %s, περιττά κλεισίματα %s' % (dict(collections.Counter(x.unclosed + x.stack)), dict(collections.Counter(x.stray))))
        if x.lang != 'el':
            bad('λείπει lang="el"')
        h1 = [t for l, t in x.heads if l == 1]
        if len(h1) != 1:
            bad('πρέπει να έχει ακριβώς ένα h1 (έχει %d)' % len(h1))
        prev = 0
        for l, t in x.heads:
            if prev and l > prev + 1:
                bad('πήδημα επικεφαλίδας h%d -> h%d «%s»' % (prev, l, t[:40]))
            prev = l
        for tag, want in (('main', 1), ('header', 1), ('footer', 1)):
            if x.land[tag] != want:
                bad('περιοχή <%s>: %d (θέλει %d)' % (tag, x.land[tag], want))
        if 'main' not in x.ids:
            bad('λείπει id="main" (στόχος του «Μετάβαση στο περιεχόμενο»)')
        if not any(a.get('href') == '#main' for a in x.links):
            bad('λείπει ο σύνδεσμος «Μετάβαση στο περιεχόμενο»')
        dup = [k for k, v in x.ids.items() if v > 1]
        if dup:
            bad('διπλά id: ' + ', '.join(dup))
        for ref in x.aria_refs:
            if ref not in x.ids:
                bad('aria αναφορά σε id που δεν υπάρχει: ' + ref)
        if x.handlers:
            bad('inline χειριστές συμβάντων (on…=): %d' % x.handlers)
        if x.scripts_inline != 1:
            bad('inline scripts: %d (επιτρέπεται μόνο το ένα που έχει hash στην πολιτική ασφαλείας)' % x.scripts_inline)
        if not x.csp or "script-src 'self' 'sha256-" not in x.csp:
            bad('λείπει ή είναι ελλιπής η πολιτική ασφαλείας (CSP)')
        if len(x.css) != 1:
            bad('αρχεία στυλ: %d (θέλει 1)' % len(x.css))
        for s in x.js:
            if 'defer' not in s and s.get('type') != 'module':
                bad('script χωρίς defer: ' + s.get('src', ''))
        # σύνδεσμοι
        base_dir = DOCS
        for a in x.links:
            href = a.get('href')
            if href is None:
                bad('σύνδεσμος χωρίς href'); continue
            if href.startswith(('tel:', 'mailto:')):
                continue
            if href.startswith('#'):
                if len(href) > 1 and href[1:] not in x.ids:
                    bad('άγκυρα που δεν υπάρχει: ' + href)
                continue
            if re.match(r'https?://', href):
                if a.get('target') == '_blank' and 'noopener' not in (a.get('rel') or ''):
                    bad('εξωτερικός σύνδεσμος σε νέα καρτέλα χωρίς rel="noopener": ' + href)
                continue
            target, _, frag = href.partition('#')
            target = target.split('?')[0]
            if target.endswith('.html'):
                if target not in P:
                    bad('σύνδεσμος σε σελίδα που δεν υπάρχει: ' + href)
                elif frag and frag not in P[target].ids:
                    bad('σύνδεσμος σε άγκυρα που δεν υπάρχει: ' + href)
            elif target and not os.path.exists(os.path.join(base_dir, urllib.parse.unquote(target))):
                bad('σύνδεσμος σε αρχείο που δεν υπάρχει: ' + href)
        for tag, a, text, has_img in x.controls:
            if not (text.strip() or a.get('aria-label') or a.get('title') or has_img):
                bad('<%s> χωρίς όνομα για αναγνώστη οθόνης (%s)' % (tag, a.get('href') or a.get('id') or a.get('class', '')[:30]))
        # εικόνες
        for im in x.imgs:
            src = im.get('src', '')
            if 'alt' not in im:
                bad('εικόνα χωρίς alt: ' + src)
            if not (im.get('width') and im.get('height')):
                bad('εικόνα χωρίς width/height: ' + src)
            files = [src] + [c.strip().split(' ')[0] for c in (im.get('srcset') or '').split(',') if c.strip()]
            for f in files:
                if not os.path.exists(os.path.join(DOCS, f)):
                    bad('λείπει αρχείο εικόνας: ' + f)
            if im.get('srcset') and not im.get('sizes'):
                bad('εικόνα με srcset χωρίς sizes: ' + src)
        heroes = [im for im in x.imgs if im.get('fetchpriority') == 'high']
        # 404 και Επικοινωνία δεν έχουν φωτογραφία στην πρώτη οθόνη (η Επικοινωνία ανοίγει με τα τηλέφωνα)
        if name not in NO_HERO_IMAGE and not heroes:
            bad('καμία εικόνα με fetchpriority="high" (η πρώτη μεγάλη εικόνα)')
        if name in NO_HERO_IMAGE and heroes:
            bad('σελίδα χωρίς φωτογραφία πρώτης οθόνης έχει εικόνα με fetchpriority="high"')
        for im in heroes:
            if im.get('loading') == 'lazy':
                bad('η κύρια εικόνα δεν πρέπει να είναι lazy: ' + im.get('src', ''))
        for ref in set(re.findall(r'(?:href|src)="(assets/[^"#?]+)', x.raw)) | set(re.findall(r"url\('(assets/[^')]+)'\)", x.raw)):
            if not os.path.exists(os.path.join(DOCS, ref)):
                bad('λείπει αρχείο: ' + ref)
        # SEO
        t = x.title.strip(); d = x.meta.get('description', '')
        titles[t] += 1; descs[d] += 1
        if not 10 <= len(t) <= 60:
            bad('τίτλος %d χαρακτήρες (10 έως 60): «%s»' % (len(t), t))
        if name != '404.html' and not 110 <= len(d) <= 160:
            bad('περιγραφή %d χαρακτήρες (110 έως 160)' % len(d))
        if name != '404.html' and not x.canon:
            bad('λείπει canonical')
        for k in ('og:title', 'og:description', 'og:image', 'og:url', 'og:type', 'og:image:alt', 'twitter:card'):
            if k not in x.meta:
                bad('λείπει ' + k)
        og = x.meta.get('og:image', '')
        if og and not os.path.exists(os.path.join(DOCS, 'assets', og.rsplit('/', 1)[-1])):
            bad('λείπει η εικόνα og:image: ' + og.rsplit('/', 1)[-1])
        if 'viewport' not in x.meta:
            bad('λείπει viewport')
        types = []
        for j in x.ld:
            try:
                data = json.loads(j)
            except Exception as ex:
                bad('JSON-LD που δεν διαβάζεται: %s' % str(ex)[:60]); continue
            types.append(data.get('@type'))
            if data.get('@type') == 'MedicalOrganization':
                for s in data.get('medicalSpecialty', []):
                    if s.rsplit('/', 1)[-1] not in SCHEMA_SPECIALTY:
                        bad('JSON-LD: άγνωστη ειδικότητα schema.org «%s»' % s)
                if len(data.get('location', [])) != 4:
                    bad('JSON-LD: θέλει 4 κέντρα')
            if data.get('@type') == 'BreadcrumbList':
                last = data['itemListElement'][-1]
                if x.canon and last.get('item') != x.canon:
                    bad('JSON-LD: η διαδρομή δεν καταλήγει στη σελίδα')
            if data.get('@type') == 'FAQPage' and not all(q.get('name') and q['acceptedAnswer'].get('text') for q in data['mainEntity']):
                bad('JSON-LD: ερώτηση χωρίς κείμενο')
        if 'MedicalOrganization' not in types:
            bad('λείπει το JSON-LD του οργανισμού')
        if name not in ('index.html', '404.html') and 'BreadcrumbList' not in types:
            bad('λείπει το JSON-LD της διαδρομής')
        if '<details' in x.raw.split('<main', 1)[-1].split('</main>')[0] and 'FAQPage' not in types:
            bad('σελίδα με ερωτήσεις χωρίς JSON-LD FAQPage')
        # κανόνες κειμένου
        visible = ' '.join(x.text) + ' ' + ' '.join(im.get('alt', '') for im in x.imgs) + ' ' + t + ' ' + d
        for word, label in BANNED:
            if word in visible:
                bad('κείμενο: ' + label)
        if re.search(r'\[[^\]]{0,40}(?:Χ|ΣΥΜΠΛΗΡ|;)[^\]]{0,40}\]', visible):
            bad('κείμενο: αγκύλη προς συμπλήρωση')
    # γραμματοσειρές: κάθε χαρακτήρας των σελίδων να καλύπτεται από τα 4 βασικά αρχεία (αλλιώς κατεβαίνει επιπλέον αρχείο 20 έως 85 KB)
    fonts_css = os.path.join(HERE, 'css', '10-fonts.css')
    if os.path.exists(fonts_css):
        def cps(rng):
            out = set()
            for part in rng.split(','):
                part = part.strip().replace('U+', '')
                if part:
                    lo, _, hi = part.partition('-'); out.update(range(int(lo, 16), int(hi or lo, 16) + 1))
            return out
        base_cov, extra = {}, {}
        for fam, fname, rng in re.findall(r"font-family:'([^']+)'[^}]*?url\(fonts/([\w.-]+)\)[^}]*?unicode-range:([^;}]+)", open(fonts_css, encoding='utf-8').read()):
            target = extra if re.search(r'-(full|ext)\.woff2$', fname) else base_cov
            target.setdefault(fam, {}).setdefault(fname, set()).update(cps(rng))
        for name, x in P.items():
            chars = set(ord(c) for c in ' '.join(x.text) + x.title if ord(c) > 0x20)
            for fam in base_cov:
                covered = set().union(*base_cov[fam].values())
                for fname, rng in extra.get(fam, {}).items():
                    hit = sorted(chars & rng - covered)
                    if hit:
                        problems.append('%-28s οι χαρακτήρες «%s» κατεβάζουν επιπλέον γραμματοσειρά (%s): πρόσθεσέ τους στο CORE του make_fonts.py' % (name, ''.join(chr(c) for c in hit[:8]), fname))
    for t, n in titles.items():
        if n > 1:
            problems.append('ίδιος τίτλος σε %d σελίδες: «%s»' % (n, t))
    for d, n in descs.items():
        if n > 1 and d:
            problems.append('ίδια περιγραφή σε %d σελίδες' % n)
    # sitemap, robots, καθαρός φάκελος δημοσίευσης
    sm = open(os.path.join(DOCS, 'sitemap.xml'), encoding='utf-8').read() if os.path.exists(os.path.join(DOCS, 'sitemap.xml')) else ''
    locs = re.findall(r'<loc>([^<]+)</loc>', sm)
    canon = [x.canon for n, x in P.items() if n != '404.html']
    if sorted(locs) != sorted(c for c in canon if c):
        problems.append('το sitemap δεν συμφωνεί με τα canonical των σελίδων')
    if not os.path.exists(os.path.join(DOCS, 'robots.txt')):
        problems.append('λείπει robots.txt')
    else:
        robots = open(os.path.join(DOCS, 'robots.txt'), encoding='utf-8').read()
        noindex = [n for n, x in P.items() if 'noindex' in x.meta.get('robots', '')]
        final = 'Allow: /' in robots
        if final and [n for n in noindex if n != '404.html']:
            problems.append('τελική έκδοση (robots Allow) αλλά υπάρχουν σελίδες με noindex')
        if not final and len(noindex) != len(P):
            problems.append('δοκιμαστική έκδοση (robots Disallow) αλλά δεν έχουν όλες οι σελίδες noindex')
        notes.append('έκδοση: %s' % ('ΤΕΛΙΚΗ (ευρετηριάζεται)' if final else 'δοκιμαστική (noindex παντού)'))
    for junk in ('_build', 'README.md', '.git', '.DS_Store', 'node_modules'):
        if os.path.exists(os.path.join(DOCS, junk)):
            problems.append('εσωτερικό αρχείο μέσα στον φάκελο δημοσίευσης: ' + junk)
    total = sum(os.path.getsize(os.path.join(d, f)) for d, _, fs in os.walk(DOCS) for f in fs)
    notes.append('φάκελος δημοσίευσης: %d αρχεία, %.1f MB' % (sum(len(fs) for _, _, fs in os.walk(DOCS)), total / 1e6))
    for n in notes:
        print('·', n)
    for p in problems:
        print('ΠΡΟΒΛΗΜΑ', p)
    print('%s: %d σελίδες, %d προβλήματα' % ('ΑΠΟΤΥΧΙΑ' if problems else 'ΟΚ', len(P), len(problems)))
    sys.exit(1 if problems else 0)


if __name__ == '__main__':
    main()
