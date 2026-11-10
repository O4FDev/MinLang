.PHONY: garden check-garden
# Report the upkeep the tree needs (docs/garden.md). Reads the tree only, needs no build; GARDEN_FLAGS adds
# options such as --online or --check-log FILE.
garden:
	@python3 tools/garden.py $(GARDEN_FLAGS)

# Fail when docs name things that do not exist or agent leftovers are tracked. Run nightly by
# .github/workflows/fuzz-nightly.yml.
check-garden:
	python3 tools/garden.py --fail-on docs,leftovers docs leftovers
