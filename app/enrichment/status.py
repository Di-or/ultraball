# The lifecycle of one card_enrichment row (CONTEXT.md: card_enrichment).
#
# PENDING: a batch call is in flight for this dedupe_key; do not resubmit, poll instead.
# COMPLETED: enrichment applied and passed the post-validator.
# FAILED: the Batch job itself failed; eligible for automatic resubmission.
# NEEDS_REPAIR: the model refused or emitted an out-of-taxonomy tag; parked for the
#   human repair path rather than auto-resubmitted (see the refusal-first post-validator).
PENDING = "pending"
COMPLETED = "completed"
FAILED = "failed"
NEEDS_REPAIR = "needs_repair"
