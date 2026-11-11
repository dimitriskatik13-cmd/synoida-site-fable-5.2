#!/usr/bin/env python3
"""Παράγει τις εκδόσεις εικόνων που δημοσιεύονται (docs/assets) από τις κύριες εικόνες του assets/.

Χρειάζεται Pillow (το build.py ΔΕΝ το χρειάζεται). Τρέξε το μόνο όταν αλλάξει ή προστεθεί φωτογραφία:
    python3 -m venv .venv && .venv/bin/pip install pillow && .venv/bin/python _build/tools/make_images.py

Για κάθε φωτογραφία assets/<όνομα>.jpg γράφει docs/assets/<όνομα>-<πλάτος>.webp σε 400, 640, 800, 1200, 1600
(και 1920, 2880 για το hero της Αρχικής, από την πρωτότυπη λήψη όταν υπάρχει στον υπολογιστή).
Όσο μεγαλύτερο το πλάτος, τόσο χαμηλότερη η ποιότητα: σε οθόνες υψηλής ανάλυσης δεν φαίνεται και μειώνει το βάρος.
Γράφει και το _build/images.json (διαστάσεις και διαθέσιμα πλάτη), από το οποίο το build.py φτιάχνει srcset, width, height.
"""
import glob, json, os, re, sys
from PIL import Image, ImageOps

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
ASSETS = os.path.join(ROOT, 'assets')
OUT = os.path.join(ROOT, 'docs', 'assets')
FRAG = os.path.join(ROOT, '_build', 'fragments')

WIDTHS = (400, 640, 800, 1200, 1600)
HERO = {'hero-room-bg': (1920, 2880)}                 # full-bleed hero της Αρχικής
QUALITY = {400: 80, 640: 80, 800: 78, 1200: 74, 1600: 70, 1920: 66, 2880: 56}
ALPHA = {'hero-room-fg': (800, 1200, 1920, 2880)}      # cut-out προσκήνιο του hero (διαφάνεια)
LOGOS = {'logo-horizontal': (200, 280, 400, 560), 'logo-stacked-light': (210, 300, 420)}   # χωρίς απώλειες: το λογότυπο μένει αυθεντικό
SKIP = ('favicon', 'apple-touch')


def used_images():
    """Ονόματα εικόνων που αναφέρονται σε template και fragments, και η πρώτη εικόνα κάθε σελίδας (για og:image)."""
    used, first = set(), {}
    files = [os.path.join(ROOT, '_build', 'template.html')] + sorted(glob.glob(os.path.join(FRAG, '*.html')))
    for f in files:
        names = re.findall(r'<img\b[^>]*\bsrc="assets/([A-Za-z0-9_-]+)\.(?:jpg|png|webp)"', open(f, encoding='utf-8').read())
        used.update(names)
        if names and os.path.dirname(f) == FRAG:
            first[os.path.basename(f)] = names[0]
    return used, first


def originals():
    src = json.load(open(os.path.join(ROOT, '_build', 'photo-sources.json'), encoding='utf-8'))
    base = src.get('_originals_dir', '')
    # ο ίδιος φάκελος υπάρχει με άλλο όνομα χρήστη στον δεύτερο υπολογιστή
    cands = [base, re.sub(r'^/Users/[^/]+/', os.path.expanduser('~') + '/', base)]
    for c in cands:
        if os.path.isdir(c):
            return c, src
    return None, src


def fit(im, w):
    if im.width <= w:
        return im.copy()
    return im.resize((w, round(im.height * w / im.width)), Image.LANCZOS)


def main():
    os.makedirs(OUT, exist_ok=True)
    used, first = used_images()
    odir, omap = originals()
    manifest, total, n = {}, 0, 0
    for name in sorted(used):
        if name.startswith(SKIP):
            continue
        if name in LOGOS:
            im = Image.open(os.path.join(ASSETS, name + '.png')).convert('RGBA')
            ws = [w for w in LOGOS[name] if w <= im.width]
            for w in ws:
                p = os.path.join(OUT, '%s-%d.webp' % (name, w)); fit(im, w).save(p, 'WEBP', lossless=True, method=6)
                total += os.path.getsize(p); n += 1
            manifest[name] = {'w': im.width, 'h': im.height, 'widths': ws}
            continue
        if name in ALPHA:
            srcp = max(glob.glob(os.path.join(ASSETS, name + '*.webp')), key=os.path.getsize)
            im = Image.open(srcp).convert('RGBA')
            ws = [w for w in ALPHA[name] if w <= im.width]
            for w in ws:
                p = os.path.join(OUT, '%s-%d.webp' % (name, w)); fit(im, w).save(p, 'WEBP', quality=QUALITY.get(w, 70), alpha_quality=80, method=6)
                total += os.path.getsize(p); n += 1
            manifest[name] = {'w': im.width, 'h': im.height, 'widths': ws}
            continue
        master = os.path.join(ASSETS, name + '.jpg')
        if not os.path.exists(master):
            print('ΠΑΡΑΛΕΙΨΗ (δεν υπάρχει κύρια εικόνα):', name); continue
        im = ImageOps.exif_transpose(Image.open(master)).convert('RGB')
        wanted = list(WIDTHS) + list(HERO.get(name, ()))
        big = None
        if name in HERO and odir and os.path.exists(os.path.join(odir, omap.get(name, '-'))):
            big = ImageOps.exif_transpose(Image.open(os.path.join(odir, omap[name]))).convert('RGB')
        ws = []
        for w in wanted:
            src = big if (big is not None and w > im.width) else im
            if w > src.width:
                continue
            p = os.path.join(OUT, '%s-%d.webp' % (name, w)); fit(src, w).save(p, 'WEBP', quality=QUALITY[w], method=6)
            total += os.path.getsize(p); n += 1; ws.append(w)
        if im.width not in ws and im.width < min(WIDTHS):
            p = os.path.join(OUT, '%s-%d.webp' % (name, im.width)); im.save(p, 'WEBP', quality=80, method=6); ws.append(im.width)
        manifest[name] = {'w': im.width, 'h': im.height, 'widths': ws}
    # og:image: JPG 1200x630 από την πρώτη εικόνα κάθε σελίδας (τα κοινωνικά δίκτυα θέλουν JPG/PNG)
    for page, name in sorted(first.items()):
        name = 'hero-room' if name == 'hero-room-bg' else name
        master = os.path.join(ASSETS, name + '.jpg')
        if not os.path.exists(master):
            continue
        im = ImageOps.fit(ImageOps.exif_transpose(Image.open(master)).convert('RGB'), (1200, 630), Image.LANCZOS, centering=(0.5, 0.5))
        p = os.path.join(OUT, '%s-og.jpg' % name); im.save(p, 'JPEG', quality=80, optimize=True, progressive=True)
        manifest.setdefault(name, {'w': 1200, 'h': 630, 'widths': []})['og'] = True
    json.dump(manifest, open(os.path.join(ROOT, '_build', 'images.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1, sort_keys=True)
    print('εικόνες: %d αρχεία webp, %.1f MB, %d ονόματα · πρωτότυπα: %s' % (n, total / 1e6, len(manifest), 'βρέθηκαν' if odir else 'όχι σε αυτόν τον υπολογιστή'))


if __name__ == '__main__':
    main()
