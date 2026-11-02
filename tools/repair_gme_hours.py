"""Toglie dalla cache GME i giorni con i quattro quarti d'ora in una riga.

Dal 2025-10 il MGP manda quattro periodi da un quarto d'ora dentro la stessa ora
(stesso `Hour`, colonna `Period` che il parser non leggeva). Un giorno sano ha 552
righe (23 zone x 24 ore); uno sporco ne ha 2208, e in Influx l'ora valeva l'ultimo
quarto invece della media. Il collector ora li media, ma i giorni gia' in cache non
si rileggono finche' il file c'e': questo script li elenca e, con --delete, li
toglie — poi `main.py --history --source gme` li riscarica corretti e ricalcola
l'SSP.

    python3 tools/repair_gme_hours.py            # elenca soltanto
    python3 tools/repair_gme_hours.py --delete   # toglie i file sporchi
"""

import glob
import gzip
import json
import os
import sys

CACHE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     'cache', 'gme', 'data')
RIGHE_SANE_PER_ORA = 24.5      # 23 zone, una riga per ora; oltre = piu' periodi


def sporco(path: str) -> bool:
    try:
        prices = json.load(gzip.open(path, 'rt', encoding='utf-8'))['data'].get('prices') or []
    except Exception:
        return False
    ore = len({p.get('hour') for p in prices}) or 1
    return len(prices) / ore > RIGHE_SANE_PER_ORA


def main() -> int:
    elimina = '--delete' in sys.argv[1:]
    files = sorted(glob.glob(os.path.join(CACHE, '20*')))
    bad = [f for f in files if sporco(f)]
    print(f"giorni in cache: {len(files)} | con piu' di un periodo per ora: {len(bad)}")
    if bad:
        mesi = sorted({os.path.basename(f)[:7] for f in bad})
        print('  dal', os.path.basename(bad[0])[:10], 'al', os.path.basename(bad[-1])[:10])
        print('  mesi da rileggere:', ', '.join(mesi))
    if bad and elimina:
        for f in bad:
            os.remove(f)
        print(f"eliminati {len(bad)} file. Ora: main.py --history --source gme")
    elif bad:
        print('  (niente eliminato: rilancia con --delete)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
