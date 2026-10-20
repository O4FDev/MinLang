.PHONY: check-utf8-validation check-utf8-validation-sanitize

UTF8_VALIDATION_INPUTS = tests/utf8-validation.min tests/utf8-validation-oracle.c runtime/minyar_native.h library/text.min library/errors.min

build/tooling/tests/utf8-validation.ll: $(UTF8_VALIDATION_INPUTS)

build/utf8-validation-o0: build/tooling/tests/utf8-validation.ll build/minyar-runtime.o $(UTF8_VALIDATION_INPUTS)
	$(LIMITED) "$(LLVM_CC)" $(CPPFLAGS) $(CFLAGS) -O0 -Wno-override-module "$<" build/minyar-runtime.o tests/utf8-validation-oracle.c -lm -o "$@"

build/utf8-validation-o2: build/tooling/tests/utf8-validation.ll build/minyar-runtime.o $(UTF8_VALIDATION_INPUTS)
	$(LIMITED) "$(LLVM_CC)" $(CPPFLAGS) $(CFLAGS) -O2 -Wno-override-module "$<" build/minyar-runtime.o tests/utf8-validation-oracle.c -lm -o "$@"

check-utf8-validation: build/utf8-validation-o0 build/utf8-validation-o2
	$(LIMITED) ./build/utf8-validation-o0
	$(LIMITED) ./build/utf8-validation-o2

build/utf8-validation-sanitize.ll: build/tooling/tests/utf8-validation.ll build/tooling/tools/clang-driver
	$(SANITIZER_LIMITED) ./build/tooling/tools/clang-driver sanitize-llvm "$<" "$@"

build/utf8-validation-sanitize: build/utf8-validation-sanitize.ll build/minyar-runtime-sanitize.o $(UTF8_VALIDATION_INPUTS)
	$(SANITIZER_LIMITED) "$(LLVM_CC)" $(CPPFLAGS) $(CFLAGS) $(SANITIZER_FLAGS) "$<" build/minyar-runtime-sanitize.o tests/utf8-validation-oracle.c -lm -o "$@"

check-utf8-validation-sanitize: build/utf8-validation-sanitize
	$(NATIVE_SANITIZER_ENV) $(SANITIZER_LIMITED) ./build/utf8-validation-sanitize

check check-portable: check-utf8-validation
check-sanitize: check-utf8-validation-sanitize
