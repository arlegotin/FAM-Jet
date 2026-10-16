"""Small offline fixtures; expectations are hand-derived civil-hour arithmetic."""
import csv
from dataclasses import replace
from datetime import datetime
import io
import json
from pathlib import Path
import zipfile

import numpy as np
import pytest

FIXTURE = Path(__file__).parent / 'fixtures/beijing_small.csv'


def archive_fixture(tmp_path, rows=None):
    rows = list(csv.DictReader(FIXTURE.open())) if rows is None else rows
    path = tmp_path / 'sample.zip'
    inner = io.BytesIO()
    with zipfile.ZipFile(inner, 'w') as z:
        for station in sorted({r['station'] for r in rows}):
            text = io.StringIO()
            writer = csv.DictWriter(text, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(r for r in rows if r['station'] == station)
            z.writestr(f'PRSA_Data_20130301-20170228/PRSA_Data_{station}_20130301-20170228.csv', text.getvalue())
    with zipfile.ZipFile(path, 'w') as z:
        z.writestr('PRSA2017_Data_20130301-20170228.zip', inner.getvalue())
    return path


def test_observed_pm25_only(tmp_path):
    from famjet.data.beijing import load_observations
    data, audit = load_observations(archive_fixture(tmp_path), 1 << 20)
    assert data['times'].tolist()[:3] == [0, 2, 2]
    assert data['values'].tolist()[:3] == [10, 20, 30]
    assert audit['rows'] == 5 and audit['missing_pm25'] == 1


def test_split_boundary_drops_crossing_history():
    from famjet.data.beijing import block_inventory
    m = block_inventory()
    assert m['training']['start'] == '2013-03-01'
    assert m['training']['end'] == m['development_fit']['start'] == '2014-09-01'
    assert m['development_fit']['end'] == m['development_calibration']['start'] == '2014-11-01'
    assert m['development_calibration']['end'] == m['test']['start'] == '2015-01-01'
    assert m['test']['end'] == '2017-03-01'
    assert [len(m[s]['blocks']) for s in m] == [39, 4, 3, 56]
    # Anchored September1 blocks: Oct27-Nov10 crosses calibration boundary.
    assert m['development_fit']['boundary_excluded_hours'] == 14 * 24
    assert m['development_calibration']['blocks'][0]['start'] == '2014-11-10'
    assert m['training']['trailing_hours'] == 72
    assert m['test']['trailing_hours'] == 144


def test_nonoverlap_blocks_all_stations_together(tmp_path):
    from famjet.data.beijing import load_observations, block_inventory, make_episode
    data, _ = load_observations(archive_fixture(tmp_path), 1 << 20)
    block = block_inventory()['training']['blocks'][0]
    ep = make_episode(data, block, {'mean': 0., 'scale': 1.}, normalized=False)
    assert ep.events.key_ids.tolist() == [[0, 0, 1]]
    assert ep.queries.T.unique().tolist() == [336]
    assert ep.events.timestamps.max() < ep.queries.T.min()
    blocks = block_inventory()['test']['blocks']
    assert all(a['end'] == b['start'] for a,b in zip(blocks, blocks[1:]))
    assert [b['cluster_28d'] for b in blocks[:4]] == ['test:28d:0000']*2 + ['test:28d:0001']*2
    assert len({b['cluster_56d'] for b in blocks[:4]}) == 1
    assert ep.events.time_unit == 'dataset_local_civil_hour_since_2013-03-01'


def test_train_scaling_preserves_test_extreme(tmp_path):
    from famjet.data.beijing import load_observations, fit_normalization
    data, _ = load_observations(archive_fixture(tmp_path), 1 << 20)
    scale = fit_normalization(data)
    assert scale['count'] == 3 and scale['mean'] == 20
    assert scale['scale'] == pytest.approx(np.sqrt(200/3))
    assert (data['values'][-1] - scale['mean']) / scale['scale'] > 1000


def test_tied_station_events_stable(tmp_path):
    from famjet.data.beijing import load_observations
    rows = list(csv.DictReader(FIXTURE.open()))
    first, _ = load_observations(archive_fixture(tmp_path, rows), 1 << 20)
    second, _ = load_observations(archive_fixture(tmp_path, rows[::-1]), 1 << 20)
    for name in first:
        np.testing.assert_array_equal(first[name], second[name])


@pytest.mark.parametrize('member', ['../evil.csv', '/evil.csv', 'C:/evil.csv', 'foo\\evil.csv'])
def test_archive_path_traversal_rejected(tmp_path, member):
    from famjet.data.beijing import load_observations
    path = tmp_path / 'bad.zip'
    with zipfile.ZipFile(path, 'w') as z:
        z.writestr(member, 'evil')
    with pytest.raises(ValueError, match='unsafe'):
        load_observations(path, 1 << 20)
    assert not (tmp_path.parent/'evil.csv').exists()


def test_oracle_raw_and_normalized_labels_and_block_end(tmp_path):
    from famjet.data.beijing import load_observations, block_inventory, make_episode
    rows = list(csv.DictReader(FIXTURE.open()))[:1]
    for hour, value in [(22, '30'), (23, '50')]:
        r = dict(rows[0], day='14', hour=str(hour), **{'PM2.5': value})
        rows.append(r)
    # Mar15 00 belongs to next block and must not affect first labels.
    rows.append(dict(rows[0], day='15', hour='0', **{'PM2.5': '9999'}))
    data, _ = load_observations(archive_fixture(tmp_path, rows), 1 << 20)
    block = block_inventory()['training']['blocks'][0]
    raw = make_episode(data, block, {'mean': 20., 'scale': 10.}, normalized=False)
    norm = make_episode(data, block, {'mean': 20., 'scale': 10.}, normalized=True)
    assert raw.labels[0,0,0].item() == 50  # width1 includes age1
    assert norm.labels[0,0,0].item() == 3
    assert raw.labels[0,1,0].item() == 20  # recent50 - older30
    assert norm.labels[0,1,0].item() == 2  # contrast does not subtract center
    assert raw.metadata['observed_counts'][0][0] == [[1], [1]]
    assert raw.metadata['last_event_to_query_hours'] == 1


def test_iterator_rejects_protected_before_opening(tmp_path):
    from famjet.data.beijing import iter_beijing_episodes
    with pytest.raises(ValueError, match='protected'):
        list(iter_beijing_episodes(tmp_path/'does-not-exist.json', 'test'))


def test_prepare_cli_missing_asset_records_unavailable(tmp_path):
    from famjet.prepare import main
    out = tmp_path/'unavailable.json'
    assert main(['--config','configs/data.yaml','--dataset','beijing','--archive',str(tmp_path/'missing.zip'),
                 '--out',str(out)]) == 2
    assert json.loads(out.read_text())['status'] == 'unavailable'


def test_week_query_half_open_ages_1_168_336(tmp_path):
    from famjet.data.beijing import load_observations, block_inventory, make_episode
    template = list(csv.DictReader(FIXTURE.open()))[0]
    rows = [dict(template, day=d, hour=h, **{'PM2.5':v})
            for d,h,v in [('1','0','9999'), ('8','0','30'), ('14','23','50')]]
    data,_ = load_observations(archive_fixture(tmp_path,rows), 1 << 20)
    ep = make_episode(data,block_inventory()['training']['blocks'][0],{'mean':0.,'scale':1.},normalized=False)
    assert ep.labels[0,8,0].item() == 50  # age1 in recent[0,168)
    assert ep.labels[0,9,0].item() == 20  # age168 in older[168,336); age336 excluded
    assert ep.metadata['observed_counts'][0][9] == [[1], [1]]
    assert not ep.metadata['target_valid'][0][10]  # absent Changping remains invalid
    assert ep.metadata['status'] == 'contains_unsupported_queries'


def test_archive_duplicate_station_hour_and_nested_traversal_rejected(tmp_path):
    from famjet.data.beijing import load_observations
    rows = list(csv.DictReader(FIXTURE.open()))[:1]
    with pytest.raises(ValueError,match='duplicate'):
        load_observations(archive_fixture(tmp_path,rows*2),1 << 20)
    inner = io.BytesIO()
    with zipfile.ZipFile(inner,'w') as z:
        z.writestr('../evil.csv','evil')
    path = tmp_path/'nested.zip'
    with zipfile.ZipFile(path,'w') as z:
        z.writestr('PRSA2017_Data_20130301-20170228.zip',inner.getvalue())
    with pytest.raises(ValueError,match='unsafe'):
        load_observations(path,1 << 20)


def test_archive_decoded_budget_enforced(tmp_path):
    from famjet.data.beijing import load_observations
    with pytest.raises(ValueError,match='budget'):
        load_observations(archive_fixture(tmp_path),1)


def test_iterator_uses_sealed_local_labels_and_rejects_tamper(tmp_path):
    from famjet.data.beijing import (load_observations,block_inventory,make_episode,
                                      iter_beijing_episodes,VERSION,QUERY_GRID)
    from famjet.provenance import canonical_hash
    import hashlib
    data,_ = load_observations(archive_fixture(tmp_path),1 << 20)
    block = block_inventory()['training']['blocks'][0]
    normalization = {'mean':20.,'scale':10.}
    ep = make_episode(data,block,normalization,normalized=True)
    path = tmp_path/'block.npz'
    np.savez_compressed(path,times=data['times'],keys=data['keys'],raw_values=data['values'],labels_normalized=ep.labels.numpy())
    block.update(artifact='block.npz',sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    payload = {'preparation_version':VERSION,'query_grid_version':QUERY_GRID,'normalization':normalization,
               'bulk_root':'.','config':{'data':{'beijing':{'derived_path':str(tmp_path)}}},'splits':{'training':{'blocks':[block]}}}
    payload['manifest_hash'] = canonical_hash(payload)
    manifest = tmp_path/'manifest.json';manifest.write_text(json.dumps(payload))
    loaded = list(iter_beijing_episodes(manifest,'training'))
    assert len(loaded) == 1 and loaded[0].events.values.tolist() == [[[-1.],[0.],[1.]]]
    path.write_bytes(b'corrupted')
    with pytest.raises(ValueError,match='modified'):
        list(iter_beijing_episodes(manifest,'training'))


def test_prepare_rejects_wrong_history_length_before_archive_access(tmp_path):
    from famjet.data.beijing import prepare_beijing
    from famjet.config import load_config
    c = load_config(Path('configs/beijing.yaml'))
    c = replace(c,data=replace(c.data,length=335))
    with pytest.raises(ValueError,match='336'):
        prepare_beijing(tmp_path/'missing.zip',tmp_path/'out.json',c)


def test_iterator_manifest_relative_paths_survive_working_directory_change(tmp_path,monkeypatch):
    from famjet.data.beijing import iter_beijing_episodes,VERSION,QUERY_GRID
    from famjet.provenance import canonical_hash
    import hashlib
    root=tmp_path/'project';bulk=root/'data/derived/beijing';bulk.mkdir(parents=True)
    manifest_dir=root/'configs/manifests';manifest_dir.mkdir(parents=True)
    path=bulk/'block.npz'
    labels=np.full((1,120,1),np.nan)
    np.savez_compressed(path,times=np.array([],dtype=np.int64),keys=np.array([],dtype=np.int64),
                        raw_values=np.array([],dtype=np.float64),labels_normalized=labels)
    block={'history_id':'training:0000','split':'training','start_tick':0,'end_tick':336,
           'artifact':'../../data/derived/beijing/block.npz','sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
    payload={'preparation_version':VERSION,'query_grid_version':QUERY_GRID,'normalization':{'mean':0.,'scale':1.},
             'bulk_root':'../../data/derived/beijing','config':{'data':{'beijing':{'derived_path':'data/derived/beijing'}}},
             'splits':{'training':{'blocks':[block]}}}
    payload['manifest_hash']=canonical_hash(payload)
    manifest=manifest_dir/'test.json';manifest.write_text(json.dumps(payload))
    monkeypatch.chdir(tmp_path)
    assert len(list(iter_beijing_episodes(manifest,'training'))) == 1


@pytest.fixture
def preparation_fixture(tmp_path, monkeypatch):
    """Stub only official-source verification; exercise real preparation/publishing.

    The tiny CSV cannot satisfy official full-grid counts or pinned bytes. Source
    identity/audit are isolated here; arrays, oracle, seals and filesystem I/O are real.
    """
    import copy
    import famjet.data.beijing as beijing
    from famjet.config import load_config
    archive = archive_fixture(tmp_path)
    data,audit = beijing.load_observations(archive,1 << 20)
    with archive.open('ab') as stream:
        stream.truncate(8192212)
    original_sha = beijing._sha
    monkeypatch.setattr(beijing,'_sha',lambda path: beijing.ARCHIVE_SHA256 if Path(path)==archive else original_sha(path))
    audit.update(inner_sha256=beijing.INNER_SHA256,rows=420768,missing_pm25=8739,observed=412029)
    audit['stations']={s:{'rows':35064,'first_tick':0,'last_tick':35063,'backward_steps':0,'nonhourly_steps':0} for s in beijing.STATIONS}
    monkeypatch.setattr(beijing,'load_observations',lambda *args:(data,copy.deepcopy(audit)))
    inventory=beijing.block_inventory()
    inventory['training']['blocks']=inventory['training']['blocks'][:2]
    for name in ['development_fit','development_calibration','test']:
        inventory[name]['blocks']=[]
    monkeypatch.setattr(beijing,'block_inventory',lambda:copy.deepcopy(inventory))
    c=load_config(Path('configs/beijing.yaml'))
    c=replace(c,data=replace(c.data,beijing=replace(c.data.beijing,archive_path=str(archive),derived_path=str(tmp_path/'bulk'))))
    out=tmp_path/'manifest.json'
    return beijing,archive,out,c


def test_preparation_recovers_missing_derived_without_replacing_good_files(preparation_fixture):
    beijing,archive,out,c=preparation_fixture
    expected=beijing.prepare_beijing(archive,out,c)
    blocks=expected['splits']['training']['blocks']
    paths=[out.parent/b['artifact'] for b in blocks]
    manifest_bytes=out.read_bytes();good_bytes=paths[1].read_bytes();good_inode=paths[1].stat().st_ino
    missing_bytes=paths[0].read_bytes();paths[0].unlink()
    assert beijing.prepare_beijing(archive,out,c)==expected
    assert paths[0].read_bytes()==missing_bytes
    assert paths[1].read_bytes()==good_bytes and paths[1].stat().st_ino==good_inode
    assert out.read_bytes()==manifest_bytes


def test_preparation_unavailable_to_available_transition(preparation_fixture):
    beijing,archive,out,c=preparation_fixture
    from famjet.prepare import main
    from famjet.config import save_resolved_config
    config_path=out.parent/'config.json';save_resolved_config(config_path,c)
    saved=archive.read_bytes();archive.unlink()
    assert main(['--config',str(config_path),'--out',str(out)])==2
    assert json.loads(out.read_text())['status']=='unavailable'
    archive.write_bytes(saved)
    assert main(['--config',str(config_path),'--out',str(out)])==0
    manifest=json.loads(out.read_text())
    assert manifest['status']=='prepared'
    assert all((out.parent/b['artifact']).is_file() for b in manifest['splits']['training']['blocks'])


def test_recovery_rejects_corrupt_existing_array_before_publication(preparation_fixture):
    beijing,archive,out,c=preparation_fixture
    expected=beijing.prepare_beijing(archive,out,c)
    paths=[out.parent/b['artifact'] for b in expected['splits']['training']['blocks']]
    paths[0].unlink();paths[1].write_bytes(b'corrupted')
    original=out.read_bytes()
    with pytest.raises(ValueError,match='checksum'):
        beijing.prepare_beijing(archive,out,c)
    assert not paths[0].exists() and paths[1].read_bytes()==b'corrupted' and out.read_bytes()==original


def test_recovery_validates_complete_inventory_before_any_publication(preparation_fixture):
    beijing,archive,out,c=preparation_fixture
    from famjet.provenance import canonical_hash
    expected=beijing.prepare_beijing(archive,out,c)
    for b in expected['splits']['training']['blocks']:
        (out.parent/b['artifact']).unlink()
    # A valid seal alone cannot authorize a different regenerated inventory.
    expected['splits']['training']['blocks'][1]['sha256']='0'*64
    expected['manifest_hash']=canonical_hash({k:v for k,v in expected.items() if k!='manifest_hash'})
    out.write_text(json.dumps(expected));original=out.read_bytes()
    with pytest.raises(ValueError,match='(differs|checksum|inventory)'):
        beijing.prepare_beijing(archive,out,c)
    assert out.read_bytes()==original
    assert not list(Path(c.data.beijing.derived_path).iterdir())


def test_unavailable_output_preserved_if_final_publication_fails(preparation_fixture,monkeypatch):
    beijing,archive,out,c=preparation_fixture
    previous={'schema_version':1,'dataset':'beijing','status':'unavailable','reason':'local_archive_missing',
              'archive':str(archive),'real_transfer':'untested','substitution':False}
    out.write_text(json.dumps(previous));original=out.read_bytes()
    def fail(*args):
        raise OSError('publication failed')
    monkeypatch.setattr(beijing,'atomic_json',fail)
    with pytest.raises(OSError,match='publication failed'):
        beijing.prepare_beijing(archive,out,c)
    assert out.read_bytes()==original
    assert not list(Path(c.data.beijing.derived_path).iterdir())


def test_recovery_rejects_different_config_before_publication(preparation_fixture):
    beijing,archive,out,c=preparation_fixture
    expected=beijing.prepare_beijing(archive,out,c)
    path=out.parent/expected['splits']['training']['blocks'][0]['artifact'];path.unlink()
    original=out.read_bytes()
    with pytest.raises(ValueError,match='differs'):
        beijing.prepare_beijing(archive,out,replace(c,seed=c.seed+1))
    assert not path.exists() and out.read_bytes()==original


def test_partial_array_publication_failure_rolls_back_new_files(preparation_fixture,monkeypatch):
    beijing,archive,out,c=preparation_fixture
    previous={'schema_version':1,'dataset':'beijing','status':'unavailable','reason':'local_archive_missing',
              'archive':str(archive),'real_transfer':'untested','substitution':False}
    out.write_text(json.dumps(previous));original=out.read_bytes()
    real_link=beijing.os.link
    def fail_second(source,destination):
        if destination.name=='training-0001.npz':
            raise OSError('array publication failed')
        real_link(source,destination)
    monkeypatch.setattr(beijing.os,'link',fail_second)
    with pytest.raises(OSError,match='array publication failed'):
        beijing.prepare_beijing(archive,out,c)
    assert out.read_bytes()==original
    assert not list(Path(c.data.beijing.derived_path).iterdir())


def test_unavailable_state_must_be_an_explicit_known_record(preparation_fixture):
    beijing,archive,out,c=preparation_fixture
    out.write_text(json.dumps({'status':'unavailable','other':'conflicting output'}));original=out.read_bytes()
    with pytest.raises(ValueError,match='unavailable'):
        beijing.prepare_beijing(archive,out,c)
    assert out.read_bytes()==original
    assert not Path(c.data.beijing.derived_path).exists()


def test_preparation_rejects_conflicting_unsealed_array(preparation_fixture):
    beijing,archive,out,c=preparation_fixture
    bulk=Path(c.data.beijing.derived_path);bulk.mkdir()
    old=bulk/'training-0000.npz';old.write_bytes(b'previous data')
    with pytest.raises(ValueError,match='checksum'):
        beijing.prepare_beijing(archive,out,c)
    assert old.read_bytes()==b'previous data' and not out.exists()
    assert list(bulk.iterdir())==[old]


def test_repeated_missing_archive_preserves_unavailable_status(tmp_path):
    from famjet.prepare import main
    out=tmp_path/'unavailable.json'
    args=['--config','configs/beijing.yaml','--archive',str(tmp_path/'missing.zip'),'--out',str(out)]
    assert main(args)==2
    original=out.read_bytes()
    assert main(args)==2 and out.read_bytes()==original


def test_missing_archive_preserves_matching_prepared_manifest(preparation_fixture):
    beijing,archive,out,c=preparation_fixture
    from famjet.prepare import main
    from famjet.config import save_resolved_config
    beijing.prepare_beijing(archive,out,c)
    previous=out.read_bytes();archive.unlink()
    config_path=out.parent/'config.json';save_resolved_config(config_path,c)
    assert main(['--config',str(config_path),'--out',str(out)])==2
    assert out.read_bytes()==previous
    # A different config cannot claim this existing preparation status.
    save_resolved_config(config_path,replace(c,seed=c.seed+1))
    with pytest.raises(ValueError,match='(differs|replace)'):
        main(['--config',str(config_path),'--out',str(out)])
    assert out.read_bytes()==previous
