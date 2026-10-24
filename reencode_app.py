import pathlib, datetime, sys, os
src = pathlib.Path(r'C:\\decade\\dashboard\\app.py')
# timestamp
ts = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
backup_path = src.parent / f"app.py.backup.{ts}"
# copy backup
backup_path.write_bytes(src.read_bytes())
print('Backup created at', backup_path)
# read as windows-1252
raw = src.read_bytes()
text = raw.decode('windows-1252')
# write as utf-8 without BOM
src.write_text(text, encoding='utf-8')
print('Re‑encoded to UTF‑8')
# verify
try:
    src.read_bytes().decode('utf-8')
    print('Verification passed: file decodes as UTF-8')
except UnicodeDecodeError as e:
    print('Verification failed:', e)
    sys.exit(1)
