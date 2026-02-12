---
description: 宪法优化 — 将工程效率原则增量合并到项目宪法中
argument-hint: [可选: 额外原则描述]
handoffs:
  - label: Run Pipeline
    agent: speckit.pipeline
    prompt: Run the full pipeline with the updated constitution principles.
---

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

## Preset Principles

The following 4 engineering principles are the preset payload of this command. They address real pain points observed in pipeline execution: sub-agent timeouts, low planning quality, and serial task inefficiency.

### Principle A — Module Decomposition（大模块拆分）

> 当功能模块超过 500 行或涉及 3 个以上独立职责时，MUST 拆分为子模块。每个子模块独立可测、职责单一。spec 阶段按模块生成 spec-\<module\>.md，tasks 阶段按模块生成 tasks-\<module\>.md 分片。

### Principle B — Chunked Write（大文件分段写入）

> 所有子代理写入超过 200 行的文件时，MUST 分段写入（每段 ≤200 行）。首段用 Create，后续用 Edit 追加。违反此规则导致的超时视为可预防故障。

### Principle C — Planning Model Gate（规划阶段模型约束）

> spec、plan、tasks 三个规划阶段 MUST 由顶级模型（Opus 级别）执行，禁止委派给 Sonnet/Haiku 等低级模型。规划质量直接决定实现质量，不可在此环节降级。

### Principle D — Parallelism-First Task Design（任务并行化优先）

> spec、plan、tasks 阶段在设计任务时，MUST 优先识别可并行的工作单元并标记 [P]。可并行任务 SHOULD 委派子代理同时执行以提高效率。串行依赖必须显式声明理由。

## Execution Flow

Follow these 6 steps precisely.

### Step 1 — Load Existing Constitution

Read `.specify/memory/constitution.md`.

- If the file does not exist, copy from `.specify/templates/constitution-template.md` first.
- If neither exists, report an error and stop — the project must be initialized with `specify init` first.

Parse the current `CONSTITUTION_VERSION` (semver) and `LAST_AMENDED_DATE`.

### Step 2 — Deduplication Check

Scan the existing constitution content for each preset principle using keyword matching:

| Principle | Detection Keywords (ANY match = already present) |
|-----------|--------------------------------------------------|
| A — Module Decomposition | `拆分` AND `子模块`, OR `module decomposition` |
| B — Chunked Write | `分段写入` OR `chunked write` (case-insensitive) |
| C — Planning Model Gate | `规划阶段` AND `模型约束`, OR `planning model gate` |
| D — Parallelism-First | `并行` AND `parallel`, OR `parallelism-first` |

For each principle:
- If keywords are detected → mark as **SKIP** (already present)
- If not detected → mark as **APPEND**

If ALL 4 principles are SKIP, output a summary ("All preset principles already present, no changes made.") and stop.

### Step 3 — Merge User Custom Principles

If `$ARGUMENTS` is non-empty, parse the user input as additional principle(s) to append alongside the preset ones. Treat each paragraph or numbered item as a separate principle. Apply the same deduplication logic — skip if semantically similar content already exists.

### Step 4 — Incremental Write

Locate the `## Core Principles` section in the constitution file. Append each APPEND-marked principle at the end of this section, formatted as:

```markdown
### [Principle Name]

> [Principle statement]

**Rationale**: [Brief rationale derived from the principle context]
```

Update metadata:
- `CONSTITUTION_VERSION`: bump MINOR (e.g., `2.4.0` → `2.5.0`). Reset PATCH to 0.
- `LAST_AMENDED_DATE`: set to today's date (ISO 8601 format: YYYY-MM-DD).

### Step 5 — Consistency Propagation

Search for references to the old constitution version string (e.g., `Constitution v2.4.0`) in these files:
- `.specify/templates/commands/pipeline.md`
- `.specify/templates/commands/fixbug.md`
- Any other files under `.specify/` that reference `Constitution v`

Replace old version references with the new version string.

If no version references are found, skip this step silently.

### Step 6 — Output Summary

Report to the user:

```
Constitution Optimization Summary
──────────────────────────────────
Principles appended: [N] (list names)
Principles skipped:  [M] (list names, reason: already present)
Custom principles:   [K] (from user input, if any)
New version:         vX.Y.Z (was vA.B.C)
Files updated:       [list of files modified]

Suggested commit message:
  docs: amend constitution to vX.Y.Z — add engineering efficiency principles
```

## Important Notes

- This command is an incremental operation — it NEVER removes or modifies existing principles.
- The preset principles are complementary to whatever is already in the constitution.
- Do NOT modify `pipeline.md` or `fixbug.md` content beyond version string references. Those files contain execution-level implementations of these principles and are maintained separately.
- If the constitution file structure differs from expected (e.g., no `## Core Principles` heading), adapt by appending to the most appropriate section, or create the section if missing.
