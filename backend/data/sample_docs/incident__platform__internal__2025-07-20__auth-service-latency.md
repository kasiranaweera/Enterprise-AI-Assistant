# Incident Report INC-1090: Auth Service Latency Spike

Severity: SEV3
Service: SVC-AUTH-01 (Auth Service)
Date: 2025-07-20
Duration: 15 minutes

## Summary
Auth token validation latency increased from p99 40ms to p99 1.2s due
to a noisy-neighbor CPU contention issue on a shared Kubernetes node.

## Root Cause
No CPU limits were set on a batch analytics job that was co-located on
the same node pool as the auth service pods.

## Resolution
Applied CPU requests/limits to the batch job and moved it to a
dedicated node pool.

## Customer Impact
Minor login delays reported by ~300 users; no failed logins.
