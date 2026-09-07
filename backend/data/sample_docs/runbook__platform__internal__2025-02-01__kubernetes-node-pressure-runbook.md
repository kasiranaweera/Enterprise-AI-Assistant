# Runbook: Kubernetes Node Resource Pressure

## Symptoms
Elevated latency across multiple services on the same node pool, without
a corresponding traffic increase.

## Steps
1. Check `kubectl top nodes` for CPU/memory pressure.
2. Identify co-located workloads via `kubectl get pods -o wide --field-selector spec.nodeName=<node>`.
3. Confirm all batch/analytics jobs have CPU requests and limits set.
4. If an unbounded job is found, cordon the node, evict the job, and
   apply resource limits before rescheduling.
5. Consider moving batch workloads to a dedicated node pool with taints.
