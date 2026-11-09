#!/usr/bin/env python3
"""Collector bolletta: ARERA (bonus + rete/oneri), indice GO GME, in InfluxDB (Bolletta)."""
import base64
import io
import json
import os
import re
import urllib.request
import urllib.error
import zipfile
from datetime import date, datetime
from zoneinfo import ZoneInfo

import openpyxl
import requests

from app_logging import get_logger
from collector.collector_gme import CollectorGME

log = get_logger('collector.bolletta')
ROME = ZoneInfo('Europe/Rome')


class CollectorBolletta:
    ORG = 'fotovoltaico'
    BUCKET = 'Bolletta'
    # Fonti ARERA 2026 (TIT annuale + TIC trimestrale + UC3/UC6)
    TIT_URL = 'https://www.arera.it/fileadmin/allegati/docs/25/575-2025-R-eel-TABELLE_TIT.xlsx'
    TABAB_URL = 'https://www.arera.it/fileadmin/user_upload/227-2026-_R-com_Relazione_Tecnica_TabAB.xlsx'
    TIC7_URL = 'https://www.arera.it/fileadmin/allegati/docs/25/588-2025-R-com-TABELLE.xlsx'

    def __init__(self):
        self.token = os.getenv('INFLUXDB_TOKEN')
        self.url = os.getenv('INFLUXDB_URL', 'http://localhost:8086').rstrip('/')
        self.org = os.getenv('INFLUXDB_ORG', self.ORG)
        if not self.token:
            raise RuntimeError('INFLUXDB_TOKEN non configurato')

    # ---------- Influx ----------
    def _last(self, measurement):
        q = ('from(bucket:"%s") |> range(start:-10y) '
             '|> filter(fn:(r)=>r._measurement=="%s") |> last() '
             '|> pivot(rowKey:["_time"],columnKey:["_field"],valueColumn:"_value")'
             % (self.BUCKET, measurement))
        req = urllib.request.Request(
            self.url + '/api/v2/query?org=' + self.org,
            data=q.encode(),
            headers={'Authorization': 'Token ' + self.token,
                     'Content-Type': 'application/vnd.flux'})
        body = urllib.request.urlopen(req, timeout=30).read().decode('utf-8', 'ignore')
        lines = body.splitlines()
        if not lines:
            return None
        hdr = lines[0].split(',')
        rows = [l for l in lines[1:] if l.startswith(',_result')]
        if not rows:
            return None
        return dict(zip(hdr, rows[-1].split(',')))

    def _write(self, line):
        req = urllib.request.Request(
            self.url + '/api/v2/write?org=' + self.org + '&bucket=' + self.BUCKET + '&precision=s',
            data=line.encode(),
            headers={'Authorization': 'Token ' + self.token,
                     'Content-Type': 'text/plain'})
        return urllib.request.urlopen(req, timeout=30).status

    # ---------- ARERA bonus ----------
    def fetch_bonus(self):
        u = ('https://www.arera.it/consumatori/bonus-sociale/'
             'bonus-sociale-per-disagio-economico/a-quanto-ammontano')
        req = urllib.request.Request(u, headers={'User-Agent': 'Mozilla/5.0'})
        html = urllib.request.urlopen(req, timeout=30).read().decode('utf-8', 'ignore')
        text = re.sub(r'<[^>]+>', ' ', html)
        text = re.sub(r'\s+', ' ', text)
        out = {}
        for label, key in [('1-2 componenti', 'b12'),
                           ('3-4 componenti', 'b34'),
                           ('oltre 4 componenti', 'b4plus')]:
            m = re.search(r'Numerosit\u00e0 familiare ' + re.escape(label) +
                          r'\s+([\d.,]+)\s+([\d.,]+)\s+([\d.,]+)', text)
            if not m:
                raise RuntimeError('riga bonus non trovata: ' + label)
            out[key] = float(m.group(3).replace('.', '').replace(',', '.'))
        return out

    # ---------- ARERA rete + oneri ----------
    def _load(self, url):
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        return openpyxl.load_workbook(io.BytesIO(urllib.request.urlopen(req, timeout=60).read()),
                                      data_only=True)

    def fetch_rete(self):
        tit = self._load(self.TIT_URL)['Tab 4']
        s1 = s2 = s3 = None
        for row in tit.iter_rows(values_only=True):
            if row and str(row[0]) == '2026':
                s1, s2, s3 = float(row[1]), float(row[3]), float(row[4])
                break
        tab = self._load(self.TABAB_URL)

        def residenti(ws):
            for row in ws.iter_rows(values_only=True):
                if row and any(isinstance(v, str) and 'residenti' in v for v in row):
                    return float(row[4])
            raise RuntimeError('residenti non trovato')

        asos = residenti(tab['Tabella A'])
        arim = residenti(tab['Tabella B'])
        t7 = self._load(self.TIC7_URL)['Tabella 7']
        uc3 = uc6p = uc6e = None
        for row in t7.iter_rows(values_only=True):
            if row and row[1] and 'Utenza domestica in bassa tensione' in str(row[1]):
                uc3, uc6p, uc6e = float(row[2]), float(row[4]), float(row[5])
                break
        if None in (s1, s2, s3, asos, arim, uc3, uc6p, uc6e):
            raise RuntimeError('parsing ARERA incompleto')
        net_var = round((s3 + asos + arim + uc3 + uc6e) / 100.0, 6)
        net_fix = round(s1 / 1200.0, 6)
        potenza = round((s2 + uc6p) / 1200.0, 6)
        # robustezza: soglie di plausibilita'
        if not 0.03 < net_var < 0.07:
            raise RuntimeError('net_var fuori range: %s' % net_var)
        if not 1.0 < net_fix < 3.0:
            raise RuntimeError('net_fix fuori range: %s' % net_fix)
        if not 1.0 < potenza < 3.0:
            raise RuntimeError('potenza fuori range: %s' % potenza)
        return {'net_var': net_var, 'net_fix': net_fix, 'potenza_tariffa': potenza}

    # ---------- GME indice GO ----------
    def fetch_go(self):
        gme = CollectorGME()
        token = gme._get_token()
        if not token:
            raise RuntimeError('GME token mancante')
        today = date.today()
        payload = {'Platform': 'PublicMarketResults', 'Segment': 'GO',
                   'DataName': 'ENV_HourlyPrice',
                   'IntervalStart': today.replace(day=1).strftime('%Y%m%d'),
                   'IntervalEnd': today.strftime('%Y%m%d'), 'Attributes': {}}
        r = requests.post(gme.BASE_URL + '/RequestData', json=payload,
                          headers={'Authorization': 'Bearer ' + token,
                                   'Content-Type': 'application/json'}, timeout=60)
        d = r.json()
        if not d.get('contentResponse'):
            raise RuntimeError('GO: risposta senza contenuto')
        with zipfile.ZipFile(io.BytesIO(base64.b64decode(d['contentResponse']))) as z:
            rows = json.loads(z.read('data.json').decode('utf-8', 'ignore'))
        num = den = 0.0
        for x in rows:
            p = float(x['Price'])
            v = float(x['Volumes'])
            num += p * v
            den += v
        if den <= 0:
            raise RuntimeError('GO: volumi nulli')
        return round((num / den) / 1000.0, 6), today.strftime('%Y-%m')

    def _flux_value(self, q):
        req = urllib.request.Request(
            self.url + '/api/v2/query?org=' + self.org,
            data=q.encode(),
            headers={'Authorization': 'Token ' + self.token,
                     'Content-Type': 'application/vnd.flux'})
        body = urllib.request.urlopen(req, timeout=30).read().decode('utf-8', 'ignore')
        lines = body.splitlines()
        if not lines:
            return None
        hdr = lines[0].split(',')
        rows = [l for l in lines[1:] if l.startswith(',_result')]
        if not rows:
            return None
        d = dict(zip(hdr, rows[-1].split(',')))
        try:
            return float(d.get('_value'))
        except (TypeError, ValueError):
            return None

    def fetch_prev_pun(self):
        q = """import "timezone"
import "date"
option location = timezone.location(name: "Europe/Rome")
stop = date.truncate(t: now(), unit: 1mo)
start = date.sub(d: 2mo, from: stop)
from(bucket:"GME") |> range(start: start, stop: stop) |> filter(fn:(r)=>r._measurement=="gme_monthly_avg" and r._field=="pun_kwh_avg") |> group() |> last()"""
        return self._flux_value(q)

    # ARERA pubblica per i domestici in libero un foglio per mese: dispacciamento
    # (CDISPD), sigma1/2/3, UC3, UC6.
    ARERA_DOMESTICO = ('https://www.arera.it/fileadmin/area_operatori/prezzi_e_tariffe/'
                       'Corrispettivi_libero_elettrico_domestico_%d.xlsx')
    MESI = ('gennaio', 'febbraio', 'marzo', 'aprile', 'maggio', 'giugno', 'luglio',
            'agosto', 'settembre', 'ottobre', 'novembre', 'dicembre')
    ADM_PAGINA = 'https://www.adm.gov.it/portale/aliquote-accisa-nazionali'

    @staticmethod
    def _scarica(url, timeout=60):
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        return urllib.request.urlopen(req, timeout=timeout).read()

    def fetch_disp_mesi(self):
        """CDISPD di ogni mese pubblicato nel foglio ARERA dei domestici in libero.

        Torna {'YYYY-MM': valore}. Il mese corrente compare in ritardo: finche' non
        c'e', i pannelli usano l'ultimo disponibile.
        """
        oggi = date.today()
        mesi = {}
        for anno in (oggi.year, oggi.year - 1):
            try:
                data = self._scarica(self.ARERA_DOMESTICO % anno)
                if data[:2] != b'PK':
                    continue
                wb = openpyxl.load_workbook(io.BytesIO(data), data_only=True, read_only=True)
                for foglio in wb.sheetnames:
                    nome = foglio.split()[0].lower()
                    if nome not in self.MESI:
                        continue
                    for row in wb[foglio].iter_rows(values_only=True):
                        cells = [str(c).strip() if c is not None else '' for c in row]
                        if len(cells) > 2 and cells[1].startswith('Quota energia'):
                            mese = '%s-%02d' % (anno, self.MESI.index(nome) + 1)
                            mesi[mese] = round(float(cells[2]), 6)
                            break
            except Exception as e:
                # ARERA tiene online solo il foglio dell'anno corrente: la 404
                # dell'anno precedente e' lo stato normale, non un guasto.
                if isinstance(e, urllib.error.HTTPError) and e.code == 404:
                    log.info('ARERA corrispettivi %d non online (404), ignorato', anno)
                else:
                    log.warning('ARERA corrispettivi %d non leggibili: %s', anno, e)
        return mesi

    def fetch_accise(self):
        """Accisa domestica (EUR/kWh) e data dell'aggiornamento, dal PDF ADM.

        La tabella delle aliquote non dice nulla della fascia esente: qui si prende
        solo l'aliquota, quella della riga "per ogni kWh" accanto al D.M. 30/12/2011
        (l'altra riga "per ogni kWh" e' 0,0005, le navi in porto).
        """
        try:
            html = self._scarica(self.ADM_PAGINA).decode('utf-8', 'ignore')
        except Exception as e:
            log.warning('ADM non raggiungibile: %s', e)
            return None, None
        links = re.findall(r'href="([^"]*Aliquote[^"]*\.pdf[^"]*)"', html, re.I)
        if not links:
            log.warning('ADM: nessun link alle aliquote nella pagina')
            return None, None
        link = links[0].replace('&amp;', '&')
        url = link if link.startswith('http') else 'https://www.adm.gov.it' + link
        data_agg = re.search(r'aggiornamento\+al\+([0-9]+)\+([a-z]+)\+([0-9]{4})', url)
        data_str = ('%s %s %s' % data_agg.groups()) if data_agg else ''
        try:
            pdf = self._scarica(url)
            from pypdf import PdfReader
            lettore = PdfReader(io.BytesIO(pdf))
            for pagina in lettore.pages:
                testo = pagina.extract_text() or ''
                if 'ACCISE SULL' not in testo.upper() or 'ENERGIA ELETTRICA' not in testo.upper():
                    continue
                righe = [r.strip() for r in testo.splitlines() if r.strip()]
                candidate = []
                for i, riga in enumerate(righe):
                    m = re.match(r'€\s*0,0*(\d+)\s*per ogni kWh', riga)
                    if not m:
                        continue
                    valore = float('0.' + m.group(1).rjust(4, '0'))
                    vicino = ' '.join(righe[i + 1:i + 3])
                    if 'D.M. 30/12/2011' in vicino:
                        return valore, data_str
                    candidate.append(valore)
                if candidate:
                    # ripiego: la riga domestica e' l'unica "per ogni kWh" sopra 0,01
                    return max(candidate), data_str
        except Exception as e:
            log.warning('ADM: PDF aliquote non leggibile: %s', e)
        return None, None

    def _dashboard_uid(self, auth, url):
        """L'uid della dashboard cambia da un'installazione all'altra: si cerca per
        titolo invece di dare per buono quello di chi ha esportato il file."""
        try:
            req = urllib.request.Request(url + '/api/search?type=dash-db&limit=100',
                                         headers={'Authorization': auth})
            for hit in json.load(urllib.request.urlopen(req, timeout=15)):
                if (hit.get('title') or '').strip() == 'Solaredge 3.0':
                    return hit.get('uid')
        except Exception:
            pass
        return None

    def update_pun_threshold(self, prev_pun):
        import base64 as b64
        url = os.getenv('GRAFANA_URL', 'http://localhost:3000').rstrip('/')
        user = os.getenv('GRAFANA_USER', 'admin')
        pwd = os.getenv('GRAFANA_PASSWORD')
        if not pwd or prev_pun is None:
            return
        auth = 'Basic ' + b64.b64encode((user + ':' + pwd).encode()).decode()
        uid = self._dashboard_uid(auth, url)
        if not uid:
            return
        req = urllib.request.Request(url + '/api/dashboards/uid/' + uid,
                                     headers={'Authorization': auth})
        d = json.load(urllib.request.urlopen(req, timeout=30))['dashboard']
        found = False
        changed = False
        for p in d.get('panels', []):
            if p.get('id') == 202:
                found = True
                steps = [{'color': 'dark-green', 'value': 0},
                         {'color': 'dark-red', 'value': round(float(prev_pun), 6)}]
                cur = p['fieldConfig']['defaults']['thresholds'].get('steps', [])
                if not cur or abs(float(cur[-1].get('value', -1)) - float(prev_pun)) > 1e-9:
                    p['fieldConfig']['defaults']['thresholds']['steps'] = steps
                    changed = True
        if not found:
            log.warning('Dashboard: nessun pannello con id 202, soglia PUN non aggiornata')
        if changed:
            req = urllib.request.Request(url + '/api/dashboards/db',
                                         data=json.dumps({'dashboard': d, 'overwrite': True}).encode(),
                                         headers={'Authorization': auth, 'Content-Type': 'application/json'})
            urllib.request.urlopen(req, timeout=30)

    def write_stato(self, ok, error=''):
        err = error.replace('"', '').replace('\n', ' ')[:300]
        self._write('stato,flow=bolletta ok=%d,error="%s"' % (1 if ok else 0, err))

    # ---------- run ----------
    def collect(self):
        result = {}
        bonus = self.fetch_bonus()
        last = self._last('bonus')
        unchanged = last and all(abs(float(last.get(k, -1)) - bonus[k]) < 1e-9
                                 for k in ('b12', 'b34', 'b4plus'))
        if not unchanged:
            self._write('bonus,valid_from=%d-01-01,fonte=ARERA b12=%s,b34=%s,b4plus=%s'
                        % (date.today().year, bonus['b12'], bonus['b34'], bonus['b4plus']))
        result['bonus'] = {'values': bonus, 'changed': not unchanged}

        try:
            go_value, go_month = self.fetch_go()
            last = self._last('go')
            go_changed = not (last and abs(float(last.get('value', -1)) - go_value) < 1e-9)
            if go_changed:
                self._write('go,month=%s,fonte=GME value=%s' % (go_month, go_value))
            result['go'] = {'value': go_value, 'month': go_month, 'changed': go_changed}
        except Exception as e:
            # A inizio mese il GME non ha ancora i volumi dell'asta GO: si tiene
            # l'ultimo valore pubblicato, come per il PUN, invece di perdere rete,
            # oneri e soglia del mese che vengono dopo.
            last = self._last('go')
            if not last:
                raise
            result['go'] = {'value': float(last.get('value', 0.0)),
                            'month': last.get('month', 'stimato'),
                            'changed': False, 'stimato': str(e)[:120]}

        disp_mesi = self.fetch_disp_mesi()
        accise, accise_data = self.fetch_accise()
        if accise is None:
            # ADM giu' o PDF cambiato: si tiene l'ultima aliquota scritta, mai
            # un punto senza accise (i pannelli leggono quel campo).
            prev = self._last('tasse') or {}
            accise = prev.get('accise')
            accise_data = accise_data or prev.get('accise_data')
            if accise:
                log.warning('ADM: aliquota non letta, tengo %s (%s)', accise, accise_data)
            else:
                log.error('ADM: aliquota accise sconosciuta e nessun valore precedente')
        # Il foglio ARERA arriva con mesi di ritardo: si scrivono anche i mesi
        # fino al corrente, con l'ultima aliquota nota, cosi' il menu puo'
        # scegliere novembre e il pannello non resta senza punto.
        pubblicati = set(disp_mesi)
        if disp_mesi:
            ultimo = max(disp_mesi)
            mesi_indietro = (date.today().year - int(ultimo[:4])) * 12 + (date.today().month - int(ultimo[5:]))
            if mesi_indietro >= 2:
                log.warning('CDISPD: ultimo mese pubblicato %s (%d mesi fa)', ultimo, mesi_indietro)
            anno_u, mese_u = (int(x) for x in ultimo.split('-'))
            oggi = date.today()
            while (anno_u, mese_u) < (oggi.year, oggi.month):
                mese_u += 1
                if mese_u > 12:
                    mese_u, anno_u = 1, anno_u + 1
                disp_mesi['%d-%02d' % (anno_u, mese_u)] = disp_mesi[ultimo]
        scritti = 0
        for mese, valore in sorted(disp_mesi.items()):
            anno, num = mese.split('-')
            ts = datetime(int(anno), int(num), 1, tzinfo=ROME).timestamp()
            campi = ['disp=%s' % valore,
                     'disp_da="%s"' % (mese if mese in pubblicati else ultimo)]
            if accise:
                campi.append('accise=%s' % float(accise))
            if accise_data:
                campi.append('accise_data="%s"' % str(accise_data).replace('"', ''))
            self._write('tasse,mese=%s %s %d' % (mese, ','.join(campi), int(ts)))
            scritti += 1
        if disp_mesi:
            result['disp'] = disp_mesi[max(disp_mesi)]
        if scritti:
            log.info('Tasse: %d mesi scritti, ultimo %s disp=%s accise=%s (%s)',
                     scritti, max(disp_mesi), disp_mesi[max(disp_mesi)], accise, accise_data)

        rete = self.fetch_rete()
        last = self._last('rete')
        rete_changed = not (last and all(abs(float(last.get(k, -1)) - rete[k]) < 1e-9
                                         for k in rete))
        if rete_changed:
            self._write('rete,fonte=ARERA net_var=%s,net_fix=%s,potenza=%s'
                        % (rete['net_var'], rete['net_fix'], rete['potenza_tariffa']))
        result['rete'] = dict(rete, changed=rete_changed)
        prev = self.fetch_prev_pun()
        self.update_pun_threshold(prev)
        result['pun_prev'] = prev
        self.write_stato(True)
        return result
