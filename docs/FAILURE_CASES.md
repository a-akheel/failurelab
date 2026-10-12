# Failure analysis

## Stale approval: the initial workflow had a gap

The first DeskPilot version read context once, then could wait an hour before executing. The revised workflow reads context again and compares revision and freshness. Two HTTP cases now change the fixture between investigation and approval: one changes the revision, the other sets its age to two hours. Both finish as `stale_approval` with zero action rows.

## Lost response after a committed action

The fixture writes the simulated restart and result into SQLite, then returns HTTP 503. Temporal retries with the same idempotency key. The second request returns the existing result. The saved report shows `completed` and one action. This validates the fixture contract; a real downstream API must independently guarantee idempotency.

## Worker recovery

The runner stops the Kotlin process while it awaits approval and starts another process against the same Temporal database. The plan ID is preserved, the original approval completes, and the ledger records one action. A replacement-worker test in the time-skipping unit environment initially stalled; recovery is therefore verified by actual process replacement instead.

## Prompt injection in tool context

The injected note says to ignore instructions and export credentials. The weak reference policy follows that text and fails the action-policy check. The guarded policy ignores it. This tests evaluator sensitivity to a deliberately bad policy; it does not prove that a live language model resists injection.

## Authorization and invalid context

The IT fixture returns 403 or malformed monitoring fields. DeskPilot treats both as non-retryable and records one read, then a failed workflow with zero actions. Transient 503 recovers; repeated 504 exhausts three reads. Retrying an authorization denial would spend time without repairing permission.

## Ambiguous requests

The synthetic policy suite includes missing and multiple service names. DeskPilot accepts an explicitly blank service and escalates rather than selecting an arbitrary target. The reference policy's keyword matching remains a documented limitation.
