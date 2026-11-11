# Εργαλεία επιπέδων hero (layered hero)

`cutcrop.swift` κόβει ένα αντικείμενο από φωτογραφία με το Vision του macOS (χωρίς cloud):

    swift cutcrop.swift <in.jpg> <outdir> <tag> x y w h     # crop κανονικοποιημένο, αρχή πάνω-αριστερά

Το Vision δεν βρίσκει «θέμα» σε ολόκληρη σκηνή χώρου· δώσε crop γύρω από το αντικείμενο.
Για την αρχική (2026-09-08): hero-room.jpg, crop τραμπολίνου `0 0.52 0.42 0.48`.
Μετά, με numpy+opencv: inpaint (Telea, r=9, dilate 13) + απαλή σκιά 30% στη θέση του αντικειμένου
→ `assets/hero-room-bg.jpg`, και RGBA cutout με feathered alpha → `assets/hero-room-fg.webp`.
Το OG image μένει η αρχική φωτογραφία (build.py αντικαθιστά `-bg.jpg` → `.jpg`).
