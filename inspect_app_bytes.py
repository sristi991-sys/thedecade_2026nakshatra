import pathlib, sys
p = pathlib.Path(r'C:\\decade\\dashboard\\app.py')
bytes_data = p.read_bytes()
print('File size:', len(bytes_data))
pos = 12807
if pos < len(bytes_data):
    print('Byte at position', pos, ':', hex(bytes_data[pos]), 'decimal', bytes_data[pos])
    start = max(0, pos-10)
    end = min(len(bytes_data), pos+10)
    print('Surrounding bytes:', bytes_data[start:end].hex(' '))
else:
    print('Position out of range')
try:
    bytes_data.decode('utf-8')
    print('Decodes as UTF-8')
except UnicodeDecodeError as e:
    print('UnicodeDecodeError:', e)
