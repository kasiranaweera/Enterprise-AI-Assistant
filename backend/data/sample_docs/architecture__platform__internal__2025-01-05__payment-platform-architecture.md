# Architecture: Payment Platform Overview

## Components
- SVC-PAY-01 (Payment Gateway): stateless API layer, backed by a
  primary/replica Postgres cluster, connection-pooled via PgBouncer.
- SVC-AUTH-01 (Auth Service): issues short-lived JWTs, backed by Redis
  for session state.
- SVC-NOTIF-01 (Notification Service): async worker consuming from a
  Kafka topic to send payment confirmation emails/SMS.

## Data Flow
Client -> API Gateway -> Auth Service (token validation) -> Payment
Gateway -> Postgres (transaction write) -> Kafka (event) -> Notification
Service.

## Known Fragility Points
The Payment Gateway's connection pool has historically been the single
largest source of SEV1/SEV2 incidents (see INC-1042, INC-1077) due to
stale connection handling across database failovers. A cross-cutting
fix (active health checks) is tracked under JIRA-4821 and is the
highest-priority reliability item for the payments team this quarter.
