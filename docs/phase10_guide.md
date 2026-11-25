# Phase 10 | Final documentation and evidence

## Install safely

From the existing Task 6 root, in VS Code:

```bash
unzip -n ~/Downloads/Task_6_Phase_10_Final_Documentation.zip -d .
source .venv/bin/activate
python scripts/run_phase10.py --setup --live
```

Keep Phase 9 Docker containers running for the optional `--live` smoke check. `--setup` installs only document-generation dependencies. Run without `--live` if the stack is stopped; the check is marked NOT RUN. The launcher reads existing JSON and CSV reports, does not retrain, modify Phase 1–9, copy private keys, deploy cloud resources, or push to GitHub. It writes only new Phase 10 report and presentation paths; reruns replace generated Phase 10 outputs. Exit 1 means one or more automated evidence checks need review; documents are still generated. `--verify-only --live` checks without generating files.

## Open deliverables on macOS

```bash
open reports/phase10/technical_report.docx
open presentation/phase10/realestate_ai_presentation.pptx
```

Use VS Code Markdown preview (Cmd+Shift+V) for `docs/phase10_README.md`, `reports/phase10/model_card.md`, `reports/phase10/verification.md`, `docs/phase10_submission_checklist.md`, and portfolio files in `career/`. The bundled reference report and deck contain archived Phase 3 metrics, NOT the latest Mac metrics. Do not submit those in place of the generated local edition.

## Source publishing

Keep generated files, screenshots and private reports local. The professional README is `docs/phase10_README.md`, intentionally not replacing the original `README.md`. The Phase 9 git-stage helper stages source Markdown and Python; it may not include the new dependency file or career Markdown. Review staged paths and existing history before pushing. To publish reviewed Phase 10 source only, explicitly add the following paths (never `git add .`):

```bash
git rev-parse --show-toplevel
git add docs/phase10_README.md docs/phase10_guide.md docs/phase10_submission_checklist.md scripts/run_phase10.py tests/test_phase10.py requirements-phase10.txt
git diff --cached --stat
git diff --cached
```

Ensure the root is the Task 6 folder. After review, commit and push normally. If you want the final README on the repository landing page, manually replace the original after backing it up; this is optional and intentionally not automated. Do not publish portfolio materials without review. The existing Phase 9 staging allowlist may need an explicit update before future uses if you track the new requirements file. No workflow file is overwritten.

## Verify manually

The launcher checks recorded coverage, tests, benchmarks, model lineage report consistency, screenshot file signatures, local Git root/index/history paths, and optionally live Docker smoke. It does not verify screenshot contents, remote CI, remote current HEAD, authorization, official requirements or cloud hosting. Review the complete submission checklist. Screenshot 39 requires actual authorized HTTPS deployment if required; screenshot 40 is captured only after successful portal submission.
