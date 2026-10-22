# Path Reporter WS – tools

## How report types work
`docs/templates/bundle.json` lists every report type in `reportTypes` (name, `.dotx` layout, engine, schema, case templates).
The Home screen builds its cards from that list, so nothing in the app code has to change for a new type.

| engine | used by | schema |
|---|---|---|
| `histo` | Histopathology (+ Cancer CAP layout for CAP cases) | custom editor |
| `ihc` | Immunohistochemistry | custom editor |
| `generic` | Cytology/FNAC, PAP, Serous Effusion, Other Fluid, BM Aspiration, BM Biopsy, PS Comment, **and any new Basic Template** | detected from the `.dotx` by `schema.py` |

`schema.py` reads each table of the template (heading = first row) and makes editable parts:
`label` (a "Label:" paragraph – value written after it), `free` (empty cell – paragraphs, `**Label:**` prints bold),
`grow` (grid row with a label/unit – value written before a unit suffix such as " g/dL"), `dyn` (empty grid row – rows can be added/removed),
`gross` (Container / Gross / Sections block). The sign-off table is never touched. The app (`docs/js/docx.js` → `buildGenericDocx`)
writes values back with the same primitives Wajid's case-template builders use, so output is identical to the builder output.

## Adding a new Basic Template (e.g. "Frozen Section Template.dotx")
```bash
# 1. put the .dotx in the Basic Templates source folder (synced copy of OneDrive 'Report Templates/Basic Templates')
cp "Frozen Section Template.dotx" /workspace/casetemplates/basic/
# 2. (only if case templates for it exist in /workspace/casetemplates) rebuild the case cache
python3 tools/build_cache.py
#    and add a block to tools/report_types.json with "case_prefixes" pointing at the built-case folder
# 3. regenerate the bundle – a brand-new .dotx gets a 'generic' Home card automatically
python3 tools/gen_bundle.py
# 4. check the app's filler reproduces the builders exactly (optional, needs: cd tools/node && npm i)
node tools/node/verify_generic.js /tmp/vg && python3 tools/compare_docx.py /tmp/vg/manifest.json
# 5. bump CACHE in docs/sw.js, commit, push  → on the tablet: Templates & backup → Update templates
git add -A && git commit -m "Add Frozen Section report type" && git push
```
Optional: give it a nicer name/description/order by adding an entry to `tools/report_types.json`
(`{"id","name","template","engine":"generic","desc","case_prefixes":[...],"blank_on_pick":["CLINICAL DETAILS"]}`).
`blank_on_pick` sections are never overwritten when a case template is chosen (default: CLINICAL DETAILS).

## Other scripts
* `build_cache.py` – runs the case-template builders into `build_cache/` (not `casetemplates/out`, nothing uploaded).
* `gen_bundle.py` – histopathology diagnoses, gross library, IHC panels, report types → `docs/templates/`.
  `PRWS_BASIC_DIR=/path` uses another Basic Templates folder (for testing).
* `compare_docx.py` – compares two Word bodies (structure, text, bold).

## Sections, rows & sign-out (all report types, app v8)
`docs/js/docx.js` → `applyLayout()` runs after every engine (histo, ihc, generic) on the filled document:
* `R.secLayout.secs[]` = ordered sections `{src:<template heading>|null, type, heading, removed, del:[template row idx], add:[[cell text…]]}`.
  New sections use the 5 types from `Type of sections.docx` (OneDrive *Pathology Reporting Assets*): single 9638, two symmetrical 4819/4819,
  two asymmetrical 3212/6426, three 3212/3213/3213, four 2409/2410/2409/2410. Heading row: CAPS, bold, bottom sz 18; last row: bottom sz 4;
  one empty paragraph between tables; sectPr/header/footer untouched.
* `R.signout = {n:1|2, left:[lines], right:[lines]}` rewrites only the text of the last row of the End-of-Report table (widths 4223/1407/4224 kept).
* IndexedDB v2 adds store `doctors` (never touched by Update templates; included in backups). Tests: `test/e2e_layout.py`.
