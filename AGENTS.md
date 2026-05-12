# AGENTS.md

## Repository Workflow

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

Do not:

* Reformat unrelated files.
* Change unrelated dependencies.
* Modify lockfiles unless dependency changes require it.
* Delete files unless the task clearly requires it.
* Rename files unnecessarily.
* Mix unrelated refactors with feature work.
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
