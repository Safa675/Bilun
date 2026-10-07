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

The three workflows are Patients → authored patient 0003 → actual highest ranked
action's shared Source drawer; patient 0017 → actual materials pre-check → linked
Source if available; Rejection Queue → an actual matched authored rejection →
its patient/claim-scoped playbook. API patient, action, claim, clause, rejection
and corrective-step identities are checked against rendered content.
The playbook table is also scrolled horizontally to expose its corrective steps.

On the reviewed UI6/UI7 input, patient 0017 has a real NF1040 pre-check but its
action's `clause_ref` is null and Source is disabled. The second video therefore
ends at the actual pre-check; the command reports `partial` and exits **3** after
producing all three videos. It never invents a linked clause. Exit **0** means all
three requested paths completed; **1** means a safety/ownership/browser/tool
failure. Failed runs can leave unfinished videos for diagnosis; use a new output
directory after fixing an actual failure, and remove your failed output yourself.

Output must be a new directory outside every Git checkout, with no symlink
ancestors. Loopback HTTP origins only; no credentials or developer cookies.
Preflight refuses non-synthetic or unknown provenance before creating recorded
pages. Chat stays unopened and any accidental request is blocked and fails the
run. Browser errors and console warnings/errors fail, except the already known
GET `/api/frontend-config` 404, which is counted. One compact `run.txt` contains
commit, ownership identifiers, limitations, video dimensions and frame positions;
no full API payload or secrets are logged. WebMs and extracted representative
frames stay outside Git. Inspect those frames before sharing a recording.

Wave A remains subject to its real signed capability gate. Local recordings are
demonstration material, not clinical evidence, release admission or a signature.
This tool does not change or replace Phase0 capture, its baseline or parity guard.

Focused safety tests: `npx vitest run scripts/lib/recording-kit.test.mjs`.
Stop only your own servers and remove your own cache/build/dependencies afterward.
