#!/usr/bin/env python3
"""Χτίζει το site ΣΥΝΟΙΔΑ: template + fragments -> docs/ (ο μόνος φάκελος που δημοσιεύεται).

    python3 _build/build.py                 δοκιμαστική έκδοση (noindex, σήμα «Δοκιμαστική έκδοση»)
    python3 _build/build.py --final         τελική έκδοση (επιτρέπει ευρετηρίαση, χωρίς σήμα)
    python3 _build/build.py --base https://www.synoida.gr/      άλλη διεύθυνση (canonical, sitemap, og)
    python3 _build/build.py --prune         σβήνει από το docs/assets ό,τι δεν αναφέρεται πια

Μόνο βασική Python, χωρίς πακέτα. Πηγές:
    _build/template.html        κοινό κέλυφος (head, μενού, υποσέλιδο)
    _build/fragments/*.html     το <main> κάθε σελίδας
    _build/pages.json           τίτλος, περιγραφή, όνομα πλοήγησης ανά σελίδα
    _build/css/*.css            στυλ, με αλφαβητική σειρά (ενώνονται σε ένα αρχείο)
    assets/*.js, assets/fonts   συμπεριφορά και γραμματοσειρές
    _build/images.json          διαστάσεις και πλάτη εικόνων (το γράφει το tools/make_images.py)
    _build/image-sizes.json     το sizes κάθε εικόνας (το γράφει το tools/measure_sizes.py)
Μετά από κάθε build τρέξε: python3 _build/check.py
"""
import argparse, base64, glob, hashlib, html, json, os, re, shutil, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
FRAG = os.path.join(HERE, 'fragments')
SRC_ASSETS = os.path.join(ROOT, 'assets')
DEFAULT_BASE = 'https://dimitriskatik13-cmd.github.io/synoida-site-fable-5.2/'
MARKER = ('<!-- ΠΑΡΑΓΕΤΑΙ ΑΥΤΟΜΑΤΑ από _build/build.py. Μην επεξεργάζεσαι αυτό το αρχείο: '
          'άλλαξε το _build/fragments/<σελίδα>.html ή το _build/template.html και τρέξε python3 _build/build.py -->')
# ποιο script φορτώνει πού (το site.js φορτώνει παντού)
PAGE_JS = (('index.html', 'stars-mark.js'), ('treatment-', 'therapy-motion.js'), ('rating.html', 'assessment-motion.js'), ('contact-us.html', 'contact.js'))
DEFAULT_SIZES = '(max-width: 1023px) 100vw, 50vw'


def read(p):
    with open(p, encoding='utf-8') as f:
        return f.read()


def write(p, s):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    data = s.encode('utf-8') if isinstance(s, str) else s
    if os.path.exists(p) and open(p, 'rb').read() == data:
        return                                            # δεν αλλάζει mtime χωρίς λόγο
    with open(p, 'wb') as f:
        f.write(data)


def minify_css(css):
    css = re.sub(r'/\*.*?\*/', '', css, flags=re.S)
    css = re.sub(r'\s+', ' ', css)
    css = re.sub(r'\s*([{};,])\s*', r'\1', css)
    css = re.sub(r':\s+', ':', css)                       # «a: b» -> «a:b» (ποτέ κενό ΠΡΙΝ από «:», για να μη χαλάσει «a :hover»)
    return css.replace(';}', '}').strip()


def text_of(fragment):
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', fragment))).strip()


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--base', default=DEFAULT_BASE, help='διεύθυνση του site, με τελικό /')
    ap.add_argument('--final', action='store_true', help='τελική έκδοση: επιτρέπει ευρετηρίαση, χωρίς σήμα δοκιμής')
    ap.add_argument('--out', default=os.path.join(ROOT, 'docs'))
    ap.add_argument('--prune', action='store_true', help='σβήνει αρχεία του docs/assets που δεν αναφέρονται')
    a = ap.parse_args()
    base = a.base if a.base.endswith('/') else a.base + '/'
    out, out_assets = a.out, os.path.join(a.out, 'assets')
    template = read(os.path.join(HERE, 'template.html'))
    pages = json.load(open(os.path.join(HERE, 'pages.json'), encoding='utf-8'))
    images = json.load(open(os.path.join(HERE, 'images.json'), encoding='utf-8'))
    sizes_path = os.path.join(HERE, 'image-sizes.json')
    sizes = json.load(open(sizes_path, encoding='utf-8')) if os.path.exists(sizes_path) else {}

    # ---------- CSS: όλα τα στρώματα σε ένα αρχείο με όνομα από το περιεχόμενο ----------
    layers = sorted(glob.glob(os.path.join(HERE, 'css', '*.css')))
    css = minify_css('\n'.join(read(p) for p in layers))
    css_name = 'assets/site.%s.css' % hashlib.sha256(css.encode()).hexdigest()[:10]
    write(os.path.join(out, css_name), css)
    for font in sorted(set(re.findall(r'url\(fonts/([A-Za-z0-9._-]+)\)', css))):
        write(os.path.join(out_assets, 'fonts', font), open(os.path.join(SRC_ASSETS, 'fonts', font), 'rb').read())

    # ---------- JS: αντίγραφο με όνομα από το περιεχόμενο ----------
    js_names = {}
    for name in ['site.js'] + [j for _, j in PAGE_JS]:
        data = open(os.path.join(SRC_ASSETS, name), 'rb').read()
        js_names[name] = 'assets/%s.%s.js' % (name[:-3], hashlib.sha256(data).hexdigest()[:10])
        write(os.path.join(out, js_names[name]), data)

    # το μοναδικό inline script (σημαδεύει ότι υπάρχει JS πριν ζωγραφιστεί η σελίδα) μπαίνει στην πολιτική με hash
    inline = re.search(r'<script>(.*?)</script>', template, re.S).group(1)
    csp = ("default-src 'self'; script-src 'self' 'sha256-%s'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
           "font-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'self'; form-action 'none'"
           % base64.b64encode(hashlib.sha256(inline.encode()).digest()).decode())

    built, problems = [], []
    for outfile, meta in pages.items():
        fpath = os.path.join(FRAG, outfile)
        if not os.path.exists(fpath):
            problems.append('ΛΕΙΠΕΙ fragment: ' + outfile); continue
        main_html = read(fpath).strip()
        if not re.match(r'<main\b', main_html):
            problems.append('%s: το fragment πρέπει να ξεκινά με <main>' % outfile)
        if 'id="main"' not in main_html.split('>', 1)[0]:
            main_html = re.sub(r'^<main\b', '<main id="main"', main_html, 1)      # στόχος του «Μετάβαση στο περιεχόμενο»
        url = base if outfile == 'index.html' else base + outfile

        # og:image: JPG 1200x630 από την πρώτη φωτογραφία της σελίδας
        first = re.search(r'<img\b[^>]*\bsrc="assets/([A-Za-z0-9_-]+)\.(?:jpg|png|webp)"[^>]*>', main_html)
        og_name = (first.group(1) if first else 'hero-room').replace('hero-room-bg', 'hero-room')
        if not images.get(og_name, {}).get('og'):
            og_name = 'hero-room'
        og_alt = re.search(r'\balt="([^"]*)"', first.group(0)).group(1) if first and re.search(r'\balt="([^"]+)"', first.group(0)) else 'Χώρος θεραπείας στη ΣΥΝΟΙΔΑ'
        og_extra = ('  <meta property="og:image:width" content="1200" />\n  <meta property="og:image:height" content="630" />\n'
                    '  <meta property="og:image:alt" content="%s" />\n' % og_alt)

        # δομημένα δεδομένα ανά σελίδα: διαδρομή και συχνές ερωτήσεις
        ld = []
        if outfile not in ('index.html', '404.html'):
            trail = [('Αρχική', base)]
            if outfile.startswith('treatment-'):
                trail.append((pages['treatments.html']['crumb'], base + 'treatments.html'))
            trail.append((meta['crumb'], url))
            ld.append({'@context': 'https://schema.org', '@type': 'BreadcrumbList', 'itemListElement': [
                {'@type': 'ListItem', 'position': i + 1, 'name': n, 'item': u} for i, (n, u) in enumerate(trail)]})
        faq = re.findall(r'<details\b[^>]*>\s*<summary\b[^>]*>(.*?)</summary>(.*?)</details>', main_html, re.S)
        if faq:
            ld.append({'@context': 'https://schema.org', '@type': 'FAQPage', 'mainEntity': [
                {'@type': 'Question', 'name': text_of(q), 'acceptedAnswer': {'@type': 'Answer', 'text': text_of(ans)}} for q, ans in faq]})
        jsonld = ''.join('  <script type="application/ld+json">%s</script>\n' % json.dumps(x, ensure_ascii=False, separators=(',', ':')) for x in ld)

        scripts = '  <script src="%s" defer></script>\n' % js_names['site.js']
        for prefix, js in PAGE_JS:
            if outfile.startswith(prefix):
                scripts += '  <script src="%s" defer></script>\n' % js_names[js]

        page = (template
                .replace('{{TITLE}}', html.escape(meta['title'], quote=True))
                .replace('{{DESC}}', html.escape(meta['description'], quote=True))
                .replace('{{PAGE}}', meta['nav'])
                .replace('{{URL}}', url)
                .replace('{{OGIMG}}', base + 'assets/%s-og.jpg' % og_name)
                .replace('{{OGEXTRA}}', og_extra)
                .replace('{{CSP}}', '  <meta http-equiv="Content-Security-Policy" content="%s" />\n' % csp)
                .replace('{{JSONLD}}', jsonld)
                .replace('{{CSS}}', css_name)
                .replace('{{SCRIPTS}}', scripts)
                .replace('{{MAIN}}', main_html)
                .replace('{{BASE}}', base))
        page = page.replace('<!doctype html>', '<!doctype html>\n' + MARKER, 1)
        if outfile == 'contact-us.html':
            # σε αυτή τη σελίδα το δεύτερο κουμπί της κάτω μπάρας θα έδειχνε στον εαυτό της: δίνει email
            page = page.replace('<a href="contact-us.html" class="callbar-contact">Επικοινωνία</a>', '<a href="mailto:info@synoida.gr" class="callbar-contact">Email</a>', 1)
        if outfile == '404.html':
            # το 404 σερβίρεται σε οποιοδήποτε path: τα σχετικά links θέλουν σταθερή βάση
            page = page.replace('<head>', '<head>\n  <base href="%s" />' % (re.sub(r'^https?://[^/]+', '', base) or '/'), 1)
            page = page.replace('  <link rel="canonical" href="%s" />\n' % url, '')
        if a.final:
            page = re.sub(r'<(p|figcaption|aside|span|small|div)\b[^>]*\bdata-preview-only\b[^>]*>.*?</\1>\n?', '', page, flags=re.S)
            if outfile != '404.html':
                page = page.replace('  <!-- demo deployment: εκτός ευρετηρίασης -->\n  <meta name="robots" content="noindex, nofollow" />\n', '')

        # ---------- εικόνες: WebP σε πολλά πλάτη, sizes από μέτρηση, width/height για σταθερή διάταξη ----------
        seen = {}

        def img(m):
            tag, name = m.group(0), m.group(1)
            info = images.get(name)
            if not info or not info.get('widths'):
                return tag
            k = seen.get(name, 0); seen[name] = k + 1
            ws = info['widths']
            srcset = ', '.join('assets/%s-%d.webp %dw' % (name, w, w) for w in ws)
            sz = sizes.get(outfile, {}).get('%s#%d' % (name, k)) or sizes.get('*', {}).get(name) or DEFAULT_SIZES
            fallback = min(ws, key=lambda w: abs(w - 800))
            tag = re.sub(r'\s(?:srcset|sizes)="[^"]*"', '', tag)
            tag = re.sub(r'\bsrc="[^"]*"', 'src="assets/%s-%d.webp" srcset="%s" sizes="%s"' % (name, fallback, srcset, sz), tag, 1)
            if ' width=' not in tag:
                tag = tag.replace('<img ', '<img width="%d" height="%d" ' % (info['w'], info['h']), 1)
            return tag
        page = re.sub(r'<img\b[^>]*\bsrc="assets/([A-Za-z0-9_-]+)\.(?:jpg|png|webp)"[^>]*>', img, page)

        # mosaic: η φωτογραφία σε κομμάτια. Το fragment δηλώνει style="--img:url(assets/<όνομα>.jpg)" στο πλαίσιο·
        # εδώ γίνεται inline φόντο σε κάθε κομμάτι (.tile), γιατί url μέσα σε μεταβλητή CSS δεν λύνεται ίδια σε όλους τους browsers.
        def mosaic(m):
            name = m.group(2)
            ws = images.get(name, {}).get('widths', [])
            if 800 not in ws or 1600 not in ws:
                problems.append('%s: mosaic χωρίς εκδόσεις 800/1600 για %s' % (outfile, name)); return m.group(0)
            # πρώτα απλό url (παλιότεροι browsers), μετά image-set για οθόνες υψηλής ανάλυσης
            bg = "background-image:url('assets/%s-800.webp');background-image:image-set(url('assets/%s-800.webp') 1x,url('assets/%s-1600.webp') 2x);" % (name, name, name)
            block = m.group(1) + m.group(3)
            block, n = re.subn(r'(<span class="tile[^"]*" style=")', r'\1' + bg, block)
            if not n:
                problems.append('%s: mosaic χωρίς κομμάτια .tile' % outfile)
            return block
        page = re.sub(r'(<div class="mosaic[^"]*") style="--img:url\(assets/([A-Za-z0-9_-]+)\.jpg\)"([^>]*>.*?</div>)', mosaic, page, flags=re.S)

        left = sorted(set(re.findall(r'\{\{[A-Z_]+\}\}', page)))
        if left:
            sys.exit('Ασυμπλήρωτα σημεία στο %s: %s' % (outfile, ', '.join(left)))
        write(os.path.join(out, outfile), page)
        built.append(outfile)

    # ---------- sitemap, robots, λοιπά αρχεία ----------
    sm = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    sm += ['  <url><loc>%s</loc></url>' % (base if p == 'index.html' else base + p) for p in pages if p != '404.html']
    write(os.path.join(out, 'sitemap.xml'), '\n'.join(sm + ['</urlset>']) + '\n')
    write(os.path.join(out, 'robots.txt'), ('User-agent: *\nAllow: /\nSitemap: %ssitemap.xml\n' % base) if a.final else 'User-agent: *\nDisallow: /\n')
    write(os.path.join(out, '.nojekyll'), '')

    # ό,τι άλλο αναφέρεται ως assets/… και δεν είναι παραγόμενο (favicon κ.λπ.) αντιγράφεται όπως είναι
    produced = '\n'.join(read(os.path.join(out, p)) for p in built) + css
    refs = set(re.findall(r'assets/[A-Za-z0-9._/-]+\.[A-Za-z0-9]+', produced)) | set('assets/fonts/' + f for f in re.findall(r'url\(fonts/([A-Za-z0-9._-]+)\)', css))
    for ref in sorted(refs):
        dst = os.path.join(out, ref)
        if not os.path.exists(dst):
            src = os.path.join(ROOT, ref)
            if os.path.exists(src):
                shutil.copyfile(src, dst)
            else:
                problems.append('ΛΕΙΠΕΙ αρχείο που αναφέρεται: %s (εικόνα; τρέξε _build/tools/make_images.py)' % ref)
    extra = sorted(os.path.relpath(os.path.join(d, f), out) for d, _, fs in os.walk(out_assets) for f in fs
                   if os.path.relpath(os.path.join(d, f), out) not in refs and not f.startswith('.'))
    if a.prune:
        for e in extra:
            os.remove(os.path.join(out, e))
    stale = sorted(set(os.path.basename(p) for p in glob.glob(os.path.join(out, '*.html'))) - set(pages))
    orphans = sorted(set(f for f in os.listdir(FRAG) if f.endswith('.html')) - set(pages))

    print('BUILD: %d σελίδες στο %s · CSS %.1f KB (%d στρώματα) · %s' % (
        len(built), os.path.relpath(out, ROOT), len(css.encode()) / 1024, len(layers), 'ΤΕΛΙΚΗ' if a.final else 'δοκιμαστική (noindex)'))
    if extra:
        print('%s %d αρχεία του docs/assets που δεν αναφέρονται%s' % ('ΣΒΗΣΤΗΚΑΝ' if a.prune else 'ΠΕΡΙΣΣΕΥΟΥΝ', len(extra), '' if a.prune else ' (τρέξε με --prune)'))
    for label, items in (('ΠΑΛΙΕΣ σελίδες στο docs χωρίς πηγή', stale), ('FRAGMENTS χωρίς εγγραφή στο pages.json', orphans)):
        if items:
            problems.append('%s: %s' % (label, ', '.join(items)))
    for p in problems:
        print('ΠΡΟΒΛΗΜΑ:', p)
    sys.exit(1 if problems else 0)


if __name__ == '__main__':
    main()
