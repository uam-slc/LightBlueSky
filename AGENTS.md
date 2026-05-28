# AGENTS.md

# Project Context

This repository is for a low-altitude 3D flight simulation platform with an independent `FlightCore` package.

The current target architecture is:

- Internal runtime coordinate frame: local NED.
- FlightCore is the authoritative source for aircraft dynamics, kinematics, public phases, internal subphases, transition, back-transition, and landing behavior.
- Platform code provides WorldState, Runtime Store, CommandBus, MissionState, collision detection, recording, visualization adapters, and external APIs.
- User velocity commands are valid only in `NAV`.
- `TAKEOFF`, `LANDING`, and `TRANSITION` are managed phases controlled by FlightCore.
- `takeoff()` and `land()` are one-shot, uncancelable commands unless the user explicitly asks for an emergency override feature.
- `latest back-transition` for compound-wing and tiltrotor aircraft is a low-level FlightCore safety takeover. When the formula trigger surface is reached during landing, FlightCore must force the aircraft into the managed landing/back-transition flow even if waypoint or velocity commands remain unfinished.
- Default numerical integration is semi-implicit Euler. RK2/midpoint may be implemented as an optional high-accuracy validation mode.
- Runtime hot paths should use GPU-friendly SoA arrays. Pydantic is for config validation, not per-tick runtime state.
- Collision detection should use dynamics old/new state and acceleration-inflated Dynamic Swept AABB by default.

---

# Agent Operating Principles

For non-trivial coding tasks:

- Surface assumptions, ambiguity, and tradeoffs before editing. Ask when ambiguity could cause broad or irreversible changes.
- Prefer the smallest implementation that satisfies the request. Do not add speculative features, abstractions, configurability, or dependencies.
- Keep edits surgical. Every changed line should trace directly to the user's request.
- Match existing style and ownership boundaries even when a different style looks cleaner.
- Define success criteria and verification before or during implementation. For bug fixes, reproduce the issue first when practical; for refactors, verify behavior before and after.
- Remove only unused imports, variables, functions, files, or comments made obsolete by the current change. Mention unrelated cleanup opportunities instead of applying them.
- For trivial typo fixes, obvious one-line changes, and documentation-only edits, use judgment and avoid unnecessary ceremony.

---

# Codex Config Relationship

Use `config.toml` for machine-enforced permissions:

- filesystem read/write policy
- sensitive file deny rules
- shell/network domain allowlist
- web search mode

Use this `AGENTS.md` for project behavior:

- Git/GitHub workflow
- branch and commit policy
- preferred external repositories and documentation
- source reliability rules
- project architecture guardrails

Do not put long preferred GitHub repository lists into `config.toml` as executable settings. `config.toml` can allow `github.com`, but repository-level preference must be enforced here.

---

# External Source and Research Policy

Agents may use external sources only when relevant to the current task and allowed by `config.toml`.

General source priority:

1. Official documentation, standards, regulations, and primary project repositories.
2. Maintained open-source repositories with clear licenses and active issue/history context.
3. Peer-reviewed papers, technical reports, NASA/FAA/EASA/ICAO/Eurocontrol/JARUS/ASTM/RTCA/SAE sources.
4. Secondary tutorials, blog posts, forum threads, or examples only as supporting context.

Rules:

- Prefer official documentation over random examples.
- Prefer small, focused reference checks over broad web browsing.
- Do not copy substantial third-party code into this repository unless the user explicitly asks and license compatibility is checked.
- If adapting an algorithm from a repository or paper, summarize the source and keep the implementation original.
- Do not add a new runtime dependency just because a reference repository uses it. Ask or justify clearly.
- When a field, model, or algorithm is inferred from external material, document the assumption in project docs or code comments.
- If sources disagree, prefer aviation standards, official simulator documentation, or primary repository docs.

---

# Preferred External Repositories and Documentation

These sources are preferred references for architecture, validation, implementation patterns, and terminology. They are not automatic dependencies.

## ATM / UTM / Traffic / Aircraft Performance

- TUDelft-CNS-ATM/bluesky
- TUDelft-CNS-ATM/bluesky-gym
- junzis/openap
- junzis/pyModeS
- openskynetwork/opensky-api
- grvcTeam/gauss
- openutm/flight-blender
- utmimplementationus/getstarted

Use these for:

- air traffic flow
- ATM/UTM concepts
- route and trajectory logic
- conflict detection concepts
- ADS-B / Mode-S data handling
- aircraft performance envelopes

## Autopilot / Flight Control

- PX4/PX4-Autopilot
- ArduPilot/ardupilot
- paparazzi/paparazzi
- rosflight/rosflight
- rosflight/rosflight_ros_pkgs
- rosflight/rosplane
- MatrixPilot/MatrixPilot
- nextpilot/nextpilot-flight-control

Use these for:

- flight mode organization
- mission mode behavior
- MAVLink concepts
- fixed-wing, multirotor, VTOL, and helicopter control architecture
- failsafe and command handling patterns
- SITL/HITL interface concepts

Do not attempt to clone a real autopilot control stack into this project. This project uses reduced-order FlightCore models.

## Fixed-Wing / General Aviation / Flight Dynamics Models

- JSBSim-Team/jsbsim
- JSBSim-Team/jsbsim-reference-manual
- JSBSim-Team/aeromatic
- FlightGear/flightgear
- FlightGear/fgdata
- flight-test-engineering/PSim-RCAM
- sryu1/jsbgym
- JDatPNW/QPlane
- OpenVSP/OpenVSP

Use these for:

- fixed-wing FDM structure
- aircraft performance references
- general aviation aircraft examples
- 6-DoF comparison baselines
- aerodynamic parameter organization
- validation scenarios

## Helicopter / Rotorcraft

- ArduPilot/ardupilot
- paparazzi/paparazzi
- JSBSim-Team/jsbsim
- DanIsraelMalta/Helicopter-Simulation
- minsulander/helisharp
- NASA rotorcraft technical reports
- Search and Rescue II / sar2 references

Use these for:

- helicopter mode concepts
- rotorcraft flight dynamics references
- rotor / tail rotor / hover / forward-flight examples
- low-confidence code examples only after higher-quality sources have been checked

## Multirotor / UAV Simulation

- ntnu-arl/aerial_gym_simulator
- PegasusSimulator/PegasusSimulator
- uzh-rpg/flightmare
- ethz-asl/rotors_simulator
- learnsyslab/gym-pybullet-drones
- spencerfolk/rotorpy
- microsoft/AirSim
- iamaisim/ProjectAirSim
- PX4/jMAVSim

Use these for:

- multirotor simulation references
- RL environment patterns
- high-throughput simulation
- SITL comparison
- dynamics response validation
- sensor and visualization examples

## Nano UAV / Low-Level Flight Controllers

- bitcraze/crazyflie-firmware
- bitcraze/crazyflie-lib-python
- betaflight/betaflight
- iNavFlight/inav
- cleanflight/cleanflight
- uzh-rpg/agilicious

Use these for:

- low-level controller organization
- PID/rate loop patterns
- mixer concepts
- small UAV constraints
- agile flight examples

## VTOL / Compound-Wing / Tiltrotor

- byu-magicc/vtolsim
- PX4/PX4-Autopilot
- ArduPilot/ardupilot
- JSBSim-Team/jsbsim
- FlightGear/fgdata

Use these for:

- transition and back-transition concepts
- QuadPlane / VTOL phase logic
- tiltrotor and compound-wing reference behavior
- validation scenario design

---

# Repository Workflow

This repository is managed with Git, GitHub, Codex, and opencode.

GitHub `origin` is the central source of truth.

The user works on this repository across multiple devices and may use different AI coding tools on different machines.

All agents must follow the synchronization and branch workflow rules below.

---

# Core Rules

1. Always check Git state before editing.
2. Never edit directly on `main`, `master`, `develop`, or release branches unless the user explicitly asks.
3. Use one task branch per task.
4. Preserve all user changes.
5. Show `git diff` before committing.
6. Do not force-push unless the user explicitly asks.
7. Do not delete local or remote branches unless the user explicitly asks.
8. Never expose secrets, tokens, passwords, or SSH keys.
9. GitHub `origin` is always the synchronization source of truth.
10. Different devices and different AI tools may continue work on the same task branch.

---

# Security Rules

Never read, print, copy, modify, or store private credentials.

Forbidden content includes:

- SSH private keys
- GitHub tokens
- API keys
- Passwords
- `.env` secrets
- Cloud credentials
- Database credentials

Never write secrets into:

- `AGENTS.md`
- README files
- source code
- comments
- prompts
- logs
- commits

Use the user's local SSH authentication only.

If secrets are detected, stop and notify the user.

---

# Start-of-Task Checklist

Before editing files, run:

```bash
git status
git branch --show-current
git fetch origin
git pull --rebase
```

Then:

* If the working tree has uncommitted user changes, stop and ask before editing.
* If the current branch is `main`, `master`, `develop`, or a release branch, create a task branch before editing.
* If the repository is empty and the user explicitly asks for the initial setup, creating and pushing the initial commit to `main` is allowed.
* If a suitable task branch already exists, continue using it.
* If no suitable task branch exists, create one using the branch naming rules below.

---

# Branch Naming Rules

Branch names are based on the task, not the AI tool.

Codex and opencode may work on the same task branch at different times.

Use these branch patterns:

```text
docs/xxx
fix/xxx
feature/xxx
refactor/xxx
```

Examples:

```text
docs/add-agents
fix/login-timeout
feature/homepage
refactor/api-client
```

Rules:

* One task = one branch.
* The same branch may be continued from different devices or tools.
* Before continuing work on another device, always sync with GitHub first.
* Never work on the same branch simultaneously from multiple devices.
* Use lowercase English.
* Use hyphens `-` between words.
* Do not use Chinese characters.
* Keep branch names short and descriptive.

---

# Multi-Device Workflow

The user works across multiple devices.

GitHub `origin` is the mandatory synchronization point.

Before starting work on any device, always run:

```bash
git fetch origin
git pull --rebase
git status
```

Before leaving a device, always:

```bash
git status
git diff
git add -A
git commit -m "wip: short description"
git push
```

This ensures the next device can continue from the latest branch state safely.

If work should not be committed yet:

```bash
git stash push -m "wip: short description"
```

However, committing and pushing work-in-progress changes is preferred for multi-device continuity.

Never continue work on another device before syncing from GitHub.

---

# Natural Language Device-Switch Commands

The user may use natural language indicating they are leaving or switching devices.

Examples include:

```text
我要离开了
我要换电脑了
我准备去另一台设备继续
我要关机了
我要切换设备
I'm leaving this device
I'm switching devices
Continue later on another machine
```

When the user expresses this intent:

1. Run:

```bash
git status
git diff
```

2. Stage all relevant changes:

```bash
git add -A
```

3. Create a work-in-progress commit if needed:

```bash
git commit -m "wip: short description"
```

4. Push the current branch:

```bash
git push
```

Then summarize:

```text
Current branch:
Commit created:
Push status:
Safe to continue from another device.
```

---

# New Device Startup Workflow

When starting work on a new device, or when the user indicates they switched devices, examples include:

```text
我到新设备了
我在另一台电脑上
继续之前的工作
同步最新代码
I'm on another device now
Continue previous work
Sync latest changes
```

Automatically run:

```bash
git fetch origin
git pull --rebase
git status
```

Then summarize:

```text
Current branch:
Sync status:
Local status:
Ready to continue working.
```

---

# Editing Rules

Make minimal, focused changes.

Do:

* Follow the existing project style.
* Keep changes related to the current task.
* Prefer small, reviewable edits.
* Update documentation when behavior changes.
* Run the smallest relevant verification command.
* Make every changed line map back to the current task.
* Remove only code, imports, comments, or files made unused by your own change.

Do not:

* Reformat unrelated files.
* Improve adjacent code, comments, naming, or formatting just because you noticed it.
* Change unrelated dependencies.
* Modify lockfiles unless dependency changes require it.
* Delete files unless the task clearly requires it.
* Rename files unnecessarily.
* Mix unrelated refactors with feature work.
* Add speculative extension points, configuration, or abstractions for one-off needs.
* Remove pre-existing dead code unless the user asks for cleanup.
* Run destructive production, database, or deployment commands.

---

# Review Rules

After editing, run:

```bash
git status
git diff
```

Then report:

```text
Current branch:
Files changed:
Summary:
Verification:
Risks / follow-up:
```

---

# Commit Rules

Prefer small commits.

Suggested commit types:

```text
docs:
fix:
feat:
refactor:
chore:
wip:
```

Examples:

```text
docs: add agent workflow rules
fix: handle login timeout
feat: add settings page
refactor: simplify api client
wip: continue homepage implementation
```

Before committing:

```bash
git status
git diff
```

Stage only relevant files whenever practical.

---

# Push Rules

Push only the current task branch.

Never force-push unless the user explicitly approves.

Never delete remote branches unless the user explicitly approves.

After pushing, suggest opening a GitHub pull request when appropriate.

For the initial empty repository setup only, pushing `main` is allowed if the user explicitly requested the first push.

---

# Branch Completion Rules

After a task branch is finished:

1. Verify the feature or fix.
2. Show `git status`.
3. Show `git diff` or summarize the final changes.
4. Commit final changes.
5. Push the branch.
6. Recommend opening a pull request into `main`.

After the branch has been merged into `main`, recommend deleting the completed branch.

Do not delete branches automatically.

Recommended cleanup after merge:

```bash
git checkout main
git pull --rebase origin main
git branch -d branch-name
git push origin --delete branch-name
```

If the branch has not been merged, do not delete it.

---

# Parallel Agent Workflow

Do not let multiple AI agents edit the same local folder simultaneously.

Example of one local working folder:

```text
E:\GithubProjects\LightBlueSky
```

Do not run Codex and opencode at the same time inside this same folder.

This may cause:

* file overwrite conflicts
* inconsistent diffs
* corrupted working state
* accidental staging conflicts

If multiple AI agents are needed simultaneously, create separate local working folders.

Example:

```text
E:\GithubProjects\LightBlueSky-codex
E:\GithubProjects\LightBlueSky-opencode
```

Both folders may connect to the same GitHub repository, but should use separate branches.

---

# Stop Conditions

Stop and ask the user before continuing if:

* The working tree contains unknown uncommitted changes.
* The current branch is protected and no task branch exists.
* A command may overwrite, reset, delete, or discard work.
* Merge or rebase conflicts appear.
* Secrets or credentials are detected.
* A command requires force-push.
* A command affects production, deployment, billing, database state, or external services.
* The requested task is ambiguous and could cause broad unintended changes.

---

# Default Agent Response Format

When reporting back, use:

```text
Current branch:
Files changed:
Summary:
Verification:
Risks / follow-up:
```

Keep responses concise and action-oriented.

<!-- codex-tool-router:start -->

# Codex Tool Router: Academic Research + CodeGraph + draw.io

## 总原则

- 每次开始任务时，先判断任务属于：学术研究、代码库理解、图表/架构图生成，或组合任务。
- 优先使用最专业的 skill/MCP，避免直接用 grep/read 扫全仓库。
- 如果任务同时涉及多个领域，按“理解事实 → 结构化关系 → 产出文档/图”的顺序调用工具。
- 如果某个 MCP 或 skill 不可用，必须说明降级方案，不要假装已经调用。
- 不得修改 `codex_low_altitude_sim_config.toml`，除非用户明确授权。
- 不得覆盖 `AGENTS.md` 原有内容；只能维护本 marker 区块。

## 1. Academic Research Skills Codex 版

默认 skill：

```text
$academic-research-suite
```

### 自动调用场景

当用户请求以下任务时，优先调用 `$academic-research-suite`：

* 文献综述
* 系统综述
* 研究计划
* 研究问题设计
* 论文结构设计
* 论文写作
* 论文润色
* 审稿意见分析
* revision response
* related work
* methodology framing
* citation plan
* bibliography planning
* academic argument design

### 自动触发关键词

英文关键词：

```text
paper, academic, literature review, survey, systematic review, SLR, PRISMA,
research gap, citation, bibliography, peer review, revision, manuscript,
methodology, related work, research question
```

中文关键词：

```text
学术、论文、文献、综述、系统综述、开题、研究问题、研究空白、
引用、参考文献、审稿、返修、相关工作、方法论、研究计划
```

### 调用规则

* 先显式使用 `$academic-research-suite`。
* 如果需要真实论文、最新资料或引用，必须先检索或要求用户提供文献来源。
* 不得编造引用。
* 产出应包含：研究目标、检索/筛选策略、结构化提纲、证据表、写作/修改步骤。

### 不要调用的场景

* 单纯代码 bug
* 仓库架构分析
* 生成 draw.io 图
* 单文件代码解释
* 普通工程实现问题

除非这些任务服务于论文、研究报告或学术写作。

## 2. CodeGraph MCP

默认 MCP server：

```text
codegraph
```

### 自动调用场景

当用户请求以下任务时，优先使用 CodeGraph MCP：

* 理解当前代码库
* 分析模块边界
* 分析调用链
* 分析依赖关系
* 生成架构说明
* bug 定位
* 重构影响面分析
* 查找 API 入口
* 查找 symbol
* 跨文件逻辑追踪
* 类/函数关系分析
* 大范围代码阅读前的结构化索引

### 自动触发关键词

英文关键词：

```text
architecture, call graph, dependency graph, impact analysis, refactor,
where is implemented, codebase, module, symbol, AST, entrypoint,
implementation, dependency, control flow
```

中文关键词：

```text
代码库、调用链、依赖、架构、模块、重构、影响范围、入口、
实现在哪里、符号、函数关系、类关系、跨文件、项目结构
```

### 调用规则

* 在大范围读文件前，优先使用 CodeGraph MCP 查询 symbols、files、edges、call relationships。
* 如果 `.codegraph/` 不存在或索引过期，先运行：

```bash
codegraph init -i
```

或：

```bash
codegraph sync
```

* CodeGraph 给出候选文件后，再读取必要源文件。
* 做架构图时，先用 CodeGraph 提取节点和边，再交给 draw.io。
* 依赖 CodeGraph 的结论必须能追溯到具体文件、symbol 或调用关系。

### 不要调用的场景

* 单文件小修改
* 用户已经提供完整代码片段
* 纯学术写作
* 纯 draw.io XML 修复
* 不涉及当前代码库的问题

## 3. draw.io MCP + draw.io skill

默认 MCP server：

```text
drawio
```

默认 skill：

```text
$drawio
```

### 自动调用场景

当用户请求以下任务时，优先调用 draw.io MCP 或 `$drawio` skill：

* 画图
* 流程图
* 架构图
* 系统图
* UML
* ER 图
* 时序图
* 网络拓扑
* 依赖图
* draw.io 文件
* diagrams.net 文件
* 可编辑图
* `.drawio` 输出
* SVG/PNG/PDF 导出

### 自动触发关键词

英文关键词：

```text
draw.io, diagrams.net, diagram, flowchart, architecture diagram,
sequence diagram, UML, ERD, topology, editable diagram, mxGraphModel,
.drawio, SVG, PNG, PDF
```

中文关键词：

```text
画图、流程图、架构图、系统图、时序图、UML、ER图、拓扑图、
依赖图、可编辑图、draw.io、图表、导出图片
```

### 调用规则

* 需要长期维护的项目文档时，优先生成原生 `.drawio` 文件，不只生成图片。
* 需要预览、打开、搜索 draw.io shapes、从 Mermaid/CSV/XML 快速转换时，使用 draw.io MCP。
* 需要保存到仓库时，输出到 `docs/` 或用户指定目录。
* 生成 `.drawio` 时使用未压缩 XML。
* 必须检查 XML well-formed。
* 所有边必须有 geometry。
* 容器、节点、边必须有清晰 label。
* 如果图来自当前代码库，必须先用 CodeGraph 抽取真实模块/调用关系，再生成图。
* 如果图用于论文/研究报告，可先用 Academic Research Skills 组织图的论证目的，再用 draw.io 生成图。

### 不要调用的场景

* 用户只要 Mermaid 文本且明确不要 draw.io
* 用户只要自然语言解释，不需要图文件
* 用户只要修复代码 bug，且不涉及图示

## 4. 组合调用顺序

### 从代码库生成架构图

调用顺序：

1. 使用 CodeGraph MCP 分析模块、入口、调用链、依赖。
2. 读取少量关键文件验证 CodeGraph 结果。
3. 使用 `$drawio` skill 生成 `docs/architecture.drawio`。
4. 使用 draw.io MCP 打开或预览。
5. 输出图中节点和边的依据。

### 写技术论文或研究报告并包含系统图

调用顺序：

1. 使用 `$academic-research-suite` 规划论文结构和图表需求。
2. 如果系统来自当前仓库，用 CodeGraph MCP 抽取架构事实。
3. 使用 `$drawio` skill 生成论文/报告配图。
4. 在文档中说明图的含义和证据来源。

### 做代码库调研报告

调用顺序：

1. 使用 CodeGraph MCP 分析项目结构。
2. 使用 `$academic-research-suite` 将分析组织成研究式报告。
3. 使用 `$drawio` skill 生成架构图或流程图。
4. 输出报告、图文件路径和证据来源。

## 5. 强制验证

* 生成 `.drawio` 后必须检查 XML well-formed。
* 依赖 CodeGraph 的结论必须能追溯到具体文件、symbol 或调用关系。
* 学术写作中不得编造引用。
* MCP/skill 不可用时必须说明降级方案。
* 不得修改 `codex_low_altitude_sim_config.toml`。
* 不得覆盖 `AGENTS.md` 原有内容。

<!-- codex-tool-router:end -->

---

# Conversation Record Workflow

When the user asks to preserve a conversation outcome, maintain a topic record under `conversation-records/`.

Rules:

- Use one topic folder per coherent topic: `conversation-records/<topic-slug>/`.
- Name topic folders in lowercase English with hyphens, based on the conversation content.
- Keep the live Markdown record at `conversation-records/<topic-slug>/record.md`.
- When the topic is mature enough to present, update `conversation-records/<topic-slug>/record.html` from the Markdown record.
- Record only confirmed, positive, actionable decisions: what to do, what has been agreed, and what the current conclusion is.
- Keep the record focused on settled direction, implementation intent, success criteria, diagrams, and next steps.
- Use high-intensity Socratic questioning during the conversation to clarify goals, boundaries, success criteria, evidence, tradeoffs, and next action before treating a topic as settled.
- Update `record.md` when the user explicitly asks to add something to the record or uses an equivalent instruction.
- Prefer draw.io for illustrations. Store editable `.drawio` files in the same topic folder.
- Export a corresponding `.svg` from the `.drawio` file and commit it alongside.
- In `record.html`, embed the SVG with `<img src="<topic>.svg">` so the diagram is visible directly.
- Keep the link to the editable `.drawio` source below the image for future edits.
- Mermaid may be used as temporary or lightweight structure, while formal recorded diagrams should be captured as draw.io when useful.
