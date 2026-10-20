# 12. Give a program its input

[Previous](11-files.md) · [Contents](README.md)

So far, changing our programs' inputs has meant editing their source. An
argument is a piece of text supplied when a program starts. We can greet a
different person without changing the program.

Create a fresh project:

```sh
minyar new "greetings"
cd "greetings"
```

Replace `src/main.min` with this complete program:

```minyar
use "process" as process

match process.argumentAt(0) {
    Some(name) {
        if name == "" {
            print("Please give a name, or leave the argument out.")
        } else {
            print("Hello, \(name)!")
        }
    }
    None { print("Hello, gardener!") }
}
```
```output
Hello, gardener!
```

Save the file and enter `minyar run`. With no program argument, position 0
is absent. `argumentAt` returns `None`, so our default greeting prints.
Minyar also prints build messages; the boxes here show our program's output.

This is the `Maybe` from [chapter 7](07-results.md): either `Some` text or
`None`. Positions start at zero, just as they do in a List. The executable's
own filename is not one of these arguments.

## Supply a name

Enter:

```sh
minyar run -- "Ada Lovelace"
```

The program prints:

```text
Hello, Ada Lovelace!
```

The `--` tells Minyar that the following arguments belong to our program.
The quotation marks keep the name and its space together as one argument;
the marks themselves are not part of the name.

## Empty is different from absent

Enter:

```sh
minyar run -- ""
```

The program prints:

```text
Please give a name, or leave the argument out.
```

The terminal passes one argument whose text is empty. That becomes
`Some("")`; it does not become `None`. We chose to explain the empty input.
Run without an argument to get the default greeting again.

## Names that look like options

Enter:

```sh
minyar run -- "--help"
```

The program prints:

```text
Hello, --help!
```

After the separator, even text beginning with `-` is passed to our program.
This program treats it as a name. `minyar run --help`, without the separator,
asks Minyar for its own help instead.

Our program reads only the first argument. Any later arguments have no
effect: giving it `Ada` followed by `Jo` still greets Ada. It also preserves
spaces within the supplied text; it does not trim a name before greeting it.

Try it: greet yourself, keeping quotation marks around a name containing
spaces. Then compare an omitted argument with `""` again and predict which
match arm each one uses before you run it.
