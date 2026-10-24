import pathlib, json

def find_errors(path):
    p = pathlib.Path(path)
    data = p.read_bytes()
    errors = []
    i = 0
    while i < len(data):
        try:
            data[i:].decode('utf-8')
            break
        except UnicodeDecodeError as e:
            pos = i + e.start
            errors.append({'pos': pos, 'byte': data[pos]})
            i = pos + 1
    return errors

files = [r'C:\decade\dashboard\app.py', r'C:\decade\dashboard\map_utils.py']
report = {}
for f in files:
    report[f] = find_errors(f)
print(json.dumps(report, indent=2))
