enum Weather { case clear, rain }
func warmth(_ weather: Weather) -> Int {
    switch weather { case .clear: return 1 }
}
print(warmth(.clear))
