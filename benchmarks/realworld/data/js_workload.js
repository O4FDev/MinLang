// Fixed real-world workload for the minyar-js engine: numeric, array, object and
// string work whose result is printed and checked by benchmarks/realworld/run.py.
var limit = 4000;
var sieve = [];
for (var i = 0; i <= limit; i++) sieve.push(1);
sieve[0] = 0;
sieve[1] = 0;
for (var p = 2; p * p <= limit; p++) {
    if (sieve[p] === 1) {
        for (var q = p * p; q <= limit; q += p) sieve[q] = 0;
    }
}
var primes = 0;
var lastPrime = 0;
for (var k = 2; k <= limit; k++) {
    if (sieve[k] === 1) {
        primes += 1;
        lastPrime = k;
    }
}

function fib(n) {
    if (n < 2) return n;
    return fib(n - 1) + fib(n - 2);
}
var fibResult = fib(20);

var inventory = {};
var names = ["alpha", "beta", "gamma", "delta", "epsilon"];
for (var j = 0; j < 8000; j++) {
    var name = names[j % 5];
    if (inventory[name] === undefined) inventory[name] = 0;
    inventory[name] += j % 7;
}
var total = 0;
for (var m = 0; m < 5; m++) total += inventory[names[m]];

var text = "";
for (var t = 0; t < 800; t++) {
    if (t % 3 === 0) text += "abc";
    else if (t % 3 === 1) text += "de";
    else text += "f";
}
var checksum = 0;
for (var c = 0; c < text.length; c++) checksum += text.charCodeAt(c) % 251;

print(primes, lastPrime, fibResult, total, text.length, checksum);
