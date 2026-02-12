<p align="right"><a href="./README.md">🇺🇸 English</a></p>

<div align="center">
    <img src="./media/logo_large.webp" alt="Spec Kit Logo" width="200" height="200"/>
    <h1>🌱 Spec Kit — Z-WICK 增强版分支</h1>
    <h3><em>通过子代理流水线，更快地构建高质量软件。</em></h3>
</div>

<p align="center">
    <strong><a href="https://github.com/github/spec-kit">github/spec-kit</a> 的增强分支，新增了额外命令、专用子代理和自动化 Bug 修复流水线。</strong>
</p>

<p align="center">
    <a href="https://github.com/Z-WICK/spec-kit/actions/workflows/release.yml"><img src="https://github.com/Z-WICK/spec-kit/actions/workflows/release.yml/badge.svg" alt="Release"/></a>
    <a href="https://github.com/Z-WICK/spec-kit/releases/latest"><img src="https://img.shields.io/github/v/release/Z-WICK/spec-kit" alt="Latest Release"/></a>
    <a href="https://github.com/Z-WICK/spec-kit/stargazers"><img src="https://img.shields.io/github/stars/Z-WICK/spec-kit?style=social" alt="GitHub stars"/></a>
    <a href="https://github.com/Z-WICK/spec-kit/blob/main/LICENSE"><img src="https://img.shields.io/github/license/Z-WICK/spec-kit" alt="License"/></a>
    <a href="https://github.com/github/spec-kit"><img src="https://img.shields.io/badge/upstream-github%2Fspec--kit-lightgrey" alt="Upstream"/></a>
</p>

---

## 本分支的增强功能

本分支在上游 [github/spec-kit](https://github.com/github/spec-kit) 的基础上扩展了以下功能：

- `/speckit.init` — 项目感知初始化，自动检测技术栈、构建工具和项目约定
- `/speckit.pipeline` — 从需求到测试代码的全自动流水线
- `/speckit.issue` — 结构化 GitHub Issue 创建，支持上下文自动检测
- `/speckit.fixbug` — **四阶段子代理流水线**（定位 → 分析 → 修复 → 验证），权限逐级提升
- `/speckit.update` — AI 驱动的增量模板更新
- `/speckit.optimize-constitution` — 将工程效率原则（模块拆分、分段写入、规划模型约束、任务并行化）增量追加到项目宪法中
- 7 个专用子代理：`bug-locator`、`bug-analyzer`、`bug-fixer`、`bug-verifier`、`log-analyzer`、`test-runner`、`impact-analyzer`

## 目录

- [🤔 什么是规格驱动开发？](#-什么是规格驱动开发)
- [⚡ 快速开始](#-快速开始)
- [🔗 子代理架构](#-子代理架构)
- [📽️ 视频概览](#️-视频概览)
- [🤖 支持的 AI 代理](#-支持的-ai-代理)
- [🔧 Specify CLI 参考](#-specify-cli-参考)
- [📚 核心理念](#-核心理念)
- [🌟 开发阶段](#-开发阶段)
- [🎯 实验目标](#-实验目标)
- [🔧 前置要求](#-前置要求)
- [📖 了解更多](#-了解更多)
- [📋 详细流程](#-详细流程)
- [🔍 故障排除](#-故障排除)
- [👥 维护者](#-维护者)
- [💬 支持](#-支持)
- [🙏 致谢](#-致谢)
- [📄 许可证](#-许可证)

## 🤔 什么是规格驱动开发？

规格驱动开发（Spec-Driven Development）**颠覆了**传统软件开发的模式。几十年来，代码一直是核心——规格说明只是我们搭建后就丢弃的脚手架，一旦"真正的工作"（编码）开始就不再需要了。规格驱动开发改变了这一点：**规格说明变得可执行**，直接生成可运行的实现，而不仅仅是指导开发。

## ⚡ 快速开始

### 1. 安装 Specify CLI

选择你偏好的安装方式：

#### 方式一：持久安装（推荐）

安装一次，随处使用：

```bash
uv tool install specify-cli --from git+https://github.com/Z-WICK/spec-kit.git
```

然后直接使用：

```bash
# 创建新项目
specify init <PROJECT_NAME>

# 或在现有项目中初始化
specify init . --ai claude
# 或
specify init --here --ai claude

# 检查已安装的工具
specify check
```

如需升级 Specify，请参阅[升级指南](./docs/upgrade.md)获取详细说明。快速升级：

```bash
uv tool install specify-cli --force --from git+https://github.com/Z-WICK/spec-kit.git
```

#### 方式二：一次性使用

无需安装，直接运行：

```bash
uvx --from git+https://github.com/Z-WICK/spec-kit.git specify init <PROJECT_NAME>
```

**持久安装的优势：**

- 工具保持安装状态，可在 PATH 中直接使用
- 无需创建 shell 别名
- 通过 `uv tool list`、`uv tool upgrade`、`uv tool uninstall` 更好地管理工具
- 更简洁的 shell 配置

### 2. 建立项目原则

在项目目录中启动你的 AI 助手。助手中已内置 `/speckit.*` 命令。

使用 **`/speckit.constitution`** 命令创建项目的治理原则和开发指南，这些原则将指导后续所有开发工作。

```bash
/speckit.constitution Create principles focused on code quality, testing standards, user experience consistency, and performance requirements
```

### 3. 创建规格说明

使用 **`/speckit.specify`** 命令描述你想要构建的内容。专注于**做什么**和**为什么**，而不是技术栈。

```bash
/speckit.specify Build an application that can help me organize my photos in separate photo albums. Albums are grouped by date and can be re-organized by dragging and dropping on the main page. Albums are never in other nested albums. Within each album, photos are previewed in a tile-like interface.
```

### 4. 创建技术实施计划

使用 **`/speckit.plan`** 命令提供你的技术栈和架构选择。

```bash
/speckit.plan The application uses Vite with minimal number of libraries. Use vanilla HTML, CSS, and JavaScript as much as possible. Images are not uploaded anywhere and metadata is stored in a local SQLite database.
```

### 5. 分解为任务

使用 **`/speckit.tasks`** 从实施计划中创建可执行的任务列表。

```bash
/speckit.tasks
```

### 6. 执行实施

使用 **`/speckit.implement`** 执行所有任务，按照计划构建你的功能。

```bash
/speckit.implement
```

如需详细的分步说明，请参阅我们的[完整指南](./spec-driven.md)。

## 🔗 子代理架构

增强命令将工作分派给专用子代理，每个子代理拥有限定的权限和单一职责。这使主对话保持简洁——各阶段之间只传递结构化报告。

### 开发流水线（`/speckit.pipeline`）

一条命令，从需求文档到测试通过、合并完成的代码：

```
Stage 0   Read Requirements     Parse external docs into structured summary
Stage 1   Specify + Worktree    Create isolated workspace, generate spec.md
Stage 2   Clarify               Auto-resolve ambiguities in spec
Stage 3   Plan                  Generate technical implementation plan
Stage 3.5 Impact Pre-Analysis   Lightweight risk assessment before coding
Stage 4   Tasks                 Generate executable task list (multi-module sharding)
          ── User Confirmation ──
Stage 5   Implement             Dispatch coding workers by complexity (low/medium/high)
Stage 5.5 Impact Analysis       Post-implementation risk analysis + knowledge feedback
Stage 6   Code Review           Structured review with auto-fix for CRITICAL/HIGH issues
Stage 7   Test                  Write and run tests per module
Stage 8   Merge                 Auto-merge to main with user confirmation
Stage 9   Rebuild + Docs        Deploy and verify
```

核心特性：检查点恢复（可从任何失败阶段继续）、多模块并行执行、迁移版本冲突检测，以及渐进式知识库积累。

### Bug 修复流水线（`/speckit.fixbug`）

```
Phase 1  Gather Context     fixbug (no sub-agent)
Phase 2  Log Analysis        → log-analyzer
Phase 3  Locate              → bug-locator        Read-only
Phase 4  Analyze             → bug-analyzer        Read-only
Phase 5  Fix                 → bug-fixer           Write access
Phase 5.5 Impact Analysis    → impact-analyzer     Read-only
Phase 6  Verify              → bug-verifier        Bash access
Phase 7  Report              fixbug (no sub-agent)
```

每个代理只接收前一阶段的结构化输出以及原始 Bug 上下文。代理可以独立替换、回滚或审计。

### 可用子代理

| Agent | 角色 | Tools | Model |
|-------|------|-------|-------|
| `bug-locator` | 定位 Bug 的源头 | Read, Grep, Glob | sonnet |
| `bug-analyzer` | 深度根因分析 | Read, Grep, Glob | sonnet |
| `bug-fixer` | 实施最小化修复 | Read, Edit, Write, Grep, Glob | sonnet |
| `bug-verifier` | 运行测试并验证修复 | Read, Bash, Grep, Glob | haiku |
| `log-analyzer` | 解析和分析日志文件 | Read, Grep, Glob, Bash | sonnet |
| `test-runner` | 执行测试套件 | Bash | haiku |
| `impact-analyzer` | 追踪调用链并评估变更影响 | Read, Grep, Glob, Bash | sonnet |

> [!NOTE]
> **Factory Droid 的模型继承**：使用 Factory Droid（`--ai droid`）时，子代理默认继承主会话的模型。如需使用自定义模型，请在 Droid 配置中通过 `model` 字段指定，格式为 `custom:` 前缀——例如 `model: custom:GLM-4.7-[duojie]-7`。未显式配置时，所有子代理将使用与父会话相同的模型，这可能增加成本或降低效率。

## 📽️ 视频概览

想看 Spec Kit 的实际演示？观看我们的[视频概览](https://www.youtube.com/watch?v=a9eR1xsfvHg&pp=0gcJCckJAYcqIYzv)！

[![Spec Kit video header](/media/spec-kit-video-header.jpg)](https://www.youtube.com/watch?v=a9eR1xsfvHg&pp=0gcJCckJAYcqIYzv)

## 🤖 支持的 AI 代理

| 代理                                                                                  | 支持状态 | 备注                                                                                                                                       |
| ------------------------------------------------------------------------------------ | ------- | ----------------------------------------------------------------------------------------------------------------------------------------- |
| [Qoder CLI](https://qoder.com/cli)                                                   | ✅      |                                                                                                                                           |
| [Amazon Q Developer CLI](https://aws.amazon.com/developer/learning/q-developer-cli/) | ⚠️      | Amazon Q Developer CLI [不支持](https://github.com/aws/amazon-q-developer-cli/issues/3064)斜杠命令的自定义参数。 |
| [Amp](https://ampcode.com/)                                                          | ✅      |                                                                                                                                           |
| [Auggie CLI](https://docs.augmentcode.com/cli/overview)                              | ✅      |                                                                                                                                           |
| [Claude Code](https://www.anthropic.com/claude-code)                                 | ✅      |                                                                                                                                           |
| [CodeBuddy CLI](https://www.codebuddy.ai/cli)                                        | ✅      |                                                                                                                                           |
| [Codex CLI](https://github.com/openai/codex)                                         | ✅      |                                                                                                                                           |
| [Cursor](https://cursor.sh/)                                                         | ✅      |                                                                                                                                           |
| [Gemini CLI](https://github.com/google-gemini/gemini-cli)                            | ✅      |                                                                                                                                           |
| [GitHub Copilot](https://code.visualstudio.com/)                                     | ✅      |                                                                                                                                           |
| [IBM Bob](https://www.ibm.com/products/bob)                                          | ✅      | 基于 IDE 的代理，支持斜杠命令                                                                                                |
| [Jules](https://jules.google.com/)                                                   | ✅      |                                                                                                                                           |
| [Kilo Code](https://github.com/Kilo-Org/kilocode)                                    | ✅      |                                                                                                                                           |
| [opencode](https://opencode.ai/)                                                     | ✅      |                                                                                                                                           |
| [Qwen Code](https://github.com/QwenLM/qwen-code)                                     | ✅      |                                                                                                                                           |
| [Roo Code](https://roocode.com/)                                                     | ✅      |                                                                                                                                           |
| [SHAI (OVHcloud)](https://github.com/ovh/shai)                                       | ✅      |                                                                                                                                           |
| [Windsurf](https://windsurf.com/)                                                    | ✅      |                                                                                                                                           |
| [Factory Droid](https://docs.factory.ai/cli/getting-started/quickstart) | ✅      | 子代理默认继承主会话模型；通过 `model: custom:<id>` 覆盖 |

## 🔧 Specify CLI 参考

`specify` 命令支持以下选项：

### 命令

| 命令    | 描述                                                                                                                                             |
| ------- | ------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `init`  | 从最新模板初始化一个新的 Specify 项目                                                                                                |
| `check` | 检查已安装的工具（`git`、`claude`、`gemini`、`code`/`code-insiders`、`cursor-agent`、`windsurf`、`qwen`、`opencode`、`codex`、`shai`、`qoder`） |

### `specify init` 参数与选项

| 参数/选项               | 类型     | 描述                                                                                                                                                                                  |
| ---------------------- | -------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `<project-name>`       | 参数     | 新项目目录的名称（使用 `--here` 时可选，或使用 `.` 表示当前目录）                                                                                           |
| `--ai`                 | 选项     | 使用的 AI 助手：`claude`、`gemini`、`copilot`、`cursor-agent`、`qwen`、`opencode`、`codex`、`windsurf`、`kilocode`、`auggie`、`roo`、`codebuddy`、`amp`、`shai`、`q`、`bob`、`qoder` 或 `droid` |
| `--script`             | 选项     | 脚本变体：`sh`（bash/zsh）或 `ps`（PowerShell）                                                                                                                  |
| `--ignore-agent-tools` | 标志     | 跳过 AI 代理工具（如 Claude Code）的检查                                                                                                                              |
| `--no-git`             | 标志     | 跳过 git 仓库初始化                                                                                                                                                           |
| `--here`               | 标志     | 在当前目录中初始化项目，而不是创建新目录                                                                                                                    |
| `--force`              | 标志     | 在当前目录初始化时强制合并/覆盖（跳过确认）                                                                                                             |
| `--skip-tls`           | 标志     | 跳过 SSL/TLS 验证（不推荐）                                                                                                                                  |
| `--debug`              | 标志     | 启用详细调试输出以便排查问题                                                                                                                                             |
| `--github-token`       | 选项     | 用于 API 请求的 GitHub 令牌（或设置 GH_TOKEN/GITHUB_TOKEN 环境变量）                                                                                                    |

### 示例

```bash
# Basic project initialization
specify init my-project

# Initialize with specific AI assistant
specify init my-project --ai claude

# Initialize with Cursor support
specify init my-project --ai cursor-agent

# Initialize with Qoder support
specify init my-project --ai qoder

# Initialize with Windsurf support
specify init my-project --ai windsurf

# Initialize with Amp support
specify init my-project --ai amp

# Initialize with SHAI support
specify init my-project --ai shai

# Initialize with IBM Bob support
specify init my-project --ai bob

# Initialize with Factory Droid support
specify init my-project --ai droid

# Initialize with PowerShell scripts (Windows/cross-platform)
specify init my-project --ai copilot --script ps

# Initialize in current directory
specify init . --ai copilot
# or use the --here flag
specify init --here --ai copilot

# Force merge into current (non-empty) directory without confirmation
specify init . --force --ai copilot
# or
specify init --here --force --ai copilot

# Skip git initialization
specify init my-project --ai gemini --no-git

# Enable debug output for troubleshooting
specify init my-project --ai claude --debug

# Use GitHub token for API requests (helpful for corporate environments)
specify init my-project --ai claude --github-token ghp_your_token_here

# Check system requirements
specify check
```

### 可用斜杠命令

运行 `specify init` 后，你的 AI 编码代理将可以使用以下斜杠命令进行结构化开发：

#### 核心命令

规格驱动开发工作流的基本命令：

| 命令                    | 描述                                                              |
| ----------------------- | ------------------------------------------------------------------------ |
| `/speckit.constitution` | 创建或更新项目治理原则和开发指南 |
| `/speckit.specify`      | 定义你想要构建的内容（需求和用户故事）            |
| `/speckit.plan`         | 使用你选择的技术栈创建技术实施计划        |
| `/speckit.tasks`        | 生成可执行的实施任务列表                        |
| `/speckit.implement`    | 执行所有任务，按照计划构建功能             |

#### 可选命令

用于增强质量和验证的附加命令：

| 命令                 | 描述                                                                                                                          |
| -------------------- | ------------------------------------------------------------------------------------------------------------------------------------ |
| `/speckit.clarify`   | 澄清规格中不明确的部分（建议在 `/speckit.plan` 之前使用；原名 `/quizme`）                                                |
| `/speckit.analyze`   | 跨制品一致性和覆盖率分析（在 `/speckit.tasks` 之后、`/speckit.implement` 之前运行）                             |
| `/speckit.checklist` | 生成自定义质量检查清单，验证需求的完整性、清晰度和一致性（类似于"英文的单元测试"） |

#### 增强命令

用于高级自动化和问题管理的扩展工作流命令：

| 命令                | 描述                                                                                                                                                      |
| ------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `/speckit.init`     | 项目感知初始化——分析你的代码库并自动填充所有配置占位符（技术栈、构建工具、约定等）          |
| `/speckit.pipeline` | 全自动流水线——读取外部需求文档并自主执行完整工作流（specify → clarify → plan → tasks → implement → test） |
| `/speckit.issue`    | 创建 GitHub Issue（Bug 报告、功能请求或任务），使用结构化模板并自动检测上下文                                         |
| `/speckit.fixbug`   | 四阶段 Bug 修复流水线——分派 `bug-locator` → `bug-analyzer` → `bug-fixer` → `bug-verifier`，权限逐级提升（read → write → bash）       |
| `/speckit.update`   | AI 驱动的增量模板更新——检测版本偏差并应用最新发布的变更                                                           |
| `/speckit.optimize-constitution` | 将 4 条工程效率原则增量追加到项目宪法中，支持去重检测 |

### 环境变量

| 变量              | 描述                                                                                                                                                                                                                                                                                            |
| ----------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `SPECIFY_FEATURE` | 为非 Git 仓库覆盖功能检测。设置为功能目录名称（例如 `001-photo-albums`），以便在不使用 Git 分支时处理特定功能。<br/>\*\*必须在使用 `/speckit.plan` 或后续命令之前，在代理的上下文中设置。 |

## 📚 核心理念

规格驱动开发是一个结构化流程，强调：

- **意图驱动开发**——规格说明先定义"做什么"，再考虑"怎么做"
- **丰富的规格创建**——使用护栏和组织原则
- **多步骤迭代**——而非从提示词一次性生成代码
- **深度依赖**先进 AI 模型的规格解读能力

## 🌟 开发阶段

| 阶段                                    | 重点                    | 关键活动                                                                                                                                     |
| ---------------------------------------- | ------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **从零到一开发**（"绿地项目"）    | 从零开始生成    | <ul><li>从高层需求出发</li><li>生成规格说明</li><li>规划实施步骤</li><li>构建生产就绪的应用</li></ul> |
| **创意探索**                 | 并行实现 | <ul><li>探索多样化方案</li><li>支持多种技术栈和架构</li><li>实验不同的用户体验模式</li></ul>                         |
| **迭代增强**（"棕地项目"） | 棕地现代化 | <ul><li>迭代添加功能</li><li>现代化遗留系统</li><li>适配流程</li></ul>                                                                |

## 🎯 实验目标

我们的研究和实验聚焦于：

### 技术无关性

- 使用多样化的技术栈创建应用
- 验证规格驱动开发是一种不绑定特定技术、编程语言或框架的流程

### 企业约束

- 展示关键任务应用的开发
- 纳入组织约束（云服务商、技术栈、工程实践）
- 支持企业设计系统和合规要求

### 以用户为中心的开发

- 为不同用户群体和偏好构建应用
- 支持多种开发方式（从 vibe-coding 到 AI 原生开发）

### 创意与迭代流程

- 验证并行实现探索的概念
- 提供健壮的迭代功能开发工作流
- 将流程扩展到升级和现代化任务

## 🔧 前置要求

- **Linux/macOS/Windows**
- [支持的](#-支持的-ai-代理) AI 编码代理
- [uv](https://docs.astral.sh/uv/) 包管理工具
- [Python 3.11+](https://www.python.org/downloads/)
- [Git](https://git-scm.com/downloads)

如果你在使用某个代理时遇到问题，请提交 Issue，以便我们改进集成。

## 📖 了解更多

- **[完整的规格驱动开发方法论](./spec-driven.md)** - 深入了解完整流程
- **[详细教程](#-详细流程)** - 分步实施指南

---

## 📋 详细流程

<details>
<summary>点击展开详细的分步教程</summary>

以下详细教程来自上游项目，保留英文原文。

You can use the Specify CLI to bootstrap your project, which will bring in the required artifacts in your environment. Run:

```bash
specify init <project_name>
```

Or initialize in the current directory:

```bash
specify init .
# or use the --here flag
specify init --here
# Skip confirmation when the directory already has files
specify init . --force
# or
specify init --here --force
```

![Specify CLI bootstrapping a new project in the terminal](./media/specify_cli.gif)

You will be prompted to select the AI agent you are using. You can also proactively specify it directly in the terminal:

```bash
specify init <project_name> --ai claude
specify init <project_name> --ai gemini
specify init <project_name> --ai copilot

# Or in current directory:
specify init . --ai claude
specify init . --ai codex

# or use --here flag
specify init --here --ai claude
specify init --here --ai codex

# Force merge into a non-empty current directory
specify init . --force --ai claude

# or
specify init --here --force --ai claude
```

The CLI will check if you have Claude Code, Gemini CLI, Cursor CLI, Qwen CLI, opencode, Codex CLI, Qoder CLI, or Amazon Q Developer CLI installed. If you do not, or you prefer to get the templates without checking for the right tools, use `--ignore-agent-tools` with your command:

```bash
specify init <project_name> --ai claude --ignore-agent-tools
```

### **STEP 1:** Establish project principles

Go to the project folder and run your AI agent. In our example, we're using `claude`.

![Bootstrapping Claude Code environment](./media/bootstrap-claude-code.gif)

You will know that things are configured correctly if you see the `/speckit.constitution`, `/speckit.specify`, `/speckit.plan`, `/speckit.tasks`, and `/speckit.implement` commands available.

The first step should be establishing your project's governing principles using the `/speckit.constitution` command. This helps ensure consistent decision-making throughout all subsequent development phases:

```text
/speckit.constitution Create principles focused on code quality, testing standards, user experience consistency, and performance requirements. Include governance for how these principles should guide technical decisions and implementation choices.
```

This step creates or updates the `.specify/memory/constitution.md` file with your project's foundational guidelines that the AI agent will reference during specification, planning, and implementation phases.

### **STEP 2:** Create project specifications

With your project principles established, you can now create the functional specifications. Use the `/speckit.specify` command and then provide the concrete requirements for the project you want to develop.

> [!IMPORTANT]
> Be as explicit as possible about *what* you are trying to build and *why*. **Do not focus on the tech stack at this point**.

An example prompt:

```text
Develop Taskify, a team productivity platform. It should allow users to create projects, add team members,
assign tasks, comment and move tasks between boards in Kanban style. In this initial phase for this feature,
let's call it "Create Taskify," let's have multiple users but the users will be declared ahead of time, predefined.
I want five users in two different categories, one product manager and four engineers. Let's create three
different sample projects. Let's have the standard Kanban columns for the status of each task, such as "To Do,"
"In Progress," "In Review," and "Done." There will be no login for this application as this is just the very
first testing thing to ensure that our basic features are set up. For each task in the UI for a task card,
you should be able to change the current status of the task between the different columns in the Kanban work board.
You should be able to leave an unlimited number of comments for a particular card. You should be able to, from that task
card, assign one of the valid users. When you first launch Taskify, it's going to give you a list of the five users to pick
from. There will be no password required. When you click on a user, you go into the main view, which displays the list of
projects. When you click on a project, you open the Kanban board for that project. You're going to see the columns.
You'll be able to drag and drop cards back and forth between different columns. You will see any cards that are
assigned to you, the currently logged in user, in a different color from all the other ones, so you can quickly
see yours. You can edit any comments that you make, but you can't edit comments that other people made. You can
delete any comments that you made, but you can't delete comments anybody else made.
```

After this prompt is entered, you should see Claude Code kick off the planning and spec drafting process. Claude Code will also trigger some of the built-in scripts to set up the repository.

Once this step is completed, you should have a new branch created (e.g., `001-create-taskify`), as well as a new specification in the `specs/001-create-taskify` directory.

The produced specification should contain a set of user stories and functional requirements, as defined in the template.

At this stage, your project folder contents should resemble the following:

```text
└── .specify
    ├── memory
    │  └── constitution.md
    ├── scripts
    │  ├── check-prerequisites.sh
    │  ├── common.sh
    │  ├── create-new-feature.sh
    │  ├── setup-plan.sh
    │  └── update-claude-md.sh
    ├── specs
    │  └── 001-create-taskify
    │      └── spec.md
    └── templates
        ├── plan-template.md
        ├── spec-template.md
        └── tasks-template.md
```

### **STEP 3:** Functional specification clarification (required before planning)

With the baseline specification created, you can go ahead and clarify any of the requirements that were not captured properly within the first shot attempt.

You should run the structured clarification workflow **before** creating a technical plan to reduce rework downstream.

Preferred order:

1. Use `/speckit.clarify` (structured) – sequential, coverage-based questioning that records answers in a Clarifications section.
2. Optionally follow up with ad-hoc free-form refinement if something still feels vague.

If you intentionally want to skip clarification (e.g., spike or exploratory prototype), explicitly state that so the agent doesn't block on missing clarifications.

Example free-form refinement prompt (after `/speckit.clarify` if still needed):

```text
For each sample project or project that you create there should be a variable number of tasks between 5 and 15
tasks for each one randomly distributed into different states of completion. Make sure that there's at least
one task in each stage of completion.
```

You should also ask Claude Code to validate the **Review & Acceptance Checklist**, checking off the things that are validated/pass the requirements, and leave the ones that are not unchecked. The following prompt can be used:

```text
Read the review and acceptance checklist, and check off each item in the checklist if the feature spec meets the criteria. Leave it empty if it does not.
```

It's important to use the interaction with Claude Code as an opportunity to clarify and ask questions around the specification - **do not treat its first attempt as final**.

### **STEP 4:** Generate a plan

You can now be specific about the tech stack and other technical requirements. You can use the `/speckit.plan` command that is built into the project template with a prompt like this:

```text
We are going to generate this using .NET Aspire, using Postgres as the database. The frontend should use
Blazor server with drag-and-drop task boards, real-time updates. There should be a REST API created with a projects API,
tasks API, and a notifications API.
```

The output of this step will include a number of implementation detail documents, with your directory tree resembling this:

```text
.
├── CLAUDE.md
├── memory
│  └── constitution.md
├── scripts
│  ├── check-prerequisites.sh
│  ├── common.sh
│  ├── create-new-feature.sh
│  ├── setup-plan.sh
│  └── update-claude-md.sh
├── specs
│  └── 001-create-taskify
│      ├── contracts
│      │  ├── api-spec.json
│      │  └── signalr-spec.md
│      ├── data-model.md
│      ├── plan.md
│      ├── quickstart.md
│      ├── research.md
│      └── spec.md
└── templates
    ├── CLAUDE-template.md
    ├── plan-template.md
    ├── spec-template.md
    └── tasks-template.md
```

Check the `research.md` document to ensure that the right tech stack is used, based on your instructions. You can ask Claude Code to refine it if any of the components stand out, or even have it check the locally-installed version of the platform/framework you want to use (e.g., .NET).

Additionally, you might want to ask Claude Code to research details about the chosen tech stack if it's something that is rapidly changing (e.g., .NET Aspire, JS frameworks), with a prompt like this:

```text
I want you to go through the implementation plan and implementation details, looking for areas that could
benefit from additional research as .NET Aspire is a rapidly changing library. For those areas that you identify that
require further research, I want you to update the research document with additional details about the specific
versions that we are going to be using in this Taskify application and spawn parallel research tasks to clarify
any details using research from the web.
```

During this process, you might find that Claude Code gets stuck researching the wrong thing - you can help nudge it in the right direction with a prompt like this:

```text
I think we need to break this down into a series of steps. First, identify a list of tasks
that you would need to do during implementation that you're not sure of or would benefit
from further research. Write down a list of those tasks. And then for each one of these tasks,
I want you to spin up a separate research task so that the net results is we are researching
all of those very specific tasks in parallel. What I saw you doing was it looks like you were
researching .NET Aspire in general and I don't think that's gonna do much for us in this case.
That's way too untargeted research. The research needs to help you solve a specific targeted question.
```

> [!NOTE]
> Claude Code might be over-eager and add components that you did not ask for. Ask it to clarify the rationale and the source of the change.

### **STEP 5:** Have Claude Code validate the plan

With the plan in place, you should have Claude Code run through it to make sure that there are no missing pieces. You can use a prompt like this:

```text
Now I want you to go and audit the implementation plan and the implementation detail files.
Read through it with an eye on determining whether or not there is a sequence of tasks that you need
to be doing that are obvious from reading this. Because I don't know if there's enough here. For example,
when I look at the core implementation, it would be useful to reference the appropriate places in the implementation
details where it can find the information as it walks through each step in the core implementation or in the refinement.
```

This helps refine the implementation plan and helps you avoid potential blind spots that Claude Code missed in its planning cycle. Once the initial refinement pass is complete, ask Claude Code to go through the checklist once more before you can get to the implementation.

You can also ask Claude Code (if you have the [GitHub CLI](https://docs.github.com/en/github-cli/github-cli) installed) to go ahead and create a pull request from your current branch to `main` with a detailed description, to make sure that the effort is properly tracked.

> [!NOTE]
> Before you have the agent implement it, it's also worth prompting Claude Code to cross-check the details to see if there are any over-engineered pieces (remember - it can be over-eager). If over-engineered components or decisions exist, you can ask Claude Code to resolve them. Ensure that Claude Code follows the [constitution](base/memory/constitution.md) as the foundational piece that it must adhere to when establishing the plan.

### **STEP 6:** Generate task breakdown with /speckit.tasks

With the implementation plan validated, you can now break down the plan into specific, actionable tasks that can be executed in the correct order. Use the `/speckit.tasks` command to automatically generate a detailed task breakdown from your implementation plan:

```text
/speckit.tasks
```

This step creates a `tasks.md` file in your feature specification directory that contains:

- **Task breakdown organized by user story** - Each user story becomes a separate implementation phase with its own set of tasks
- **Dependency management** - Tasks are ordered to respect dependencies between components (e.g., models before services, services before endpoints)
- **Parallel execution markers** - Tasks that can run in parallel are marked with `[P]` to optimize development workflow
- **File path specifications** - Each task includes the exact file paths where implementation should occur
- **Test-driven development structure** - If tests are requested, test tasks are included and ordered to be written before implementation
- **Checkpoint validation** - Each user story phase includes checkpoints to validate independent functionality

The generated tasks.md provides a clear roadmap for the `/speckit.implement` command, ensuring systematic implementation that maintains code quality and allows for incremental delivery of user stories.

### **STEP 7:** Implementation

Once ready, use the `/speckit.implement` command to execute your implementation plan:

```text
/speckit.implement
```

The `/speckit.implement` command will:

- Validate that all prerequisites are in place (constitution, spec, plan, and tasks)
- Parse the task breakdown from `tasks.md`
- Execute tasks in the correct order, respecting dependencies and parallel execution markers
- Follow the TDD approach defined in your task plan
- Provide progress updates and handle errors appropriately

> [!IMPORTANT]
> The AI agent will execute local CLI commands (such as `dotnet`, `npm`, etc.) - make sure you have the required tools installed on your machine.

Once the implementation is complete, test the application and resolve any runtime errors that may not be visible in CLI logs (e.g., browser console errors). You can copy and paste such errors back to your AI agent for resolution.

</details>

---

## 🔍 故障排除

### Linux 上的 Git 凭据管理器

如果你在 Linux 上遇到 Git 认证问题，可以安装 Git Credential Manager：

```bash
#!/usr/bin/env bash
set -e
echo "Downloading Git Credential Manager v2.6.1..."
wget https://github.com/git-ecosystem/git-credential-manager/releases/download/v2.6.1/gcm-linux_amd64.2.6.1.deb
echo "Installing Git Credential Manager..."
sudo dpkg -i gcm-linux_amd64.2.6.1.deb
echo "Configuring Git to use GCM..."
git config --global credential.helper manager
echo "Cleaning up..."
rm gcm-linux_amd64.2.6.1.deb
```

## 👥 维护者

**上游（[github/spec-kit](https://github.com/github/spec-kit)）：**
- Den Delimarsky ([@localden](https://github.com/localden))
- John Lam ([@jflam](https://github.com/jflam))

**本分支：**
- [@Z-WICK](https://github.com/Z-WICK)

## 💬 支持

如遇本分支特有的问题（增强命令、子代理、流水线），请在 [Z-WICK/spec-kit](https://github.com/Z-WICK/spec-kit/issues/new) 提交 Issue。
如遇上游问题，请前往 [github/spec-kit](https://github.com/github/spec-kit/issues/new)。

## 🙏 致谢

本项目深受 [John Lam](https://github.com/jflam) 的工作和研究的影响，并以此为基础。

## 📄 许可证

本项目基于 MIT 开源许可证授权。完整条款请参阅 [LICENSE](./LICENSE) 文件。
