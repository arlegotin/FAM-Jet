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
