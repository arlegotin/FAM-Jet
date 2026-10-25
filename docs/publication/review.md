# Public release review — 2026-10-25

Reviewed base `e640157b58bf6b55741d77368c47e4cb3a1a9e5e` through prepared HEAD `c77743012fbe25e8fcae6a482b17991d91f3d6ca`. This is a fresh publication review, not another review of the prior scientific implementation. The adopted public-release spec, plan and three rulings in `.superpowers/sdd/2026-10-25-public-release/progress.md` define the scope.

## Verdict

**Ready to publish, subject to the release owner's pending runtime checks and actual GitHub verification.** No Critical, Important or Minor publication defect found in this candidate. No requested correction to source, frozen evidence, licensing scope or README claims.

Before visibility changes, the owner must finish the already planned broad/inference checks, execute the documented copied-bundle replay, append its actual verification receipts, and verify the pushed branch and uploaded evidence/license/checksum assets. Public visibility and unauthenticated repository/asset access must then be checked. Pending release URLs are expected at this review stage and are not broken-link findings.

## Findings

| Severity | Finding | Required fix |
| --- | --- | --- |
| Critical | None | None |
| Important | None | None |
| Minor | None | None |

`git diff --check` reports one new blank line at `licenses/CC-BY-4.0.txt:396`. This is an intentional consequence of preserving the exact adopted upstream license text, whose hash matches the documented source. It is not a publication defect; do not normalize the text merely to silence that check.

## Assessment

The README explains the research question before the machinery and makes the reusable implementation and controlled comparison concrete. Both inconclusive synthetic panels, the stronger bucket averages, poor frozen transfer against simple controls, and the real-trained bank win remain visible. Exact moments are presented as a known repeated-pole/gamma mechanism, with architectural novelty, learned addressing, all-family superiority and agent-memory claims explicitly excluded. This is a strong presentation of a limited result rather than an inflated success claim.

The public tables and paired intervals match the canonical human report and selected machine fields: 3,072 histories in each panel; effects +0.0353537664622 and +0.0396830788643, both intervals crossing zero; synthetic Jet/Bank/bucket means correctly rounded; frozen sensor RMSE 130.49/1069.5; real-trained RMSE 68.64/21.36. The conditional-fit inference and finite 56-block sensor scope are stated. The original failed report assembly and separate audited recovery are accurately distinguished.

AGPL-3.0-only original software and CC BY 4.0 original writing/results have explicit, consistent scopes. The historical original source grant is explicit; external rights remain separate. Notices identify UCI attribution and transformations, equation-based implementations, the NVIDIA noncommercial-source boundary and unlicensed external Time-Local source. Citation metadata identifies Artem Legotin without invented identifiers or a general performance claim. The package license expression and accompanying explanation are coherent. Full license hashes match the adopted owner-repository copies.

The reproduction guide separates a small mechanism check, broad tests, isolated inference, opt-in full-archive admission, report-only replay and fresh study execution. It identifies the exact recorded interpreter/platform, uses the reporting environment explicitly and explains historical test counts. The download name, archive hash, extraction destination, sibling `run`/`prep` layout, archived-source path and recovery compatibility ID agree with the archive and loader. The guide does not imply that reusing registered seeds creates a new independent confirmation.

Historical development prose is clearly marked and moved out of onboarding. Publication scope discloses retained owner-local provenance, preserved Git history and incomplete binary/privacy scan coverage. Removing broken temporary aliases improves portability without changing scientific payloads. `.gitattributes` changes presentation and binary treatment only; it does not exclude the evidence from distribution.

## Direct checks and coverage

- Read the complete public README, reproduction guide, licensing/third-party notices, CFF, package metadata, contribution guide, notice, publication/readiness documents, attributes and archived prepublication README. Read the adopted spec/plan and publication ledger. Compared relevant claims with the canonical human report and bounded selections from its 45-MB JSON.
- Independently hashed all 74 current pinned source/lock files against `new_files` in `e2e-run06-report-safety-migration.json`; all match. No changed path intersects that map. Independently hashed all seven canonical files against `e2e-report-recovery-actual/index.json`; all match.
- Programmatically compared the deletion set with all 1,066 inventory entries. Every removal is an original Git-mode `120000` symlink under `docs/research/task18-*`, with matching original blob identity and no current file/link remaining. There are no extra deletions.
- Parsed CFF and TOML and verified the shared `0.1.0` version. Checked 92 local Markdown targets across public entry points and archived README; none is missing. Verified both full license SHA-256 identities.
- Independently verified the unchanged bundle's 285,608,419 bytes and SHA-256 `b6de6ba91c234a30bf885f5695b26244358749597bd9f043621f1a44bbd624ae`. Inspected its 5,888 member names/types: the documented run/prep/source paths exist, with no absolute/traversal paths or symbolic/hard links.
- Reviewed the existing read-only security audit and its stated exclusions. Did not rerun its full credential/history content scan, claim universal privacy clearance, or extend the license review into a legal opinion.

The approximately 1.24-MB change package was reviewed in bounded passes: human entry points in full, repetitive removed-link inventory programmatically, stock licenses by exact identity. This review does not pretend that every repetitive raw diff line was manually read. It does not re-review the preceding scientific implementation, recalibrate inference, run fresh experiments, inspect excluded run04 private outcomes, scan binary payload contents, run heavy suites or verify yet-unpublished GitHub state. The release owner retains the runtime, package-build and publication execution seats. This reviewer changed only this review artifact.
