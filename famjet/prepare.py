"""Explicit offline preparation for synthetic inventories and observed sensors."""
import argparse
from dataclasses import asdict
import json
from pathlib import Path

from famjet.artifacts import atomic_json
from famjet.config import load_config, config_documents_equal
from famjet.data.beijing import prepare_beijing, _is_unavailable, _verify_manifest
from famjet.eval.splits import build_split_manifest, verify_split_manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--dataset', choices=['synthetic','beijing'])
    parser.add_argument('--archive', type=Path)
    parser.add_argument('--out', type=Path)
    args = parser.parse_args(argv)
    config = load_config(args.config)
    dataset = args.dataset or ('beijing' if config.data.generator_version == 'beijing_observed_v1' else 'synthetic')
    if dataset == 'synthetic':
        out = args.out or Path('configs/manifests/synthetic_v1.json')
        if out.exists():
            manifest = verify_split_manifest(out)
            # Checking an existing sealed inventory must also honor the supplied config.
            if not config_documents_equal(manifest['config'], asdict(config)):
                raise ValueError('existing synthetic inventory config differs')
        else:
            build_split_manifest(config,out)
        print(f'checked synthetic manifest: {out}')
        return 0
    archive = args.archive or Path(config.data.beijing.archive_path if config.data.beijing else 'data/raw/beijing-uci501.zip')
    out = args.out or Path('configs/manifests/beijing_v1.json')
    if not archive.is_file():
        if out.exists():
            previous = json.loads(out.read_text())
            if _is_unavailable(previous):
                if previous['archive'] != str(archive):
                    raise ValueError('refusing to replace an existing manifest with unavailable status')
            else:
                prepared = _verify_manifest(out)
                if (prepared.get('status') != 'prepared' or prepared.get('dataset') != 'beijing'
                        or not config_documents_equal(prepared.get('config'), asdict(config))):
                    raise ValueError('existing Beijing manifest differs; cannot report its availability')
                print(f'Beijing unavailable: local archive missing; preserved prepared manifest {out}; preparation not run')
                return 2
        else:
            atomic_json(out,{'schema_version':1,'dataset':'beijing','status':'unavailable',
                             'reason':'local_archive_missing','archive':str(archive),
                             'real_transfer':'untested','substitution':False})
        print(f'Beijing unavailable: local archive missing; recorded {out}')
        return 2
    prepare_beijing(archive,out,config)
    print(f'prepared Beijing manifest: {out}; protected artifacts sealed, no evaluation')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
