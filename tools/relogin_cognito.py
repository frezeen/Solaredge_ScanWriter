#!/usr/bin/env python3
import base64, hashlib, json, os, re, sys, time, urllib.parse
from pathlib import Path
import requests

ENV = {}
for line in Path('/opt/Solaredge_ScanWriter/.env').read_text().splitlines():
    line = line.strip()
    if line and '=' in line and not line.startswith('#'):
        k, v = line.split('=', 1)
        ENV[k.strip()] = v.strip()
U, P = ENV['SOLAREDGE_USERNAME'], ENV['SOLAREDGE_PASSWORD']
SITE = ENV['SOLAREDGE_SITE_ID']
BASE = ENV.get('SOLAREDGE_WEB_BASE_URL', 'https://monitoring.solaredge.com').rstrip('/')
CF = Path(ENV.get('SOLAREDGE_COOKIE_FILE', '/opt/Solaredge_ScanWriter/cookies/web_cookies.json'))
CLI, RED = 'ugfnsujd3384sshcjehaphlh3', 'https://monitoring.solaredge.com/mfe/auth/callback'
UA = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0 Safari/537.36'

def log(k, v):
    print(f'{k}: {v}', flush=True)

def b64u(b):
    return base64.urlsafe_b64encode(b).rstrip(b'=').decode()

def retry(fn, n=5):
    for i in range(n):
        try:
            return fn()
        except requests.exceptions.RequestException as e:
            log(f'   retry {i+1}', type(e).__name__)
            time.sleep(3)
    raise RuntimeError('max retries')

ver = b64u(os.urandom(48))
ch = b64u(hashlib.sha256(ver.encode()).digest())
auth = (f'https://login.solaredge.com/login?lang=en_US&response_type=code&client_id={CLI}'
        f'&scope=email+openid&redirect_uri={urllib.parse.quote(RED, safe="")}'
        f'&code_challenge_method=S256&code_challenge={ch}')

s = requests.Session()
s.headers['User-Agent'] = UA
r = retry(lambda: s.get(auth, timeout=25))
log('STEP1_login_page', r.status_code)
csrf = re.search(r'name="csrf"[^>]*?value="([^"]+)"', r.text).group(1)
action = re.search(r'<form[^>]*?action="([^"]*)"', r.text).group(1).replace('&amp;', '&')
post_url = urllib.parse.urljoin('https://login.solaredge.com/', action)
log('STEP1_post_url_host_path', urllib.parse.urlparse(post_url).netloc + urllib.parse.urlparse(post_url).path)

r2 = retry(lambda: s.post(post_url, data={'csrf': csrf, 'username': U, 'password': P, 'cognitoAsfData': ''},
                          allow_redirects=False, timeout=25))
log('STEP2_submit', r2.status_code)
log('STEP2_redirect', bool(r2.headers.get('Location')))
title = (re.search(r'<title>(.*?)</title>', r2.text) or [None, ''])[1]
log('STEP2_body_title', title)

loc = r2.headers.get('Location', '')
code = None
hops = 0
while loc and hops < 6:
    q = urllib.parse.urlparse(loc)
    if q.hostname and 'monitoring.solaredge.com' in q.hostname and q.path.startswith('/mfe/auth/callback'):
        code = urllib.parse.parse_qs(q.query).get('code', [None])[0]
        break
    nxt = loc if loc.startswith('http') else urllib.parse.urljoin('https://login.solaredge.com/', loc)
    rr = retry(lambda: s.get(nxt, allow_redirects=False, timeout=25))
    loc = rr.headers.get('Location', '')
    hops += 1
log('STEP3_code', bool(code))
if not code:
    log('ABORT', 'no authorization code')
    sys.exit(1)

r3 = retry(lambda: s.post('https://login.solaredge.com/oauth2/token',
    data={'grant_type': 'authorization_code', 'client_id': CLI, 'redirect_uri': RED,
          'code': code, 'code_verifier': ver}, timeout=25))
log('STEP4_token_exchange', r3.status_code)
try:
    tok = r3.json()
except Exception:
    tok = {}
log('STEP4_token_fields', sorted(tok.keys()))
if not tok.get('id_token'):
    log('ABORT', str(tok.get('error', 'no id_token')))
    sys.exit(1)

r4 = retry(lambda: s.post(f'{BASE}/services/auth/token?legacy=false',
    json={'id_token': tok['id_token'], 'access_token': tok.get('access_token'),
          'refresh_token': tok.get('refresh_token'), 'expires_in': tok.get('expires_in'),
          'token_type': tok.get('token_type')}, timeout=25))
log('STEP5_handover', r4.status_code)
sel = [c for c in s.cookies if 'monitoring' in c.domain or c.domain in ('.solaredge.com', 'solaredge.com')]
log('STEP5_cookie_names', sorted({c.name for c in sel}))
cookie = '; '.join(f'{c.name}={c.value}' for c in sel)

r5 = retry(lambda: s.get(f'{BASE}/services/auth/valid?legacy=false', timeout=25))
log('STEP6_valid', r5.status_code)

r6 = retry(lambda: s.get(f'{BASE}/solaredge-web/p/site/{SITE}/', headers={'accept': 'text/html,*/*'}, timeout=25))
ct = r6.headers.get('content-type', '').lower()
body = r6.text[:2048].lower() if 'html' in ct else ''
ok = r6.status_code == 200 and not any(x in body for x in ('j_username', 'j_password', 'login'))
log('STEP7_site_page', f'status={r6.status_code} legacy_valid={ok}')

if ok and cookie:
    if CF.exists():
        CF.rename(CF.with_suffix('.json.bak-cognito'))
    CF.write_text(json.dumps({'cookie': cookie, 'last_login_ts': int(time.time()), 'csrf_token': None}, indent=2), encoding='utf-8')
    os.chmod(CF, 0o600)
    log('STEP8_cookie_file', f'REWRITTEN {CF.name}')
    if tok.get('refresh_token'):
        rp = CF.with_name('cognito_refresh_token.json')
        rp.write_text(json.dumps({'refresh_token': tok['refresh_token'], 'expires_in': tok.get('expires_in'),
                                  'ts': int(time.time())}, indent=2), encoding='utf-8')
        os.chmod(rp, 0o600)
        log('STEP8_refresh_token_file', rp.name)
else:
    log('STEP8_cookie_file', 'SKIPPED (validation failed; old cookie untouched)')
