# Incident Report INC-1042: Payment Gateway Outage

Severity: SEV1
Service: SVC-PAY-01 (Payment Gateway)
Date: 2025-03-14
Duration: 47 minutes

## Summary
The payment gateway returned ERR-504 (upstream timeout) for approximately
62% of transactions between 09:12 and 09:59 UTC. Root cause was a
connection pool exhaustion on the primary database replica after a
scheduled failover did not release stale connections.

## Root Cause
Connection pool exhaustion caused by stale connections following a
database failover. The connection pool's idle-timeout was set too high
(30 minutes), so dead connections from the old primary were not evicted
before new requests queued behind them.

## Resolution
On-call SRE manually restarted the connection pool and reduced idle
timeout to 5 minutes. Long-term fix: implement active health checks on
pooled connections (tracked as JIRA-4821).

## Customer Impact
Approximately 18,000 payment attempts failed; 94% were successfully
retried by the client SDK within 2 minutes.
