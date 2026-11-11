#!/usr/bin/env python3
"""Καθαρίζει τα στρώματα CSS (_build/css/*.css) από νεκρούς και ακυρωμένους κανόνες.

    python3 _build/build.py && python3 _build/tools/css_clean.py            μόνο αναφορά
    python3 _build/build.py && python3 _build/tools/css_clean.py --apply    γράφει τα αρχεία

1. Νεκροί επιλογείς: ανοίγει ΟΛΕΣ τις σελίδες σε πραγματικό Chrome (κινητό και υπολογιστής, μετά από κύλιση, με ανοιχτά μενού
   και ερωτήσεις) και κρατά μόνο όσους επιλογείς ταιριάζουν σε κάποιο στοιχείο. Κλάσεις που προσθέτει η JavaScript και
   καταστάσεις (:hover, :focus κ.λπ.) δεν θεωρούνται ποτέ νεκρές: ελέγχεται ο επιλογέας χωρίς αυτές.
2. Ακυρωμένες δηλώσεις: όταν ο ΙΔΙΟΣ επιλογέας (στο ίδιο @media) ορίζει την ίδια ιδιότητα πιο κάτω, η παλιά δήλωση
   δεν εφαρμόζεται ποτέ και σβήνεται. Δεν αγγίζει δηλώσεις !important που θα κέρδιζαν, ούτε εφεδρικές τιμές.
Μετά από --apply τρέξε build και σύγκριση εικόνων πριν και μετά: το αποτέλεσμα πρέπει να είναι ίδιο pixel προς pixel.
"""
import glob, json, os, re, sys, time
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cdp

CSS_DIR = os.path.join(cdp.ROOT, '_build', 'css')
STATE = r':(?:hover|focus-visible|focus-within|focus|active|visited|checked|disabled|target|link|any-link|placeholder-shown|open)\b'
PSEUDO_EL = r'::?(?:before|after|placeholder|selection|marker|first-line|first-letter|backdrop|file-selector-button|details-content|-webkit-[\w-]+|-moz-[\w-]+)\b'
NEWISH = re.compile(r'\d(?:dvh|svh|lvh|dvw|svw|lvw)\b|color-mix\(|oklch\(|oklab\(|lab\(|lch\(|image-set\(|env\(')


# ---------------------------------------------------------------- parser
def split_top(s, sep):
    out, depth, cur, q = [], 0, '', None
    for ch in s:
        if q:
            cur += ch
            if ch == q:
                q = None
            continue
        if ch in '"\'':
            q = ch; cur += ch
        elif ch in '([':
            depth += 1; cur += ch
        elif ch in ')]':
            depth -= 1; cur += ch
        elif ch == sep and depth == 0:
            out.append(cur); cur = ''
        else:
            cur += ch
    out.append(cur)
    return out


def parse(css, i=0, end=None):
    """Επιστρέφει λίστα κόμβων: ('comment', text) | ('rule', selector, decls) | ('at', prelude, children|None, raw_body)."""
    nodes = []; n = len(css) if end is None else end
    while i < n:
        if css[i].isspace():
            i += 1; continue
        if css.startswith('/*', i):
            j = css.index('*/', i) + 2; nodes.append(('comment', css[i:j])); i = j; continue
        # διαβάζει μέχρι { ή ; (εκτός εισαγωγικών/παρενθέσεων)
        j = i; q = None; depth = 0
        while j < n:
            ch = css[j]
            if q:
                if ch == '\\':
                    j += 1
                elif ch == q:
                    q = None
            elif ch in '"\'':
                q = ch
            elif ch == '(':
                depth += 1
            elif ch == ')':
                depth -= 1
            elif ch in '{;' and depth == 0:
                break
            elif css.startswith('/*', j):
                j = css.index('*/', j) + 1
            j += 1
        prelude = css[i:j].strip()
        if j >= n or css[j] == ';':
            nodes.append(('at', prelude, None, None)); i = j + 1; continue
        # βρίσκει το ταιριαστό }
        k = j + 1; depth = 1; q = None
        while k < n and depth:
            ch = css[k]
            if q:
                if ch == '\\':
                    k += 1
                elif ch == q:
                    q = None
            elif ch in '"\'':
                q = ch
            elif css.startswith('/*', k):
                k = css.index('*/', k) + 1
            elif ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
            k += 1
        body = css[j + 1:k - 1]
        if prelude.startswith('@'):
            name = prelude.split()[0].split('(')[0]
            if name in ('@media', '@supports', '@layer', '@container'):
                nodes.append(('at', prelude, parse(body), None))
            else:                                   # @font-face, @keyframes, @property…: αυτούσια
                nodes.append(('at', prelude, None, body))
        else:
            nodes.append(('rule', prelude, body.strip()))
        i = k
    return nodes


def decls(body):
    out = []
    for d in split_top(body, ';'):
        d = d.strip()
        if not d:
            continue
        if d.startswith('/*') and d.endswith('*/'):
            out.append((None, d, False)); continue
        m = re.match(r'(?:/\*.*?\*/\s*)*([\w-]+)\s*:\s*(.*)$', d, re.S)
        if not m:
            out.append((None, d, False)); continue
        out.append((m.group(1).lower() if not m.group(1).startswith('--') else m.group(1), d, bool(re.search(r'!\s*important\s*$', m.group(2)))))
    return out


def serialize(nodes, indent=''):
    out = []
    for nd in nodes:
        if nd[0] == 'comment':
            out.append(indent + nd[1])
        elif nd[0] == 'rule':
            out.append('%s%s{%s}' % (indent, nd[1], nd[2]))
        elif nd[2] is not None:
            out.append('%s%s{\n%s\n%s}' % (indent, nd[1], serialize(nd[2], indent + '  '), indent))
        elif nd[3] is not None:
            out.append('%s%s{%s}' % (indent, nd[1], nd[3]))
        else:
            out.append('%s%s;' % (indent, nd[1]))
    return '\n'.join(out)


def walk(nodes, ctx=''):
    """Δίνει (λίστα-γονέα, θέση, πλαίσιο) για κάθε κανόνα, σε σειρά εγγράφου."""
    for idx, nd in enumerate(nodes):
        if nd[0] == 'rule':
            yield nodes, idx, ctx
        elif nd[0] == 'at' and nd[2] is not None:
            yield from walk(nd[2], ctx + ' ' + re.sub(r'\s+', ' ', nd[1]))


# ---------------------------------------------------------------- live matching
def js_classes():
    """Κλάσεις που ΠΡΟΣΘΕΤΕΙ ή αφαιρεί η JavaScript (classList.add/toggle/remove, className=). Όσες απλώς αναζητούνται δεν μετρούν."""
    names = set(['js'])                                  # μπαίνει από το inline script του <head>
    for f in glob.glob(os.path.join(cdp.ROOT, 'assets', '*.js')):
        src = open(f, encoding='utf-8').read()
        for args in re.findall(r'classList\.(?:add|toggle|remove)\(([^)]*)\)', src):
            names.update(re.findall(r'''['"]([\w-]+)['"]''', args))
        for val in re.findall(r'''className\s*=\s*['"]([^'"]+)['"]''', src):
            names.update(val.split())
    return names


def relax(sel, dyn):
    """Ο επιλογέας χωρίς καταστάσεις, ψευδοστοιχεία και κλάσεις που βάζει η JS (για να ελεγχθεί αν ΜΠΟΡΕΙ να ταιριάξει)."""
    s = re.sub(PSEUDO_EL, '', sel)
    # :not(...), :is(...), :where(...), :has(...) που εξαρτώνται από κατάσταση ή κλάση της JS: μπορεί να ισχύουν, άρα φεύγουν ολόκληρα
    out, i = '', 0
    while i < len(s):
        m = re.compile(r':(?:not|is|where|has)\(').match(s, i)
        if not m:
            out += s[i]; i += 1; continue
        j, depth = m.end(), 1
        while j < len(s) and depth:
            depth += {'(': 1, ')': -1}.get(s[j], 0); j += 1
        inner = s[m.end():j - 1]
        dynamic = re.search(STATE, inner) or '[open]' in inner or any(c.replace('\\', '') in dyn for c in re.findall(r'\.((?:\\.|[\w-])+)', inner))
        out += '' if dynamic else s[i:j]
        i = j
    s = re.sub(STATE, '', out).replace('[open]', '')
    # χωρισμός σε σύνθετα και συνδυαστές (εκτός παρενθέσεων): κάθε σύνθετο χάνει τις κλάσεις της JS, κι αν αδειάσει γίνεται *
    tokens, cur, depth = [], '', 0
    for ch in s.strip():
        if ch in '([':
            depth += 1
        elif ch in ')]':
            depth -= 1
        if depth == 0 and (ch.isspace() or ch in '>+~'):
            if cur:
                tokens.append(cur); cur = ''
            if tokens and tokens[-1].strip() in ('', '>', '+', '~') and tokens[-1] in (' ', '>', '+', '~'):
                tokens[-1] = ch if not ch.isspace() else tokens[-1]      # « > » -> «>»
            else:
                tokens.append(' ' if ch.isspace() else ch)
        else:
            cur += ch
    if cur:
        tokens.append(cur)
    out = ''
    for tok in tokens:
        if tok in (' ', '>', '+', '~'):
            out += tok; continue
        tok = re.sub(r'\.((?:\\.|[\w-])+)', lambda m: '' if m.group(1).replace('\\', '') in dyn else m.group(0), tok)
        out += tok or '*'
    if out[:1] in ('>', '+', '~'):
        out = '*' + out
    return out.strip() or '*'


PROBE = r"""(sels=>{const hit=[];for(let i=0;i<sels.length;i++){try{if(document.querySelector(sels[i]))hit.push(i)}catch(e){hit.push(i)}}return hit})"""


def live_matches(tests):
    alive = set()
    with cdp.session() as (ws, base):
        payload = json.dumps(tests, ensure_ascii=False)
        for w in (390, 1440):
            ws.viewport(w)
            for p in cdp.PAGES:
                ws.open(base + p + '.html', settle=0.8)
                alive.update(ws.js(PROBE + '(' + payload + ')'))
                ws.scroll_through(0.15)
                ws.js("""document.querySelectorAll('details').forEach(d=>d.open=true);var t=document.getElementById('navToggle');
                         if(t&&getComputedStyle(t).display!=='none'){t.click();var b=document.getElementById('mTherapiesBtn');if(b)b.click()} 1""")
                time.sleep(0.3)
                alive.update(ws.js(PROBE + '(' + payload + ')'))
            print('  έλεγχος σε πλάτος', w, '· ζωντανοί', len(alive), 'από', len(tests), flush=True)
    return alive


# ---------------------------------------------------------------- main
def main():
    apply = '--apply' in sys.argv
    files = sorted(glob.glob(os.path.join(CSS_DIR, '*.css')))
    trees = {f: parse(open(f, encoding='utf-8').read()) for f in files}
    before = sum(os.path.getsize(f) for f in files)
    dyn = js_classes()

    # 1. νεκροί επιλογείς
    parts = {}
    for f in files:
        if os.path.basename(f).startswith('10-'):
            continue
        for parent, idx, ctx in walk(trees[f]):
            for part in split_top(parent[idx][1], ','):
                part = part.strip()
                if part:
                    parts.setdefault(relax(part, dyn), set()).add(part)
    tests = sorted(parts)
    alive = live_matches(tests)
    dead = set()
    for i, t in enumerate(tests):
        if i not in alive:
            dead.update(parts[t])
    removed_rules = removed_parts = 0
    for f in files:
        if os.path.basename(f).startswith('10-'):
            continue
        for parent, idx, ctx in list(walk(trees[f])):
            sel = parent[idx][1]
            keep = [p.strip() for p in split_top(sel, ',') if p.strip() and p.strip() not in dead]
            n_all = len([p for p in split_top(sel, ',') if p.strip()])
            if len(keep) < n_all:
                removed_parts += n_all - len(keep)
                parent[idx] = ('rule', ','.join(keep), parent[idx][2]) if keep else None
                removed_rules += 0 if keep else 1

    def prune(nodes):
        out = []
        for nd in nodes:
            if nd is None:
                continue
            if nd[0] == 'at' and nd[2] is not None:
                kids = prune(nd[2])
                if not [k for k in kids if k[0] != 'comment']:
                    continue
                nd = ('at', nd[1], kids, None)
            out.append(nd)
        return out
    for f in files:
        trees[f] = prune(trees[f])

    # 2. ακυρωμένες δηλώσεις: ίδιο πλαίσιο + ίδιος επιλογέας + ίδια ιδιότητα πιο κάτω
    later = {}                                                           # (ctx, selector, prop) -> important της τελευταίας
    order = []
    for f in files:
        for parent, idx, ctx in walk(trees[f]):
            order.append((parent, idx, ctx))
    removed_decls = 0
    for parent, idx, ctx in reversed(order):
        sel = re.sub(r'\s+', ' ', parent[idx][1]); body = parent[idx][2]
        ds = decls(body); kept = []; mine = {}
        for prop, raw, imp in ds:
            if prop is None:
                kept.append(raw); continue
            win = later.get((ctx, sel, prop))
            if win is not None and (win[0] or not imp) and not NEWISH.search(win[1]):
                removed_decls += 1; continue                             # δεν εφαρμόζεται ποτέ
            kept.append(raw); mine[prop] = (imp, raw)
        for prop, v in mine.items():
            if (ctx, sel, prop) not in later or v[0] or not later[(ctx, sel, prop)][0]:
                later.setdefault((ctx, sel, prop), v)
        parent[idx] = ('rule', parent[idx][1], ';'.join(kept)) if kept else None
    for f in files:
        trees[f] = prune(trees[f])

    # 3. @keyframes που δεν χρησιμοποιούνται πια
    allcss = '\n'.join(serialize(trees[f]) for f in files)
    removed_kf = 0
    for f in files:
        out = []
        for nd in trees[f]:
            if nd[0] == 'at' and nd[1].startswith('@keyframes'):
                name = nd[1].split()[1]
                uses = len(re.findall(r'(?<![\w-])%s(?![\w-])' % re.escape(name), allcss)) - 1
                if uses <= 0:
                    removed_kf += 1; continue
            out.append(nd)
        trees[f] = out

    after = 0
    for f in files:
        text = serialize(trees[f]) + '\n'
        after += len(text.encode())
        if apply:
            open(f, 'w', encoding='utf-8').write(text)
    print('νεκροί επιλογείς: %d (ολόκληροι κανόνες: %d) · ακυρωμένες δηλώσεις: %d · αχρησιμοποίητα @keyframes: %d' % (removed_parts, removed_rules, removed_decls, removed_kf))
    print('μέγεθος πηγών: %.1f KB -> %.1f KB%s' % (before / 1024, after / 1024, '' if apply else '  (δοκιμή: τίποτα δεν γράφτηκε, πρόσθεσε --apply)'))


if __name__ == '__main__':
    main()
