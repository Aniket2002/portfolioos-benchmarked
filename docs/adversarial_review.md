# PortfolioOS v1 adversarial review

Read-only review of the initial implementation was followed by targeted fixes
and regression validation. This is a self-review, not independent certification.

## Critical/high checks

- Signals and covariance receive the exclusive price slice ending at t-1.
  Same-day rebalance and future-price mutations leave earlier holdings and risk
  estimates identical. Benchmark and external-signal mutations are tested too.
- Covariance annualization is applied once; tracking-error constraints use
  annual variance against the square of the annual TE cap.
- The solver's reported status is insufficient by itself: postprocessed holdings
  are independently checked. An adversarial mocked optimal-but-infeasible solver
  result is rejected. Fallback is explicit and subject to the same constraints.
- Strategy and benchmark drift after each realized return. Rebalance turnover
  uses drifted pre-trade holdings. Benchmark snapshots are applied only after
  their timestamp, and the equal-weight fallback is explicitly labelled.
- Costs use half-L1 turnover times bps/10,000 and are deducted once. Gross/net
  accounting, initial transition costs and benchmark frictionlessness are explicit.
- Security and Brinson-Fachler daily effects reconcile to gross active return.
  Subtracting costs reconciles net active returns. Zero-weight sector cases pass.
- Synthetic outputs are not presented as historical evidence. Fixed-universe,
  execution-timing and survivorship limitations are prominent.

No unresolved critical/high issue was found within the documented simulation
contract. The idealized previous-close fill is a real-world limitation; it is
not presented as an executable closing-auction strategy.

## Defects found and fixed

1. Required optimizer coefficients accepted null during configuration validation,
   failing later with an unhelpful modelling error. They now fail immediately
   with the offending setting named; regression tests cover all required fields.
2. Covariance symmetry validation inherited NumPy's relative tolerance, broader
   than the intended absolute threshold. It now uses zero relative tolerance.
3. Nonfinite covariance ridge/annualization and metric annualization were not
   explicitly rejected at their public function boundaries. They now raise
   validation errors; regression tests cover NaN/infinite inputs.
4. Notebook generation through the local shell damaged mathematical Unicode.
   Notebook formulas were corrected to portable ASCII and validated by execution.
5. Pandas plotting triggered Matplotlib deprecation warnings. Direct Matplotlib
   plotting removed the compatibility warning without changing calculated results.

These were input validation and presentation defects; the valid default demo's
portfolio accounting did not change as a result of the fixes.

## Output interpretation checks

All eight charts were visually inspected. Numeric outputs are finite, costs and
turnover nonnegative, holdings fully invested and rebalance caps satisfied.
Initial missing values in the 63-day rolling TE chart are the intended warmup.
The default demo has no undefined summary ratios. Solver message cells are blank
when no error occurs. Limits apply at rebalances; the largest drifted position
can exceed the target position cap. The synthetic strategy underperforms its
benchmark; no parameters were retuned to change that result.

Daily sector effects are arithmetic attribution, not multi-period linked
effects. Terminal IC is flagged because its period may be partial. Dependencies
are recorded in summary JSON to identify the environment behind each artifact.
