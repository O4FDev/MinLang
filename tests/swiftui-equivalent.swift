import SwiftUI
import AppKit

struct CounterView: View {
    @State private var count = 0
    var body: some View {
        VStack {
            Text("Count: \(count)")
            Button("Increment") { count += 1 }
        }.padding()
    }
}

@inline(never)
func sum<T: BinaryInteger>(_ values: [T]) -> T {
    var total: T = 0
    for value in values { total += value }
    return total
}

@main
struct Probe {
    static func main() {
        _ = NSApplication.shared
        let host = NSHostingView(rootView: CounterView())
        print(sum([Int64(1), 2, 3, 4]))
        print(MemoryLayout<CounterView>.size)
        print(host.fittingSize.width > 0)
    }
}
