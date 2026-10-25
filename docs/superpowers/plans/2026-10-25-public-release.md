# FAM-Jet public release implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans for native implementation; delegate independent read-only review where useful.

**Goal:** Publish a human-readable, licensed, citable and reproducible research repository without changing its scientific evidence.

**Architecture:** Documentation and publication metadata change around the existing frozen program. A read-only audit checks history/assets independently of the README rewrite. Publish the complete evidence through a GitHub release rather than regular Git.

**Tech stack:** Existing Python environment, Git, gh CLI, CFF/TOML/YAML, Markdown.

**Spec:** docs/superpowers/specs/2026-10-25-public-release-design.md.

## Global constraints

- Work on current main; preserve pinned74 source/lock bytes, canonical7 outputs and original sealed bundle.
- No result inflation, unregistered superiority, invented citation identifiers or relicensing upstream material.
- Use write-like-me only for reader-facing README prose; technical commands and evidence stay exact.
- Repo visibility changes after source, release assets, attribution and verification are ready.

## Review focus

- A reader can find the mechanism, reusable parts, full outcome and limitations without reading execution history.
- A clean reader gets exact supported-environment instructions and available evidence, not hidden local dependencies.
- No credentials are intentionally published; scoped scan limits and owner-path metadata are disclosed.
- License scopes distinguish original software/writing and UCI/upstream rights.
- GitHub public state, default branch, citation, license recognition and evidence asset are verified after publication.

## Tasks

- [x] Audit current/history/source assets and read recent public-repo conventions and exact writing skill.
- [x] Rewrite README, archive old README with working links, add reproduction/publication guides and licensing/citation/package metadata; remove broken temporary aliases with inventory. Validate and commit.
- [x] Review the public entrypoints, run appropriate checks, build the package and replay the public-bundle command. Record results and commit.
- [x] Push private main, create versioned evidence release with checksums/licenses, verify it, set public visibility and check anonymous access.
