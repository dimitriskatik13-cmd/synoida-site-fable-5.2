#!/usr/bin/env python3
"""Έλεγχος του χτισμένου site (docs/) σε πραγματικό Chrome, σε κινητό και υπολογιστή.

    python3 _build/tools/check_browser.py            όλες οι σελίδες, κινητό 390 και υπολογιστής 1440
    python3 _build/tools/check_browser.py index      μόνο μία σελίδα
    python3 _build/tools/check_browser.py --json out.json

Τι ελέγχει σε κάθε σελίδα και στα δύο πλάτη:
  σφάλματα     κανένα σφάλμα κονσόλας, καμία αποτυχία αιτήματος, καμία παραβίαση της πολιτικής ασφαλείας
  διάταξη      καμία οριζόντια κύλιση (και στα 360, 768, 1024, 1920), μετατόπιση διάταξης CLS <= 0.05
  ανάγνωση     αντίθεση κειμένου WCAG AA σε ΚΑΘΕ στάση της κύλισης (πιάνει και κείμενο που «περιμένει να ανάψει»),
               κανένα κείμενο κάτω από 12px. Δεν κρίνει κείμενο πάνω σε φωτογραφία (θέλει μάτι) ούτε διακοσμητική αρίθμηση.
               Οι λέξεις έμφασης των τίτλων στο πράσινο/μπλε/πορτοκαλί του λογοτύπου αναφέρονται χωριστά ως εξαίρεση brand.
  άγγιγμα      στο κινητό, κουμπιά και σύνδεσμοι τουλάχιστον 44x44 (όριο προτύπου 24x24)
  βάρος        όρια μεγέθους πρώτης οθόνης και ολόκληρης σελίδας, καμία εικόνα πολύ μεγαλύτερη από όσο φαίνεται
Το βάρος μετριέται όπως θα το σερβίρει ο server (κείμενο συμπιεσμένο gzip).
Έξοδος: γραμμή ανά εύρημα και τελικό ΟΚ ή ΑΠΟΤΥΧΙΑ (κωδικός εξόδου 1).
"""
import gzip, json, os, sys, time, urllib.parse
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cdp

BUDGET = {  # KB, όπως φτάνουν στον επισκέπτη
    'mobile': {'first': 400, 'full': 800, 'requests': 18},
    'desktop': {'first': 650, 'full': 1300, 'requests': 18},
}
MODES = {'mobile': (390, 844, 2), 'desktop': (1440, 900, 1)}
OVERFLOW_WIDTHS = (360, 768, 1024, 1920)

INIT = r"""window.__cls=0;window.__lcp=null;window.__seen=new Map();
try{new PerformanceObserver(l=>{for(const e of l.getEntries()) if(!e.hadRecentInput) window.__cls+=e.value}).observe({type:'layout-shift',buffered:true})}catch(e){}
try{new PerformanceObserver(l=>{for(const e of l.getEntries()) window.__lcp=(e.url||'').split('/').pop()||e.element&&e.element.tagName}).observe({type:'largest-contentful-paint',buffered:true})}catch(e){}"""

# Τρέχει σε κάθε στάση της κύλισης: αντίθεση για ό,τι κείμενο φαίνεται ΤΩΡΑ στην οθόνη.
STOP = r"""(()=>{
 const parse=c=>{const m=c&&c.match(/rgba?\(([^)]+)\)/); if(!m) return null; const p=m[1].split(/[,\s\/]+/).filter(Boolean).map(Number); return {r:p[0],g:p[1],b:p[2],a:p.length>3?p[3]:1}};
 const lum=c=>{const f=v=>{v/=255; return v<=0.03928?v/12.92:Math.pow((v+0.055)/1.055,2.4)}; return 0.2126*f(c.r)+0.7152*f(c.g)+0.0722*f(c.b)};
 const over=(t,b)=>({r:t.r*t.a+b.r*(1-t.a),g:t.g*t.a+b.g*(1-t.a),b:t.b*t.a+b.b*(1-t.a),a:1});
 const BRAND=['rgb(141,198,63)','rgb(0,174,239)','rgb(247,148,29)','rgb(237,28,36)'];
 const w=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT); const done=new Set();
 while(w.nextNode()){ const el=w.currentNode.parentElement; const txt=w.currentNode.nodeValue.replace(/\s+/g,' ').trim();
   if(txt.length<2||!el||done.has(el)||el.closest('script,style,noscript,[data-preview-only],[aria-hidden="true"]')) continue; done.add(el);   // aria-hidden: διακοσμητική αρίθμηση
   const r=el.getBoundingClientRect(); if(r.width<2||r.height<2||r.bottom<0||r.top>innerHeight) continue;
   const s=getComputedStyle(el); if(s.visibility==='hidden'||s.display==='none') continue;
   let op=1,e=el,layers=[],photo=false,solid=false;
   while(e&&e.nodeType===1){ const cs=getComputedStyle(e); op*=parseFloat(cs.opacity);
     if(!solid){ if(/url\(/.test(cs.backgroundImage)) photo=true; const c=parse(cs.backgroundColor); if(c&&c.a>0){layers.push(c); if(c.a>=1) solid=true} }
     e=e.parentElement }
   if(op<0.05) continue;                                   // δεν έχει εμφανιστεί ακόμη
   // κείμενο πάνω σε φωτογραφία (hero): το κέντρο του πέφτει μέσα σε εικόνα της ίδιας ενότητας που δεν είναι πρόγονός του
   const sec=el.closest('section,header,footer')||document.body, cx=r.left+r.width/2, cy=r.top+r.height/2;
   for(const im of sec.querySelectorAll('img,canvas,.tile')){ const q=im.getBoundingClientRect(); if(q.width>60&&cx>=q.left&&cx<=q.right&&cy>=q.top&&cy<=q.bottom&&!im.contains(el)){photo=true;break} }
   let bg={r:255,g:255,b:255,a:1}; for(let i=layers.length-1;i>=0;i--) bg=over(layers[i],bg);
   const col=parse(s.color); if(!col) continue; const fs=parseFloat(s.fontSize), bold=parseInt(s.fontWeight)>=700;
   const fg=over({r:col.r,g:col.g,b:col.b,a:Math.min(1,op*col.a)},bg); const L1=lum(fg),L2=lum(bg); const ratio=(Math.max(L1,L2)+.05)/(Math.min(L1,L2)+.05);
   const need=(fs>=24||(fs>=18.66&&bold))?3:4.5; const prev=window.__seen.get(el);
   if(!prev||ratio<prev.ratio) window.__seen.set(el,{txt:txt.slice(0,48),ratio:+ratio.toFixed(2),need,fs:+fs.toFixed(1),photo,dim:op<0.99,
     accent:need===3&&fs>=24&&BRAND.includes(s.color.replace(/\s/g,'')),   // λέξη έμφασης ή μεγάλος αριθμός στο χρώμα του λογοτύπου
     where:(el.closest('section,header,footer,nav')||{}).className?String(el.closest('section,header,footer,nav').className).split(' ').slice(0,2).join('.'):el.tagName}); }
 return 1})()"""

FINAL = r"""(()=>{
 const dpr=devicePixelRatio, vis=el=>{const r=el.getBoundingClientRect(),s=getComputedStyle(el); return r.width>1&&r.height>1&&s.visibility!=='hidden'&&s.display!=='none'};
 const all=[...window.__seen.values()];
 const contrast=all.filter(x=>!x.photo&&x.ratio<x.need&&!x.accent), brand=all.filter(x=>!x.photo&&x.ratio<x.need&&x.accent), small=all.filter(x=>x.fs<12);
 const taps=[...document.querySelectorAll('a[href],button,summary,[role=button]')].filter(vis).filter(e=>!e.closest('[data-preview-only]')).map(e=>{const r=e.getBoundingClientRect(),s=getComputedStyle(e);
   return {t:(e.textContent||e.getAttribute('aria-label')||'').replace(/\s+/g,' ').trim().slice(0,32), w:Math.round(r.width), h:Math.round(r.height), inline:s.display==='inline'&&!!e.closest('p,li,dd,blockquote'),
     named:!!((e.textContent||'').trim()||e.getAttribute('aria-label')||e.querySelector('img[alt]:not([alt=""])'))}}).filter(t=>!t.inline);
 const imgs=[...document.images].filter(i=>i.currentSrc&&i.naturalWidth&&vis(i)).map(i=>{const r=i.getBoundingClientRect(),s=getComputedStyle(i);
   const need=(s.objectFit==='cover'?Math.max(r.width,r.height*i.naturalWidth/i.naturalHeight):r.width)*dpr; const m=i.currentSrc.match(/-(\d+)\.webp$/), nat=m?+m[1]:i.naturalWidth;   // με srcset το naturalWidth είναι διορθωμένο για την πυκνότητα: το πραγματικό πλάτος είναι στο όνομα
   return {src:i.currentSrc.split('/').pop(), nat, need:Math.round(need), ratio:+(nat/need).toFixed(2)}});
 return {contrast, brand, small, onPhoto:all.filter(x=>x.photo).length, texts:all.length, dimmed:all.filter(x=>x.dim&&!x.photo&&x.ratio<x.need).length,
   taps:taps.length, tapsSmall:taps.filter(t=>t.w<44||t.h<44), tapsTiny:taps.filter(t=>t.w<24||t.h<24), unnamed:taps.filter(t=>!t.named),
   oversize:imgs.filter(i=>i.ratio>2.05), undersize:imgs.filter(i=>i.ratio<0.8&&i.nat<1200), images:imgs.length,
   overflow:document.documentElement.scrollWidth>innerWidth+1, cls:+window.__cls.toFixed(4), lcp:window.__lcp,
   urls:[location.href].concat(performance.getEntriesByType('resource').map(r=>r.name))}})()"""


def weigh(urls, base, cache={}):
    """KB όπως θα έφταναν από τον server: κείμενο με gzip, εικόνες και γραμματοσειρές ως έχουν."""
    total = 0
    for u in set(urls):
        if not u.startswith(base):
            continue
        rel = urllib.parse.unquote(u[len(base):].split('?')[0].split('#')[0]) or 'index.html'
        p = os.path.join(cdp.DOCS, rel)
        if rel not in cache and os.path.isfile(p):
            data = open(p, 'rb').read()
            cache[rel] = len(gzip.compress(data, 6)) if rel.endswith(('.html', '.css', '.js', '.xml', '.svg', '.json')) else len(data)
        total += cache.get(rel, 0)
    return total / 1024


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    out_json = sys.argv[sys.argv.index('--json') + 1] if '--json' in sys.argv else None
    if out_json:
        args = [a for a in args if a != out_json]
    # το 404 σερβίρεται από τον server σε άγνωστη διεύθυνση και έχει <base>: τοπικά δεν φορτώνει στυλ, ελέγχεται μετά τη δημοσίευση
    pages = args or [p for p in cdp.PAGES if p != '404']
    problems, warnings, report, brand = [], [], {}, set()
    with cdp.session() as (ws, base):
        ws.send('Page.addScriptToEvaluateOnNewDocument', {'source': INIT})
        for mode, (w, h, dpr) in MODES.items():
            ws.viewport(w, h, dpr)
            for p in pages:
                ws.open(base + p + '.html', settle=2.0)
                first = ws.js('[location.href].concat(performance.getEntriesByType("resource").map(r=>r.name))')
                total = ws.js('document.documentElement.scrollHeight'); y = 0
                while True:                                    # στάσεις ανάγνωσης: μισή οθόνη κάθε φορά
                    ws.js('window.scrollTo({top:%d,behavior:"instant"});1' % y); time.sleep(0.9); ws.js(STOP)
                    if y + h >= total:
                        break
                    y = min(y + h // 2, total - h)
                r = ws.js(FINAL)
                errs = []
                for e in ws.events:
                    if e['method'] == 'Runtime.exceptionThrown':
                        errs.append('σφάλμα JS: ' + str(e['params'].get('exceptionDetails', {}).get('exception', {}).get('description', ''))[:140])
                    elif e['method'] == 'Log.entryAdded' and e['params']['entry']['level'] == 'error':
                        errs.append('κονσόλα: ' + e['params']['entry'].get('text', '')[:140])
                    elif e['method'] == 'Network.loadingFailed' and not e['params'].get('canceled'):
                        errs.append('αίτημα απέτυχε: ' + e['params'].get('errorText', ''))
                    elif e['method'] == 'Network.responseReceived' and e['params']['response']['status'] >= 400:
                        errs.append('HTTP %d: %s' % (e['params']['response']['status'], e['params']['response']['url'].split('/')[-1]))
                kb_first, kb_full, nreq = weigh(first, base), weigh(r['urls'], base), len(set(first))
                tag = '%-8s %-24s' % (mode, p)
                b = BUDGET[mode]
                for e in sorted(set(errs)):
                    problems.append('%s %s' % (tag, e))
                if r['overflow']:
                    problems.append('%s οριζόντια κύλιση' % tag)
                if r['cls'] > 0.05:
                    problems.append('%s μετατόπιση διάταξης CLS %.3f' % (tag, r['cls']))
                for c in r['contrast']:
                    problems.append('%s αντίθεση %.2f (θέλει %.1f) %spx%s «%s» [%s]' % (tag, c['ratio'], c['need'], c['fs'], ' αχνό' if c['dim'] else '', c['txt'], c['where']))
                for c in r['brand']:
                    brand.add('%.2f:1 «%s»' % (c['ratio'], c['txt']))
                for c in r['small']:
                    problems.append('%s κείμενο %spx «%s» [%s]' % (tag, c['fs'], c['txt'], c['where']))
                for i in r['oversize']:
                    problems.append('%s εικόνα %s: %dpx ενώ χρειάζεται %d' % (tag, i['src'], i['nat'], i['need']))
                for i in r['undersize']:
                    warnings.append('%s εικόνα %s μικρότερη από όσο φαίνεται: %dpx για %d' % (tag, i['src'], i['nat'], i['need']))
                for t in r['unnamed']:
                    problems.append('%s στοιχείο χωρίς όνομα για αναγνώστη οθόνης (%dx%d)' % (tag, t['w'], t['h']))
                if mode == 'mobile':
                    for t in r['tapsTiny']:
                        problems.append('%s στόχος αγγίγματος %dx%d «%s»' % (tag, t['w'], t['h'], t['t']))
                    for t in r['tapsSmall']:
                        if t not in r['tapsTiny']:
                            warnings.append('%s στόχος αγγίγματος %dx%d «%s» (κάτω από 44)' % (tag, t['w'], t['h'], t['t']))
                if p != '404':
                    if kb_first > b['first']:
                        problems.append('%s πρώτη οθόνη %.0f KB (όριο %d)' % (tag, kb_first, b['first']))
                    if kb_full > b['full']:
                        problems.append('%s ολόκληρη σελίδα %.0f KB (όριο %d)' % (tag, kb_full, b['full']))
                    if nreq > b['requests']:
                        problems.append('%s %d αιτήματα στην πρώτη οθόνη (όριο %d)' % (tag, nreq, b['requests']))
                report['%s/%s' % (mode, p)] = {'first_kb': round(kb_first), 'full_kb': round(kb_full), 'requests': nreq, 'cls': r['cls'], 'lcp': r['lcp'],
                                               'texts': r['texts'], 'on_photo': r['onPhoto'], 'taps': r['taps'], 'taps_lt44': len(r['tapsSmall']), 'images': r['images']}
                print('%s πρώτη %4.0f KB · όλη %4.0f KB · %2d αιτήματα · CLS %.3f · κείμενα %3d · LCP %s' % (tag, kb_first, kb_full, nreq, r['cls'], r['texts'], r['lcp']), flush=True)
        for w in OVERFLOW_WIDTHS:                               # οριζόντια κύλιση στα ενδιάμεσα πλάτη
            ws.viewport(w)
            for p in pages:
                ws.open(base + p + '.html', settle=0.5)
                if ws.js('document.documentElement.scrollWidth>innerWidth+1'):
                    problems.append('%-8s %-24s οριζόντια κύλιση' % (str(w) + 'px', p))
    if out_json:
        json.dump({'pages': report, 'problems': problems, 'warnings': warnings}, open(out_json, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print()
    for x in warnings:
        print('ΠΡΟΣΟΧΗ ', x)
    for x in problems:
        print('ΠΡΟΒΛΗΜΑ', x)
    m = [v for k, v in report.items() if k.startswith('mobile/') and not k.endswith('/404')]
    d = [v for k, v in report.items() if k.startswith('desktop/') and not k.endswith('/404')]
    med = lambda xs: sorted(xs)[len(xs) // 2] if xs else 0
    print('\nΚινητό: πρώτη οθόνη διάμεσος %d KB, μέγιστο %d · όλη η σελίδα διάμεσος %d, μέγιστο %d' % (med([x['first_kb'] for x in m]), max([x['first_kb'] for x in m] or [0]), med([x['full_kb'] for x in m]), max([x['full_kb'] for x in m] or [0])))
    print('Υπολογιστής: πρώτη οθόνη διάμεσος %d KB, μέγιστο %d · όλη η σελίδα διάμεσος %d, μέγιστο %d' % (med([x['first_kb'] for x in d]), max([x['first_kb'] for x in d] or [0]), med([x['full_kb'] for x in d]), max([x['full_kb'] for x in d] or [0])))
    if brand:
        print('Εξαίρεση brand (απόφαση ιδιοκτήτη): %d λέξεις έμφασης σε τίτλους στο χρώμα του λογοτύπου, κάτω από 3:1. Π.χ. %s' % (len(brand), ' · '.join(sorted(brand)[:3])))
    print('%s: %d προβλήματα, %d σημειώσεις προσοχής' % ('ΑΠΟΤΥΧΙΑ' if problems else 'ΟΚ', len(problems), len(warnings)))
    sys.exit(1 if problems else 0)


if __name__ == '__main__':
    main()
