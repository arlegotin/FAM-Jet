"""Standalone Matplotlib export from frozen chart JSON; no model/data imports."""

import argparse
import hashlib
from importlib import metadata
import json
import math
import os
from pathlib import Path
import platform
import tempfile


_NAMES = ('accuracy-memory.svg', 'cost.svg', 'primary-effect.svg')


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _locked_packages(lock):
    pins = {}
    for line in Path(lock).read_text().splitlines():
        if not line or line.startswith('#') or line.startswith('--'):
            continue
        name, rest = line.split('==', 1)
        version = rest.split()[0]
        if not name or not version or metadata.version(name) != version:
            raise RuntimeError(f'Matplotlib report environment differs from lock: {name}')
        pins[name] = version
    if 'matplotlib' not in pins or 'numpy' not in pins:
        raise RuntimeError('Matplotlib report lock is incomplete')
    return pins


def render_charts(data_path, out):
    """Render three descriptive plots and a renderer/data/output receipt."""
    data_path, out = Path(data_path), Path(out)
    raw = data_path.read_bytes()
    data = json.loads(raw)
    if (data.get('schema_version') != 1 or data.get('kind') != 'famjet_e5_chart_data' or
            type(data.get('methods')) is not list or not data['methods'] or
            type(data.get('effects')) is not list or len(data['effects']) != 2):
        raise ValueError('complete frozen chart JSON required')
    methods = data['methods']
    for item in methods:
        if (type(item.get('name')) is not str or not item['name'] or
                any(type(item.get(field)) not in (int, float) or not math.isfinite(item[field]) or
                    item[field] < 0 for field in
                    ('loss', 'state_bytes', 'static_bytes', 'query_seconds'))):
            raise ValueError('finite actual method chart values required')
    if len({item['name'] for item in methods}) != len(methods):
        raise ValueError('duplicate chart method')
    effects = data['effects']
    if {item.get('panel') for item in effects} != {'confirmation', 'replication'}:
        raise ValueError('confirmation and replication chart points required')
    for item in effects:
        if (any(type(item.get(field)) not in (int, float) or not math.isfinite(item[field])
                for field in ('estimate', 'lower', 'upper')) or
                not item['lower'] <= item['estimate'] <= item['upper']):
            raise ValueError('finite interval chart values required')
    out.mkdir(parents=True, exist_ok=True)
    # Import only after both settings are bound; font-cache writes remain in tmp.
    with tempfile.TemporaryDirectory(prefix='famjet-mpl-', dir=out.parent) as cache:
        os.environ['MPLBACKEND'] = 'Agg'
        os.environ['MPLCONFIGDIR'] = cache
        import matplotlib
        matplotlib.use('Agg', force=True)
        matplotlib.rcParams.update({'font.family': 'DejaVu Sans',
                                    'svg.hashsalt': 'famjet-e5-frozen-v1',
                                    'svg.fonttype': 'none'})
        import matplotlib.pyplot as plt
        import numpy as np

        colors = ['#1d577a' if item['name'] == 'jet' else
                  '#b35b35' if item['name'] == 'bank' else '#687b74'
                  for item in methods]
        fig, ax = plt.subplots(figsize=(7.2, 4.2), layout='constrained')
        for item, color in zip(methods, colors, strict=True):
            ax.scatter(item['state_bytes'], item['loss'], color=color,
                       s=65, label=item['name'])
            ax.annotate(item['name'], (item['state_bytes'], item['loss']),
                        xytext=(4, 4), textcoords='offset points', fontsize=8)
        ax.set(xlabel='Persistent state (bytes)', ylabel='Development normalized loss',
               title='Entered configurations at the declared state budget')
        ax.grid(alpha=.2)
        fig.savefig(out / _NAMES[0], format='svg', metadata={'Date': None})
        plt.close(fig)

        names = [item['name'] for item in methods]
        x = np.arange(len(names))
        fig, axes = plt.subplots(2, 1, figsize=(8.0, 6.0), layout='constrained')
        axes[0].bar(x, [item['static_bytes'] for item in methods], color=colors)
        axes[0].set(ylabel='Full static wire/export (bytes)',
                    title='Static storage and measured read cost')
        axes[1].bar(x, [item['query_seconds'] for item in methods], color=colors)
        axes[1].set(ylabel='Median warm read block (seconds)')
        axes[1].set_xticks(x, names, rotation=35, ha='right')
        fig.savefig(out / _NAMES[1], format='svg', metadata={'Date': None})
        plt.close(fig)

        order = {item['panel']: item for item in effects}
        points = [order[name] for name in ('confirmation', 'replication')]
        fig, ax = plt.subplots(figsize=(6.8, 3.6), layout='constrained')
        y = [1, 0]
        for level, item in zip(y, points, strict=True):
            ax.plot([item['lower'], item['upper']], [level, level], color='#1d577a', lw=2)
            ax.scatter([item['estimate']], [level], color='#b35b35', zorder=3)
        ax.axvline(0, color='#444444', ls='--', lw=1)
        ax.set(yticks=y, yticklabels=['Confirmation', 'Replication'],
               xlabel='Paired Bank minus Jet normalized loss (history units)',
               title='Separate frozen-model conditional intervals')
        fig.savefig(out / _NAMES[2], format='svg', metadata={'Date': None})
        plt.close(fig)

        lock = Path(__file__).resolve().parents[1] / 'docs/reporting-requirements.lock'
        pins = _locked_packages(lock)
        receipt = {'schema_version': 1, 'kind': 'famjet_e5_plot_receipt',
                   'renderer_sha256': _sha(__file__),
                   'data_sha256': hashlib.sha256(raw).hexdigest(),
                   'report_lock_sha256': _sha(lock),
                   'python': platform.python_version(),
                   'matplotlib': matplotlib.__version__, 'numpy': np.__version__,
                   'locked_packages': pins,
                   'backend': matplotlib.get_backend(), 'font': 'DejaVu Sans',
                   'svg_hashsalt': 'famjet-e5-frozen-v1',
                   'outputs': {name: {'sha256': _sha(out / name),
                                      'bytes': (out / name).stat().st_size} for name in _NAMES}}
    (out / 'plots-receipt.json').write_text(json.dumps(receipt, sort_keys=True,
                                                    separators=(',', ':')) + '\n')
    return receipt


def main(argv=None):
    parser = argparse.ArgumentParser(description='Render frozen FAM-Jet chart JSON with Matplotlib.')
    parser.add_argument('--data', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args(argv)
    render_charts(args.data, args.out)


if __name__ == '__main__':
    main()
