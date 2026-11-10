# The lifecycle of one card_enrichment row (CONTEXT.md: card_enrichment).
#
# PENDING: a batch call is in flight for this dedupe_key; do not resubmit, poll instead.
# COMPLETED: enrichment applied and passed the post-validator.
# FAILED: the Batch job itself failed; eligible for automatic resubmission.
# NEEDS_REPAIR: the answer failed (refused, truncated, unparseable, no description) or
#   carried an out-of-taxonomy tag. Stored with a NULL description, so it is never
#   embedded, and with only its valid tags, so tag-match still reaches it. Not
#   auto-resubmitted: a repair-only submit re-tags just these (see the post-validator).
PENDING = "pending"
COMPLETED = "completed"
FAILED = "failed"
NEEDS_REPAIR = "needs_repair"
