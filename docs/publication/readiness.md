# Public release readiness — 25 October 2026

Preparation starts from `e640157b` on the existing `main` branch. The owner requested a public release, the recent-repository style/licensing convention, citation metadata and a human README using [write-like-me](https://github.com/arlegotin/write-like-me). Publication is authorized after verification.

The README presents the concrete deferred-query mechanism, usable components, both protected synthetic panels, both real transfer modes and the actual limits. Detailed commands move to REPRODUCE.md; the earlier README remains an explicitly historical document. Original software uses AGPL-3.0-only and original prose/results CC BY 4.0, matching the recent public research repositories. CITATION.cff credits Artem Legotin without inventing an ORCID, DOI or external review.

## Privacy, package and history audit

A read-only audit of the prepublication snapshot inventoried 27,171 tracked paths and scanned regular text for private keys, credential assignments and common AWS/GitHub/OpenAI/Slack/Stripe token shapes. Reachable history covered 302 commits and 25,858 objects: 14,922 text blobs were scanned; 5,053 binary blobs and 17 deliberately excluded run04-path blobs were not content-scanned. No credential pattern was found. The largest reachable Git blob was 46,357,395 bytes. This is a scoped pattern check, not a universal absence-of-secrets guarantee.

The release tar was checked for unsafe member paths, symlink members, credential filenames and known token patterns: 4,776 text members scanned, 118 binary members not content-scanned. No credential pattern was found. No raw source CSV/ZIP or excluded unfinished run04 outcome is in that bundle. Three sealed metadata files retain the owner's nonsecret local home-path fields, as disclosed in [publication scope](../PUBLICATION.md); these are preserved for their recorded hashes.

The only broad current-tree issue was 1,066 broken absolute temporary symlinks in historical task18 specimens. They are removed, with path/blob inventory in [removed-temporary-links.json](removed-temporary-links.json). No pinned executable, original source archive, regular evidence payload or canonical publication byte is altered. History is retained.

## Verification and publication boundaries

The 74-file executable map remains `5d3b8e9f028250c90da4ca5f7d23a720d4c52fc59dea97b5ad217d90fbee2b64`. The seven canonical report files, original v1/v2 migration/launcher identities and unchanged run06 bundle hash remain authoritative. License/package metadata are outside that scientific executable map.

Checks cover license-text identity, CFF/TOML parsing and package build, local README/reproduction links, source/canonical/bundle hashes, ordinary tests, and the actual public-bundle report-replay command. Results and execution receipts are appended below after verification. Visibility changes last, after the prepared main branch, release assets and metadata are in place. No forced history rewrite or scientific rerun is part of publication.

## Prepared release verification

The fresh publication review found no Critical, Important or Minor defect. [Review](review.md) and [scoped security/history audit](security-audit.md) retain coverage and limits.

- Main suite: **1,774 passed, 58 skipped, two subtests**, 256.43 s, exit 0. Separate inference: **22 passed**,0.66 s. [Raw logs and exact command/time receipts](verification/).
- Package wheel builds with valid `AGPL-3.0-only AND CC-BY-4.0` metadata and all four declared license/notice files. Standard license text hashes remain unchanged; CC text's final blank line is preserved rather than reformatted.
- All 74 pinned executable/lock files and canonical 7 outputs match their original maps. The92 local entrypoint/history links resolve; all 1,066 removed aliases match the recorded Git mode 120000 paths/blob identities.
- Actual report replay from a **fresh extraction of the exact release bundle** passed in 73.014 s, sampled peak RSS 1,048,150,016 B, no guard violation. The full scientific JSON matches canonical v1 excluding only `report_recovery`; chart data, all three SVGs and renderer receipt are byte-identical. Source before/after was clean prepared commit `c7774301`. [Witness and comparison](verification/replay-comparison.json).

The run06 archive remains exactly 285,608,419 bytes / SHA-256 `b6de6ba91c234a30bf885f5695b26244358749597bd9f043621f1a44bbd624ae`. Release assets carry the evidence notice, both full licenses, author notice and SHA256SUMS. Visibility and unauthenticated access are checked only after the release is uploaded.
