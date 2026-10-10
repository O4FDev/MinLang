import AppKit
@MainActor public func makeWindow(_ title: String) -> NSWindow {
    let window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 640, height: 480), styleMask: [.titled, .closable, .resizable, .miniaturizable], backing: .buffered, defer: false)
    window.title = title
    let button = NSButton(title: "Hello", target: nil, action: nil)
    window.contentView?.addSubview(button)
    return window
}
