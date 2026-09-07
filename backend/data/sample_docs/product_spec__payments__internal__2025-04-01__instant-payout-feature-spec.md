# Product Spec: Instant Payout Feature

## Overview
Allows merchants to receive payouts within 30 minutes of settlement,
instead of the standard T+2 business days, for a 1.5% expedite fee.

## Requirements
- Merchant must have a verified bank account (KYC level 2+).
- Feature flag: `instant-payout-enabled`, rolled out per-merchant.
- Depends on SVC-PAY-01 exposing a new `/payouts/instant` endpoint.

## Risks
Given the Payment Gateway's history of connection-pool-related outages
during high load (INC-1042, INC-1077), Instant Payout traffic should be
isolated onto a separate connection pool to avoid contending with
standard transaction traffic.
