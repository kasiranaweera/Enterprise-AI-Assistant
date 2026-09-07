# Runbook: Payment Gateway On-Call Response

## When paged for ERR-504 spikes on SVC-PAY-01

1. Check the connection pool utilization dashboard (Grafana: payments/pool-health).
2. If pool utilization is >90%, restart the pool via `kubectl rollout restart deploy/pay-gateway-pool`.
3. Verify idle-timeout config is set to 5 minutes (post JIRA-4821). If not, this is
   the same root cause as INC-1042 and INC-1077 — escalate immediately, do not wait.
4. Check upstream database replica health; a recent failover is the most common trigger.
5. If retries from client SDKs are amplifying load, consider enabling
   the emergency rate limiter (`feature-flag: pay-gateway-emergency-throttle`).
6. Notify #incidents channel and open an incident ticket if downtime exceeds 5 minutes.

## Escalation
- Primary: Payments on-call (PagerDuty schedule "payments-primary")
- Secondary: SRE Lead (Kasun Perera)
