# Repair completion checks and release the locked pilot

The user requested a small repair before the larger ownership/portability
refactor. Allow additional result files instead of requiring duplicate filename
lists to match. Check files on disk, repair final-record validation, and recover
run `thal-irem-fade-pilot-20261020b` without rerunning simulations.

Preserve the original request and final record. Keep existing staged pilot edits
separate. Prepare and test candidate helpers before the required manual promotion;
then use installed commands for recovery and release.
