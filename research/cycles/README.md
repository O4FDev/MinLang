# Incremental cycle collection research

Work in progress. The initial red tests require cycle-forming source mutations,
reclamation during execution, root protection (including temporaries and take
transfers), small-pool reuse, and cleanup budgets down to one. The baseline has
no cycle collector and rejects the source fixture. `research/reclamation/`,
mentioned in the task, is absent in this checkout.

The design under investigation augments ownership counts with internal incoming
edge counts and traces a finite cohort incrementally. A deletion barrier
preserves a snapshot while the mutator changes the graph, avoiding repeated
trial-deletion aborts. Scalar records and Text keep their existing representation;
the compiler arena remains outside automatic reclamation, as before.
