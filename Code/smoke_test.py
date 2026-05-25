import urllib.request, urllib.parse, http.cookiejar, json, uuid, sys, time

BASE = 'http://127.0.0.1:3000'

cj = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))


def post(path, data=None):
    url = BASE + path
    if data is None:
        data_bytes = b''
    else:
        data_bytes = urllib.parse.urlencode(data).encode()
    req = urllib.request.Request(url, data=data_bytes)
    try:
        with opener.open(req, timeout=10) as resp:
            body = resp.read().decode()
            code = resp.getcode()
            return code, body
    except Exception as e:
        print('HTTP POST error', e)
        raise


def get(path):
    url = BASE + path
    req = urllib.request.Request(url)
    try:
        with opener.open(req, timeout=10) as resp:
            body = resp.read().decode()
            code = resp.getcode()
            return code, body
    except Exception as e:
        print('HTTP GET error', e)
        raise


name = f"smoke-{uuid.uuid4().hex[:8]}"
password = 'TestPass123!'
icon = '🧪'

print('Registering device', name)
code, body = post('/register', {'name': name, 'password': password, 'icon': icon})
if code != 200:
    print('Register failed:', code, body)
    sys.exit(2)

resp = json.loads(body)
if not resp.get('ok'):
    print('Register returned not ok:', resp)
    sys.exit(2)

device = resp.get('device')
print('Registered device id', device.get('id'))

# Verify /api/me (should be authenticated via cookie set by register)
print('Checking /api/me')
code, body = get('/api/me')
if code != 200:
    print('/api/me failed', code, body)
    sys.exit(3)
me = json.loads(body)
if me.get('id') != device.get('id') or me.get('name') != name:
    print('/api/me returned unexpected data', me)
    sys.exit(3)
print('/api/me OK')

# Logout
print('Logging out')
code, body = post('/logout')
if code != 200:
    print('Logout failed', code, body)
    sys.exit(4)

# Login
print('Logging in')
code, body = post('/login', {'name': name, 'password': password})
if code != 200:
    print('Login failed', code, body)
    sys.exit(5)
resp = json.loads(body)
if not resp.get('ok'):
    print('Login returned not ok', resp)
    sys.exit(5)
print('Login OK')

# Final /api/devices check
print('Fetching device list')
code, body = get('/api/devices')
if code != 200:
    print('/api/devices failed', code, body)
    sys.exit(6)
devs = json.loads(body)
if not any(d.get('id') == device.get('id') for d in devs):
    print('Device not in device list')
    sys.exit(6)

print('SMOKE TEST PASSED')
sys.exit(0)
