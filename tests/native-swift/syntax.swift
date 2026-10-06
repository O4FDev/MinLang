import Foundation
@_spi(ExperimentalLanguageFeatures) @_spi(Minyar) import SwiftParser
import SwiftSyntax
import SwiftParserDiagnostics

for path in CommandLine.arguments.dropFirst() {
  let source = try String(contentsOfFile: path, encoding: .utf8)
  var parser = Parser(source, experimentalFeatures: [.minyarSyntax])
  let tree = SourceFileSyntax.parse(from: &parser)
  let map = parser.minyarSourceMap(for: tree)
  let diagnostics = ParseDiagnosticsGenerator.diagnostics(for: tree)
  for diagnostic in diagnostics {
    print("\(path):\(map.sourceOffset(forSyntaxOffset: diagnostic.position.utf8Offset)): \(diagnostic.message)")
  }
  var mismatches = 0
  let bytes = Array(source.utf8)
  for token in tree.tokens(viewMode: .sourceAccurate) {
    // Synthesized unlabelled parameters have no original token.
    if token.text == "_" || token.text.isEmpty { continue }
    let syntaxOffset = token.positionAfterSkippingLeadingTrivia.utf8Offset
    let sourceOffset = map.sourceOffset(forSyntaxOffset: syntaxOffset)
    let end = sourceOffset + token.text.utf8.count
    let original = sourceOffset >= 0 && end <= bytes.count ? String(decoding: bytes[sourceOffset..<end], as: UTF8.self) : "<invalid>"
    let aliases = ["func": "function", "struct": "record", "let": "constant", "var": "let", "import": "use", "->": ":"]
    let suffix = sourceOffset >= 0 && sourceOffset <= bytes.count
      ? String(decoding: bytes[sourceOffset...], as: UTF8.self) : ""
    let spellingMatches = original == token.text || aliases[token.text].map { suffix.hasPrefix($0) } == true
    if !spellingMatches || map.syntaxOffset(forSourceOffset: sourceOffset) != syntaxOffset {
      print("\(path): mapping mismatch \(token.text) at \(syntaxOffset) -> \(sourceOffset): \(original)")
      mismatches += 1
    }
  }
  print("\(path): \(diagnostics.count) diagnostics; \(mismatches) source mapping failures")
  if !diagnostics.isEmpty || mismatches != 0 { exit(1) }
}

// Dialect selection must never change imported Swift or generated Swift.
let swiftSource = "let function = 1\nstruct Box { let value: Int }\n"
let swiftTree = Parser.parse(source: swiftSource)
precondition(swiftTree.description == swiftSource)
precondition(ParseDiagnosticsGenerator.diagnostics(for: swiftTree).isEmpty)

let dialectSource = "constant fixed = 1\nlet mutable = 2\nfunction f(value: Int): Int { value }\n"
var dialectParser = Parser(dialectSource, experimentalFeatures: [.minyarSyntax])
let dialectTree = SourceFileSyntax.parse(from: &dialectParser)
precondition(dialectTree.description == "let fixed = 1\nvar mutable = 2\nfunc f(_ value: Int)-> Int { value }\n")
let dialectMap = dialectParser.minyarSourceMap(for: dialectTree)
precondition(dialectMap.sourceOffset(forSyntaxOffset: dialectTree.endPosition.utf8Offset) == dialectSource.utf8.count)
precondition(dialectMap.syntaxOffset(forSourceOffset: dialectSource.utf8.count) == dialectTree.endPosition.utf8Offset)

for malformed in ["use \"Unterminated", "use \"\"", "use \"Bad..Module\"", "use \"bad module\"", "use \"\\(module)\""] {
  var parser = Parser(malformed, experimentalFeatures: [.minyarSyntax])
  let tree = SourceFileSyntax.parse(from: &parser)
  precondition(!ParseDiagnosticsGenerator.diagnostics(for: tree).isEmpty,
               "invalid import silently accepted: \(malformed)")
}
print("Swift dialect isolation, native declaration semantics, EOF mapping and malformed imports passed")

let memberSource = "constant binding = Binding.constant(42)\nconstant x = api.function(record: api.use)\n"
var memberParser = Parser(memberSource, experimentalFeatures: [.minyarSyntax])
let memberTree = SourceFileSyntax.parse(from: &memberParser)
precondition(ParseDiagnosticsGenerator.diagnostics(for: memberTree).isEmpty)
precondition(memberTree.description == "let binding = Binding.constant(42)\nlet x = api.function(record: api.use)\n")
print("SDK member names and argument labels preserved")
