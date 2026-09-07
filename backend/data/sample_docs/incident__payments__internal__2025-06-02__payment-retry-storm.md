# Incident Report INC-1077: Payment Retry Storm

Severity: SEV2
Service: SVC-PAY-01 (Payment Gateway)
Date: 2025-06-02
Duration: 22 minutes

## Summary
A misconfigured client-side retry policy caused a 6x spike in traffic
to the payment gateway, triggering rate limiting and cascading ERR-504
timeouts similar to INC-1042.

## Root Cause
Same underlying fragility as INC-1042: the connection pool health-check
fix from JIRA-4821 had not yet been deployed to the EU region, so the
pool again exhausted under load, this time triggered by a retry storm
rather than a failover.

## Resolution
Rolled back the client SDK retry policy; expedited JIRA-4821 rollout to
all regions.

## Customer Impact
Approximately 4,200 payment attempts delayed; no permanent failures.
