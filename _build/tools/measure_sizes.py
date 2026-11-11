#!/usr/bin/env python3
"""Μετρά πόσο πλάτος πιάνει ΠΡΑΓΜΑΤΙΚΑ κάθε εικόνα σε 8 πλάτη οθόνης και γράφει το sizes της στο _build/image-sizes.json.

Έτσι ο browser κατεβάζει την έκδοση που χρειάζεται και όχι μεγαλύτερη. Τρέξε το όταν αλλάξει η διάταξη ή προστεθεί εικόνα:
    python3 _build/build.py && python3 _build/tools/measure_sizes.py && python3 _build/build.py
Χρειάζεται μόνο Google Chrome. Το πλάτος υπολογίζεται με περιθώριο ασφαλείας (ποτέ μικρότερο από το πραγματικό).
"""
import json, os, sys
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cdp

WIDTHS = [360, 390, 430, 768, 1024, 1280, 1440, 1920]
# περιοχές του sizes: (μέγιστο πλάτος οθόνης, δείγματα που ανήκουν εκεί)
# Σε κινητό το hero είναι όρθιο κουτί και η φωτογραφία (cover) θέλει πλάτος πάνω από την οθόνη, έως 240vw.
# Όριο 150vw: σε οθόνη 2x κατεβαίνει η έκδοση 1200 (καθαρή εικόνα) και όχι η 1600 ή 1920 (διπλάσιο βάρος για κομμένα pixels).
CAP = 150
BANDS = [(767, (360, 390, 430)), (1023, (768,)), (1279, (1024,)), (1439, (1280,)), (None, (1440, 1920))]

PROBE = r"""(()=>{const seen={},out=[];
 for(const i of document.images){const m=(i.getAttribute('src')||'').match(/assets\/([A-Za-z0-9_-]+?)-\d+\.webp$/); if(!m) continue;
   const k=seen[m[1]]||0; seen[m[1]]=k+1; const r=i.getBoundingClientRect(), s=getComputedStyle(i);
   const ar=(+i.getAttribute('width')||i.naturalWidth||3)/(+i.getAttribute('height')||i.naturalHeight||2);
   let w=r.width; if(s.objectFit==='cover') w=Math.max(r.width, r.height*ar);      // το cover μπορεί να θέλει πλατύτερη εικόνα από το κουτί
   out.push({key:m[1]+'#'+k, w:(s.display==='none'||r.width<1)?0:Math.ceil(w)})}
 return out})()"""


def sizes_for(samples):
    """samples: {πλάτος οθόνης: πλάτος εικόνας σε CSS px}. Επιστρέφει string για το sizes."""
    parts = []
    for limit, vws in BANDS:
        vals = [(samples[v], v) for v in vws if samples.get(v)]
        if not vals:
            continue
        if limit is None:
            a, b = samples.get(1440, 0), samples.get(1920, 0)
            if a and b and b > a * 1.15:          # μεγαλώνει με την οθόνη: ποσοστό
                entry = '%dvw' % min(CAP, max(-(-w * 100 // v) for w, v in vals))
            else:                                  # σταθερό σε μεγάλες οθόνες: pixels
                entry = '%dpx' % max(w for w, _ in vals)
        else:
            entry = '%dvw' % min(CAP, max(-(-w * 100 // v) for w, v in vals))
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
    return ', '.join(('(max-width: %dpx) %s' % (l, e)) if l else e for l, e in merged)


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
