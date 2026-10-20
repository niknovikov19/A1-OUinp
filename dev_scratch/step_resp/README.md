# Static population-response prediction

Predict connected population-rate changes from open-loop J and Q measured in
the spiking model. Steps probe static endpoints; transient/oscillatory prediction
is outside the current scope.

- [Experiment registry](data/registry.md): datasets, scientific roles, selected
  versus preliminary results, figures, source paths, and former local names.
- [Documentation guide](doc/README.md): current contracts, processing recipes,
  completed results, open branches, deferred issues, and historical proposals.
- [Frozen prediction contract](doc/contracts/static_prediction.md): exact J/Q,
  provisional zeros, rate-change definitions, and plot symbols.
- [Latest connected results](doc/results/connected_steps_5seeds_15_30pa.md):
  five seeds, IT2/PV2 steps at ±15/±30 pA, with ordinary zero-input controls.

```text
step_resp/
├── code/                 Local processing and tests
├── data/registry.md      Tracked experiment catalogue
├── data/<dataset>/       Local inputs/results; ignored by git
├── data/_old/            Superseded preliminary datasets; retained
└── doc/                  Project documentation, organized by role
```

Use registry names rather than pilot numbers when discussing results.
Original HPC names, run IDs, saved matrix bytes, and provenance remain unchanged.
