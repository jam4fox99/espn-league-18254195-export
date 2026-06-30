# LazyCodex, OmO, And No-Codex Alternatives

## How LazyCodex Works

LazyCodex is not the model. It is an agent harness/plugin layer that sits on top of Codex.

Think of it like this:

```text
Codex App / Codex CLI
  + LazyCodex installer
  + OmO plugin
  + skills/hooks/agents
  + state files under .omo/
  = research -> plan -> execute workflows
```

On the original machine, the installed setup was:

```text
LazyCodex / OmO 4.13.0
Plugin name: omo@sisyphuslabs
```

The main workflow is:

```text
$omo:ultraresearch
  -> deeply researches/specs the project

$omo:ulw-plan
  -> turns research into an implementation plan

$omo:start-work
  -> executes the plan with Codex subagents/team threads
```

How it works internally:

- Skills are structured workflows like `ultraresearch`, `ulw-plan`, `start-work`, and `teammode`.
- Hooks watch Codex prompts/tool calls and load the right behavior.
- Agents/subagents are specialized Codex workers: researcher, planner, executor, reviewer, QA, etc.
- State/artifacts are written into `.omo/`, like research journals, plans, ledgers, team state, and evidence logs.
- Teammode can create real Codex App background threads so multiple workers can run in parallel.
- Insane-search / ultimate-browsing helps research hard-to-fetch public web pages, blocked pages, YouTube, Reddit, X, docs, etc.

Repos/links:

- LazyCodex repo: [github.com/code-yeongyu/lazycodex](https://github.com/code-yeongyu/lazycodex)
- Main OmO / oh-my-openagent repo: [github.com/code-yeongyu/oh-my-openagent](https://github.com/code-yeongyu/oh-my-openagent)
- LazyCodex install docs: [installation.md](https://github.com/code-yeongyu/lazycodex/blob/main/packages/web/content/docs/installation.md)
- OmO releases: [oh-my-openagent releases](https://github.com/code-yeongyu/oh-my-openagent/releases)
- Insane-search repo: [github.com/fivetaku/insane-search](https://github.com/fivetaku/insane-search)

To recreate it on another machine with Codex:

```bash
npx lazycodex-ai install --no-tui --codex-autonomous
```

Then restart Codex and run:

```bash
npx lazycodex-ai doctor
```

Then inside Codex, use prompts like:

```text
$omo:ultraresearch
Research and spec this project...
```

For a corporate machine, the important caution is policy: only install/use this if the company allows that codebase to be sent to the model/provider behind Codex or an approved proxy. The harness gives parallelism and orchestration; it does not solve data-governance issues by itself.

## If You Do Not Have Codex

If you do not have Codex, then LazyCodex is not the right target.

Use one of these instead.

## Option A: Use OmO / Oh My OpenAgent With OpenCode

This is the closest equivalent. LazyCodex is the Codex distribution of OmO; the broader project is Oh My OpenAgent, which also supports OpenCode. The docs describe OmO as a multi-agent orchestration harness for OpenCode, and note that `lazycodex-ai` is the Codex Light installer while the shared `omo` CLI defaults to OpenCode.

Install path:

```bash
bunx oh-my-openagent install --platform=opencode
```

or:

```bash
npx oh-my-openagent install --platform=opencode
```

Then verify:

```bash
bunx oh-my-openagent doctor
```

Repos:

- [Oh My OpenAgent](https://github.com/code-yeongyu/oh-my-openagent)
- [LazyCodex](https://github.com/code-yeongyu/lazycodex)
- [OpenCode overview docs in OmO](https://github.com/code-yeongyu/oh-my-openagent/blob/dev/docs/guide/overview.md)

## Option B: Build A Mini LazyCodex

If a corporate machine only has an approved LLM endpoint/proxy, you can recreate the pattern yourself:

```text
your-cli
  -> approved LLM API/proxy
  -> planner agent
  -> N worker agents
  -> shared SQLite/JSONL state
  -> git worktrees
  -> shell/test runner
  -> final verifier
```

The core commands would look like:

```bash
agent research "spec this feature" --workers 20
agent plan --from .agent/research/latest.md
agent work --plan .agent/plans/feature.md --workers 6 --worktrees
agent status
agent integrate
```

The key thing LazyCodex/OmO gives you is not secret model access. It gives you orchestration:

```text
ultraresearch = parallel research + source ledger + synthesis
ulw-plan      = decision-complete implementation plan
start-work    = execute plan with agents + evidence gates
teammode      = durable parallel workers/threads
```

You can reproduce that with any LLM calls if you implement the surrounding runtime.

For corporate use, the safe rule is: only route company code through an approved provider/proxy. Do not scrape Copilot extension internals or bypass company controls. If the proxy is approved and OpenAI-compatible, OpenCode/OmO may be the fastest route. If not, build a small local CLI around the proxy.
