#!/usr/bin/env python3
"""Μετρά πόσο πλάτος πιάνει ΠΡΑΓΜΑΤΙΚΑ κάθε εικόνα σε 9 πλάτη οθόνης και γράφει το sizes της στο _build/image-sizes.json.

Έτσι ο browser κατεβάζει την έκδοση που χρειάζεται και όχι μεγαλύτερη. Τρέξε το όταν αλλάξει η διάταξη ή προστεθεί εικόνα:
    python3 _build/build.py && python3 _build/tools/measure_sizes.py && python3 _build/build.py
Χρειάζεται μόνο Google Chrome. Το δηλωμένο πλάτος είναι σκόπιμα λίγο μικρότερο από το πραγματικό όταν έτσι πέφτει ακριβώς σε διαθέσιμη
έκδοση (έως 8%, δες SNAP), και στα κινητά πυκνότητας 3 δίνεται η εικόνα ενός κινητού πυκνότητας 2: η διαφορά δεν φαίνεται, το βάρος πέφτει.
"""
import json, os, sys
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cdp

WIDTHS = [360, 390, 430, 700, 768, 1024, 1280, 1440, 1920]
# περιοχές του sizes: (μέγιστο πλάτος οθόνης, δείγματα που ανήκουν εκεί)
# Σε κινητό το hero είναι όρθιο κουτί και η φωτογραφία (cover) θέλει πλάτος πάνω από την οθόνη, έως 240vw.
# Όριο 150vw: σε οθόνη 2x κατεβαίνει η έκδοση 1200 (καθαρή εικόνα) και όχι η 1600 ή 1920 (διπλάσιο βάρος για κομμένα pixels).
CAP = 150
BANDS = [(639, (360, 390, 430)), (767, (700,)), (1023, (768,)), (1279, (1024,)), (1439, (1280,)), (None, (1440, 1920))]

PROBE = r"""(()=>{const seen={},out=[];
 for(const i of document.images){const m=(i.getAttribute('src')||'').match(/assets\/([A-Za-z0-9_-]+?)-\d+\.webp$/); if(!m) continue;
   const k=seen[m[1]]||0; seen[m[1]]=k+1; const s=getComputedStyle(i);
   // offsetWidth/Height: το μέγεθος στη διάταξη, χωρίς τις προσωρινές μεγεθύνσεις των εφέ (transform)
   const bw=i.offsetWidth, bh=i.offsetHeight, ar=(+i.getAttribute('width')||i.naturalWidth||3)/(+i.getAttribute('height')||i.naturalHeight||2);
   let w=bw; if(s.objectFit==='cover') w=Math.max(bw, bh*ar);            // το cover μπορεί να θέλει πλατύτερη εικόνα από το κουτί
   out.push({key:m[1]+'#'+k, w:(s.display==='none'||bw<1)?0:Math.round(w)})}
 return out})()"""


TOL = 0.985          # ανοχή 1,5%: μια εικόνα 1,5% μικρότερη δεν φαίνεται, ενώ η στρογγύλευση προς τα πάνω ανέβαζε ολόκληρο σκαλί


STEPS = (240, 400, 640, 800, 1200, 1600)   # τα πλάτη που βγάζει το make_images.py
SNAP = 1.08          # αν σε πυκνότητα 1, 2 ή 3 η εικόνα ξεπερνά μια έκδοση έως 8%, δηλώνεται όσο η έκδοση: η διαφορά δεν φαίνεται,
                     # ενώ αλλιώς ο browser κατεβάζει ολόκληρο σκαλί πάνω (π.χ. 136px x 3 = 408 θα έφερνε την 640 αντί της 400)


def vw(w, v):
    return max(1, int(w * 100 * TOL / v + 0.5))


def snap_px(px):
    for dpr in (3, 2, 1):
        for st in STEPS:
            if st < px * dpr <= st * SNAP:
                px = st // dpr
    return px


def snap_vw(n):
    return 100 if 100 < n <= 100 * SNAP else n


def sizes_for(samples):
    """samples: {πλάτος οθόνης: πλάτος εικόνας σε CSS px}. Επιστρέφει string για το sizes."""
    parts = []
    for limit, vws in BANDS:
        vals = [(samples[v], v) for v in vws if samples.get(v)]
        if not vals:
            continue
        ws = [w for w, _ in vals]
        if max(ws) - min(ws) <= 2 and (len(ws) > 1 or limit is None):       # ίδιο πλάτος σε όλα τα δείγματα: σταθερά pixels
            entry = '%dpx' % snap_px(int(max(ws) * TOL + 0.5))
        elif limit is None and not (samples.get(1920, 0) > samples.get(1440, 0) * 1.15):
            entry = '%dpx' % snap_px(int(max(ws) * TOL + 0.5))               # δεν μεγαλώνει με την οθόνη
        else:
            entry = '%dvw' % snap_vw(min(CAP, max(vw(w, v) for w, v in vals)))
        parts.append((limit, entry))
    if not parts:
        return None
    merged = []
    for limit, entry in parts:                     # ίδιες διαδοχικές τιμές γίνονται μία
        if merged and merged[-1][1] == entry:
            merged[-1] = (limit, entry)
        else:
            merged.append((limit, entry))
    if merged[-1][0] is not None:                  # δεν φαίνεται σε μεγάλες οθόνες: η τελευταία τιμή ισχύει για όλες
        merged[-1] = (None, merged[-1][1])
    out = [('(max-width: %dpx) %s' % (l, e)) if l else e for l, e in merged]
    # Κινητά με πυκνότητα 3: αρκεί η εικόνα που θα έπαιρνε ένα κινητό πυκνότητας 2 (η διαφορά δεν φαίνεται, το βάρος πέφτει έως 40%).
    # Browser που δεν καταλαβαίνει το min-resolution μέσα στο sizes απλώς αγνοεί τη γραμμή και κρατά τη συνηθισμένη συμπεριφορά.
    limit, entry = merged[0]
    if samples.get(390):                           # η πρώτη τιμή καλύπτει τα κινητά, όποιο κι αν είναι το όριό της (767, 1023 ή κανένα)
        n = int(entry[:-2])
        capped = ('%dvw' % max(1, int(n * 2 / 3 + 0.5))) if entry.endswith('vw') else ('%dpx' % max(1, int(n * 2 / 3 + 0.5)))
        out.insert(0, '(min-resolution: 2.5dppx) and (max-width: %dpx) ' % (639 if limit == 639 else 767) + capped)
    return ', '.join(out)


def main():
    result = {}
    with cdp.session() as (ws, base):
        data = {}
        for w in WIDTHS:
            ws.viewport(w)
            for p in cdp.PAGES:
                ws.open(base + p + '.html', settle=0.6)
                for it in ws.js(PROBE):
                    data.setdefault(p + '.html', {}).setdefault(it['key'], {})[w] = it['w']
            print('μέτρηση', w, 'px', flush=True)
    for page, imgs in sorted(data.items()):
        for key, samples in sorted(imgs.items()):
            s = sizes_for(samples)
            if s:
                result.setdefault(page, {})[key] = s
    out = os.path.join(cdp.ROOT, '_build', 'image-sizes.json')
    json.dump(result, open(out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1, sort_keys=True)
    print('γράφτηκε', os.path.relpath(out, cdp.ROOT), '·', sum(len(v) for v in result.values()), 'εικόνες σε', len(result), 'σελίδες')


if __name__ == '__main__':
    main()
