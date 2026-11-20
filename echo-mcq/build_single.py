"""Builds echo-mcq-offline.html: one self-contained file (questions + all figures embedded)."""
import os, base64, json
here = os.path.dirname(os.path.abspath(__file__))
html = open(os.path.join(here, 'index.html'), encoding='utf-8').read()
data = open(os.path.join(here, 'data.js'), encoding='utf-8').read()
imgs = {f: 'data:image/jpeg;base64,' + base64.b64encode(open(os.path.join(here, 'img', f), 'rb').read()).decode()
        for f in sorted(os.listdir(os.path.join(here, 'img')))}
inline = '<script>' + data + 'window.MCQ_IMG=' + json.dumps(imgs) + ';</script>'
html = html.replace('<script src="data.js"></script>', inline)
html = html.replace('<link rel="manifest" href="manifest.webmanifest">\n', '')
icon = base64.b64encode(open(os.path.join(here, 'icon.svg'), 'rb').read()).decode()
html = html.replace('href="icon.svg"', 'href="data:image/svg+xml;base64,' + icon + '"')
out = os.path.join(here, 'echo-mcq-offline.html')
open(out, 'w', encoding='utf-8').write(html)
print(out, round(os.path.getsize(out) / 1e6, 1), 'MB')
