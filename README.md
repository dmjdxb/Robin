<p align="center">
  <img src="resources/robin-icon.svg" width="120" alt="Robin"/>
</p>

<h1 align="center">Robin</h1>
<p align="center"><em>Because every superhero needs a sidekick.</em></p>
<p align="center">A branded desktop AI agent by <strong>EnergyIR</strong>.</p>

---

Robin is a downloadable, one-click desktop assistant for everyday office work —
drafting and rewriting documents, parsing files, writing emails, brainstorming,
and light research — that reads and writes files in folders you grant, with
per-action consent. It is built for non-technical users: install it from the
EnergyIR website and start, no setup required.

Robin is powered by **DeepSeek V4 Pro via the Together AI API** (an
OpenAI-compatible cloud service hosted in the US). The model runs in Together
AI's cloud — not on your machine — while the agent and your files stay local.

## Download

Get the signed installer for your platform from
[**Releases**](https://github.com/dmjdxb/Robin/releases/latest):

| Platform | File |
|---|---|
| macOS (Apple Silicon + Intel) | `Robin-<version>-mac-<arch>.dmg` |
| Windows 10/11 | `Robin-Setup-<version>.exe` |
| Linux (best-effort) | `Robin-<version>-<arch>.AppImage` / `.deb` |

Each release publishes a **SHA-256 checksum** and an `electron-updater` feed, so
Robin updates itself in place. Verify the checksum before running.

## First run

1. Launch Robin.
2. Paste your **Together AI API key** ([get one here](https://api.together.xyz/settings/api-keys)). It is stored in your OS keychain — never in plaintext on disk.
3. Grant Robin its first folder.
4. Pick light or dark — Robin ships with both.
5. Give it a task.

The model is preconfigured (**DeepSeek V4 Pro**) and is not user-selectable by
design — there is nothing to choose, it just works.

## What Robin can do

- **Documents** — create and rewrite Markdown and `.docx`; parse files you point it at.
- **Email & drafting** — compose, summarise, and restructure.
- **Files** — read/write/create/move within folders you grant, with a file browser and edit previews.
- **Shell & code** — run commands and code, pinned to your working directory, with per-action approval.
- **Web** — fetch and search.
- **Connectors** — MCP servers (calendar, docs, and more) — curated set, opt-in.

### Trust & safety

- **Scoped access** — file/shell tools are confined to folders you grant; out-of-scope paths are rejected at the tool boundary.
- **Per-action consent** — every write / exec / network action prompts by default (Approve · Approve-for-session · Deny).
- **Global Stop** — halts the agent and reaps child processes.
- **Audit log** — an exportable record of tool calls and approvals.
- **Secrets in the OS keychain** — Keychain / Credential Manager / libsecret.
- **Honest data handling** — model inference goes to Together AI (US). See [docs/PRIVACY.md](docs/PRIVACY.md).

## Build from source

All packaging, signing, and publishing runs in CI — see
[`.github/workflows/release.yml`](.github/workflows/release.yml). To produce a
local desktop build:

```bash
npm install                 # installs the workspace (apps/desktop, web, …)
cd apps/desktop
npm run build               # type-check + bundle the renderer + Electron main
npx electron-builder --mac  # or --win / --linux
```

Push a tag (`v1.0.0`) to build, sign, and publish all platforms to Releases.

## Licence

Robin is a product of **EnergyIR**, released under the MIT License — see
[`LICENSE`](LICENSE). Robin's modifications and branding are © 2026 EnergyIR.
Robin is built on open-source software; the required upstream copyright and
permission notices are retained in [`LICENSE`](LICENSE) and
[docs/THIRD_PARTY_NOTICES.md](docs/THIRD_PARTY_NOTICES.md).
