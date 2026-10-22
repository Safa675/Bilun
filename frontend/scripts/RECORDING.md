# Local UI workflow recording

Use an existing local production frontend/backend pair serving the committed
authored synthetic cohort in anonymous public billing mode. Install the existing
frontend dependencies with `npm ci`. Installed Chrome, system `ffmpeg` (libvpx-vp9)
and `ffprobe` are required. No new dependency or browser download is added.

From `frontend/`, one command records exactly three WebMs:

```bash
node scripts/record-workflows.mjs --base-url http://127.0.0.1:13008 \
  --out "$HOME/.cache/bilun-ui8-recordings/run-01"
```

Default locale is Turkish. `--locale en` selects English for that same single
batch; `--size 390x844` selects one phone CSS viewport instead of the default
1440x900. Each context uses actual device scale factor 2 and normal motion.
The command checks physical screenshot dimensions, encoded WebM dimensions and
extracted PNG dimensions (default 2880x1800); setting an option alone is not
treated as density proof. Native Chrome screencasting produced a padded,
CSS-sized image despite DPR 2 in this environment, so the script encodes actual
device-scale browser PNG frames at up to 16 captures/second with their elapsed
durations. It performs no resizing, cropping or padding. Temporary raw frames
are removed after encoding. Videos contain real browser output with no overlays,
amount edits or source/playbook substitutes. Meaningful steps settle and hold.

The three workflows are Patients → the `default_landing` patient → actual highest ranked
action's shared Source drawer; the `showcase_S5` patient → actual materials pre-check →
linked Source if available; Rejection Queue → an actual matched authored rejection →
its patient/claim-scoped playbook. The two patients are cohort roles read from
`data/synthetic/cohort_registry.json` (`scripts/lib/cohort-registry.mjs`), never ids.
API patient, action, claim, clause, rejection and corrective-step identities are
checked against rendered content. The playbook table is also scrolled horizontally to
expose its corrective steps.

**Known limit on the showcase cohort** (8 patients when this was checked, 12 patients with 16 bills now, patient 4 having three and patients 10 and 12 two; engine billing reports and the
registry, checked 2026-10-18): none of the three paths can complete there, because the
workflows were written for the retired 50-patient cohort. (1) The landing patient's top
ranked action has no `clause_ref` (only the S7 copay-exemption row has one, and it is not
its patient's top action), so there is no Source drawer to record. (2) No patient has a
`material_pre_auth` action: `materials.pre_auth_required` is empty for all 8, and S5's
materials findings are prose-bundling ones. (3) Until WP7 (2026-10-21) the cohort had no
MEDULA rejection event and the preflight refused ("Authored rejection queue unavailable").
Since WP7 `medula_rejection_events` holds one row: the rejection 0901 of S10, on the manual
haematocrit line of patient 12's ER bill, matched to the playbook entry
`0901_duplicate_procedure` (corrective steps in Turkish), so `selectRejection` finds a row
(not run with Playwright: paths (1) and (2) still stop the command before it records
anything). Making the first two workflows follow the showcase data (or adding a
pre-authorised material to a story) is a separate decision.

On the reviewed legacy UI6/UI7 input, the second patient had a real NF1040 pre-check but
its action's `clause_ref` was null and Source was disabled. That video ended at the
actual pre-check; the command reported `partial` and exited **3** after producing all
three videos. It never invents a linked clause. Exit **0** means all three requested
paths completed; **1** means a safety/ownership/browser/tool failure. Failed runs can
leave unfinished videos for diagnosis; use a new output directory after fixing an actual
failure, and remove your failed output yourself.

Output must be a new directory outside every Git checkout, with no symlink
ancestors. Loopback HTTP origins only; no credentials or developer cookies.
Preflight refuses non-synthetic or unknown provenance before creating recorded
pages. Chat stays unopened and any accidental request is blocked and fails the
run. Browser errors and console warnings/errors fail, except the already known
GET `/api/frontend-config` 404 and Chrome's "preloaded but not used" hint for the
self-hosted `/fonts/inter|fraunces/*.woff2` files (a memory-cache false alarm on
later pages; the fonts are loaded and in use), which are counted separately. One compact `run.txt` contains
commit, ownership identifiers, limitations, video dimensions and frame positions;
no full API payload or secrets are logged. WebMs and extracted representative
frames stay outside Git. Inspect those frames before sharing a recording.

Wave A remains subject to its real signed capability gate. Local recordings are
demonstration material, not clinical evidence, release admission or a signature.
This tool does not change or replace Phase0 capture, its baseline or parity guard.

Focused safety tests: `npx vitest run scripts/lib/recording-kit.test.mjs`.
Stop only your own servers and remove your own cache/build/dependencies afterward.
