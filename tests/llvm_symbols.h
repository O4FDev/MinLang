/* Test probes bind to generated language functions without changing their IR.
 * These names are compiler internals, not a public native package ABI. */
#ifndef MINYAR_TEST_LLVM_SYMBOLS_H
#define MINYAR_TEST_LLVM_SYMBOLS_H

#define MINYAR_TEST_STRINGIFY_INNER(value) #value
#define MINYAR_TEST_STRINGIFY(value) MINYAR_TEST_STRINGIFY_INNER(value)
#define MINYAR_TEST_LANGUAGE_SYMBOL(name)                                                          \
    __asm__(MINYAR_TEST_STRINGIFY(__USER_LABEL_PREFIX__) ".minyar.fn." #name)

#endif
