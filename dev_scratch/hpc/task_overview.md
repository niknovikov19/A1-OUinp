
## Current workflow

repo: https://github.com/niknovikov19/A1-OUinp/tree/netstim-bkg

### HPC

HPC workflow involves Slurm. The main code performs netpyne simulations. One single-sim master script run_exp.py. It is enriched with  experiment specifications from exp_configs. Corresponding reults are in sim_results. Most of results are huge and stored on HPC only. 

1-sim jobs are submitted via submit_single_slurm_local.sh
multi-sim (batch) jobs are submitted via submit_batch_slurm_local.sh, then batchtools spawn 1-sim jobs.

On HPC, there is a gateway "lethe" and slurm master "grid". Filesystem is shared between lethe, grid, and compute nodes.
To submit a job, one needs 2-hop ssh: local->lethe->grid. only slurm-related tasks are allowed on grid, anything else stricly prohibited.
On lethe, lightweight tasks are allowed, but carefully.

### Manual job submission

For job submission and monitoring, I have a separate terminal conencted via lethe to grid. I monitor slurm diagnostics and job logs (batchtools and simualtions). 
Many problems my appear: all HPC nodes hopelessly busy, HPC is down, ssh connection broken, batchtools didn't wait for the jobs to finish (e.g. failed to establish socket conenction with child sim jobs), jobs failed and batchtoold hang etc..

### VSCode-lethe setup

When I work with the repo manually, I usually connect my vscode directly to lethe via ssh and work with the HPC copy of the repo. One benefit is that vscode has access to all the files, even ignored by git. Small (< 1-minute) analyses that don't need much ram/cores, I do via vscode terminal (i.e. on lethe via ssh).
In vscode-lethe setup, I use AI minimally - mostly Colab for autocomplete and writing small code blocks (no execution!). AI creates unallowed load on lethe cpu/ram/disk.

### VSCode-WSL-Codex setup

For AI-heavy work, I use Codex in WSL on my local windows laptop, also via vscode. Codex works with a local WSL repo clone. Any write/execution access to HPC is prohibited. Codex doesn't run actual simulations, only smoke-tests. When a piece of work is complete, I commit and push to github. Then, on lethe, I pull from github. Finally, I submit it on grid. Sometimes I encounter minor bugs, do the bugfixes in vscode+lethe setup, and commit/push from lethe to gihub (I give a special name to such commits - "HPC sync").

In the vscode-WSL-codex local setup, I have necessary gitignore'd folders mounted from lethe via sshfs in read-only mode - so that I see them in vscode, and Codex sees them as well. I'm trying to limit the mounted scope (full sim_results are huge and deep) to avoid cluttering of Codex context and prevent Codex from doing excessive I/O with lethe. At the same time, I'm trying to reproduce the HPC repo structure, so that Codex could write and use scripts for analyzing mounted read-only data which (scripts) would be also usable directly on lethe. Usually, I mount several required subfolders of HPC sim_results onto the corresponding subfolders of WSL sim_results. To be extra clean, sometimes I instead mount these subfolders into dedicated HPC_mount WSL folder, and subfolders of WSL sim_results become symlinks to HPC_mount subfolders.

## Task: workflow automation with Codex

The manual routine described above is often tedious. I want to let my WSL Codex operate on HPC. Your task is to propose how to organize this setup, given the HPC restrictions.

### My proposal

- Keep the existing WSL file structure: local repo clone with missing folders added with read-only sshfs from lethe, as needed.
- Create a dedicated branch and allow WSL Codex to commit/push into it.
- Strictly prohibit Codex usage of ssh or sshfs. Keep read-only access to the folders pre-mounted with sshfs.
- For every action involving HPC, in a WSL folder without write permissions for Codex, create an sh-script that would ssh to lethe/grid and run the required commands there.
- Force codex to log its actions.

Actions made by non-writable WSL scripts:
- Pull the repo branch from github (lethe)
- Submit a job (grid)
- Check Slurm status (grid)
- Read batchtools/simulation logs (lethe)

To prevent frequent ssh reconnections, Slurm status could be monitored with "watch".
Logs could be monitored either with "watch" or directly from a read-only sshfs-mounted folder. Also, "tail" is often useful because logs tend to become huge.
