#!/usr/bin/env python3
"""Ελαφριές γραμματοσειρές για το site, από τα αρχικά αρχεία Google Fonts (Inter, Comfortaa, μεταβλητές).

Χρειάζεται fonttools και brotli (το build.py ΔΕΝ τα χρειάζεται). Τρέξε το μόνο αν αλλάξουν οι γραμματοσειρές:
    .venv/bin/pip install fonttools brotli && .venv/bin/python _build/tools/make_fonts.py

Τι κάνει:
- Δεν αλλάζει τα περιγράμματα ή τα πλάτη των γραμμάτων: το κείμενο στοιχίζεται ακριβώς όπως με τα αρχικά αρχεία.
  (Ο περιορισμός των βαρών του Inter σε 400-700 δοκιμάστηκε: κερδίζει 14 KB αλλά μετακινεί πλάτη κατά 1 μονάδα, γι' αυτό δεν γίνεται.)
- Λατινικά: κρατά βασικά λατινικά, ψηφία και σημεία στίξης. Τα υπόλοιπα (τονισμένα λατινικά κ.λπ.) μένουν στο
  πλήρες αρχείο *-full.woff2, που ο browser κατεβάζει μόνο αν εμφανιστεί τέτοιος χαρακτήρας.
- Γράφει το _build/css/10-fonts.css. Κάθε βάρος (400, 500, 600, 700) δείχνει στο ΙΔΙΟ αρχείο, άρα ο browser το κατεβάζει μία φορά.
  Τα βάρη δηλώνονται ένα ένα και όχι ως εύρος, ώστε τα ενδιάμεσα (550, 650) να αποδίδονται όπως στην εγκεκριμένη εμφάνιση.
"""
import io, os
from fontTools.ttLib import TTFont
from fontTools.subset import Subsetter, Options
from fontTools.varLib import instancer

HERE = os.path.dirname(os.path.abspath(__file__))
FONTS = os.path.join(os.path.dirname(os.path.dirname(HERE)), 'assets', 'fonts')
SRC = os.path.join(FONTS, 'src')          # τα αρχικά αρχεία, όπως ήρθαν από Google Fonts

GREEK = 'U+0370-0377, U+037A-037F, U+0384-038A, U+038C, U+038E-03A1, U+03A3-03FF'
GREEK_EXT = 'U+1F00-1FFF'
LATIN_FULL = 'U+0000-00FF, U+0131, U+0152-0153, U+02BB-02BC, U+02C6, U+02DA, U+02DC, U+0304, U+0308, U+0329, U+2000-206F, U+20AC, U+2122, U+2191, U+2193, U+2212, U+2215, U+FEFF, U+FFFD'
LATIN_EXT = 'U+0100-02BA, U+02BD-02C5, U+02C7-02CC, U+02CE-02D7, U+02DD-02FF, U+0304, U+0308, U+0329, U+1D00-1DBF, U+1E00-1E9F, U+1EF2-1EFF, U+2020, U+20A0-20AB, U+20AD-20C0, U+2113, U+2C60-2C7F, U+A720-A7FF'
# βασικά λατινικά + στίξη που χρησιμοποιεί ελληνικό κείμενο
CORE = list(range(0x20, 0x7F)) + [0xA0, 0xAB, 0xBB, 0xB7, 0xB0, 0xA9, 0xAE, 0xB4, 0x2013, 0x2014, 0x2018, 0x2019, 0x201C, 0x201D, 0x2022, 0x2026, 0x2032, 0x2033, 0x20AC, 0x2122, 0x2212]


def ranges(cps):
    cps = sorted(cps); out = []; a = b = cps[0]
    for c in cps[1:]:
        if c == b + 1: b = c
        else: out.append((a, b)); a = b = c
    out.append((a, b))
    return ', '.join('U+%04X' % x if x == y else 'U+%04X-%04X' % (x, y) for x, y in out)


def process(src, dst, wght=None, keep=None):
    f = TTFont(os.path.join(SRC, src))
    if wght:
        f = instancer.instantiateVariableFont(f, {'wght': wght})
        buf = io.BytesIO(); f.flavor = None; f.save(buf); buf.seek(0); f = TTFont(buf)   # καθαρό ξαναδιάβασμα πριν το υποσύνολο
    covered = None
    if keep:
        o = Options(); o.layout_features = ['*']; o.notdef_outline = True; o.name_IDs = ['*']; o.hinting = False
        s = Subsetter(o); s.populate(unicodes=keep); s.subset(f)
        covered = sorted(set(f.getBestCmap()) & set(keep))
    f.flavor = 'woff2'; f.save(os.path.join(FONTS, dst))
    return os.path.getsize(os.path.join(FONTS, dst)), covered


def main():
    css = ['/* Τοπικές γραμματοσειρές Inter και Comfortaa (μεταβλητές, ένα αρχείο ανά αλφάβητο για όλα τα βάρη). Καμία σύνδεση με Google.',
           '   Παράγεται από _build/tools/make_fonts.py: μην το επεξεργάζεσαι με το χέρι. */']
    total = 0
    for fam, low, wght, weights in (('Inter', 'inter', None, (400, 500, 600, 700)), ('Comfortaa', 'comfortaa', None, (500, 600, 700))):
        first = '400' if fam == 'Inter' else '500'
        plan = [  # (πηγή, αρχείο, unicode-range, υποσύνολο)  — η σειρά μετρά: το τελευταίο που καλύπτει έναν χαρακτήρα κερδίζει
            ('%s-%s-latin-ext.woff2' % (low, first), '%s-latin-ext.woff2' % low, LATIN_EXT, None),
            ('%s-%s-latin.woff2' % (low, first), '%s-latin-full.woff2' % low, LATIN_FULL, None),
            ('%s-%s-latin.woff2' % (low, first), '%s-latin.woff2' % low, None, CORE),
            ('%s-%s-greek.woff2' % (low, first), '%s-greek.woff2' % low, GREEK, None)]
        if fam == 'Inter':
            plan.insert(0, ('inter-400-greek-ext.woff2', 'inter-greek-ext.woff2', GREEK_EXT, None))
        for src, dst, ur, keep in plan:
            size, covered = process(src, dst, wght, keep)
            total += size
            ur = ur or ranges(covered)
            for wt in weights:
                css.append("@font-face{font-family:'%s';font-style:normal;font-weight:%d;font-display:swap;src:url(fonts/%s) format('woff2');unicode-range:%s}" % (fam, wt, dst, ur))
            print('%-28s %6d bytes' % (dst, size))
    open(os.path.join(os.path.dirname(os.path.dirname(HERE)), '_build', 'css', '10-fonts.css'), 'w', encoding='utf-8').write('\n'.join(css) + '\n')
    print('σύνολο', total, 'bytes · οι 4 που φορτώνουν σε κάθε σελίδα:', sum(os.path.getsize(os.path.join(FONTS, x)) for x in ('inter-greek.woff2', 'inter-latin.woff2', 'comfortaa-greek.woff2', 'comfortaa-latin.woff2')))


if __name__ == '__main__':
    main()
