# Observed-event Beijing preparation — 16 October 2026

Chen, S. (2017). *Beijing Multi-Site Air Quality* [Dataset]. UCI Machine Learning Repository. [DOI 10.24432/C5RK5G](https://doi.org/10.24432/C5RK5G), [official catalog](https://archive.ics.uci.edu/dataset/501/beijing+multi+site+air+quality+data), [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). License provenance is the official catalog, previously verified in `2026-10-16-source-verification.md`; no license file is included in the ZIP. The archive contains the named PRSA nested ZIP plus auxiliary files; only the named PRSA CSVs supply events.

Changes: select PM2.5 scalar observations (micrograms/m³), omit NA/empty measurements without imputation, sort equal-hour stations by the fixed alphabetical 12-key registry, fit training-only affine unit normalization without clipping, build chronological 14-day histories, and compute labels with the independent raw-event oracle. Raw and normalized arrays remain local in ignored `data/derived/beijing_v1`; the source archive remains ignored in `data/raw`. No dataset or derived bulk arrays are committed.

The outer archive has 8,192,212 bytes and SHA-256 `b04da438b2f331ac0ffd45aebdfec0d20d2367feb5f6948c4b1f7ce1191e33c4`; the named inner archive hash is `d1b9261c54132f04c374f762f1e5e512af19f95c95fd6bfa1e8ac7e927e3b0b8`. Archive ingestion validates paths, duplicate members, encryption, symlinks, bounded member counts and decoded bytes before any member is opened; it streams CSVs without filesystem extraction. The raw archive cap is 32 MiB, decoded cap across both levels 128 MiB, and real config declares 128 MiB disk budget with free-capacity preflight. A missing local archive emits status `unavailable` and exit 2; preparation does not silently download or substitute data.

All 12 stations have 35,064 consecutive unique civil-hour rows. Actual totals are 420,768 rows, 8,739 missing PM2.5 values and 412,029 observed events. These are structural/missingness counts. PM values are parsed for preparation but no protected target distribution, extrema, loss, model output or performance comparison has been inspected. An independent standard-library pass checked CRCs through complete station reads, timestamps, duplicates, missing flags and split exclusions without parsing numeric PM values; its durable record is `2026-10-16-beijing-preparation-audit.json`.

Time is integer dataset-local civil hours since 2013-03-01, with no timezone inference or system-local DST conversion. Training is [2013-03-01,2014-09-01), development [2014-09-01,2015-01-01), protected test [2015-01-01,2017-03-01). Blocks anchor at each original split start, include events in[start,end), and query at T=end. Models must use temporary no-write decay from the last observed event. The event at the endpoint belongs to the next block.

| Parent split | Retained14d blocks | Included observed events | Trailing hours / observed events | Other excluded events |
|---|---:|---:|---:|---:|
| Training |39|154,350|72 /840|0|
| Development |7|27,455|240 /2,575|3,937|
| Protected test |56|221,191|144 /1,681|0|

Development fit retains four September–October blocks; calibration retains three wholly November–December blocks, beginning November 10. The anchored October27–November 10 block crosses the calibration boundary and is excluded in full. Block indices and 28/56-day cluster indices are never compressed after exclusion. Test has 28 primary clusters and 14 sensitivity clusters. Calibration's three histories and one 56-day cluster are modest; this preparation establishes no statistical power or conclusive inference.

The explicit value-blind query version is `station_mean_contrast_widths_1_6_24_72_168_v1`: for every station use mean and contrast at each width 1/6/24/72/168 hours, 120 queries per history. For widths below 168, recent ages are[1,1+w); width 168 uses[0,168). Contrast subtracts the adjacent older interval. Thus width 1 includes age 1; width 168 places age 168 in the older interval and excludes age 336. Every interval stays within the 336-hour history. The grid is shared across methods and was chosen before protected evaluation. Unsupported windows retain NaN numeric labels, false validity/support, explicit status and observation counts; no numeric target is imputed. Exporters must use the oracle's null conventions if exporting JSON labels.

`configs/manifests/beijing_v1.json` seals the source identity, attribution/schema/actual audit, typed config, grid/time/normalization conventions, split/block/cluster inventory, local artifact paths and hashes, training-only event normalization and normalized-target task statistics. Each NPZ contains times,keys,raw_values,labels_raw,labels_normalized,supported,observed_counts; loads use `allow_pickle=False`. The development iterator replays normalized labels against the independent oracle and checks checksums, with paths relative to the manifest so changing working directory is safe. A storage-metadata-only `bulk_root` was added and the seal updated after a self-review path regression; no array or label changed.

`iter_beijing_episodes(manifest,'test')` refuses before reading the manifest. A later explicitly authorized frozen runner must bind the scientific/code/dependency/data/weight inventories before enabling protected loading. Preparation and hashes are administrative safeguards, not scientific preregistration or a security boundary. Protected artifact bytes are checked for integrity during idempotent preparation without opening labels. No protected target statistics or model score exists.

Offline commands after obtaining the pinned archive:

```sh
.venv/bin/python -m famjet.prepare --config configs/beijing.yaml
.venv/bin/python -m famjet.prepare --config configs/data.yaml
```

The second command verifies existing synthetic inventories. The optional typed `data.beijing` field defaults to null; existing synthetic inventories underwent the explicit schema-only migration recorded in DECISIONS.md, preserving all roots and event/query/oracle hashes. The synthetic generator still only supports its original 16-key/eight-value numeric shape. Task 22 must add an explicitly versioned 12-key/scalar synthetic extension before calibrated shape-matched transfer. Existing 16-key/eight-value checkpoints are incompatible with this dataset. Neither transfer mode has been trained or compared here.


Review fix 1 adds preparation lifecycle recovery. A tracked sealed manifest can reconstruct ignored missing arrays: preparation stages a complete candidate, verifies every regenerated hash and the full inventory before publishing any missing file, and preserves existing valid files/manifest bytes. Corrupt existing arrays and differing config/inventory remain errors. Known unavailable records transition only after successful preparation; repeated missing-archive calls preserve their status record. If a matching sealed manifest exists without the archive, report unavailable/exit2 and retain that evidence. Publication failures roll back only files created by the attempt. This is ordinary failure recovery, not multi-file crash atomicity; protected access and all scientific data conventions remain unchanged.
