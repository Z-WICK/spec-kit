---
description: 分析当前项目并自动填充 .factory 工作流配置（AGENT.md、constitution、templates 中的占位符）
argument-hint: [--force 强制重新分析]
scripts:
  sh: scripts/bash/find-placeholders.sh
  ps: scripts/powershell/find-placeholders.ps1
---

## User Input

```text
$ARGUMENTS
```

## Spec-Init: Project-Aware Initialization

This command analyzes the current project's codebase and automatically fills in all
`[PLACEHOLDER]` tokens across the `.claude/` configuration files.

### Prerequisites

- `.claude/` directory must already exist in the project root (copy from the generic template)
- If `.claude/` does not exist, report error and instruct user to copy the template first

### Execution Steps

#### Phase 1: Project Discovery

Scan the project root to detect technology stack, build tools, and conventions.

**1a. Detect Language & Framework**

Check for these indicators (in priority order):

| File/Pattern | Stack Detection |
|-------------|----------------|
| `pom.xml` | Java + Maven |
| `build.gradle` / `build.gradle.kts` | Java/Kotlin + Gradle |
| `package.json` | Node.js (check for framework: Next.js, Express, NestJS, etc.) |
| `Cargo.toml` | Rust |
| `go.mod` | Go |
| `requirements.txt` / `pyproject.toml` / `setup.py` | Python (check for Django, Flask, FastAPI) |
| `Gemfile` | Ruby (check for Rails) |
| `*.csproj` / `*.sln` | C# / .NET |
| `composer.json` | PHP (check for Laravel, Symfony) |
| `Package.swift` | Swift |

Read the detected build file to extract:
- Language version
- Framework name and version
- Key dependencies (ORM, cache, auth, etc.)
- Build/test commands

**1b. Detect Build & Test Commands**

| Build Tool | BUILD_COMMAND | TEST_COMMAND |
|-----------|---------------|--------------|
| Maven | `mvn -DskipTests compile` | `mvn test` |
| Gradle | `./gradlew build -x test` | `./gradlew test` |
| npm | `npm run build` | `npm test` |
| yarn | `yarn build` | `yarn test` |
| pnpm | `pnpm build` | `pnpm test` |
| Cargo | `cargo build` | `cargo test` |
| Go | `go build ./...` | `go test ./...` |
| pip/poetry | N/A (interpreted) | `pytest` |
| dotnet | `dotnet build` | `dotnet test` |

Also check `package.json` scripts, `Makefile`, or CI config for custom commands.

**1c. Detect Database & Migration Tool**

| File/Pattern | Migration Tool |
|-------------|---------------|
| `src/main/resources/db/migration/V*.sql` | Flyway |
| `alembic/` or `alembic.ini` | Alembic |
| `prisma/schema.prisma` | Prisma Migrate |
| `db/migrate/` | Rails ActiveRecord |
| `migrations/` + Django | Django Migrations |
| `knexfile.*` | Knex.js |
| `drizzle.config.*` | Drizzle |
| `typeorm` in dependencies | TypeORM |
| `sequelize` in dependencies | Sequelize |

**1d. Detect Project Structure**

- Scan for `src/`, `app/`, `lib/`, `cmd/`, `internal/` directories
- Detect module/package structure (monolith vs monorepo vs microservices)
- Identify test directory (`src/test/`, `tests/`, `__tests__/`, `test/`, `*_test.go`)
- Detect config files (`application.yml`, `.env`, `config/`, etc.)

**1e. Detect Deployment**

| File/Pattern | Deploy Method |
|-------------|--------------|
| `docker-compose.yml` / `compose.yml` | Docker Compose |
| `Dockerfile` | Docker |
| `k8s/` or `kubernetes/` | Kubernetes |
| `serverless.yml` | Serverless Framework |
| `vercel.json` | Vercel |
| `fly.toml` | Fly.io |
| `Procfile` | Heroku |

**1f. Detect API Documentation**

| File/Pattern | Doc Framework |
|-------------|--------------|
| `springdoc` or `knife4j` in deps | knife4j / Swagger UI |
| `swagger` in deps | Swagger |
| `@nestjs/swagger` in deps | NestJS Swagger |
| FastAPI detected | FastAPI auto-docs |
| `openapi` config | OpenAPI |

**1g. Detect Existing Modules**

Scan the source tree for module/package boundaries:
- Java: packages under `src/main/java/**/modules/` or `**/domain/`
- Node: directories under `src/modules/` or `src/features/`
- Python: packages under `app/` or `src/`
- Go: packages under `internal/` or `pkg/`

Build a module dependency table by scanning imports/references between modules.

#### Phase 2: Fill Configuration Files

Using the discovered information, replace all `[PLACEHOLDER]` tokens.

**2a. Fill AGENT.md**

Replace:
- `[YOUR_STACK]` → detected stack string
- `[YOUR_BUILD_TOOL]` → detected build tool
- `[YOUR_PORT]` → detected port from config files
- `[LANGUAGE_VERSION_MANAGER]` → detected version manager (sdkman, nvm, pyenv, etc.)
- `[YOUR_START_COMMAND]` → detected start/deploy command
- `[LIST_YOUR_SERVICES]` → detected services from docker-compose or config
- `[PATH_TO_INIT_SQL_OR_MIGRATION]` → detected migration path
- `[PATH_TO_MAIN_CONFIG]` → detected main config file
- `[YOUR_LINT_COMMAND]` → detected lint command
- `[YOUR_TYPECHECK_COMMAND]` → detected typecheck command
- `[YOUR_TEST_COMMAND]` → detected test command
- `[YOUR_BUILD_COMMAND]` → detected build command

**2b. Fill Templates**

In all files under `speckit/templates/`:
- `[BUILD_COMMAND]` → detected build command
- `[TEST_COMMAND]` → detected test command
- `[PROJECT_STACK]` → detected stack string
- `[DOCS_REPO]` → ask user if not detectable (default: `../[ProjectName]_docs`)
- `[TEST_DIR]` → detected test directory

**2c. Fill Commands**

In all files under `commands/`:
- Same placeholder replacements as templates
- `[DEPLOY_COMMAND]` → detected deploy command
- `[SERVICE_LOG_COMMAND]` → detected log command

**2d. Fill Constitution**

In `speckit/memory/constitution.md`:
- Replace generic migration tool references with the detected specific tool
- Update `[DATE]` fields with today's date
- Set version to `1.0.0`

**2e. Fill Chain Topology**

In `speckit/memory/chain-topology.md`:
- Populate the Internal Modules table with discovered modules
- Fill in Key Dependencies based on import analysis
- Set up basic call chain patterns based on detected architecture

**2f. Initialize Incident Log**

In `speckit/memory/incident-log.md`:
- No placeholders to fill — this file is auto-populated by pipeline runs
- Verify the file exists; if missing, copy from template

**2g. Configure Subagents (Claude Code only)**

If the project uses Claude Code (`.claude/` directory exists):
- Verify `.claude/agents/impact-analyzer.md` exists (copied from template during init)
- Add project-specific context to the agent's prompt if needed (e.g., known module
  boundaries, SLA budgets from chain-topology.md)

#### Phase 3: Validation & Report

**3a. Verify all placeholders are filled**

Run `{SCRIPT}` to find any remaining unfilled placeholders in `.claude/` directory.

If any unfilled placeholders remain, list them and ask user for values.

**3b. Write version marker**

Write the current Spec-Kit version to `.specify/.version` for future update detection:

```
echo "<SPEC_KIT_VERSION>" > .specify/.version
```

Where `<SPEC_KIT_VERSION>` is read from the release package's `.specify/.version` file (if present),
or from the `speckit.version` command output, or set to `unknown` if neither is available.

**3c. Run constitution init**

Trigger `/constitution init` to finalize the constitution with project-specific principles.

**3d. Report**

```
============================================================
.factory initialized for: [PROJECT_NAME]

Detected Stack:
  Language:    [language + version]
  Framework:   [framework + version]
  Build:       [build command]
  Test:        [test command]
  Database:    [database + migration tool]
  Deploy:      [deploy method]
  API Docs:    [doc framework]

Modules discovered: [N modules]
  [module list with dependencies]

Files updated:
  - AGENT.md (project overview filled)
  - speckit/memory/constitution.md (principles customized)
  - speckit/memory/chain-topology.md (modules populated)
  - speckit/memory/incident-log.md (initialized)
  - speckit/templates/*.md (placeholders replaced)
  - commands/*.md (placeholders replaced)
  - .claude/agents/impact-analyzer.md (configured, Claude Code only)

Remaining manual steps:
  - [ ] Review AGENT.md for accuracy
  - [ ] Review constitution.md principles
  - [ ] Fill in SLA budgets in chain-topology.md
  - [ ] Set [DOCS_REPO] path if not auto-detected
  - [ ] Add any project-specific conventions

Next: /specify <feature description> to start your first feature
============================================================
```

### Error Handling

- If `.claude/` does not exist:
  ```
  ERROR: .claude/ directory not found.
  Copy the generic template to your project root first:
    cp -r /path/to/factory-template .factory
  ```

- If project type cannot be detected:
  - Report what was found and what's missing
  - Ask user to provide the missing information
  - Fill in what can be determined, leave rest as placeholders

- If `--force` flag provided:
  - Re-analyze everything and overwrite previous fills
  - Preserve any manual edits in constitution.md (merge, don't overwrite)
