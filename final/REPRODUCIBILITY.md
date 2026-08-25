# Reproduction guide

1. Read `FINAL_REVIEW.json` first. Publication is based on `status=pass` with `general_hilbert_problem_solved=false`.
2. Build the PDF from this directory with `pdflatex -interaction=nonstopmode -halt-on-error main.tex` twice.
3. Compare theorem/proposition statements in `main.tex` with `CLAIMS_AUDIT.json`; the proof dependency graph is `PROOF_DEPENDENCIES.json`.
4. Verify claim-bearing inputs against `SOURCE_MANIFEST.json` in an evidence checkout that provides the `math1/` and `math2/` roots. Hashes and byte sizes are the reviewed values.
5. The finite certificates remain scoped to the domains stated in `CLAIMS_AUDIT.json` and in the paper; program success alone is not used as a mathematical proof.

No cached third-party papers, virtual environments, private agent state, credentials, or raw bulk exploratory logs are redistributed in this public package. Upstream claim-bearing source files are identified by hash and path labels rather than bundled because no top-level redistribution license for the source campaign repositories was present in the evidence checkout.
