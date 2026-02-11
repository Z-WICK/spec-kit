# Chain Topology

Project-wide module dependency map and call chain patterns.
Auto-populated by `/speckit.init` and updated by pipeline impact analysis.

## Internal Modules

| Module | Path | Depends On | Depended By |
|--------|------|------------|-------------|
| [MODULE_NAME] | [MODULE_PATH] | [DEPENDENCIES] | [DEPENDENTS] |

## Call Chain Patterns

<!-- Discovered call chains from impact analysis runs -->
<!-- Format: Caller → Callee (protocol, latency budget) -->

## SLA Budgets

<!-- Observed or target SLA data points -->
<!-- Format: Chain | P50 | P99 | Budget | Source -->

## External Dependencies

| Service | Protocol | Timeout | Fallback |
|---------|----------|---------|----------|
| [SERVICE_NAME] | [HTTP/gRPC/MQ] | [TIMEOUT_MS] | [FALLBACK_STRATEGY] |
