---
description: 自动化规格流水线：读取外部需求文档，在隔离 worktree 中自主执行 specify → clarify → plan → tasks → implement
argument-hint: 路径: /path/to/docs 描述: 功能描述
scripts:
  flyway:
    sh: scripts/bash/scan-flyway-versions.sh
    ps: scripts/powershell/scan-flyway-versions.ps1
  alembic:
    sh: scripts/bash/scan-alembic-revisions.sh
    ps: scripts/powershell/scan-alembic-revisions.ps1
---

## User Input

```text
$ARGUMENTS
```

## Execution

Parse user input and extract:
- **Doc path**: the path after "路径:"
- **Feature description**: the text after "描述:"

If either is missing, ask the user to provide: `路径: /path/to/docs 描述: feature overview`

Get the main repo root (`git rev-parse --show-toplevel`).

Dispatch sub-droids sequentially (stages 0-4); stage 5 is dispatched directly by this
command via `coding-worker-low / coding-worker-medium / coding-worker-high` (pick by task file count).
**If any stage times out or fails, retry with the same parameters.**

### Task Granularity Rules

To prevent subagent timeouts caused by overly long context:
- **Split large tasks**: If a task involves multiple files or multi-step operations, split
  it so each subagent handles only 1-2 files.
- **Single dispatch limit**: Each coding worker call MUST handle only one clear
  small task (e.g., "create one Entity class" or "write one Service method"). Never bundle
  an entire Phase into a single subagent.
- **Context trimming**: Only pass the reference information required for the current task
  in the prompt. Do not pass all design documents in full.

### Subagent Timeout and Chunked Write (Constitution v2.4.0)

- **5-minute hard timeout**: Every subagent call (Task tool) MUST set timeout=300. If a
  subagent has not returned within 5 minutes, MUST stop the call and follow the procedure
  below.
- **Chunked write instruction**: Every subagent prompt MUST include the following reminder:
  "When writing large files (>150 lines), you MUST write in chunks (each chunk <=150 lines)
  to avoid blocking that causes timeouts. Use Create for the first chunk, then Edit to
  append subsequent chunks."
- **Timeout handling procedure**:
  1. Record the timed-out TaskID and known progress.
  2. Split the task into smaller sub-tasks if the original scope was too broad.
  3. Re-dispatch with reduced scope and the chunked-write reminder.
  4. After 2 consecutive timeouts on the same task, halt and report to the user.

### Migration Version Conflict Detection

Before stage 5 begins and before each migration task dispatch, run version detection to avoid conflicts across worktrees and branches.

**For Flyway (Java/Spring)**:

Use the provided script to scan all worktrees and branches for occupied Flyway version numbers:

**Bash:**
```bash
./scripts/bash/scan-flyway-versions.sh <main-repo> <WORKTREE_ROOT>
```

**PowerShell:**
```powershell
./scripts/powershell/scan-flyway-versions.ps1 -MainRepo <main-repo> -WorktreeRoot <WORKTREE_ROOT>
```

**For Alembic (Python)**:

Use the provided script to scan for Alembic revision IDs:

**Bash:**
```bash
./scripts/bash/scan-alembic-revisions.sh <main-repo> <WORKTREE_ROOT>
```

**PowerShell:**
```powershell
./scripts/powershell/scan-alembic-revisions.ps1 -MainRepo <main-repo> -WorktreeRoot <WORKTREE_ROOT>
```

**For Prisma (Node.js/TypeScript)**:

Scan migration directories (cross-platform):

**Bash:**
```bash
ls <main-repo>/prisma/migrations/*/migration.sql 2>/dev/null || true
ls <WORKTREE_ROOT>/prisma/migrations/*/migration.sql 2>/dev/null || true
```

**PowerShell:**
```powershell
Get-ChildItem <main-repo>/prisma/migrations/*/migration.sql -ErrorAction SilentlyContinue
Get-ChildItem <WORKTREE_ROOT>/prisma/migrations/*/migration.sql -ErrorAction SilentlyContinue
```

**General procedure**:
- Merge all occupied version numbers/IDs, take the max +1 (or generate next unique ID) as the starting version
- Pass `NEXT_MIGRATION_VERSION` into every subagent prompt that involves database migrations
- If a feature needs multiple migration files, increment sequentially (e.g., V15, V16, V17... for Flyway)
- Update `NEXT_MIGRATION_VERSION` after each migration task completes

---

### Checkpoint Recovery: Detect Existing Artifacts on Startup

Before dispatching, detect current state and skip completed stages:

1. Check if a matching worktree already exists (`git worktree list` or user input contains WORKTREE_ROOT)
2. If WORKTREE_ROOT exists, check for artifacts under FEATURE_DIR:

| Detected File | Skip Stage |
|---------------|------------|
| spec.md | Stage 0 + 1 |
| spec.md contains `## Clarifications` | Stage 2 |
| plan.md + research.md | Stage 3 |
| plan.md contains impact warnings or `impact-pre-analysis.md` exists | Stage 3.5 |
| tasks.md (or tasks-index.md) | Stage 4 |
| All tasks in tasks.md marked [x] | Stage 5 |
| `impact-analysis.md` exists in FEATURE_DIR | Stage 5.5 |
| Review passed (no CRITICAL/HIGH) | Stage 6 (jump to stage 7 test) |
| Tests exist under src/test/ and `pnpm build` passes | Stage 7 (jump to stage 8 merge) |

3. Resume from the first incomplete stage
4. Report to user: `Detected artifacts for stages 0-N, resuming from stage N+1.`

If user input contains only "描述:" without "路径:" and matches an existing worktree/feature,
enter checkpoint recovery mode.

---

### Stage 0: Read Requirements Documents

```
Task:
  subagent_type: spec-read-docs
  description: "Read requirements docs"
  prompt: |
    Doc path: <parsed path>
    Read all requirements documents under this path and output a structured
    requirements summary.
    WARNING: When writing large files (>150 lines), you MUST write in chunks
    to avoid blocking timeouts.
```

**Checkpoint**: Confirm a structured requirements summary was returned; record as `DOCS_SUMMARY`.

---

### Stage 1: Specify + Worktree

```
Task:
  subagent_type: spec-specify-wt
  description: "Specify + Worktree"
  prompt: |
    Requirements summary:
    <DOCS_SUMMARY>

    Feature description: <parsed description>
    Main repo root: <repo root>

    Create an isolated worktree workspace, populate spec.md and quality checklist.
    MUST return WORKTREE_ROOT, BRANCH_NAME, FEATURE_DIR, and main repo root.

    Multi-Module Decomposition (Constitution v2.3.0):
    Count the number of distinct functional modules in the requirements first.
    - 1 module: spec.md contains all content directly.
    - 2-8 modules: spec.md serves as summary entry point only; create
      spec-<module>.md for each submodule under FEATURE_DIR/specs/.
      Reference: specs/009-asset-lifecycle/.
    - >8 modules: STOP and advise the user to split into multiple branches.

    WARNING: When writing large files (>150 lines), you MUST write in chunks
    (each chunk <=150 lines) to avoid blocking timeouts. Use Create for the
    first chunk, then Edit to append.
```

**Checkpoint**: Confirm WORKTREE_ROOT / BRANCH_NAME / FEATURE_DIR were returned; record as context variables.

---

### Stage 2: Clarify

```
Task:
  subagent_type: spec-clarify-auto
  description: "Auto Clarify"
  prompt: |
    WORKTREE_ROOT: <from stage 1>
    BRANCH_NAME: <from stage 1>
    FEATURE_DIR: <from stage 1>
    Main repo root: <repo root>

    Automatically clarify ambiguities in spec.md, select recommended answers
    and write them back.
    WARNING: When writing large files (>150 lines), you MUST write in chunks
    to avoid blocking timeouts.
```

**Checkpoint**: Confirm clarify completed and spec.md was updated.

---

### Stage 3: Plan

```
Task:
  subagent_type: spec-plan-auto
  description: "Generate Plan"
  prompt: |
    WORKTREE_ROOT: <from stage 1>
    BRANCH_NAME: <from stage 1>
    FEATURE_DIR: <from stage 1>
    Main repo root: <repo root>

    Generate the technical implementation plan and supporting design documents.
    WARNING: When writing large files (>150 lines), you MUST write in chunks
    to avoid blocking timeouts.
```

**Checkpoint**: Confirm plan.md was generated and Constitution Check passed.

---

### Stage 3.5: Impact Pre-Analysis (Lightweight)

After plan.md is generated, run a lightweight impact analysis based on the planned changes
to identify cross-module risks before task generation.

```
Task:
  subagent_type: impact-analyzer
  description: "Pre-implementation impact analysis"
  prompt: |
    Working directory: <WORKTREE_ROOT>
    Main repo root: <repo root>

    This is a PRE-IMPLEMENTATION analysis based on the technical plan (no code
    changes yet). Read these files:
    - <FEATURE_DIR>/plan.md (planned architecture and module changes)
    - <FEATURE_DIR>/spec.md (functional requirements)
    - <FEATURE_DIR>/data-model.md (if exists, planned schema changes)

    Analyze:
    1. Which existing modules will be touched or depended upon
    2. Cross-module call chains that may be affected
    3. Schema changes that could impact existing queries
    4. SLA risks from planned new queries or service calls

    Output your standard Impact Analysis Report. Mark confidence as LOW for
    items based only on plan intent (no actual diff available yet).
```

**Checkpoint**: Parse impact report. If CRITICAL downstream risks found, append them as
warnings to plan.md and ensure tasks generation accounts for them (e.g., add adaptation
tasks for affected downstream modules).

**Knowledge Feedback**: If the pre-analysis discovered module dependencies or call chain
patterns not yet documented in `chain-topology.md`, the main pipeline MUST append them
(with confidence marked as LOW/PLANNED). This seeds the knowledge base for the full
analysis in Stage 5.5.

---

### Stage 4: Tasks

```
Task:
  subagent_type: spec-tasks-auto
  description: "Generate Tasks"
  prompt: |
    WORKTREE_ROOT: <from stage 1>
    BRANCH_NAME: <from stage 1>
    FEATURE_DIR: <from stage 1>
    Main repo root: <repo root>

    Generate an executable task list organized by user stories.
    WARNING: When writing large files (>150 lines), you MUST write in chunks
    to avoid blocking timeouts.
```

**Checkpoint**: Confirm tasks.md (or shards) were generated.

---

### Stage 4-5 Transition: Sync Planning Docs to Main Repo + User Confirmation

#### Sync Planning Documents

After tasks are generated, sync the specs directory from the worktree back to the main repo
for unified management of all feature planning documents:

**Bash:**
```bash
cp -r <WORKTREE_ROOT>/specs/<BRANCH_NAME> <main-repo-root>/specs/
```

**PowerShell:**
```powershell
Copy-Item -Path <WORKTREE_ROOT>/specs/<BRANCH_NAME> -Destination <main-repo-root>/specs/ -Recurse -Force
```

Sync scope is limited to planning artifacts (no source code): spec.md, plan.md, research.md,
data-model.md, contracts/, quickstart.md, tasks.md (or shards), checklists/.

#### User Confirmation

After sync completes, **pause and show summary to user**:

```
============================================================
Specification complete (stages 0-4), artifacts generated in isolated workspace:
  Workspace: <WORKTREE_ROOT>
  Branch: <BRANCH_NAME>
  Specs: <FEATURE_DIR>
  Synced to main repo: <main-repo>/specs/<BRANCH_NAME>/

Generated files:
  - spec.md (with clarifications)
  - plan.md / research.md / data-model.md / contracts/ / quickstart.md
  - tasks.md (N tasks total, M parallelizable)

Start implementation? (yes/no)
  yes  - Begin stage 5 implementation immediately
  no   - Stop here; you can review artifacts first, then re-run
         /spec-pipeline to auto-resume from stage 5
============================================================
```

**Wait for user reply**:
- User replies yes/proceed/continue/start -> proceed to stage 5
- User replies no/stop/wait/review -> stop, output final summary (without implementation stage)

---

### Stage 5: Implement (dispatched directly by this command)

This stage is NOT delegated to a single sub-droid. The main command parses tasks and
dispatches coding workers (low/medium/high) directly based on task file count.

#### 5a. Parse and Split Tasks

Read `FEATURE_DIR/tasks.md` (or tasks-index.md + shards) and extract:
- Each task's TaskID, [P] marker, [US#], Phase, file paths
- Group by Phase; within each Phase identify parallel batches vs sequential tasks

**Split check**: For each task, if it involves 2+ files or multi-step operations, split into
sub-tasks (e.g., T005 becomes T005a, T005b), each handling only 1-2 files.

**Migration pre-scan**: Run version conflict detection (see rules above), record `NEXT_MIGRATION_VERSION`.

#### 5b. Execute Phase by Phase

For each Phase, dispatch according to these rules:

**Parallel tasks** (same Phase, marked [P], not touching the same file) -> dispatch multiple
Task calls simultaneously:

```
Dispatch simultaneously (multiple Task calls in one message):

Task 1:
  subagent_type: coding-worker-low | coding-worker-medium | coding-worker-high  # ← pick by file count
  description: "<TaskID> <brief>"
  prompt: |
    Working directory: <WORKTREE_ROOT>
    Task: <TaskID> <full description and file paths> (limit 1-2 files)
    Migration version: <NEXT_MIGRATION_VERSION> (only for migration tasks)
    Reference: <only the doc fragments needed for this task, not full docs>
    WARNING: When writing large files (>150 lines), you MUST write in chunks
    (each chunk <=150 lines) to avoid blocking timeouts. Use Create for the
    first chunk, then Edit to append.
    Return: changed files, verification results, remaining risks.
```

**Sequential tasks** (no [P] marker or touching the same file) -> dispatch one at a time,
wait for return before the next.

**After each task completes**: Mark `[x]` in tasks.md.

#### 5c. Phase Gate

After all tasks in a Phase complete, run the build command (cross-platform):

```bash
cd <WORKTREE_ROOT> && pnpm build
```

Examples: `mvn -DskipTests compile`, `npm run build`, `cargo build`, `go build ./...`

Pass -> next Phase. Fail -> attempt fix (max 2 times), still failing -> halt and report.

#### 5d. Error Handling

- Parallel batch partial failure: others continue; retry failed task once after batch ends
- Sequential task failure: halt current Phase, report blocking point
- Timeout: record TaskID, split into smaller sub-tasks and re-dispatch (max 2 retries per
  task; see "Subagent Timeout and Chunked Write" rules)

---

### Stage 5.5: Impact Analysis (Full)

After all implementation tasks complete and `pnpm build` passes, run a full
impact analysis based on the actual code diff.

```
Task:
  subagent_type: impact-analyzer
  description: "Post-implementation impact analysis"
  prompt: |
    Working directory: <WORKTREE_ROOT>
    Main repo root: <repo root>

    This is a POST-IMPLEMENTATION analysis based on actual code changes.

    1. Run: git diff main..HEAD --stat  (to get changed file list)
    2. Run: git diff main..HEAD          (to get full diff)
    3. For each changed file, trace all callers and downstream dependencies
    4. Cross-reference with chain topology and SLA budgets
    5. Check incident history for affected areas

    Output your standard Impact Analysis Report with HIGH confidence
    (based on real diff).
```

**Checkpoint**: Parse impact report.

- **No HIGH/CRITICAL risks** -> proceed to Stage 6 (Code Review), pass impact report
  as additional context
- **HIGH/CRITICAL risks found** -> show to user:
  ```
  Impact Analysis found cross-module risks:
  - [CRITICAL] <risk description>
  - [HIGH] <risk description>

  Options:
    proceed  - Continue to code review (risks noted but accepted)
    fix      - Dispatch fix tasks to address risks before review
    stop     - Halt pipeline for manual assessment
  ```
- User selects proceed -> pass risks as context to Stage 6 review
- User selects fix -> dispatch fix tasks via coding-worker-medium, re-run 5.5
- User selects stop -> halt, output summary

#### 5.5a. Knowledge Feedback (after impact report)

Regardless of the user's choice above, the **main pipeline** (not the impact-analyzer)
MUST update the project knowledge base with discoveries from the impact report:

1. **Update `chain-topology.md`**: If the impact report discovered new call chains,
   module dependencies, or SLA observations not already documented:
   - Append new chains to `## Call Chain Patterns`
   - Add/update module dependencies in the `Internal Modules` table
   - Record observed SLA data points in `## SLA Budgets`

2. **Update `incident-log.md`**: If the impact report flagged CRITICAL risks that were
   confirmed (either fixed or accepted with justification):
   - Append a new entry under `## Incidents` with:
     - Date, feature branch name, severity
     - Affected module and risk description
     - Resolution: "fixed in Stage 5.5" / "accepted with justification: ..."
     - Lesson learned for future changes

3. **Skip updates** if the impact report found no new information beyond what is already
   documented in the knowledge base.

This feedback loop ensures the knowledge base grows with each pipeline run, making future
impact analyses progressively more accurate.

---

### Stage 6: Code Review

After all implementation tasks complete and final `pnpm build` passes,
invoke `project-code-reviewer`:

```
Task:
  subagent_type: project-code-reviewer
  description: "Review implementation"
  prompt: |
    Working directory: <WORKTREE_ROOT>
    Branch: <BRANCH_NAME>
    Specs directory: <FEATURE_DIR>

    Review all changes on this branch relative to main:
    1. Run git diff main..HEAD for the full diff
    2. Validate implementation against <FEATURE_DIR>/spec.md and plan.md
    3. Run your checklist (security, quality, performance, design patterns)
    4. Output structured report:
       Summary: <one-line conclusion>
       Findings:
       - [CRITICAL/HIGH/MEDIUM/LOW] <file:line> <issue description>
       Follow-up:
       - <suggested fix action>
    WARNING: When writing large files (>150 lines), you MUST write in chunks
    to avoid blocking timeouts.
```

**Checkpoint**: Parse review results, classify by severity.

**Show review report to user**, then decide based on results:

- **No CRITICAL/HIGH issues** -> inform user review passed, pipeline complete
- **CRITICAL/HIGH issues exist** -> show issue list, ask user:
  ```
  Code Review found the following issues:
  - [CRITICAL] <issue1>
  - [HIGH] <issue2>
  ...

  Auto-fix? (yes/no)
    yes  - Dispatch each issue to coding-worker-medium for fixing,
           then re-run review
    no   - Stop; you can fix manually then re-run /spec-pipeline
  ```
- User selects yes -> dispatch each CRITICAL/HIGH finding as a fix task to
  `coding-worker-medium`, then re-run stage 6 (max 2 retry rounds)
- User selects no -> stop, output final summary with unresolved issues list

---

### Stage 7: Test (dispatch spec-test-writer)

After review passes, write and run tests for implemented code.

#### 7a. Determine Test Scope

Extract all completed implementation tasks from tasks.md, identify classes needing tests:
- Service classes -> unit tests
- Controller/Endpoint classes -> API tests
- Utility/Wrapper classes -> unit tests
- Group by module, each test class as an independent small task

#### 7b. Dispatch Test Writing

For each class needing tests, dispatch a `spec-test-writer`:

```
Task:
  subagent_type: spec-test-writer
  description: "Test <ClassName>"
  prompt: |
    Working directory: <WORKTREE_ROOT>
    Test target: <full class path, e.g. com.example.modules.xxx.service.XxxService>
    Module name: <module name, e.g. maintenance>
    Reference:
    - Acceptance criteria: <extract relevant acceptance scenarios from spec.md>
    - API contracts: <extract relevant endpoints from contracts/, if any>
    Write the test class and run verification.
    WARNING: When writing large files (>150 lines), you MUST write in chunks
    to avoid blocking timeouts.
```

Test classes for different modules/classes can be dispatched in parallel.

#### 7c. Aggregate Test Results

After all test classes are written, run full test suite (cross-platform):

```bash
cd <WORKTREE_ROOT> && pnpm build
```

Examples: `mvn test`, `npm test`, `pytest`, `cargo test`, `go test ./...`

- All pass -> proceed to stage 8
- Failures -> show failure list, dispatch `spec-test-writer` to fix (max 2 rounds)
- Still failing -> halt, report failed tests, wait for user decision

---

### Stage 8: Merge to main

After `pnpm build` all passes, auto-merge to main:

#### 8a. Pre-check

Check for uncommitted changes (cross-platform git commands):

```bash
cd <WORKTREE_ROOT> && git status
cd <WORKTREE_ROOT> && git diff --cached
```

- Confirm no uncommitted changes (commit first if any)
- Check diff for sensitive information

#### 8b. Commit Test Code

If stage 7 produced new files (cross-platform git commands):

```bash
cd <WORKTREE_ROOT> && git add src/test/ && git commit -m "test: add consolidated tests for <BRANCH_NAME>"
```

Examples for test directory: `src/test/java` (Java), `tests` (Python/Node), `test` (Go/Rust)

#### 8c. Merge

Merge the feature branch to main (cross-platform git command):

```bash
cd <main-repo-root> && git merge <BRANCH_NAME> --no-ff -m "feat: merge <BRANCH_NAME> with tests"
```

#### 8d. Confirm Push with User

```
============================================================
Branch <BRANCH_NAME> merged to main (local).
  Tests: all passed (N test classes, M test methods)
  Review: PASS

Push to remote? (yes/no)
  yes  - git push origin main
  no   - Keep local merge; you can push manually
============================================================
```

- User selects yes -> `git push origin main`
- User selects no -> stop

---

### Stage 9: Rebuild + Documentation Verification

After merge completes, rebuild and start the service, verify API documentation is accessible.

**Build and deploy** (project-specific, examples shown):

```bash
cd <main-repo-root> && pnpm build:prod && scp -P 22 -r ./dist/** root@192.168.0.188:/docker/nginx/web/html
```

Examples: `docker compose up -d --build`, `kubectl apply -f k8s/`, `npm run deploy`, `./deploy.sh`

**Wait for service startup** (poll health check, max 120 seconds):

**Bash:**
```bash
for i in $(seq 1 24); do
  curl -sf http://localhost:${APP_PORT}/${DOC_PATH} > /dev/null && break
  sleep 5
done
```

**PowerShell:**
```powershell
for ($i = 1; $i -le 24; $i++) {
  try {
    Invoke-WebRequest -Uri "http://localhost:${APP_PORT}/${DOC_PATH}" -UseBasicParsing -ErrorAction Stop | Out-Null
    break
  } catch {
    Start-Sleep -Seconds 5
  }
}
```

Examples for `${DOC_PATH}`: `doc.html` (knife4j), `swagger` (Swagger UI), `docs` (FastAPI), `api-docs` (Spring REST Docs)

Show to user:
```
============================================================
Service rebuilt and started:
  API documentation: http://localhost:${APP_PORT}/${DOC_PATH}
  New API endpoints can be found in the documentation interface
============================================================
```

**If startup fails**, show last 30 lines of service logs and report the error:

**Bash:**
```bash
ssh root@192.168.0.188 'docker logs nginx --tail=30'
```

**PowerShell:**
```powershell
ssh root@192.168.0.188 'docker logs nginx --tail=30'
```

Examples: `docker compose logs app`, `kubectl logs deployment/app`, `pm2 logs app`, `journalctl -u app`

**Note**: SSH commands work on PowerShell 7+ with OpenSSH installed. For older PowerShell versions, use `plink` or native Docker/kubectl commands.

---

## Final Summary

After all stages complete, show to user:

1. Execution status per stage (success/retry count)
2. Generated file list, task count, MVP suggestion
3. Implementation stage: completed/failed/skipped task count, modified file list, compile status
4. Review results: pass/fail, issue count (by severity), unresolved issues list (if any)
5. Test results: test class count, test method count, pass/fail
6. Merge status: merged/not merged, pushed or not

```
============================================================
Pipeline complete:
  Workspace: <WORKTREE_ROOT>
  Branch: <BRANCH_NAME>
  Specs: <FEATURE_DIR>
  Review: <PASS/FAIL>
  Tests: <N classes, M methods, all passed>
  Merge: <merged to main / pending>

Next steps:
  cd <WORKTREE_ROOT>
  /analyze    - Analyze spec/plan/tasks consistency
  /implement  - Re-run or continue unfinished tasks
============================================================
```
