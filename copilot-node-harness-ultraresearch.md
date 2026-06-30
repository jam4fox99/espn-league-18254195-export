# Node-only Coding Harness Through copilot-api

This is the sendable summary from the ultraresearch pass.

## Bottom Line

The model call already works through `copilot-api`; the missing piece is the coding-agent harness.

Try **SmallCode** first only if `copilot-api` supports OpenAI-compatible `POST /v1/chat/completions`. If only Anthropic-compatible `POST /v1/messages` works, skip SmallCode and build a small repo-local Node CLI around raw `fetch` or `@anthropic-ai/sdk`.

Nanocoder is the second off-the-shelf candidate. It supports Anthropic and OpenAI-compatible providers, subagents, file tools, shell, and MCP, but it has a larger dependency surface and needs a JPM DevShell install test.

## Commands

Start proxy:

```bat
cd /d "C:\Users\R767266\OneDrive - JPMorgan Chase\Documents\ccp"
npx copilot-api@latest start --account-type business --rate-limit 5 --wait --proxy-env
```

Smoke-test OpenAI-compatible route:

```js
const res = await fetch("http://localhost:4141/v1/chat/completions", {
  method: "POST",
  headers: {
    "content-type": "application/json",
    "authorization": "Bearer dummy"
  },
  body: JSON.stringify({
    model: "gpt-5-mini",
    messages: [{ role: "user", content: "Reply exactly OPENAI_PROXY_OK" }],
    max_tokens: 32
  })
});

console.log(res.status);
console.log(await res.text());
```

Run:

```bat
C:\Users\R767266\ds\tools\nodejs24\latest\node.exe smoke-openai.mjs
```

If it works, try SmallCode:

```bat
npm install smallcode@1.6.0 --ignore-scripts --omit=optional
set SMALLCODE_MODEL=gpt-5-mini
set SMALLCODE_BASE_URL=http://localhost:4141/v1
set SMALLCODE_API_KEY=dummy
set OPENAI_API_KEY=dummy
set OPENAI_COMPAT_API_KEY=dummy
C:\Users\R767266\ds\tools\nodejs24\latest\node.exe node_modules\smallcode\bin\smallcode.js --classic
```

## Decision

| Option | Decision |
| --- | --- |
| SmallCode | First try if `/v1/chat/completions` works. |
| Repo-local Node harness | Best strict path if only `/v1/messages` works. |
| Nanocoder | Second try if larger dependency tree is acceptable. |
| Claude Code | Reject on this JPM machine due managed settings. |
| OpenCode | Reject unless Bun or the binary is approved. |
| LazyCodex / OmO | Reject directly because Codex/OpenCode are unavailable. |

Full evidence lives in `/Users/jakemilken/Documents/MyGM/.omo/ultraresearch/20260623-120021-node-agent-harness/SYNTHESIS.md`.
