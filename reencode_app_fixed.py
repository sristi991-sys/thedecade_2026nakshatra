import pathlib, datetime, sys

src = pathlib.Path(r'C:\\decade\\dashboard\\app.py')
# timestamp backup
ts = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
backup_path = src.parent / f'app.py.backup.{ts}'
backup_path.write_bytes(src.read_bytes())
print('Backup created at', backup_path)

# read raw bytes and decode using latin-1 (direct 1‑to‑1 mapping)
raw = src.read_bytes()
text = raw.decode('latin-1')

# mapping of problematic single‑byte characters to safe replacements
replacements = {
    '\x8f': '',   # undefined control
    '\x90': '',   # undefined control
    '\x9d': '',
    '\x9e': '',
    '\x9f': '',
    '\xb2': '²',   # superscript 2 (km²)
    '\x96': '-',   # en dash
    '\x97': '-',   # em dash
    '\x91': "'",  # left single quote
    '\x92': "'",  # right single quote
    '\x93': '"',  # left double quote
    '\x94': '"',  # right double quote
    '\x95': '*',   # bullet
    '\x99': '™',   # trademark
    '\xa0': ' ',   # non‑breaking space
}

# Apply replacements safely
for bad, good in replacements.items():
    text = text.replace(bad, good)

# Write back as UTF‑8 without BOM
src.write_text(text, encoding='utf-8')
print('Re‑encoded app.py to UTF‑8')

# Verification
try:
    src.read_bytes().decode('utf-8')
    print('Verification succeeded: file decodes as UTF‑8')
except UnicodeDecodeError as e:
    print('Verification failed:', e)
    sys.exit(1)
