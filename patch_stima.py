#!/usr/bin/env python3
"""Il seme puo' essere una stima: il pannello deve dirlo (disp_da="stima")."""
import sys

P = '/opt/Solaredge_ScanWriter/collector/collector_bolletta.py'
src = open(P, encoding='utf-8').read()


def sub(old, new):
    global src
    if src.count(old) != 1:
        sys.exit(f'ANCORA: {src.count(old)} occorrenze di {old[:50]!r}')
    src = src.replace(old, new)


sub("""        mesi = {}
        try:
            with open(self.CDISPD_STORICO, encoding='utf-8') as f:
                for riga in f:
                    riga = riga.strip()
                    if not riga or riga.startswith('#') or riga.startswith('mese,'):
                        continue
                    parti = riga.split(',')
                    if len(parti) >= 2:
                        mesi[parti[0].strip()] = round(float(parti[1]), 6)""",
    """        mesi = {}
        self._stima = set()
        try:
            with open(self.CDISPD_STORICO, encoding='utf-8') as f:
                for riga in f:
                    riga = riga.strip()
                    if not riga or riga.startswith('#') or riga.startswith('mese,'):
                        continue
                    parti = riga.split(',')
                    if len(parti) >= 2:
                        mese = parti[0].strip()
                        mesi[mese] = round(float(parti[1]), 6)
                        if len(parti) > 2 and parti[2].strip() != 'arera':
                            self._stima.add(mese)""")

sub("""            campi = ['disp=%s' % valore,
                     'disp_da="%s"' % (mese if mese in pubblicati else ultimo)]""",
    """            # un valore che non viene da ARERA lo dice nel campo che il pannello stampa
            da = 'stima' if mese in getattr(self, '_stima', set()) else (
                mese if mese in pubblicati else ultimo)
            campi = ['disp=%s' % valore, 'disp_da="%s"' % da]""")

open(P, 'w', encoding='utf-8').write(src)
print('scritto', P)
