# Reading guide

These pages describe existing work. Reading them does not request execution
of simulations, analysis, fitting, transfers, or the commands they quote.

## Essential hand-off

- [Connected L2 results](results/connected_steps_5seeds_15_30pa.md): the main
  five-seed experiment, findings, limitations, and saved figures.
- [Prediction definitions](contracts/static_prediction.md): selected J/Q,
  provisional zero entries, measured quantities, and plot symbols.
- [Experiment registry](../data/registry.md): dataset locations and relevance;
  only the sections needed for the current task need reading.
- [Selected J](results/l2_rate_sweep_j.md) and [selected Q](results/l2_current_sweep_q.md):
  short summaries of the predictor inputs.

## Read only when relevant

- [Slide figure collection](../data/slide_assets/jq_prediction/README.md).
- [Connected experiment interface](contracts/connected_current_steps.md) and
  [open-loop definitions](contracts/open_loop_identification.md).
- [Connected analysis code](processing/connected_step_analysis.md) and
  [Q fitting code](processing/current_sweep_to_q.md): explanations and optional
  reproduction examples, not work requests.
- [Prioritized work inventory](plans/open_work.md): code changes, experiment
  candidates, decision status, and dependencies; suggestions are marked as such.
- [Known same-seed limitation](issues/same_seed_reproducibility.md).

Detailed execution history, old proposals, and reproduction logs are in
[archive/](archive/). They are not required context for ordinary results work.
[Source audits](reference/rate_sweep_sources.md) and the
[toy-model background](reference/rate_model_prototype.md) are optional references.
