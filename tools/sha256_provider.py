"""Standalone SHA-256 provider flags, also usable by custom link drivers."""
from format_provider import format_provider


def sha256_provider(clang='clang', compile_flags=()):
    return format_provider('sha256', clang, compile_flags)
