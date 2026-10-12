.PHONY: check-system-services
check-system-services: build/minyarc
	MINYAR_TEST_CLANG="$(LLVM_CC)" $(LIMITED) python3 tests/system-services.py --language

check check-portable: check-system-services
