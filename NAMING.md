# Project name — the one source of truth

**The project is `gui4gmns`.** One name, everywhere.

It is locked in the four places that cannot be ambiguous:

| Surface | Value |
|---|---|
| GitHub repository | [`asu-trans-ai-lab/gui4gmns`](https://github.com/asu-trans-ai-lab/gui4gmns) |
| PyPI package | `gui4gmns` |
| CLI command | `gui4gmns` |
| Python module | `gui4gmns` (`ai-gen/gui4gmns.py`) |

It belongs to the **`*4gmns` family** alongside `plot4gmns` · `path4gmns` · `osm2gmns`.

## History (why you may see other names)

```
NEXTA  ──►  NeXTA-X  ──►  gui4gmns
(legacy)    (interim)     (final, current)
```

- **NEXTA** — the original Windows-only **MFC GUI** (Network EXplorer for Traffic Analysis). It is the
  *predecessor* and remains a valid editor. Reference it **only as historical lineage** —
  e.g. *"gui4gmns is the cross-platform successor of the NEXTA GUI."* It is not this project.
- **NeXTA-X** — an **interim brand** used while the cross-platform rewrite was underway. **Deprecated as a
  name.** Anywhere it was used as the project/product name, the name is now **gui4gmns**.
- **gui4gmns** — the **final name**. Package, repo, CLI, module, and all human-facing branding.

## Policy (so collaborators stay in sync)

1. Call the project **gui4gmns** in all new docs, headings, slides, and descriptions.
2. Say **NEXTA** only when you mean the legacy GUI, and only as lineage ("successor to the NEXTA GUI").
3. Do **not** introduce **NeXTA-X** as a name in new material. Existing occurrences are being swept to gui4gmns.
4. **Viewer filenames are kept for stability**: `nexta_x.html` (web-lite), `web-gl/nexta_xgl.html`,
   `desktop-qt/nexta_qt.py`. These are the **gui4gmns viewers** — the `nexta_*` prefix is a filename, not a
   brand. Renaming them is optional cleanup, tracked separately (breaks in-code/in-doc path references).

_Last set: 2026-07-06._
