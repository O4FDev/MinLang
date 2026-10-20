.PHONY: check-changed check-changed-plan check-changed-export check-changed-inputs

# Capture on the laptop without building; sync this ignored directory with bx.
CHECK_CHANGED_EXPORT ?= target/check-changed
check-changed-export:
	python3 "tools/check-changed.py" --export "$(CHECK_CHANGED_EXPORT)"

check-changed:
	python3 "tools/check-changed.py"

check-changed-plan:
	python3 "tools/check-changed.py" --plan

check-changed-inputs:
	python3 "tests/check-changed.py"

check check-portable: check-changed-inputs
