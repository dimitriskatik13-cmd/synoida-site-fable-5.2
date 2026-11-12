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
Και, όταν τρέχει για όλες τις σελίδες, τα σενάρια που δεν φαίνονται σε απλή φόρτωση:
  μενού κινητού με ανοιχτές τις «Θεραπείες» σε οθόνη 390x664 και 360x640 (φτάνεις σε κάθε σύνδεσμο;) · χωρίς JavaScript ·
  με «μείωση κίνησης» · εστίαση πληκτρολογίου πίσω από κεφαλίδα/κάτω μπάρα · σελίδα 404 κάτω από το πρόθεμα του site ·
  βάρος πρώτης οθόνης σε κινητό πυκνότητας 3
Το βάρος μετριέται όπως θα το σερβίρει ο server (κείμενο συμπιεσμένο gzip).
Έξοδος: γραμμή ανά εύρημα και τελικό ΟΚ ή ΑΠΟΤΥΧΙΑ (κωδικός εξόδου 1).
"""
import gzip, json, os, sys, time, urllib.parse
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cdp

BUDGET = {  # KB, όπως φτάνουν στον επισκέπτη. Όρια κοντά στο σημερινό μέγιστο (+15% περίπου), ώστε μια αύξηση να φαίνεται αμέσως.
    'mobile': {'first': 250, 'full': 520, 'requests': 16},
    'desktop': {'first': 300, 'full': 430, 'requests': 16},
    'mobile3x': {'first': 245, 'full': 500},
}
MODES = {'mobile': (390, 844, 2), 'desktop': (1440, 900, 1)}
OVERFLOW_WIDTHS = (360, 768, 1024, 1920)

INIT = r"""window.__cls=0;window.__lcp=null;window.__lcpt=0;window.__seen=new Map();
try{new PerformanceObserver(l=>{for(const e of l.getEntries()) if(!e.hadRecentInput) window.__cls+=e.value}).observe({type:'layout-shift',buffered:true})}catch(e){}
try{new PerformanceObserver(l=>{for(const e of l.getEntries()) {window.__lcp=(e.url||'').split('/').pop()||e.element&&e.element.tagName;window.__lcpt=e.startTime}}).observe({type:'largest-contentful-paint',buffered:true})}catch(e){}"""

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
 const imgs=[...document.images].filter(i=>i.currentSrc&&i.naturalWidth&&vis(i)&&!/\.svg$/.test(i.currentSrc)).map(i=>{const r=i.getBoundingClientRect(),s=getComputedStyle(i);
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


MENU = r"""(async()=>{const m=document.getElementById('mobileMenu'),bar=document.querySelector('.callbar'),hdr=document.querySelector('.site-header').getBoundingClientRect().bottom;
 document.getElementById('navToggle').click(); document.getElementById('mTherapiesBtn').click(); await new Promise(r=>setTimeout(r,250));
 const cb=bar&&getComputedStyle(bar).display!=='none'&&bar.getBoundingClientRect().top<innerHeight?bar.getBoundingClientRect().top:innerHeight, bad=[];
 for(const a of m.querySelectorAll('a,button')){ a.focus(); /* όπως το Tab: ο browser φέρνει το στοιχείο στην οθόνη */ const r=a.getBoundingClientRect(); if(r.height<1) continue;
   if(r.bottom>cb+1||r.top<hdr-1) bad.push((a.textContent||'').trim().slice(0,24)) }
 return bad})()"""
FOCUS = r"""(()=>{const bar=document.querySelector('.callbar'),hb=document.querySelector('.site-header').getBoundingClientRect().bottom, bad=[];
 const els=[...document.querySelectorAll('main a[href],main button,main summary,footer a[href]')].filter(e=>e.offsetWidth>0&&!e.closest('[inert]'));
 for(const e of els){ e.focus({preventScroll:true}); e.scrollIntoView({block:'nearest',behavior:'instant'});   // όπως κυλά ο browser στο Tab, χωρίς την ομαλή κίνηση
   const r=e.getBoundingClientRect(); const cb=bar&&getComputedStyle(bar).transform==='none'&&bar.offsetHeight?bar.getBoundingClientRect().top:innerHeight;
   if(document.activeElement===e&&(r.bottom>cb+1||r.top<hb-1)) bad.push((e.textContent||'').trim().slice(0,24)) }
 return {n:els.length,bad}})()"""
HIDDEN_TEXT = r"""(()=>{const bad=[];const w=document.createTreeWalker(document.querySelector('main'),NodeFilter.SHOW_TEXT);
 while(w.nextNode()){const el=w.currentNode.parentElement; if(w.currentNode.nodeValue.trim().length<3||el.closest('[aria-hidden="true"],details:not([open]),.sr-only')) continue;
   let op=1,e=el; while(e&&e.nodeType===1){op*=parseFloat(getComputedStyle(e).opacity); e=e.parentElement} if(op<0.95) bad.push(w.currentNode.nodeValue.trim().slice(0,28)) }
 return {bad:[...new Set(bad)].slice(0,5),pinned:document.documentElement.classList.contains('stars-on'),running:document.getAnimations().filter(a=>a.playState==='running').length}})()"""


def scenarios(ws, base, problems, report):
    """Όσα δεν φαίνονται σε μια απλή φόρτωση: ανοιχτό μενού σε μικρή οθόνη, χωρίς JavaScript, μειωμένη κίνηση, πληκτρολόγιο, 404, πυκνότητα 3."""
    # 1. μενού κινητού με ανοιχτές τις «Θεραπείες», σε μικρό ορατό ύψος (iPhone με τις μπάρες του Safari, μικρό Android)
    for w, h in ((390, 664), (360, 640)):
        ws.viewport(w, h, 2)
        for p in ('index', 'treatment-speech'):
            ws.open(base + p + '.html', settle=0.8)
            if p == 'treatment-speech':
                ws.js('window.scrollTo(0,400);1'); time.sleep(0.3)
            bad = ws.js(MENU)
            if bad:
                problems.append('μενού %dx%d %-18s δεν φτάνεις με κύλιση σε: %s' % (w, h, p, ', '.join(bad[:4])))
    # 2. χωρίς JavaScript: η πλοήγηση και όλο το κείμενο πρέπει να είναι διαθέσιμα
    ws.viewport(390, 844, 2)
    for p in ('index', 'treatment-speech', 'contact-us'):
        ws.send('Emulation.setScriptExecutionDisabled', {'value': True})
        ws.send('Page.navigate', {'url': base + p + '.html'}); time.sleep(1.5)
        ws.send('Emulation.setScriptExecutionDisabled', {'value': False})
        r = ws.js("""({menu:document.getElementById('mobileMenu').offsetHeight,links:[...document.querySelectorAll('#mobileMenu a[href$=".html"]')].filter(a=>a.offsetHeight>0).length,
                      hidden:[...document.querySelectorAll('main .reveal')].filter(e=>getComputedStyle(e).opacity<0.99).length,pinned:document.documentElement.classList.contains('stars-on')})""")
        if r['menu'] < 50 or r['links'] < 10:
            problems.append('χωρίς JS  %-18s το μενού κινητού δεν είναι διαθέσιμο (%d σύνδεσμοι)' % (p, r['links']))
        if r['hidden'] or r['pinned']:
            problems.append('χωρίς JS  %-18s %d ενότητες μένουν κρυμμένες' % (p, r['hidden']))
        free = ws.js('(()=>{window.scrollTo({top:2000,behavior:"instant"});const hb=document.querySelector(".site-header").getBoundingClientRect().bottom;return Math.round(innerHeight-Math.max(0,hb))})()')
        if free < 300:
            problems.append('χωρίς JS  %-18s μετά από κύλιση φαίνονται μόνο %d px περιεχομένου (η κεφαλίδα με το ανοιχτό μενού μένει κολλημένη)' % (p, free))
    # 2β. το site.js δεν φόρτωσε (ασταθές δίκτυο): η σελίδα πρέπει να φαίνεται ολόκληρη, όπως χωρίς JavaScript
    ws.send('Network.setBlockedURLs', {'urls': ['*assets/site.*.js']})      # μόνο το script, όχι το site.<hash>.css
    for p in ('index', 'treatment-speech'):
        ws.open(base + p + '.html', settle=1.0)
        r = ws.js("""({js:document.documentElement.classList.contains('js'),css:getComputedStyle(document.querySelector('.sr-only')).position==='absolute',hidden:[...document.querySelectorAll('main .reveal')].filter(e=>getComputedStyle(e).opacity<0.99).length,
                      links:[...document.querySelectorAll('#mobileMenu a[href$=".html"]')].filter(a=>a.offsetHeight>0).length})""")
        if r['js'] or r['hidden'] or r['links'] < 10 or not r['css']:
            problems.append('χωρίς site.js %-14s κρυμμένες ενότητες %d · σύνδεσμοι μενού %d · κλάση js %s · φορτώθηκε το CSS %s' % (p, r['hidden'], r['links'], r['js'], r['css']))
    ws.send('Network.setBlockedURLs', {'urls': []})
    # 2γ. ανοιχτό μενού κινητού: η σελίδα από πίσω δεν δέχεται εστίαση
    ws.open(base + 'treatment-speech.html', settle=0.8)
    r = ws.js("""(()=>{document.getElementById('navToggle').click(); const a=document.querySelector('main').inert&&document.querySelector('footer').inert;
        document.getElementById('navToggle').click(); return {open:a,closed:!document.querySelector('main').inert&&!document.querySelector('footer').inert}})()""")
    if not (r['open'] and r['closed']):
        problems.append('μενού κινητού: η σελίδα πίσω από το ανοιχτό μενού δέχεται εστίαση (%s)' % r)
    # 2δ. άφιξη σε άγκυρα: ο στόχος κάθεται ακριβώς κάτω από την κεφαλίδα, όχι πιο χαμηλά
    for w in (390, 1440):
        ws.viewport(w)
        ws.open(base + 'contact-us.html#centre-spata', settle=1.2)
        r = ws.js('({top:Math.round(document.getElementById("centre-spata").getBoundingClientRect().top),hdr:Math.round(document.querySelector(".site-header").getBoundingClientRect().bottom)})')
        if not (r['hdr'] <= r['top'] <= r['hdr'] + 40):
            problems.append('άγκυρα %d: ο στόχος είναι στα %d px, η κεφαλίδα τελειώνει στα %d' % (w, r['top'], r['hdr']))
    # 2ε. εκτύπωση: όλες οι ενότητες ορατές, καμία κάτω μπάρα
    ws.viewport(390, 844, 2)
    ws.send('Emulation.setEmulatedMedia', {'media': 'print'})
    for p in ('index', 'treatment-speech', 'rating'):
        ws.open(base + p + '.html', settle=0.8)
        r = ws.js(HIDDEN_TEXT)
        b = ws.js("""({bar:getComputedStyle(document.querySelector('.callbar')).display,hdr:getComputedStyle(document.querySelector('.site-header')).position})""")
        if r['bad'] or b['bar'] != 'none' or b['hdr'] != 'static':
            problems.append('εκτύπωση %-16s κρυμμένο κείμενο %s · κάτω μπάρα %s · κεφαλίδα %s' % (p, r['bad'], b['bar'], b['hdr']))
    ws.send('Emulation.setEmulatedMedia', {'media': ''})
    # 2στ. το πλάτος περνά σε «υπολογιστή» με ανοιχτό το μενού κινητού (περιστροφή tablet): η σελίδα πρέπει να μείνει ενεργή
    ws.viewport(820, 1180, 2)
    ws.open(base + 'treatment-speech.html', settle=0.8)
    ws.js('document.getElementById("navToggle").click();1'); time.sleep(0.2)
    ws.viewport(1180, 820, 2); time.sleep(0.5)
    r = ws.js('({main:document.querySelector("main").inert,footer:document.querySelector("footer").inert,locked:document.documentElement.classList.contains("menu-open")})')
    if r['main'] or r['footer'] or r['locked']:
        problems.append('αλλαγή πλάτους με ανοιχτό μενού: η σελίδα μένει ανενεργή (%s)' % r)
    # 2η. κεφαλίδα κινητού: κρύβεται όταν κυλάς κάτω, επιστρέφει όταν κυλάς πάνω, και η εστίαση μέσα της δεν μετακινεί τη σελίδα
    ws.viewport(390, 844, 2)
    ws.open(base + 'treatment-speech.html', settle=0.8)
    seq = []
    for y in (700, 1500, 1900):
        ws.js('window.scrollTo({top:%d,behavior:"instant"});1' % y); time.sleep(0.35)
    seq.append(ws.js('document.documentElement.classList.contains("hdr-off")'))
    ws.js('window.scrollTo({top:1700,behavior:"instant"});1'); time.sleep(0.35)
    seq.append(ws.js('document.documentElement.classList.contains("hdr-off")'))
    y0 = ws.js('Math.round(scrollY)')
    ws.js('document.getElementById("navToggle").focus();1'); time.sleep(0.5)
    y1 = ws.js('Math.round(scrollY)')
    if seq != [True, False] or abs(y1 - y0) > 4:
        problems.append('κεφαλίδα κινητού: κρυμμένη μετά από κύλιση κάτω %s, μετά από κύλιση πάνω %s · εστίαση στο κουμπί μενού μετακίνησε τη σελίδα %d px' % (seq[0], seq[1], y1 - y0))
    ws.viewport(1440)
    ws.open(base + 'treatment-speech.html', settle=0.8)
    ws.js('window.scrollTo({top:1800,behavior:"instant"});1'); time.sleep(0.3)
    y0 = ws.js('Math.round(scrollY)')
    ws.js('document.querySelector(".nav-phones summary").focus();1'); time.sleep(0.5)
    y1 = ws.js('Math.round(scrollY)')
    if abs(y1 - y0) > 4:
        problems.append('υπολογιστής: η εστίαση στα «Τηλέφωνα» της κεφαλίδας μετακίνησε τη σελίδα %d px' % (y1 - y0))
    # 2ζ. αργό κινητό (1,6 Mbps, 150 ms, CPU x4, πυκνότητα 3): η κύρια εικόνα ή ο τίτλος πρέπει να φανεί μέσα σε 2,5 s
    ws.viewport(390, 844, 3)
    ws.send('Network.emulateNetworkConditions', {'offline': False, 'latency': 150, 'downloadThroughput': 1.6e6 / 8, 'uploadThroughput': 750e3 / 8})
    ws.send('Emulation.setCPUThrottlingRate', {'rate': 4})
    for p in ('index', 'treatments', 'treatment-speech'):
        ws.open(base + p + '.html', settle=2.5)
        t = ws.js('Math.round(window.__lcpt)')
        report['slow/%s' % p] = {'lcp_ms': t}
        if not t or t > 2500:
            problems.append('αργό κινητό %-16s LCP %s ms (όριο 2500)' % (p, t))
    ws.send('Emulation.setCPUThrottlingRate', {'rate': 1})
    ws.send('Network.emulateNetworkConditions', {'offline': False, 'latency': 0, 'downloadThroughput': -1, 'uploadThroughput': -1})
    # 3. μειωμένη κίνηση: τίποτα κρυμμένο, τίποτα καρφωμένο, καμία κίνηση σε εξέλιξη
    ws.send('Emulation.setEmulatedMedia', {'features': [{'name': 'prefers-reduced-motion', 'value': 'reduce'}]})
    for w in (390, 1440):
        ws.viewport(w)
        for p in ('index', 'treatment-speech', 'rating', 'about-us'):
            ws.open(base + p + '.html', settle=0.8)
            r = ws.js(HIDDEN_TEXT)
            if r['bad'] or r['pinned'] or r['running']:
                problems.append('μείωση κίνησης %d %-14s κρυμμένο κείμενο %s · καρφωμένη σκηνή %s · κινήσεις %d' % (w, p, r['bad'], r['pinned'], r['running']))
    ws.send('Emulation.setEmulatedMedia', {'features': []})
    # 4. πληκτρολόγιο στο κινητό: κανένα στοιχείο με εστίαση κάτω από την κεφαλίδα ή την κάτω μπάρα
    ws.viewport(390, 844, 2)
    for p in ('index', 'contact-us', 'treatment-speech'):
        ws.open(base + p + '.html', settle=0.8)
        ws.js('window.scrollTo(0,900);1'); time.sleep(0.4)
        r = ws.js(FOCUS)
        if r['bad']:
            problems.append('εστίαση   %-18s %d από %d στοιχεία κρύβονται πίσω από κεφαλίδα ή κάτω μπάρα: %s' % (p, len(r['bad']), r['n'], ', '.join(r['bad'][:4])))
    # 5. σελίδα 404 όπως τη σερβίρει το GitHub Pages: άγνωστη διεύθυνση κάτω από το πρόθεμα του site
    ws.open(base.rstrip('/') + cdp.site_prefix() + 'kati/pou-den-yparxei', settle=1.0)
    r = ws.js("""(()=>{const sk=document.querySelector('a[href="#main"]'); const before=location.pathname; sk&&sk.click();
        return {title:document.title,styled:document.querySelector('.site-header').offsetHeight>40,logo:[...document.images].every(i=>i.complete&&i.naturalWidth>0),
                stay:location.pathname===before,focus:document.activeElement&&document.activeElement.id}})()""")
    errs = [e for e in ws.events if e['method'] == 'Network.loadingFailed' and not e['params'].get('canceled')]
    if not (r['styled'] and r['logo'] and r['stay'] and r['focus'] == 'main') or errs:
        problems.append('404       %s · αποτυχίες αιτημάτων %d' % (r, len(errs)))
    # 6. κινητό υψηλής πυκνότητας (3x): το βάρος της πρώτης οθόνης, εκεί που είναι τα περισσότερα κινητά
    ws.viewport(390, 844, 3); kbs = []; fulls = []
    for p in [x for x in cdp.PAGES if x != '404']:
        ws.open(base + p + '.html', settle=2.0)
        kb = weigh(ws.js('[location.href].concat(performance.getEntriesByType("resource").map(r=>r.name))'), base)
        ws.scroll_through(0.25)
        full = weigh(ws.js('[location.href].concat(performance.getEntriesByType("resource").map(r=>r.name))'), base)
        kbs.append(kb); fulls.append(full); report['mobile3x/%s' % p] = {'first_kb': round(kb), 'full_kb': round(full)}
        if kb > BUDGET['mobile3x']['first']:
            problems.append('κινητό 3x %-18s πρώτη οθόνη %.0f KB (όριο %d)' % (p, kb, BUDGET['mobile3x']['first']))
        if full > BUDGET['mobile3x']['full']:
            problems.append('κινητό 3x %-18s ολόκληρη σελίδα %.0f KB (όριο %d)' % (p, full, BUDGET['mobile3x']['full']))
    print('σενάρια: μενού σε 2 μικρές οθόνες · χωρίς JS · χωρίς site.js · εστίαση πίσω από το μενού · άγκυρες · εκτύπωση · αλλαγή πλάτους · κεφαλίδα που κρύβεται · εστίαση στην κεφαλίδα · αργό κινητό · μείωση κίνησης · πληκτρολόγιο · 404 · κινητό 3x πρώτη οθόνη διάμεσος %d KB, μέγιστο %d · όλη η σελίδα μέγιστο %d KB' % (sorted(kbs)[len(kbs) // 2], max(kbs), max(fulls)), flush=True)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    out_json = sys.argv[sys.argv.index('--json') + 1] if '--json' in sys.argv else None
    if out_json:
        args = [a for a in args if a != out_json]
    # το 404 έχει <base>: ελέγχεται στα σενάρια, όπως το σερβίρει το GitHub Pages (άγνωστη διεύθυνση κάτω από το πρόθεμα του site)
    pages = args or [p for p in cdp.PAGES if p != '404']
    problems, warnings, report, brand = [], [], {}, set()
    with cdp.session() as (ws, base):
        ws.send('Page.addScriptToEvaluateOnNewDocument', {'source': INIT})
        for mode, (w, h, dpr) in MODES.items():
            ws.viewport(w, h, dpr)
            for p in pages:
                ws.open(base + p + '.html', settle=2.0)
                first = ws.js('[location.href].concat(performance.getEntriesByType("resource").map(r=>r.name))')
                lcp = ws.js('window.__lcp')                     # πριν από την κύλιση: μετά γράφονται και εικόνες κάτω από την πρώτη οθόνη
                total = ws.js('document.documentElement.scrollHeight'); y = 0
                while True:                                    # στάσεις ανάγνωσης: μισή οθόνη κάθε φορά
                    ws.js('window.scrollTo({top:%d,behavior:"instant"});1' % y); time.sleep(0.9); ws.js(STOP)
                    if y + h >= total:
                        break
                    y = min(y + h // 2, total - h)
                r = ws.js(FINAL); r['lcp'] = lcp
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
        if not args:
            scenarios(ws, base, problems, report)
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
