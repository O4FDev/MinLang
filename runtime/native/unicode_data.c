/* Keep the unmodified vendored engine in its own translation unit.
 * Native bridge analysis uses utf8proc's declared API; Unicode conformance
 * and sanitizer checks exercise this implementation and its property data. */
#define UTF8PROC_STATIC
#include "../../vendor/utf8proc/utf8proc.c"
