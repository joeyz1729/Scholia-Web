"""Fail-closed validation shared by the packager and restricted deployment receiver."""
from pathlib import Path
import hashlib
import json
import re
import sys
import tarfile
import xml.etree.ElementTree as ET

ORIGIN = 'https://scholia.joeyz.top'
TEXT = {'.html', '.txt', '.json', '.js', '.css', '.svg', '.xml'}
PRIVATE = re.compile(r'来源与编写说明|(?:https?:)?//(?:localhost|127\.0\.0\.1)(?=[:/])|/Users/|file://|(?:href|src)=["\'][^"\']*(?:archive|editorial|source)/', re.I)

def allowed(name):
    p = Path(name)
    if p.is_absolute() or any(x.startswith('.') or x in ('..', '') for x in p.parts):
        return False
    if name in ('index.html', 'index.txt', '404.html', 'robots.txt', 'sitemap.xml', 'icon.svg', 'release.json'):
        return True
    if re.fullmatch(r'__next\.[\w.$-]+\.txt', name):
        return True
    if name.startswith('_next/'):
        return p.suffix in {'.js', '.css', '.woff', '.woff2', '.ttf', '.svg', '.json'}
    if name.startswith(('junior-assets/figures/', 'knowledge-assets/')):
        return p.suffix in {'.png', '.svg', '.jpg', '.webp'}
    return bool(re.fullmatch(r'(?:junior|knowledge|404|_not-found)/(?:[\w.-]+/)*(?:index\.html|index\.txt|__next\.[\w.$-]+\.txt)', name))

def inspect(root, verify_manifest=False):
    root = Path(root)
    files = {}
    for p in sorted(root.rglob('*')):
        if p.is_symlink():
            raise ValueError('Symlink forbidden: ' + str(p))
        if p.is_dir():
            continue
        name = p.relative_to(root).as_posix()
        if not allowed(name):
            raise ValueError('Unapproved public file: ' + name)
        data = p.read_bytes()
        if p.suffix in TEXT and p.suffix != '.js' and PRIVATE.search(data.decode('utf-8')):
            raise ValueError('Private content/local URL in: ' + name)
        if name != 'release.json':
            files[name] = hashlib.sha256(data).hexdigest()
    for name in ('index.html', '404.html', 'robots.txt', 'sitemap.xml'):
        if name not in files:
            raise ValueError('Required file missing: ' + name)
    if 'Disallow: /' in (root/'robots.txt').read_text():
        raise ValueError('Not a public build')
    routes = []
    for el in ET.parse(root/'sitemap.xml').iter():
        if el.tag.endswith('}loc'):
            url = el.text or ''
            if not url.startswith(ORIGIN + '/'):
                raise ValueError('Unexpected sitemap origin')
            route = url[len(ORIGIN):].strip('/')
            if (route + '/index.html').lstrip('/') not in files:
                raise ValueError('Sitemap page missing: ' + route)
            routes.append(url)
    if not routes:
        raise ValueError('Empty sitemap')
    if verify_manifest:
        meta = json.loads((root/'release.json').read_text())
        if meta['files'] != files or meta['routes'] != routes:
            raise ValueError('Release digest/inventory mismatch')
    return files, routes

def package(root, destination, revision):
    files, routes = inspect(root)
    if not re.fullmatch('[a-f0-9]{40}', revision):
        raise ValueError('Expected full source commit SHA')
    Path(root, 'release.json').write_text(json.dumps(dict(schemaVersion=1, revision=revision, files=files, routes=routes)))
    inspect(root, True)
    with tarfile.open(destination, 'w:gz') as archive:
        for name in sorted([*files, 'release.json']):
            archive.add(Path(root, name), arcname=name, recursive=False)
    print(f'Validated public release: {len(files)} files, {len(routes)} routes')

if __name__ == '__main__':
    if len(sys.argv) == 2:
        files, routes = inspect(sys.argv[1])
        print(f'Validated {len(files)} files, {len(routes)} routes')
    else:
        package(*sys.argv[1:])
