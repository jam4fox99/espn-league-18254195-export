# Node-only coding-agent CLI handoff

Yes, there are existing GitHub projects close to this. The best clone/test candidates are:

1. **LLxprt Code**: https://github.com/vybestack/llxprt-code  
   Best feature fit for terminal coding agent + OpenAI-compatible providers + local models + subagents. Test first with `@vybestack/llxprt-code@0.9.3`.

2. **Local CLI**: https://github.com/HanSyngha/Local-CLI  
   Best "local/on-prem OpenAI-compatible coding agent" fit. Docs advertise Plan & Execute, file editing/searching, pipe mode, and subagents. Test first with `local-cli-agent@5.3.14`, but inspect its `postinstall` script before allowing lifecycle scripts.

3. **Nanocoder**: https://github.com/Nano-Collective/nanocoder  
   Good smaller local-first terminal coding agent. Supports local models and OpenAI-compatible APIs. Test first with `@nanocollective/nanocoder@1.28.0`.

Avoid treating these as corporate-safe until the exact package version passes JPM mirror and package scans. For strict Node-only/no-binary policy, use OpenCode, Qwen Code, Codex, and Claude Code as design references rather than install targets.

## Smoke-test commands

Run with `copilot-api` already listening at `http://localhost:4141/v1`.

```powershell
npm view local-cli-agent version engines bin scripts --json
npm view @vybestack/llxprt-code version engines bin scripts --json
npm view @nanocollective/nanocoder version engines bin scripts --json
npm view @continuedev/cli version engines bin scripts --json
```

Try LLxprt first:

```powershell
mkdir $env:USERPROFILE\llxprt-smoke
cd $env:USERPROFILE\llxprt-smoke
npm init -y
npm install @vybestack/llxprt-code@0.9.3 --ignore-scripts --omit=optional
npx llxprt
```

Inside `llxprt`:

```text
/provider openai
/baseurl http://localhost:4141/v1
/model <MODEL_FROM_COPILOT_API>
```

Then ask:

```text
Inspect this folder and write a one-paragraph summary of the files. Do not modify files.
```

If LLxprt fails, try Local CLI:

```powershell
mkdir $env:USERPROFILE\local-cli-smoke
cd $env:USERPROFILE\local-cli-smoke
npm init -y
npm install local-cli-agent@5.3.14 --ignore-scripts --omit=optional
npx local-cli
```

If Local CLI fails because `patch-yoga.js` was skipped, inspect that script before running lifecycle scripts.

## If all installs fail

Build a minimal Node harness instead:

- OpenAI-compatible client pointed at `http://localhost:4141/v1`
- file read/write/edit tools
- pure-JS search, no `rg`
- shell tool with approval gates
- task queue with max concurrency
- subagent worker prompts
- file-backed sessions and plans

That is likely easier than recreating OpenCode/Codex wholesale under locked corporate constraints.
