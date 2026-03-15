# Changelog

<!-- markdownlint-disable MD024 -->

All notable changes to the Specify CLI and templates are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.29] - 2026-03-15

### Added

- Added `init_runtime` regression coverage for raw option validation, target resolution, AI/script selection, tracker construction, and preset install routing.

### Changed

- Extracted `specify init` request validation, selection flow, tracker setup, generic command relocation, init option persistence, and preset installation into a dedicated runtime module.
- Reduced direct fork ownership inside `specify_cli.__init__` again so future upstream merges should collide with fewer lines around `init`.

## [1.0.28] - 2026-03-15

### Added

- Added a shared `template_runtime` module plus focused regression tests for ZIP validation, project-relative path safety, and re-init preservation rules.

### Changed

- Centralized fork-specific agent metadata, packaging rules, and context-update mappings into shared registries consumed by the CLI, release scripts, and lint checks.
- Extracted AI skills/init-option handling and template download/extract/bootstrap logic out of `specify_cli.__init__` while preserving Codex, Droid, Antigravity, and Kimi fork behavior.
- Slimmed `specify_cli.__init__` to orchestration code so future upstream merges touch fewer fork-owned lines.

## [1.0.27] - 2026-03-14

### Changed

- Merged the latest upstream `main` changes into the Z-WICK fork and reconciled CLI, extension, packaging, and docs conflicts.
- Kept fork-specific command layouts intact for Codex (`.agents/skills`), Droid (`.factory/skills`), and Antigravity (`.agent/commands`).
- Adopted upstream preset support, catalog stack improvements, Qwen Markdown command output, and newer community extension entries.
- Synced Bash and PowerShell release packaging with the same agent matrix, release assets, and file hash generation.

### Added

- Added fork runtime/packaging coverage for Tabnine CLI, Kimi Code, Mistral Vibe, and merged upstream catalog additions.
- Added updated agent consistency tests around Kiro aliases, Codex skills, Tabnine TOML output, and Kimi skill layouts.

## [1.0.26] - 2026-03-07

### Changed

- Merged upstream `main` updates into the Z-WICK fork.
- Adopted upstream `kiro-cli` support and removed the legacy `q` runtime key from shared agent metadata and packaging scripts.
- Canonicalized Qoder to the real executable key `qodercli` while keeping `qoder` as a compatibility alias in the CLI.
- Aligned Copilot extension command registration with `.agent.md` outputs and companion `.prompt.md` files, including cleanup on uninstall.
- Kept fork-specific Codex `.agents/skills` and Droid `.factory/skills` behaviors intact while reconciling upstream release and context-script changes.

## [0.3.0] - 2026-03-13

### Added

- Upstream preset system with catalog support, template resolution, and preset-aware skill propagation.
- `specify doctor` project diagnostics command.
- DocGuard community extension catalog entry and self-test extension scaffolding.

### Changed

- Upstream Bash/PowerShell hardening, Qwen Markdown migration, and extension catalog quality-of-life updates.

## [0.2.1] - 2026-03-11

### Added

- Upstream Kimi Code CLI support and February 2026 newsletter.
- Multi-catalog extension search improvements and additional community catalog entries.

### Changed

- Upstream docs, release workflow, and template cleanup updates.

## [0.2.0] - 2026-03-09

### Added

- Upstream Tabnine CLI, Mistral Vibe, review, ralph, fleet, and understanding ecosystem updates.

### Changed

- Upstream branch numbering, command template, and catalog consistency fixes.

Earlier release history is available in Git.
