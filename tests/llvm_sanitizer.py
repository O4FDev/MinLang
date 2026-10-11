"""Compatibility entry point for the canonical generated-program annotator."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from sanitizer_llvm import address_sanitizer_enabled, instrument_address_sanitizer, prepare_llvm_for_link, main

if __name__ == '__main__':
    main()
