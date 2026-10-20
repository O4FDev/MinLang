# Explaining ownership decisions

The standalone compiler accepts `--explain-ownership` during a whole-source
compilation. For example:

```sh
./build/minyarc app.min app.ll --library library --explain-ownership
```

After source checking succeeds, it writes one JSON remark per reported site to
standard error. Each remark has version 1, severity `remark`, pass
`terminal-ownership`, a source file, line and column, a decision and its reason.
The generated program is unchanged. Ordinary successful compilation stays quiet.
Cached module-state, documentation and test-listing modes reject this option.

This report covers the final local-ownership proof for terminal Text joins and
List `appended` operations in returns and assignments. It explains a direct local
owner transfer, a receiver with no transferable local owner, a projected receiver,
or an assignment replacing a different binding. The latter cases preserve the
ordinary ownership path at this proof stage.

It is a report of this proof's decisions, not an exhaustive allocation or borrow
report. Earlier temporary-owner and lexical proofs may already select a consuming
operation. Recovery mode does not enter this proof. Later scope passes can remove
ownership operations the report preserves.

A `transfer` decision means ownership can move after the other arguments have
been evaluated. The runtime still checks whether storage is unique. An alias,
Text backing view or arena allocation can require copying. The compiler cannot
infer that a particular execution reused memory from source syntax alone.

The feature adds no checks or counters to the generated application. Remark
collection and source-location formatting cost time and memory only in the
compiler when the option is selected.
