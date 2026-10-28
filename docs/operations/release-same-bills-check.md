# Same-bills check before a release

One idea kept from the strict release lane (deleted on 2026-10-28; the git tag `archive/strict-lane` holds it): **before a release, run the new code on the same bills as the running code and list every patient whose totals move.** A release meant to change no number lists nobody. A release meant to change numbers lists exactly the patients it was meant to change, each with the old and the new amount, and nobody else.

## Today

Bilun is pre-revenue and runs on synthetic data, so a moved total breaks the demo for minutes, and the PR's CI is the full gate. Every package that touches the engine dumps the S1–S8 showcase reports (16 reports: 8 stories, copay exempt and not) and the all-bill report before and after the change and compares the dumps byte for byte (`cmp`, with the sha256 written in the package notes). The dump script is a scratch file outside the repository.

## Once real customers exist

Then it is worth a script of about 100 lines in the repository:

1. Build the reports of both commits from one fixed input: the committed demo first, then the customer's own bills, on the machine that already holds them.
2. Compare per patient and per bill the headline fields the API serves (`total_recoverable_try`, `audit_exposure_try`, `sgk_uplift_try`, `action_count`).
3. Print one row per moved value: patient, bill, field, old, new, difference. Fail when a patient moves that the release notes do not name.

It prints identifiers and amounts only and writes nothing into the repository: customer bills never leave the machine they are on (KVKK).
