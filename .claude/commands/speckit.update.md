---
description: 智能增量更新 Spec-Kit — 检测版本差异，AI 驱动内容级合并，保留用户自定义
argument-hint: [--rollback 回滚到备份版本]
---

## User Input

```text
$ARGUMENTS
```

## Spec-Kit Update: AI-Driven Incremental Merge

This command performs an intelligent incremental update of the Spec-Kit framework files.
Instead of overwriting, it uses AI to merge new features with user customizations.

---

### Rollback Mode

If `$ARGUMENTS` contains `--rollback`, skip to **Phase R: Rollback** at the end of this document.

---

### Phase 1: Version Detection & Download

**1a. Read current version**

```bash
cat .specify/.version 2>/dev/null || echo "unknown"
```

Record as `CURRENT_VERSION`. If `unknown`, warn user:
```
WARNING: No version marker found (.specify/.version).
This project may have been initialized before version tracking was added.
Update will treat all files as potentially user-modified (conservative merge).
```

**1b. Fetch latest release**

Query GitHub API for the latest release:

```bash
curl -sf https://api.github.com/repos/Z-WICK/spec-kit/releases/latest
```

If `GH_TOKEN` or `GITHUB_TOKEN` env var is set, include it as `Authorization: Bearer` header
to avoid rate limits.

Extract `tag_name` as `LATEST_VERSION` and `body` as `RELEASE_NOTES`.

**1c. Compare versions**

If `CURRENT_VERSION` equals `LATEST_VERSION`:
```
Spec-Kit is already up to date (CURRENT_VERSION).
```
Exit.

**1d. Download new version template**

From the release assets, download the template ZIP matching the current agent and script variant.

Detection logic:
- Agent: check which agent directory exists (`.claude/`, `.cursor/`, `.github/agents/`, etc.)
- Script variant: check if `.specify/scripts/bash/` exists → `sh`, else `ps`

Download URL pattern:
```
https://github.com/Z-WICK/spec-kit/releases/download/{LATEST_VERSION}/spec-kit-template-{agent}-{variant}-{LATEST_VERSION}.zip
```

Extract to a temporary directory (e.g., `/tmp/speckit-update-{LATEST_VERSION}/` or OS temp dir).
Record as `NEW_TEMPLATE_DIR`.

---

### Phase 2: Change Analysis & User Confirmation

**2a. Generate change manifest**

Compare every file in `NEW_TEMPLATE_DIR` against the current project. Categorize each file:

| Category | Condition |
|----------|-----------|
| **NEW** | File exists in new template but not in project |
| **MODIFIED** | File exists in both; new template differs from current |
| **DELETED** | File exists in project's template scope but not in new template |
| **UNCHANGED** | File exists in both and content is identical |

For **MODIFIED** files, further classify:
- **User-unmodified**: Current file matches the hash in `.specify/.file-hashes` (user hasn't changed it)
- **User-modified**: Current file differs from the hash in `.specify/.file-hashes` (user has customized it)

If `.specify/.file-hashes` does not exist (pre-tracking project), treat ALL existing files as
potentially user-modified (conservative approach).

**2b. Extract release highlights**

From `RELEASE_NOTES`, extract key changes grouped by:
- New features / commands
- Updated commands / templates
- Updated scripts
- Breaking changes (if any)

**2c. Present update summary**

Display to user (in Chinese):

```
============================================================
Spec-Kit 更新: {CURRENT_VERSION} → {LATEST_VERSION}

新增特性:
  + [list new files with brief descriptions from release notes]

更新内容:
  ~ [list modified files with change summaries]
  ~ [N] 个脚本已更新

删除内容:
  - [list deleted files, if any]

您的项目中存在以下自定义内容:
  • [list user-modified files]

是否开始智能合并？(yes/no)
============================================================
```

**Wait for user confirmation.** If user declines, exit with no changes.

---

### Phase 3: Backup

**3a. Create backup directory**

```bash
mkdir -p .specify/.backups/{CURRENT_VERSION}-{YYYYMMDD-HHmmss}
```

**3b. Copy current state**

Copy the full `.specify/` directory and the agent command directory (e.g., `.claude/commands/`,
`.cursor/commands/`, etc.) into the backup.

**3c. Write backup metadata**

Create `.specify/.backups/{backup-name}/metadata.json`:

```json
{
  "version": "{CURRENT_VERSION}",
  "timestamp": "{ISO-8601}",
  "git_commit": "{current HEAD sha, or null}",
  "files": ["list of all backed up file paths"]
}
```

**3d. Git status warning**

If the project is a git repo with uncommitted changes:
```
WARNING: 您有未提交的变更。建议先 git commit 再继续更新。
继续？(yes/no)
```

---

### Phase 4: Smart Incremental Merge

Process each file from the change manifest. Strategy depends on category:

#### 4a. NEW files — Direct create

Files that exist only in the new template. Create them in the project.

For each new file:
```
  + 新增: {file_path} ({brief description})
```

#### 4b. MODIFIED + User-unmodified — Direct replace

The user hasn't customized these files, so safely replace with the new version.

For each:
```
  ↻ 替换: {file_path} (无用户修改)
```

#### 4c. MODIFIED + User-modified — AI Smart Merge (Core)

This is the key differentiator. For each user-modified file:

1. Read three versions:
   - **Old template**: The original version the user started from (reconstruct from `.file-hashes`
     or from the current version's release package if available)
   - **User current**: The file as it exists now in the project
   - **New template**: The file from the new release

2. Analyze the diff between old template and new template to understand what's new:
   - New sections / stages / rules added
   - Modified instructions or parameters
   - Removed or restructured content

3. Analyze the diff between old template and user current to understand user customizations:
   - Modified rules or parameters
   - Added custom content
   - Removed sections

4. Merge: Apply new template changes to the user's version while preserving their customizations.
   The merge principle is:
   - **New sections from template**: Insert into user's version at the appropriate location
   - **User's custom additions**: Always preserve
   - **Conflicting modifications** (both template and user changed the same section):
     Prefer user's version but annotate with a comment about what the new template changed

5. Present merge result to user:

```
文件: {file_path}

从 {LATEST_VERSION} 合并的变更:
  + [list of new sections/rules merged in]

保留您的自定义内容:
  ✓ [list of user customizations preserved]

应用此合并？(apply/skip/show-diff)
```

User choices per file:
- `apply` — Write the merged version
- `skip` — Keep user's current version unchanged
- `show-diff` — Display the full diff, then ask again

#### 4d. DELETED files — User confirmation

If the new template removes a file that exists in the project:

```
文件 {file_path} 在新版本中已移除。
删除此文件？(yes/no)
```

If user declines, keep the file.

#### 4e. Memory files — Special handling

Memory files contain project-specific data and require extra care:

- **constitution.md**: Only merge new structural sections (new chapter headings, new rule
  categories). Never overwrite user-filled content within existing sections.
- **chain-topology.md**: If new template adds new table columns or sections, append them.
  Never overwrite existing module data or SLA entries.
- **incident-log.md**: NEVER overwrite. Only ensure the file exists. If missing, create
  from template.

---

### Phase 5: Finalize

**5a. Update version marker**

```bash
echo "{LATEST_VERSION}" > .specify/.version
```

**5b. Update file hashes**

Regenerate `.specify/.file-hashes` with SHA256 hashes of all template-origin files
in their new state (post-merge). This becomes the baseline for the next update.

**5c. Set script permissions (POSIX only)**

```bash
chmod +x .specify/scripts/bash/*.sh 2>/dev/null || true
```

**5d. Final report**

```
============================================================
更新完成: {CURRENT_VERSION} → {LATEST_VERSION}

已应用: {N} 个文件（{replaced} 个替换, {merged} 个合并, {new} 个新增）
已跳过: {M} 个文件（用户选择跳过）
已删除: {D} 个文件
已保留: {K} 个 memory 文件

备份位置: .specify/.backups/{backup-name}/
回滚命令: /speckit.update --rollback
============================================================
```

---

### Phase R: Rollback

When `$ARGUMENTS` contains `--rollback`:

**R1. List available backups**

```bash
ls -d .specify/.backups/*/ 2>/dev/null
```

If no backups exist:
```
没有可用的备份。
```
Exit.

Display available backups:
```
可用备份:
  1. v0.2.0-20250211-143000 (2025-02-11 14:30:00)
  2. v0.1.0-20250201-100000 (2025-02-01 10:00:00)

选择要恢复的备份 (输入编号):
```

**R2. Restore from backup**

Read `metadata.json` from the selected backup. Restore all files from the backup to their
original locations, overwriting current versions.

**R3. Update version marker**

```bash
echo "{restored_version}" > .specify/.version
```

**R4. Report**

```
============================================================
已回滚到: {restored_version}
恢复时间: {backup_timestamp}
恢复文件: {N} 个

注意: .specify/.file-hashes 已恢复到备份时的状态。
============================================================
```
