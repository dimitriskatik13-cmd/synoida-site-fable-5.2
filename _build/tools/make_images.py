#!/usr/bin/env python3
"""Παράγει τις εκδόσεις εικόνων που δημοσιεύονται (docs/assets) από τις κύριες εικόνες του assets/.

Χρειάζεται Pillow (το build.py ΔΕΝ το χρειάζεται). Τρέξε το μόνο όταν αλλάξει ή προστεθεί φωτογραφία:
    python3 -m venv .venv && .venv/bin/pip install pillow && .venv/bin/python _build/tools/make_images.py

Για κάθε φωτογραφία assets/<όνομα>.jpg που αναφέρεται σε template ή fragment γράφει docs/assets/<όνομα>-<πλάτος>.webp
σε 240, 400, 640, 800, 1200 και 1600 px. Όσο μεγαλύτερο το πλάτος, τόσο χαμηλότερη η ποιότητα: σε οθόνες υψηλής ανάλυσης
δεν φαίνεται και μειώνει το βάρος. Για την πρώτη εικόνα κάθε σελίδας γράφει και <όνομα>-og.jpg 1200x630 (κοινοποίηση σε
κοινωνικά δίκτυα). Τέλος γράφει το _build/images.json (διαστάσεις και διαθέσιμα πλάτη), από το οποίο το build.py φτιάχνει
srcset, width και height.

Σημείωση: οι εκδόσεις WebP ζουν μόνο στο docs/assets (που είναι στο git). Αν σβηστεί το docs/, ξαναβγαίνουν με αυτό το εργαλείο.
"""
import glob, json, os, re
from PIL import Image, ImageOps

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
ASSETS = os.path.join(ROOT, 'assets')
OUT = os.path.join(ROOT, 'docs', 'assets')
FRAG = os.path.join(ROOT, '_build', 'fragments')

WIDTHS = (240, 400, 640, 800, 1200, 1600)
QUALITY = {240: 80, 400: 80, 640: 80, 800: 78, 1200: 74, 1600: 70}


def used_images():
    """Ονόματα φωτογραφιών που αναφέρονται σε template και fragments, και η πρώτη φωτογραφία κάθε σελίδας (για og:image)."""
    used, first = set(), {}
    files = [os.path.join(ROOT, '_build', 'template.html')] + sorted(glob.glob(os.path.join(FRAG, '*.html')))
    for f in files:
        names = re.findall(r'<img\b[^>]*\bsrc="assets/([A-Za-z0-9_-]+)\.jpg"', open(f, encoding='utf-8').read())
        used.update(names)
        if names and os.path.dirname(f) == FRAG:
            first[os.path.basename(f)] = names[0]
    return used, first


def fit(im, w):
    return im.copy() if im.width <= w else im.resize((w, round(im.height * w / im.width)), Image.LANCZOS)


def main():
    os.makedirs(OUT, exist_ok=True)
    used, first = used_images()
    manifest, total, n = {}, 0, 0
    for name in sorted(used):
        master = os.path.join(ASSETS, name + '.jpg')
        if not os.path.exists(master):
            print('ΠΑΡΑΛΕΙΨΗ (δεν υπάρχει κύρια εικόνα):', name); continue
        im = ImageOps.exif_transpose(Image.open(master)).convert('RGB')
        widths = [w for w in WIDTHS if w <= im.width]
        for w in widths:
            p = os.path.join(OUT, '%s-%d.webp' % (name, w))
            fit(im, w).save(p, 'WEBP', quality=QUALITY[w], method=6)
            total += os.path.getsize(p); n += 1
        manifest[name] = {'w': im.width, 'h': im.height, 'widths': widths}
    for page, name in sorted(first.items()):
        im = ImageOps.fit(ImageOps.exif_transpose(Image.open(os.path.join(ASSETS, name + '.jpg'))).convert('RGB'), (1200, 630), Image.LANCZOS)
        im.save(os.path.join(OUT, '%s-og.jpg' % name), 'JPEG', quality=80, optimize=True, progressive=True)
        manifest[name]['og'] = True
    json.dump(manifest, open(os.path.join(ROOT, '_build', 'images.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1, sort_keys=True)
    print('εικόνες: %d αρχεία webp, %.1f MB, %d φωτογραφίες' % (n, total / 1e6, len(manifest)))


if __name__ == '__main__':
    main()
