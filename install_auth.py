from pathlib import Path
import re, shutil

root = Path(__file__).resolve().parent
backend = root
app = backend / "app.py"
req = backend / "requirements.txt"

auth = backend / "auth_routes.py"
if not app.exists():
    print("ERROR: Put this folder inside your existing backend folder (where app.py is).")
    raise SystemExit(1)

# Add Authlib requirement without duplicating it.
if req.exists():
    text = req.read_text()
    if "Authlib==1.6.5" not in text and "Authlib" not in text:
        text = text.rstrip() + "\nAuthlib==1.6.5\n"
        req.write_text(text)
else:
    req.write_text("Flask==3.1.2\nflask-cors==6.0.1\nrequests==2.32.5\nAuthlib==1.6.5\n")

# Patch app.py automatically.
s = app.read_text()
if "from auth_routes import register_auth" not in s:
    lines=s.splitlines()
    insert_at=0
    for i,line in enumerate(lines):
        if line.startswith('import ') or line.startswith('from '):
            insert_at=i+1
    lines.insert(insert_at, 'from auth_routes import register_auth')
    s='\n'.join(lines)+'\n'

if not re.search(r'(?m)^\s*register_auth\(app\)\s*$', s):
    m=re.search(r'(?m)^\s*app\s*=\s*Flask\(__name__\)\s*$', s)
    if m:
        end=m.end()
        s=s[:end]+'\nregister_auth(app)'+s[end:]
    else:
        s='\n'.join(['from auth_routes import register_auth',s,'register_auth(app)',''])

app.write_text(s)
print("SoilSense authentication connected successfully.")
print("Added Authlib to requirements.txt and connected auth_routes.py to app.py.")
