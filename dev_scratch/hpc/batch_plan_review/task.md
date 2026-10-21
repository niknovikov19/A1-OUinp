# Batch-plan contract and portability review

Requested 2026-10-20: assess replacing the submission-only child index and
duplicated batch completion lists with a complete plan written before any child
submission. Explain change size, consequences, required Gate A/B regression and
new testing, migration/recovery, and a path toward separating HPC-Codex from this
repository while retaining Slurm/BatchTools/NetPyNE support.

Deliver a concrete Markdown assessment. Do not change code, promote helpers,
modify protected records, launch jobs, or resume the interrupted pilot analysis.
Use local source, test, and gate documentation; distinguish verified behavior
from design proposals and unresolved choices.

Initial state: four existing staged files concern the pilot request, experiment
label, and pilot documentation. Preserve these changes. The previously run pilot
has four scheduler-completed children but an inconsistent failed final record;
its automation checkout cannot currently be released through the installed helper.
