import Lake
open Lake DSL

package minyarFoundations where
  buildDir := "../build/foundations-lean"

lean_lib Minyar

@[default_target]
lean_exe «ownership-check» where
  root := `Main
