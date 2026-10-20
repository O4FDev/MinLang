# 9. More than one file

[Previous](08-garden.md) · [Contents](README.md)

A program can outgrow one file. A module lets you keep a related type and
its functions together, then use them from another file. We will put the
garden calculation in one module and the instructions that print a plan in
another.

This chapter is one complete project, with two source files. The comment at
the top of each code box gives its filename. Keep **both** files this time;
they work together. An empty output box means that file contains declarations
and tests but no instructions to print during an ordinary run.

## Make the project

From the directory where you keep your projects, enter:

```sh
minyar new "harvest"
cd "harvest"
```

Create `src/garden.min` in the new project and save this whole file:

```minyar
// file: src/garden.min
public record Bed {
    name: Text
    seeds: Integer
}

public function totalSeeds(beds: List<Bed>): Integer {
    let total = 0
    for bed in beds {
        total += bed.seeds
    }
    return total
}

function oneBed(seeds: Integer): List<Bed> {
    return [Bed { name: "Practice"; seeds: seeds }]
}

test "a module can test its private helper" {
    expect(totalSeeds(oneBed(4)) == 4)
}

test "an empty imported garden needs no seeds" {
    expect(totalSeeds([]) == 0)
}
```
```output
```

`public` makes a declaration available to other modules. We exported `Bed`
and `totalSeeds`. We left `oneBed` private by omitting `public`: it is a helper
for code in this file. Tests in the module can use it, even though code in
another module cannot.

## Use the module

Replace the generated `src/main.min` with this file:

```minyar
// file: src/main.min
use "./garden.min" as garden

let beds = [
    garden.Bed { name: "Peas"; seeds: 8 },
    garden.Bed { name: "Herbs"; seeds: 6 }
]
print("Total: \(garden.totalSeeds(beds)) seeds")
```
```output
Total: 14 seeds
```

`use` imports a module. `as garden` gives it a local name, or alias. A dot
then selects one of its public declarations: `garden.Bed` is the type and
`garden.totalSeeds` is the function. This keeps it clear where a name comes
from.

`./garden.min` is relative to the file containing the import. Since both
files are in `src`, it finds the file next to `main.min`. It does not depend
on the terminal's current directory. Imported modules contain declarations,
not executable top-level statements; the printing instruction belongs in
our entry file, `main.min`.

## Run and check the whole project

Inside `harvest`, enter:

```sh
minyar check
minyar run
minyar test
minyar build --release
"./target/release/harvest"
```

The run and the release executable both print the total above. `minyar test`
finds the two named tests in `src/garden.min` as well as the generated smoke
test in `tests/smoke.min`: three tests altogether. The smoke test was created
by `minyar new`; it checks basic arithmetic and is separate from our garden
tests.

Try it: remove `public` from `totalSeeds` and run `minyar check`. The import
still finds the file, but the calling file cannot use that private function.
Restore `public` and check again. Then change `seeds: seeds` in the private
helper to `seeds: seeds + 1` and run the tests. The helper test should fail;
restore the original calculation afterwards.

You can now divide a program by responsibility without duplicating its
calculation. For larger projects, the [module guide](../modules.md) explains
packages, and the [CLI guide](../cli.md) explains dependency declarations.

Next, practice [reading an error and making one repair](10-errors.md).
