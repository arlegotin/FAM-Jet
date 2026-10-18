"""Static source/input inventory; imports no monitored or scientific code."""
import ast
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[4]
EVIDENCE = ROOT / 'docs/research/task18-owned-root-asynchronous-rss-evidence'
BASE = 'c0e66464ea5e5361bccf007786ee8f80a6b903fc'
SOURCE = 'd95bfaf'
PATHS = [
    'validation/kernel_stage_a/monitor.py',
    'validation/kernel_stage_a/README.md',
    'tests/test_kernel_stage_a_owned_root_terminal.py',
    'docs/research/task18-owned-root-asynchronous-rss-native-control.py',
]
WORKER = 'docs/research/task18-owned-root-lifecycle-native-worker.py'
OLD_PARENT = 'docs/research/task18-owned-root-lifecycle-native-control.py'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def write(name, obj):
    (EVIDENCE / name).write_text(json.dumps(obj, indent=2) + '\n')


def meta(name):
    raw = (ROOT / name).read_bytes()
    return dict(path=str(ROOT / name), bytes=len(raw), sha256=sha(raw))


def main():
    changed = subprocess.check_output(['git', 'diff', '--name-only', BASE, SOURCE], cwd=ROOT, text=True).splitlines()
    assert changed == sorted(PATHS)
    source = {}
    for name in PATHS:
        destination = EVIDENCE / 'source-inputs' / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / name, destination)
        assert destination.read_bytes() == (ROOT / name).read_bytes()
        source[name] = meta(name)
        if name.endswith('.py'):
            ast.parse((ROOT / name).read_bytes(), filename=name)
    for name in (WORKER, OLD_PARENT):
        ast.parse((ROOT / name).read_bytes(), filename=name)
    package = {str(path.relative_to(ROOT)): sha(path.read_bytes())
               for path in sorted((ROOT / 'famjet').rglob('*.py'))}
    package_hash = sha(json.dumps(package, sort_keys=True, separators=(',', ':'),
                                  ensure_ascii=False, allow_nan=False).encode())
    lock_hash = sha((ROOT / 'requirements.lock').read_bytes())
    expected = json.loads((ROOT / 'docs/research/task18-kernel-projection-source-verification.json').read_text())['identities']['memory_components']
    memory = {name: dict(expected=value['current_sha256'], actual=package[name])
              for name, value in expected.items()}
    assert package_hash == '15cf84c28136d4f5ec34c173316d0db1f2aab1da97c6d68993a5c22bf18ec050'
    assert lock_hash == '2b1931e022c8e2555c45a9f9fb5feead7077b9043bfc088fc2db3e811bbe21d1'
    assert len(memory) == 15 and all(item['actual'] == item['expected'] for item in memory.values())
    worker = meta(WORKER)
    assert worker['sha256'] == 'da9819fb58547721371a65930c76101fe5344ad8d2a291ea88b782b007d5b8e5'
    parent_tree = ast.parse((ROOT / PATHS[-1]).read_bytes())
    vectors = [node.value for node in ast.walk(parent_tree) if isinstance(node, ast.Assign)
               and any(isinstance(target, ast.Name) and target.id == 'vector' for target in node.targets)]
    assert len(vectors) == 1 and isinstance(vectors[0], ast.List)
    assert [ast.literal_eval(item) for item in vectors[0].elts[1:3]] == ['-I', '-B']
    write('static-audit.json', dict(base=BASE, source_commit=SOURCE, changed_paths=changed,
        source=source, package_hash=package_hash, lock_hash=lock_hash, memory_components=memory,
        old_parent=meta(OLD_PARENT), unchanged_worker=worker, ast_parse=True,
        native_executed=False, scientific_import_executed=False))
    write('native-static-inputs.json', dict(executed=False, parent=meta(PATHS[-1]), worker=worker,
        old_parent=meta(OLD_PARENT), parent_vector=[str(ROOT / '.venv/bin/python'), '-I', '-B',
            str(ROOT / PATHS[-1]), '<fresh separately allocated destination>'],
        worker_vectors=[[str(ROOT / '.venv/bin/python'), '-I', '-B', str(ROOT / WORKER),
            case, '<destination>/' + case + '.socket', '<repr(actual case deadline)>']
            for case in ('empty', 'survivor')], allocation_seconds=10,
        ordered_cases=['empty', 'survivor'], case_seconds=4.5, reserve_seconds=.25,
        incremental_bytes=201326592, output_bytes=67108864, worker_threads=1,
        dynamic_slots='Destination, actual executable choice and monotonic deadlines await separate allocation; no concrete runtime vector hash exists.',
        static_ast_only=True))
    print(json.dumps(dict(changed_paths=changed, package_hash=package_hash,
                          lock_hash=lock_hash, memory_components=len(memory),
                          worker_sha256=worker['sha256'], parent_sha256=source[PATHS[-1]]['sha256'])))


if __name__ == '__main__':
    main()
