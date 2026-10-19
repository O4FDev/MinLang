enum Weather { Clear, Rain }
fn warmth(weather: Weather) -> i64 { match weather { Weather::Clear => 1 } }
fn main() { println!("{}", warmth(Weather::Clear)); }
