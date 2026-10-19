export {};
type Weather = "Clear" | "Rain";
function warmth(weather: Weather): number {
    switch (weather) { case "Clear": return 1; }
}
console.log(warmth("Clear"));
