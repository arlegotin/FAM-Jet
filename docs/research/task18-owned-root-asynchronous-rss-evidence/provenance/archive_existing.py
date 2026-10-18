"""Archive already observed fixture specimens without running tests or following links."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat

ROOT = Path(__file__).resolve().parents[4]
EVIDENCE = ROOT / 'docs/research/task18-owned-root-asynchronous-rss-evidence'
SOURCES = {
    'red-positive-rss': Path('/private/var/folders/q3/tm7kkng56417wgzydc4q8p8r0000gn/T/pytest-of-artemlegotin/pytest-4364'),
    'green-interrupted': Path('/private/var/folders/q3/tm7kkng56417wgzydc4q8p8r0000gn/T/pytest-of-artemlegotin/pytest-4365'),
    'green-focused-anaconda': Path('/private/tmp/t18async-green-1'),
    'green-focused-venv': Path('/private/tmp/t18async-green-2'),
    'affected-cover': Path('/private/tmp/t18async-cover-1'),
}


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def retain(source, destination, entries):
    mode = source.lstat().st_mode
    if stat.S_ISDIR(mode):
        destination.mkdir()
        for child in sorted(source.iterdir()):
            retain(child, destination / child.name, entries)
        return
    if stat.S_ISLNK(mode):
        raw = os.fsencode(os.readlink(source))
        destination.symlink_to(os.readlink(source))
        preserved = os.fsencode(os.readlink(destination))
        kind = 'symlink-raw-target'
    elif stat.S_ISREG(mode):
        raw = source.read_bytes()
        shutil.copy2(source, destination)
        preserved = destination.read_bytes()
        kind = 'regular'
    else:
        raw = b''
        preserved = b''
        kind = 'special-not-followed'
        destination = destination.with_name(destination.name + '.special.json')
        destination.write_text(json.dumps({'original_mode': mode, 'not_followed': True}) + '\n')
    assert raw == preserved
    entries.append(dict(original=str(source),archive=str(destination.relative_to(ROOT)),
                        kind=kind,mode=mode,bytes=len(raw),sha256=digest(raw)))


def main():
    entries = []
    for label, source in SOURCES.items():
        destination = EVIDENCE / 'specimens' / label
        assert source.exists() and not destination.exists()
        destination.parent.mkdir(parents=True, exist_ok=True)
        retain(source, destination, entries)
    (EVIDENCE / 'specimen-manifest.json').write_text(json.dumps(dict(
        entries=entries, originals_retained=True, symlinks='raw targets, never followed',
        specials='mode recorded, never opened'), indent=2) + '\n')
    print(json.dumps(dict(specimen_entries=len(entries),labels=list(SOURCES),
                          originals_retained=True)))


if __name__ == '__main__':
    main()
