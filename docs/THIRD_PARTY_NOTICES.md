# Third-Party Notices

Robin by EnergyIR incorporates open-source software. The principal components
and their licences are listed below. This file is referenced from the in-app
**Settings → About & Licences** screen and from `LICENSE`.

## Upstream base

- **Hermes Agent** — © Nous Research — MIT License. Robin is built on Hermes
  Agent; the full MIT copyright and permission notice is retained verbatim in
  the repository `LICENSE` file. Robin is independent of, and not endorsed by,
  Nous Research.

## Runtime / frameworks

| Component | Licence |
|---|---|
| Electron | MIT |
| Node.js | MIT-style (see Node.js licence) |
| React / React DOM | MIT |
| Vite | MIT |
| Python (CPython) | PSF License |

## Model provider

- **DeepSeek V4 Pro** is accessed through the **Together AI** API. The model and
  the inference service are operated by their respective owners under their own
  terms; they are not redistributed with Robin.

## Generating a full inventory

A complete, version-pinned dependency licence inventory is produced at build
time from `package-lock.json` / `uv.lock`. To regenerate locally:

```bash
npx license-checker --production --summary    # Node dependencies
pip-licenses                                   # Python dependencies
```

If you redistribute Robin, include this file and the retained MIT notice in
`LICENSE`, as those licences require.
