# Reserved function names

These names belong to the language's built-in functions and constructors.
A user function cannot declare one of them, including inside an imported
module. Choose a different function name, such as `joinTextLocal` or `joinWith`.
Record fields and methods use their receiver's namespace; this list reserves
function declarations, not field names or arbitrary prefixes.

Names are case-sensitive. Keywords and type syntax are described in
[the language reference](language.md). Standard-library functions belong to
their module alias and do not reserve every module's function namespace.

| Reserved function name |
| --- |
| `Bytes` |
| `Character` |
| `Float` |
| `Integer` |
| `Text` |
| `abs` |
| `acos` |
| `argument` |
| `argumentCount` |
| `asin` |
| `atan` |
| `atan2` |
| `ceil` |
| `clamp` |
| `cos` |
| `exit` |
| `exp` |
| `fail` |
| `fileExists` |
| `floor` |
| `joinText` |
| `log` |
| `max` |
| `min` |
| `parallelEntry` |
| `pow` |
| `print` |
| `randomBytes` |
| `readBytesFile` |
| `readTextFile` |
| `round` |
| `sin` |
| `sqrt` |
| `tan` |
| `wrappingAdd` |
| `wrappingMultiply` |
| `wrappingSubtract` |
| `writeBytesFile` |
| `writeTextFile` |

Generated from the compiler by `python3 tools/reserved-names.py`.
Run `python3 tools/reserved-names.py --check` after changing built-in names.
