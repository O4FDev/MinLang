# Batch300f — python

Fully read 33 files: 32 test_body, 1 finite_data_profile. These counts describe checked-in source bodies read, not upstream executions or completed implementations.

Reviewed 33 complete files (32 standalone bodies and one inherited Japanese-codec data profile): platform/runtime/IO tests, profile goldens, VM opcode/thread-local-bytecode probes, codecs, colorization, build details, XML helper and extension ABI tests. Each assertion/helper invocation and meaningful finite checked-in profile was considered. Imported support and corpus files remain separately pending. Windows disabled non-BMP console tests and xxlimited decorator ranges with no enabled profile were explicitly not credited as executed coverage.

Parser-prefix 17 scoped adoption rows are in resolution-parser-prefixes.jsonl after parent native4opts and ASan/UBSanO0/O2 validation. The 100000-unary source remains partial: native controlled depth failure passes; sanitizer compiler still aborts from stack exhaustion.

Across this batch: 300 current standalone test files (32 Python +100 Swift +168 Ruby), one historical guarded Ruby body and one Python finite inherited data profile; 302 fully read files in total. Source consistency checking is separate from proof of reading. Global discovery and case enumeration remain pending for Python, Swift and Ruby. No production/test files or central implementation ledger edited by this agent.
