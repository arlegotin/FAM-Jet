Promoted to durable research evidence for Task7 on 16 October 2026. The text below records the earlier reconnaissance; current preparation and its independent count audit are documented in `2026-10-16-beijing-preparation.md` and `2026-10-16-beijing-preparation-audit.json`.

# Beijing UCI501 asset inspection — 16 October 2026

This is bounded asset reconnaissance for future Task 7, not the dataset preparer or an evaluation. Only ZIP structure, schema, station/date coverage, missing-PM flags and duplicate station-hours were inspected. No PM2.5 numbers were parsed into numeric targets; no target means, extrema, protected queries, labels, tuning or training were computed. No archive member was extracted to the filesystem.

## Scope, storage and bounds

Fresh `df -k .` preflight reported 44,684,260 KiB available (~42.6 GiB), exceeding the required 1 GiB minimum. Immediately before downloading, Python disk usage independently reported 45,749,125,120 free bytes. Total transfer cap was 33,554,432 bytes (32 MiB); total declared uncompressed member cap across both archive levels was 134,217,728 bytes (128 MiB).

`data/raw/` did not exist and was not ignored. The coordinating agent explicitly authorized the alternative `.superpowers/sdd/2026-10-16-famjet/raw-assets/` to avoid changing shared files. `git check-ignore -v` confirmed its archive path is covered by `.superpowers/sdd/.gitignore:1:*`. The raw archive remains in that ignored location; Task 7 must establish durable `data/raw/` ignore handling before copying/moving it. No `.gitignore`, shared config, product code or ledger was changed by this task.

Download streamed into a task-owned `.part` file created exclusively in the destination directory. The downloader enforced the byte cap while reading, flushed/fsynced the completed file, and published it with a non-overwriting atomic hard link before removing its own temporary name. It refused an existing destination. No unfinished `.part` file remains.

## Provenance and bytes

[Official UCI dataset page](https://archive.ics.uci.edu/dataset/501/beijing+multi+site+air+quality+data), checked again during this task, identifies [DOI 10.24432/C5RK5G](https://doi.org/10.24432/C5RK5G) and CC BY 4.0. Retain attribution: Chen, S. (2017). *Beijing Multi-Site Air Quality* [Dataset]. UCI Machine Learning Repository. License: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Future preparation should identify changes such as selecting PM2.5, omitting missing observations and constructing causal split histories. License provenance is the UCI page; the archive itself contains no license file.

Requested and final URL were identical: [UCI501 outer ZIP](https://archive.ics.uci.edu/static/public/501/beijing%2Bmulti%2Bsite%2Bair%2Bquality%2Bdata.zip). A HEAD request returned HTTP 200 without Content-Length, Content-Type, Last-Modified or ETag; safety therefore relied on the streaming byte cap rather than a declared response size. Read-only network escalation succeeded; no approval rejection occurred.

Download completed at `2026-10-16T18:24:36.795032+00:00` (UTC).

| Asset | Actual bytes | SHA-256 |
|---|---:|---|
| Outer ZIP, persisted | 8,192,212 | `b04da438b2f331ac0ffd45aebdfec0d20d2367feb5f6948c4b1f7ce1191e33c4` |
| Nested `PRSA2017_Data_20130301-20170228.zip`, read in memory only | 7,959,991 | `d1b9261c54132f04c374f762f1e5e512af19f95c95fd6bfa1e8ac7e927e3b0b8` |

Persisted absolute path:

`/Users/artemlegotin/Documents/git_alter/FAM-Jet/.superpowers/sdd/2026-10-16-famjet/raw-assets/beijing-uci501.zip`

The inner PRSA ZIP is **not** a separate on-disk file. The outer archive is the correct starting point for later independent validation.

## Archive members and safety inspection

Both levels were inspected using Python's standard-library `zipfile`, with no extraction. Checked: no absolute paths, `..` components, backslashes, duplicate member names, symlinks or encrypted members. All declared uncompressed sizes were summed before opening station CSVs. These reads are reconnaissance checks, not a replacement for Task 7's independently implemented extraction/ingestion contract.

Outer ZIP has four files and no directory entries:

| Member | Uncompressed bytes | Compressed bytes | CRC32 in ZIP directory |
|---|---:|---:|---|
| `PRSA2017_Data_20130301-20170228.zip` | 7,959,991 | 7,959,991 | `c04e6fa0` |
| `2A2478DC-8517-4490-9FA7-36F9A7A542BE.JPG` | 158,758 | 158,758 | `155ae782` |
| `data.csv` | 37,769 | 37,769 | `a2b54626` |
| `test.csv` | 35,186 | 35,186 | `653d3b40` |

Only the PRSA member was opened. The auxiliary JPG/CSV contents were not inspected and must not substitute for the named PRSA dataset. The PRSA member was read fully, which invokes ZIP CRC validation; the three unopened auxiliary members' CRC fields were recorded but not independently checked by decompression.

The inner ZIP has one directory entry `PRSA_Data_20130301-20170228/` (zero bytes), followed by these 12 files under that directory. Each full filename is `PRSA_Data_<station>_20130301-20170228.csv`:

| Station / filename component | Uncompressed bytes | Compressed bytes | CRC32 |
|---|---:|---:|---|
| Aotizhongxin | 2,835,916 | 667,607 | `db1ab141` |
| Changping | 2,722,295 | 664,348 | `66ae8094` |
| Dingling | 2,675,856 | 645,648 | `f28b3500` |
| Dongsi | 2,636,684 | 665,800 | `262b3874` |
| Guanyuan | 2,695,860 | 664,651 | `eb2cf87d` |
| Gucheng | 2,654,625 | 663,049 | `5c47126d` |
| Huairou | 2,641,027 | 650,073 | `5e47b60e` |
| Nongzhanguan | 2,839,705 | 673,973 | `c524a6f8` |
| Shunyi | 2,620,654 | 656,007 | `1bcf8faa` |
| Tiantan | 2,655,061 | 662,583 | `ca99fa73` |
| Wanliu | 2,659,544 | 670,845 | `c0a0e56d` |
| Wanshouxigong | 2,871,076 | 672,231 | `e95d454b` |

All station files were streamed completely through CSV readers, with ZIP CRC checks. Declared uncompressed sizes: outer members total 8,191,704 bytes, inner members total 32,508,303 bytes, both archive levels combined **40,700,007 bytes**, below 128 MiB. Counting both levels includes the inner ZIP bytes as well as its decoded CSV bytes. No other nested archives were present.

## Schema and structural counts

All 12 station files share this exact ordered 18-column header:

```text
No,year,month,day,hour,PM2.5,PM10,SO2,NO2,CO,O3,TEMP,PRES,DEWP,RAIN,wd,WSPM,station
```

Rows were checked for field-count consistency through `csv.DictReader` with UTF-8-sig decoding; no malformed rows were found. Only year/month/day/hour and station were interpreted, plus testing the PM2.5 string against missing markers `NA`/empty string. Nonmissing PM2.5 strings were not converted to numbers or summarized. This is not validation of numeric finiteness or value-domain constraints; the future preparer must independently perform those checks under its split/protection contract.

Every station has **35,064 rows and 35,064 unique station-hours**, spanning `2013-03-01 00:00:00` through `2017-02-28 23:00:00` inclusive. Every adjacent row advances exactly one civil hour. All stations have zero duplicate station-hours, zero backward timestamp steps and zero nonhourly steps. Each station occurs in exactly one CSV, and each CSV contains one station. Consequently the raw hourly grid is complete even where PM2.5 is missing; missing PM2.5 must not be treated as an absent elapsed hour or a zero write.

| Station | Rows | Missing PM2.5 rows | Observed PM2.5 rows |
|---|---:|---:|---:|
| Aotizhongxin | 35,064 | 925 | 34,139 |
| Changping | 35,064 | 774 | 34,290 |
| Dingling | 35,064 | 779 | 34,285 |
| Dongsi | 35,064 | 750 | 34,314 |
| Guanyuan | 35,064 | 616 | 34,448 |
| Gucheng | 35,064 | 646 | 34,418 |
| Huairou | 35,064 | 953 | 34,111 |
| Nongzhanguan | 35,064 | 628 | 34,436 |
| Shunyi | 35,064 | 913 | 34,151 |
| Tiantan | 35,064 | 677 | 34,387 |
| Wanliu | 35,064 | 382 | 34,682 |
| Wanshouxigong | 35,064 | 696 | 34,368 |
| **Total** | **420,768** | **8,739** | **412,029** |

The observed total matches UCI's reported record count. Counts here cover the full asset and describe structure/missingness only; no protected target distribution was inspected. No split-specific target summaries were computed.

## Time convention and follow-up boundary

CSV timestamps have year/month/day/hour fields without timezone offsets. This inspection used naive civil-hour datetime values solely for order/coverage checks. Preserve the specification's dataset-local civil-hour convention: subtract civil-hour timestamps or use integer hour ticks from a documented civil epoch, without system-local timezone conversion or DST shifts. The UCI metadata does not establish an explicit timezone; this task does not invent one.

Task 7 still needs to independently validate checksum/schema/path bounds, establish durable ignored raw storage, implement timestamp/missingness contracts, prepare prescribed chronological splits and manifests, and enforce training-only normalization/protected-data access. No raw dataset substitution is needed based on this reconnaissance. No actual stream means/contrasts or evaluation result exists yet.

## Verification commands

Executed verification used standard-library `urllib.request`, `hashlib`, `zipfile`, `csv`, and `datetime`. Download and inspection were separate operations; no dependencies were installed. A minimal safe independent identity check is:

```sh
git check-ignore -v .superpowers/sdd/2026-10-16-famjet/raw-assets/beijing-uci501.zip
shasum -a 256 .superpowers/sdd/2026-10-16-famjet/raw-assets/beijing-uci501.zip
```

Read nested metadata without extraction:

```sh
python3 - <<'PY'
import hashlib, io, zipfile
path = '.superpowers/sdd/2026-10-16-famjet/raw-assets/beijing-uci501.zip'
with zipfile.ZipFile(path) as outer:
    payload = outer.read('PRSA2017_Data_20130301-20170228.zip')
    print(len(payload), hashlib.sha256(payload).hexdigest())
    with zipfile.ZipFile(io.BytesIO(payload)) as inner:
        print([(item.filename, item.file_size) for item in inner.infolist()])
PY
```

This small identity command assumes the verified asset; a general-purpose preparer must first enforce its own declared member/path/size bounds.
