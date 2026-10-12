import Foundation
let kind = CommandLine.arguments[1], n = Int(CommandLine.arguments[2])!
var checksum: Int64 = 0
func fold(_ number: Int64) { checksum = (checksum * 131 + number) % 1000000007 }
if kind == "hashes" {
    let input = try String(contentsOfFile: CommandLine.arguments[3], encoding: .utf8)
    var values = input.split(separator: "\n")
    precondition(values.count == n)
    let start = DispatchTime.now().uptimeNanoseconds
    values.sort()
    print(DispatchTime.now().uptimeNanoseconds - start)
    for value in values { for byte in value.utf8.prefix(8) { fold(Int64(byte)) } }
} else if kind == "records" {
    var values = (0..<n).map { ((Int64($0) * 1103515245 + 12345) % 2147483647 % 1024, Int64($0)) }
    let start = DispatchTime.now().uptimeNanoseconds
    values.sort { $0.0 < $1.0 }
    print(DispatchTime.now().uptimeNanoseconds - start)
    for value in values { fold(value.1) }
} else {
    var values = (0..<n).map { (Int64($0) * 1103515245 + 12345) % 2147483647 }
    let start = DispatchTime.now().uptimeNanoseconds
    values.sort()
    print(DispatchTime.now().uptimeNanoseconds - start)
    for value in values { fold(value) }
}
print(checksum)
