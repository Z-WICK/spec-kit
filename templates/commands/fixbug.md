---
description: 从 Bug 描述或 GitHub Issue 出发，分析日志、定位根因、修复问题
argument-hint: <bug描述> 或 issue:#123 或 issue:https://github.com/owner/repo/issues/123
---

## User Input

```text
$ARGUMENTS
```

## Spec-FixBug: Bug Investigation & Fix Workflow

### Phase 1: Gather Bug Context

**1a. Parse Input**

Determine input type from `$ARGUMENTS`:

- **GitHub Issue URL** (contains `github.com` and `/issues/`):
  Extract owner, repo, issue number. Fetch issue via GitHub MCP tool or `gh issue view`.
- **Issue shorthand** (`issue:#123` or `#123`):
  Detect repo from `git remote get-url origin`. Fetch issue details.
- **Plain text description**:
  Use directly as bug description.

**1b. Extract Bug Information**

From the issue or description, extract:
- **Summary**: One-line description of the bug
- **Reproduction steps**: How to trigger the bug
- **Expected behavior**: What should happen
- **Actual behavior**: What actually happens
- **Environment**: Version, OS, config (if mentioned)
- **Error messages**: Any error text, stack traces, or screenshots mentioned
- **Affected module**: Which part of the system is involved

If critical information is missing, ask the user (max 3 questions):
- "How do you trigger this bug?"
- "What error message or behavior do you see?"
- "When did this start happening?"

**1c. Show Bug Summary**

```
============================================================
Bug Investigation: <summary>

Source: <GitHub Issue #N / User description>
Module: <detected or unknown>
Reproduction: <steps or "not provided">
Error: <error message snippet or "not provided">

Starting investigation...
============================================================
```

---

### Phase 2: Log Analysis

Dispatch `log-analyzer` to scan for related errors.

**2a. Locate Log Files**

Search for log files in common locations:
- `logs/`, `log/`, `*.log`
- Docker logs: `docker compose logs --tail=500 <service>`
- Application logs: framework-specific paths
- If no local logs found, ask user for log location or run log command

**2b. Dispatch Log Analyzer**

```
Task:
  subagent_type: log-analyzer
  description: "Analyze logs for bug: <summary>"
  prompt: |
    Bug context:
      Summary: <summary>
      Error message: <error text if available>
      Affected module: <module if known>
      Reproduction: <steps if available>

    Search for log files in the working directory and analyze them.
    Focus on:
    1. Errors matching the reported bug symptoms
    2. Stack traces related to the affected module
    3. Timeline of events around the bug occurrence
    4. Any correlated warnings or errors

    Return your standard Log Analysis Report.
```

**2c. Parse Log Findings**

Extract from the log analysis:
- Relevant error messages and stack traces
- Timestamps and frequency
- Root cause hypothesis from logs

---

### Phase 3: Code Investigation

**3a. Trace from Error to Code**

Using the error messages and stack traces from Phase 2:
- Grep for exception classes, error messages, or method names in source code
- Trace the call chain from the error point upward
- Identify the specific file(s) and line(s) where the bug originates

**3b. Understand the Bug**

Read the identified source files and analyze:
- What is the intended logic?
- Where does it deviate from expected behavior?
- What conditions trigger the bug?
- Are there related edge cases?

**3c. Check for Related Issues**

- Grep for TODO/FIXME/HACK comments near the bug location
- Check git blame to see when the buggy code was introduced
- Check if similar patterns exist elsewhere (same bug in other places)

---

### Phase 4: Propose Fix

**4a. Present Diagnosis**

```
============================================================
Bug Diagnosis

Root Cause:
  <concise explanation of why the bug occurs>

Evidence:
  - [FILE:LINE] <code snippet showing the problem>
  - [LOG] <relevant log entry>

Affected Files:
  - <file1> (primary fix)
  - <file2> (related change, if any)

Fix Approach:
  <description of the proposed fix>
============================================================
```

**4b. Ask User for Confirmation**

```
Proceed with fix? (yes/no/alternative)
  yes         - Apply the fix
  no          - Stop, I'll fix manually
  alternative - Suggest a different approach
```

---

### Phase 5: Apply Fix

If user confirms:

**5a. Create Fix Branch (optional)**

If not already on a feature branch:
```bash
git checkout -b fix/<short-bug-description>
```

**5b. Dispatch Fix Implementation**

For each file that needs changes, dispatch the appropriate coding worker tier:

```
Task:
  subagent_type: coding-worker-low | coding-worker-medium | coding-worker-high  # ← pick by file count
  description: "Fix: <bug summary>"
  prompt: |
    Working directory: <repo root>

    Bug: <summary>
    Root cause: <diagnosis>

    Fix required in: <file path>
    Current buggy code: <code snippet>
    Expected fix: <description of change>

    Apply the fix. Run verification after:
    1. pnpm build to confirm compilation
    2. If a specific test covers this area, run it

    WARNING: When writing large files (>150 lines), you MUST write in chunks
    to avoid blocking timeouts.
```

**5c. Impact Analysis of Fix**

Before running verification, dispatch `impact-analyzer` to check the fix doesn't
introduce regressions or affect downstream modules:

```
Task:
  subagent_type: impact-analyzer
  description: "Impact analysis for bug fix: <summary>"
  prompt: |
    Working directory: <repo root>

    A bug fix has been applied. Analyze the impact of these changes:

    1. Run: git diff HEAD~1..HEAD (to get the fix diff)
    2. Trace all callers of modified functions/APIs
    3. Check if the fix changes any public interface or behavior contract
    4. Verify no downstream modules are broken by the fix
    5. Flag if the fix touches areas with prior incidents

    Bug context:
      Summary: <summary>
      Root cause: <diagnosis>
      Files changed: <file list>

    Output your standard Impact Analysis Report.
```

**Handle impact results:**
- **No HIGH/CRITICAL risks** → proceed to verification
- **Risks found** → show to user before verification:
  ```
  Impact analysis found potential side effects from the fix:
  - [SEVERITY] <risk description>

  Options:
    proceed  - Continue with verification (risks accepted)
    revise   - Adjust the fix to address risks
    stop     - Halt for manual review
  ```

**Knowledge Feedback**: If the impact report discovered new call chain information,
update `chain-topology.md`. If the bug itself is noteworthy, append to `incident-log.md`.

**5d. Verify Fix**

After all fix tasks complete:

1. Run build: `pnpm build`
2. Run tests: N/A (no test framework configured)
3. If reproduction steps were provided, describe how to verify the fix

---

### Phase 6: Report

```
============================================================
Bug Fix Complete

Bug: <summary>
Source: <GitHub Issue #N / User description>

Root Cause:
  <one-line explanation>

Changes:
  - <file1>: <what was changed>
  - <file2>: <what was changed>

Verification:
  - Build: PASS/FAIL
  - Tests: PASS/FAIL (N tests, M passed)
  - Manual verification: <steps to confirm fix>

Branch: <fix/branch-name or current branch>

Next steps:
  - [ ] Verify the fix manually with reproduction steps
  - [ ] Run full test suite if not done
  - [ ] Commit and push when satisfied
  - [ ] Close GitHub Issue #N (if applicable)
============================================================
```

If the bug came from a GitHub Issue, offer to add a comment:
```
Add a comment to Issue #N with the diagnosis and fix? (yes/no)
```

If yes, post a comment summarizing the root cause and fix via GitHub MCP tool.

---

## Error Handling

- **No logs found**: Skip Phase 2, proceed with code-only investigation
- **Cannot reproduce from description**: Ask user for more details (max 2 rounds)
- **Fix breaks build**: Revert changes, report the build error, suggest alternative approach
- **Fix breaks tests**: Show failing tests, ask user whether to adjust fix or update tests
- **Multiple possible root causes**: Present all candidates ranked by likelihood, let user choose
