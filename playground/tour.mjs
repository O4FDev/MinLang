// These programs are compiled and run by the playground's integration check.
export const tour = Object.freeze([
  {
    id: 'hello',
    title: 'A warm hello',
    description: 'Put a value inside a sentence. Text interpolation keeps the thought together.',
    source: String.raw`let name = "Ada"
print("Hello, \(name).")
print("Make yourself at home.")
`,
    expected: 'Hello, Ada.\nMake yourself at home.\n',
  },
  {
    id: 'functions',
    title: 'A small calculation',
    description: 'Name a thought with a function. Its types make the promise clear.',
    source: String.raw`function double(value: Integer): Integer {
    return value * 2
}

let answer = double(21)
print("A small thought: \(answer).")
`,
    expected: 'A small thought: 42.\n',
  },
  {
    id: 'lists',
    title: 'A collection of lights',
    description: 'A List keeps related values together. A for loop visits each one.',
    source: String.raw`let colours = ["amber", "silver", "blue"]

for colour in colours {
    print("One \(colour) lantern.")
}

print("\(colours.length) lights, one harbour.")
`,
    expected: 'One amber lantern.\nOne silver lantern.\nOne blue lantern.\n3 lights, one harbour.\n',
  },
  {
    id: 'records',
    title: 'Give an idea a shape',
    description: 'A record gives related values a name. Every field has a checked type.',
    source: String.raw`record Lantern {
    place: Text
    lights: Integer
}

let home = Lantern {
    place: "The harbour"
    lights: 42
}

print("\(home.place) keeps \(home.lights) lights.")
`,
    expected: 'The harbour keeps 42 lights.\n',
  },
  {
    id: 'choices',
    title: 'Consider every possibility',
    description: 'A choice names the possibilities. A match handles each one, with nothing forgotten.',
    source: String.raw`choice Weather {
    Clear
    Rain(drops: Integer)
}

let weather = Weather.Rain(3)

match weather {
    Clear { print("Room for stars.") }
    Rain(drops) {
        print("\(drops) drops. A warm window.")
    }
}
`,
    expected: '3 drops. A warm window.\n',
  },
  {
    id: 'lanterns',
    title: 'Bring it all together',
    description: 'Records, functions, a List, and a loop. Small ideas make something larger.',
    source: String.raw`/// Small lights, carried together.
record Lantern {
    place: Text
    light: Integer
}

function message(lantern: Lantern): Text {
    if lantern.light == 1 {
        return "\(lantern.place): one small promise."
    }
    return "\(lantern.place): \(lantern.light) small promises."
}

let harbour = [
    Lantern { place: "The harbour"; light: 3 },
    Lantern { place: "The hill"; light: 2 },
    Lantern { place: "Home"; light: 1 }
]

let total = 0
for lantern in harbour {
    print(message(lantern))
    total += lantern.light
}

print("\(total) lights. Someone will come home.")
`,
    expected: 'The harbour: 3 small promises.\nThe hill: 2 small promises.\nHome: one small promise.\n6 lights. Someone will come home.\n',
  },
].map((example) => Object.freeze(example)));
