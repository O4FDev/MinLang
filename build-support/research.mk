# Prospective research contracts: deliberately red, never dependencies of check.
.PHONY: check-reclamation-acceptance check-reclamation-acceptance-sanitize check-reclamation-acceptance-harness check-reclamation-acceptance-evidence
check-reclamation-acceptance:
	python3 research/reclamation/test_acceptance.py

check-reclamation-acceptance-sanitize:
	python3 research/reclamation/test_acceptance.py --sanitize

check-reclamation-acceptance-harness:
	python3 research/reclamation/test_acceptance_harness.py

RECLAMATION_TIMING ?= build/event-load-timing
RECLAMATION_DIAGNOSTIC ?= build/event-load-diagnostic
check-reclamation-acceptance-evidence:
	python3 research/reclamation/test_acceptance_evidence.py --timing "$(RECLAMATION_TIMING)" --diagnostic "$(RECLAMATION_DIAGNOSTIC)"
