.PHONY: dev-check dev-check-plan dev-check-index dev-check-rebase check-dev-check

# Affected-check feedback against a warm prebuilt tree; see docs/dev-check.md.
DEV_CHECK_JOBS ?= 4
dev-check:
	python3 "tools/dev-check.py" run --jobs $(DEV_CHECK_JOBS) $(if $(ONLY),--only $(ONLY))

dev-check-plan:
	python3 "tools/dev-check.py" run --plan $(if $(ONLY),--only $(ONLY))

dev-check-index:
	python3 "tools/dev-check.py" index --jobs $(DEV_CHECK_JOBS)

dev-check-rebase:
	python3 "tools/dev-check.py" rebase

check-dev-check:
	python3 "tests/dev-check.py"

check check-portable: check-dev-check
