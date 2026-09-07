# Meeting Notes: Payments Reliability Review

Attendees: Priya Fernando, Kasun Perera, Amaya Silva

## Discussion
Reviewed the three payment-related incidents this year (INC-1042,
INC-1077) and confirmed both trace back to the same connection-pool
idle-timeout defect. JIRA-4821 (active health checks) is now deployed
to all regions as of last week.

## Action Items
- Kasun: add a synthetic monitor that exercises the connection pool
  failover path weekly.
- Priya: add pool-exhaustion alerting to PagerDuty with a 5-minute
  threshold instead of the current 15-minute threshold.
- Amaya: confirm no customer PII was exposed during either incident
  (confirmed: no PII exposure, both were availability-only incidents).
