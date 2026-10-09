# Research outputs

`demo/` contains the deterministic **SYNTHETIC** mechanics demonstration.
It is not historical market evidence. Regenerate from the repository root:

```sh
python scripts/run_demo.py --config configs/demo.yaml
```

Other output directories, provider inputs and local caches are ignored. Never
commit downloaded market data. Charts and CSVs are generated together; summary
JSON records configuration and generator seed. Undefined metrics use JSON null.

`empirical_phase2/` preserves the initial historical execution failures.
`empirical_phase2_reviewed/` contains the frozen study, aggregate portfolio-return
ledgers, tables, eight research figures and verification evidence. These selected
derived artifacts are committed explicitly; raw provider prices/actions remain
under the ignored `data/` directory. See
[Phase 2 documentation](../docs/empirical_phase2.md).
