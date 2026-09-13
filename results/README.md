# Research outputs

`demo/` contains the deterministic **SYNTHETIC** mechanics demonstration.
It is not historical market evidence. Regenerate from the repository root:

```sh
python scripts/run_demo.py --config configs/demo.yaml
```

Other output directories, provider inputs and local caches are ignored. Never
commit downloaded market data. Charts and CSVs are generated together; summary
JSON records configuration and generator seed. Undefined metrics use JSON null.
