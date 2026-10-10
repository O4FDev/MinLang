import AppKit
import SwiftUI
import MinyarWidgets

@main
struct Client {
    @MainActor static func main() {
        _ = NSApplication.shared
        var value = 2
        let binding = Binding(get: { value }, set: { value = $0 })
        binding.wrappedValue = 7
        precondition(value == 7)
        let box = NativeBox(value: "native module")
        precondition(box.read() == "native module")
        precondition(nativeSum([Int64(1), 2, 3, 4]) == 10)
        let host = NSHostingView(rootView: VStack {
            NativeBadge(value: box.read())
            NativeCounter(count: binding)
        })
        precondition(host.fittingSize.width > 0)
        print("Swift imported native Minyar generics, conformances, views and bindings")
    }
}
