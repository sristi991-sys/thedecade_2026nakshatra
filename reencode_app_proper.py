import pathlib, datetime, sys

src = pathlib.Path(r'C:\\decade\\dashboard\\app.py')
# Create timestamped backup
ts = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
backup = src.parent / f'app.py.backup.{ts}'
backup.write_bytes(src.read_bytes())
print('Backup created at', backup)

# Read raw bytes
raw = src.read_bytes()
# Decode with latin-1 (guaranteed 1:1 mapping)
text = raw.decode('latin-1')

# Define a mapping of problematic single-byte characters to safe replacements
replacements = {
    '\x8f': '',   # undefined control
    '\x90': '',   # undefined control
    '\x9d': '',   # undefined control
    '\x9e': '',
    '\x9f': '',
    '\xb2': '²',  # superscript 2 (km²)
    '\x96': '-',  # en dash
    '\x97': '-',  # em dash
    '\x91': "'",  # left single quote
    '\x92': "'",  # right single quote
    '\x93': '"',  # left double quote
    '\x94': '"',  # right double quote
    '\x95': '*',  # bullet
    '\x99': '™',  # trademark
    '\xA0': ' ',  # non‑breaking space
}

# Apply replacements
cleaned = ''.join(replacements.get(ch, ch) for ch in text)

# Write back as UTF‑8 (no BOM)
src.write_text(cleaned, encoding='utf-8')
print('Re‑encoded app.py to UTF‑8')

# Verify decode
try:
    src.read_bytes().decode('utf-8')
    print('Verification succeeded: file is valid UTF‑8')
except UnicodeDecodeError as e:
    print('Verification failed:', e)
    sys.exit(1)
