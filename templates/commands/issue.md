---
description: 创建 GitHub Issue（Bug 报告、功能请求或任务）
argument-hint: <类型:bug|feature|task> <标题和描述>
---

## User Input

```text
$ARGUMENTS
```

## Spec-Issue: Create GitHub Issue

### Phase 1: Parse Input & Detect Repo

**1a. Detect Target Repository**

Determine which repo to submit the issue to:

- **Explicit repo** (user specifies `repo:owner/repo` in `$ARGUMENTS`):
  Use the specified repo directly. This supports cross-repo scenarios
  (e.g., frontend submitting issues to backend repo).
  ```
  /spec-issue repo:Z-WICK/PropFlow_Backend bug: 接口返回500
  /spec-issue repo:org/backend-api feature: 新增批量导出接口
  ```

- **No explicit repo**: Fall back to current project's remote:
  ```bash
  git remote get-url origin
  ```

If not a GitHub URL and no explicit repo provided, abort:
```
ERROR: Cannot determine target GitHub repository.
  - Current remote is not GitHub, and no repo: specified.
  - Usage: /spec-issue repo:owner/repo <type> <description>
```

Extract `owner` and `repo` from the determined source.

**1b. Verify GitHub Access**

Before proceeding, verify the user can create issues in the target repo:

1. Attempt to list issues (read access check) via GitHub MCP tool
2. If access fails, run diagnostics and show setup guide:

```
============================================================
ERROR: Cannot access GitHub repository <owner>/<repo>

Possible causes and fixes:

1. GitHub MCP not configured
   → Add GitHub MCP server in Factory settings:
     /settings → MCP → Add "github" server
   → Or add to ~/.claude/mcp.json:
     {
       "mcpServers": {
         "github": {
           "command": "npx",
           "args": ["-y", "@modelcontextprotocol/server-github"],
           "env": { "GITHUB_PERSONAL_ACCESS_TOKEN": "<your-token>" }
         }
       }
     }

2. gh CLI not authenticated
   → Install: brew install gh (macOS) / apt install gh (Linux)
   → Login:   gh auth login
   → Verify:  gh auth status

3. Insufficient permissions
   → Ensure your GitHub account has write access to <owner>/<repo>
   → For organization repos: check that your team has "Write" or
     "Triage" permission on the repository
   → Generate a PAT with 'repo' scope at:
     https://github.com/settings/tokens/new?scopes=repo

4. Organization SSO required
   → If the org uses SAML SSO, authorize your PAT:
     https://github.com/settings/tokens → Configure SSO → Authorize
============================================================
```

Stop execution after showing the guide. Do not attempt to create the issue.

**1b. Parse Issue Type**

From `$ARGUMENTS`, detect type:

| Prefix/Keyword | Type | Label |
|----------------|------|-------|
| `bug:` / `bug` / `缺陷` | Bug Report | `bug` |
| `feature:` / `feat` / `功能` | Feature Request | `enhancement` |
| `task:` / `task` / `任务` | Task | `task` |
| (none detected) | Ask user | - |

If type cannot be determined, ask:
```
What type of issue is this?
  1. Bug report (something is broken)
  2. Feature request (new functionality)
  3. Task (work item / chore)
```

**1c. Parse Title and Description**

Extract from `$ARGUMENTS`:
- **Title**: First sentence or text after type prefix
- **Description**: Remaining text

If only a brief phrase is provided, use it as the title and gather details interactively.

---

### Phase 2: Gather Details (Interactive)

Based on issue type, collect structured information.

**2a. Bug Report**

If not already provided in `$ARGUMENTS`, ask (max 3 questions):

1. **Reproduction steps**: "How do you trigger this bug?"
2. **Expected vs actual**: "What should happen vs what actually happens?"
3. **Environment**: "Any relevant version, OS, or config details?"

Also auto-detect from project context:
- Current branch: `git rev-parse --abbrev-ref HEAD`
- Recent commits: `git log --oneline -5`
- App version from build file (pom.xml, package.json, etc.)

**2b. Feature Request**

If not already provided, ask:

1. **Problem**: "What problem does this solve?"
2. **Proposed solution**: "How should it work?"
3. **Alternatives**: "Any alternatives you've considered?"

**2c. Task**

If not already provided, ask:

1. **Scope**: "What needs to be done?"
2. **Acceptance criteria**: "How do we know it's done?"

---

### Phase 3: Compose Issue

**3a. Build Issue Body**

Generate structured markdown body based on type:

**Bug Report:**
```markdown
## Bug Report

### Description
<summary of the bug>

### Reproduction Steps
1. <step 1>
2. <step 2>
3. <step 3>

### Expected Behavior
<what should happen>

### Actual Behavior
<what actually happens>

### Environment
- Branch: `<current branch>`
- Version: <detected version>
- OS: <if provided>

### Additional Context
<any extra info, logs, screenshots mentioned>
```

**Feature Request:**
```markdown
## Feature Request

### Problem
<what problem this solves>

### Proposed Solution
<how it should work>

### Alternatives Considered
<other approaches>

### Additional Context
<any extra info>
```

**Task:**
```markdown
## Task

### Description
<what needs to be done>

### Acceptance Criteria
- [ ] <criterion 1>
- [ ] <criterion 2>

### Additional Context
<any extra info>
```

**3b. Determine Labels**

Auto-assign labels based on context:

| Condition | Label |
|-----------|-------|
| Bug type | `bug` |
| Feature type | `enhancement` |
| Task type | `task` |
| Affected module detected | `module:<name>` |
| Priority mentioned (urgent/critical) | `priority:high` |
| Related to spec/pipeline | `spec-kit` |

**3c. Preview & Confirm**

Show the composed issue to user:

```
============================================================
New GitHub Issue Preview

Repository: <owner>/<repo>
Type: <Bug Report / Feature Request / Task>
Title: <title>
Labels: <label list>

Body:
---
<full markdown body>
---

Create this issue? (yes/no/edit)
  yes  - Create the issue
  no   - Cancel
  edit - Let me adjust the title or description
============================================================
```

Wait for user confirmation.

---

### Phase 4: Create Issue

**4a. Submit to GitHub**

Use GitHub MCP tool to create the issue:

```
github_create_issue:
  owner: <owner>
  repo: <repo>
  title: <title>
  body: <body>
  labels: [<labels>]
```

**4b. Report**

```
============================================================
Issue created successfully!

  #<number>: <title>
  URL: <issue URL>
  Labels: <labels>

Next steps:
  - /spec-fixbug #<number>    (if bug, start investigation)
  - /specify <description>    (if feature, start spec workflow)
============================================================
```

---

### Phase 5: Batch Mode (Optional)

If `$ARGUMENTS` contains multiple issues separated by `---` or numbered list:

```
Example:
  /spec-issue bug: 登录页面500错误 --- bug: 导出报表超时 --- task: 清理过期缓存
```

Parse each item, compose all issues, show batch preview:

```
============================================================
Batch Issue Preview (3 issues)

  1. [bug] 登录页面500错误
  2. [bug] 导出报表超时
  3. [task] 清理过期缓存

Create all 3 issues? (yes/no/select)
  yes    - Create all
  no     - Cancel
  select - Choose which to create (e.g., "1,3")
============================================================
```

---

## Error Handling

- **Not a GitHub repo & no `repo:` specified**: Abort, show usage with `repo:owner/repo` syntax
- **GitHub MCP / gh CLI not configured**: Show full setup guide (see Phase 1b)
- **No write access (403/404)**: Show permission guide — check team role, PAT scope, SSO authorization
- **Rate limited**: Wait and retry (max 2 retries)
- **Empty description**: Require at least a title before creating
- **Duplicate detection**: Search existing open issues for similar titles, warn if potential duplicate found
- **Cross-repo submission**: Verify the user has access to the target repo before composing the issue
