"""Immutable exploratory manifests and reservation-only protected namespaces."""
from dataclasses import asdict,replace
import json
from pathlib import Path

from famjet.artifacts import atomic_json
from famjet.config import RunConfig,_parse,config_documents_equal
from famjet.data._processes import REGIMES,ROBUSTNESS
from famjet.data.synthetic import (FEATURE_VERSION,GENERATOR_VERSION,NAMESPACES,POPULATIONS,
                                   PROTECTED,SEED_VERSION,generate_episode)
from famjet.provenance import canonical_hash,canonical_json,derive_seed

MANIFEST_VERSION=1


def _seal(payload):
    payload=json.loads(canonical_json(payload))
    return {**payload,'manifest_hash':canonical_hash(payload)}


def _check_seal(payload):
    if type(payload) is not dict or payload.get('manifest_version')!=MANIFEST_VERSION:
        raise ValueError('unknown split manifest version')
    if payload.get('generator_version')!=GENERATOR_VERSION:
        raise ValueError('unknown generator version')
    if payload.get('seed_version')!=SEED_VERSION or payload.get('feature_version')!=FEATURE_VERSION:
        raise ValueError('unknown seed/feature version')
    if payload.get('manifest_hash')!=canonical_hash({k:v for k,v in payload.items() if k!='manifest_hash'}):
        raise ValueError('split manifest checksum mismatch')


def _write_immutable(path,payload):
    if path.exists():
        try:
            old=json.loads(path.read_text())
        except (ValueError,OSError) as exc:
            raise ValueError(f'existing manifest is unreadable: {path}') from exc
        if old!=payload:
            raise ValueError(f'immutable manifest already exists with different content: {path}')
    else:
        atomic_json(path,payload)


def _suite_configs(config):
    # Separate schema-matched categorical artifacts and independently varied
    # dense key loads; these are configurations, never compatible checkpoints.
    for population in POPULATIONS:
        g=replace(config.data.generator,population=population,delay_multiplier=0.)
        v=32 if population in {'corrected_categorical','random_binding'} else 8
        yield population,replace(config,data=replace(config.data,value_dim=v,generator=g))
    for delay in [.125,1.,10.]:
        g=replace(config.data.generator,population='delayed',delay_multiplier=delay)
        yield f'delayed_{delay:g}',replace(config,data=replace(config.data,value_dim=8,generator=g))
    for robustness in ROBUSTNESS:
        if robustness=='standard':
            continue
        g=replace(config.data.generator,population='primary',robustness=robustness,delay_multiplier=0.)
        yield f'robustness_{robustness}',replace(config,data=replace(config.data,value_dim=8,generator=g))
    for load in [8,16,64]:
        for population in ['primary','presence','corrected_categorical','random_binding']:
            g=replace(config.data.generator,population=population,key_load=load,delay_multiplier=0.)
            v=32 if population in {'corrected_categorical','random_binding'} else 8
            d=replace(config.data,key_features='dense',value_dim=v,generator=g)
            yield f'dense_{load}_{population}',replace(config,data=d)


def _split_roots(config):
    return {name:{'root':derive_seed(config.seed,'split_root_v1',name),
                  'status':'reserved' if name in PROTECTED else 'exploratory',
                  'episodes':[]} for name in NAMESPACES}


def _population_manifest(config,roots):
    records={}
    for namespace in NAMESPACES:
        entries=[]
        if namespace not in PROTECTED:
            # Four independently seeded histories and explicit equal regime
            # allocation. This is an inventory smoke, not a scientific sample.
            for i,regime in enumerate(REGIMES):
                g=replace(config.data.generator,namespace=namespace,regime=regime)
                c=replace(config,data=replace(config.data,generator=g))
                identity=f'episode-{i:04d}'
                e=generate_episode(c,roots[namespace]['root'],identity)
                entries.append({'episode_id':identity,'regime':regime,'status':e.metadata['status'],
                                'diagnostics':e.metadata['diagnostics'],'hashes':e.metadata['hashes']})
        records[namespace]={**roots[namespace],'episodes':entries}
    return _seal({'manifest_version':MANIFEST_VERSION,'generator_version':GENERATOR_VERSION,
                  'seed_version':SEED_VERSION,'feature_version':FEATURE_VERSION,
                  'artifact_kind':'exploratory_population_inventory','config':asdict(config),
                  'regime_weights':{r:.25 for r in REGIMES},'splits':records})


def build_split_manifest(config: RunConfig,out: Path) -> dict:
    """Create small per-population inventories; protected labels are never opened.

    ``out`` is the root JSON path. Population JSON files live beside it in
    ``<stem>.populations/``. Every file is content-sealed and write-once except
    for identical reruns. No corpus tensors or protected episode hashes saved.
    """
    # Direct construction accepts integer literals for float fields. Resolve
    # those exactly as file loading does before hashing a reloadable config.
    config=_parse(json.loads(canonical_json(asdict(config))),RunConfig,'config')
    if config.phase not in {'smoke','development'} or config.data.generator.namespace in PROTECTED:
        raise ValueError('protected manifest execution belongs to a frozen-manifest runner')
    out=Path(out)
    roots=_split_roots(config)
    payloads={}
    directory=out.parent/(out.stem+'.populations')
    for name,c in _suite_configs(config):
        payloads[name]=_population_manifest(c,roots)
    manifest=_seal({'manifest_version':MANIFEST_VERSION,'generator_version':GENERATOR_VERSION,
                    'seed_version':SEED_VERSION,'feature_version':FEATURE_VERSION,
                    'artifact_kind':'exploratory_split_reservations','config_hash':canonical_hash(asdict(config)),
                    'config':asdict(config),
                    'splits':roots,'populations':{name:{'path':str(Path(directory.name)/(name+'.json')),
                                'manifest_hash':p['manifest_hash']} for name,p in payloads.items()}})
    # Check the complete existing inventory before any mutation.
    targets=[(out,manifest)]+[(directory/(name+'.json'),p) for name,p in payloads.items()]
    for path,p in targets:
        if path.exists() and json.loads(path.read_text())!=p:
            raise ValueError(f'immutable manifest already exists with different content: {path}')
    for path,p in targets[1:]:
        _write_immutable(path,p)
    _write_immutable(out,manifest)
    return manifest


def _verify_splits(splits):
    if type(splits) is not dict or set(splits)!=set(NAMESPACES):
        raise ValueError('invalid split namespaces')
    roots=[s['root'] for s in splits.values()]
    if any(type(r) is not int or not 0<=r<2**63 for r in roots) or len(set(roots))!=len(NAMESPACES):
        raise ValueError('split roots must be disjoint signed-int64 seeds')
    for name,s in splits.items():
        if name in PROTECTED and (s['status']!='reserved' or s['episodes']!=[]):
            raise ValueError('protected namespace must remain reservation-only')
        if name not in PROTECTED and s['status']!='exploratory':
            raise ValueError('unknown exploratory split status')


def verify_split_manifest(path: Path) -> dict:
    """Validate seals, namespace reservations and regenerate exploratory hashes.

    No protected generator is called. Future confirmation acceptance must also
    bind source/dependency/weight hashes and preregistered scientific settings.
    """
    path=Path(path)
    manifest=json.loads(path.read_text())
    _check_seal(manifest)
    _verify_splits(manifest['splits'])
    if manifest['config_hash']!=canonical_hash(manifest['config']):
        raise ValueError('root config checksum mismatch')
    config=_parse(manifest['config'],RunConfig,'config')
    if manifest['splits']!=_split_roots(config):
        raise ValueError('root split reservations do not match config')
    suites=dict(_suite_configs(config))
    if set(manifest['populations'])!=set(suites):
        raise ValueError('population inventory is incomplete or unknown')
    for name,record in manifest['populations'].items():
        relative=Path(record['path'])
        if relative.is_absolute() or '..' in relative.parts:
            raise ValueError('population manifest must be a local relative path')
        payload=json.loads((path.parent/relative).read_text())
        _check_seal(payload)
        _verify_splits(payload['splits'])
        if payload['manifest_hash']!=record['manifest_hash']:
            raise ValueError('population manifest checksum mismatch')
        config=_parse(payload['config'],RunConfig,'config')
        if config!=suites[name]:
            raise ValueError('population config does not match root inventory')
        expected_roots=_split_roots(config)
        if {n:s['root'] for n,s in payload['splits'].items()}!={n:s['root'] for n,s in manifest['splits'].items()}:
            raise ValueError('population split roots mismatch')
        regenerated=_population_manifest(config,expected_roots)
        if not config_documents_equal(payload['config'], regenerated['config']):
            raise ValueError('population config differs')
        # Restore only the verified original config representation, then reseal
        # the regenerated comparison in memory. Original artifacts stay intact.
        regenerated=_seal({**{k:v for k,v in regenerated.items() if k != 'manifest_hash'},
                           'config':payload['config']})
        if payload!=regenerated:
            raise ValueError('regenerated exploratory population does not match manifest')
    return manifest
