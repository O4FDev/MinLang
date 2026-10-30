// Rust peer for main.min: warehouses hold Vecs of items by value; each item
// owns a small Vec of recent stock changes.
use std::io::Write;

const CATEGORIES: usize = 12;
const WAREHOUSES: i64 = 16;

struct Item { sku: i64, category: i64, quantity: i64, price: i64, history: Vec<i32> }
struct Warehouse { name: String, items: Vec<Item>, moves: Vec<i64> }

struct Random(i64);
impl Random {
    fn next(&mut self) -> i64 { self.0 = (self.0 * 1103515245 + 12345) % 2147483648; self.0 / 16 }
}

fn new_item(random: &mut Random, next_sku: &mut i64) -> Item {
    let sku = *next_sku;
    *next_sku += 1;
    let category = random.next() % CATEGORIES as i64;
    let quantity = random.next() % 50;
    let price = 100 + random.next() % 9900;
    Item { sku, category, quantity, price, history: Vec::new() }
}

impl Item {
    fn adjust(&mut self, delta: i64) {
        self.quantity = (self.quantity + delta).max(0);
        self.history.push(delta as i32);
        if self.history.len() > 16 { let cut = self.history.len() - 8; self.history.drain(..cut); }
    }
}

fn main() {
    let operations: i64 = std::env::args().nth(1).unwrap().parse().unwrap();
    let mut random = Random(4242);
    let mut next_sku = 0i64;
    let mut warehouses: Vec<Warehouse> = (0..WAREHOUSES).map(|w| Warehouse { name: format!("wh-{}", w), items: Vec::new(), moves: Vec::new() }).collect();
    for i in 0..operations / 10 {
        let item = new_item(&mut random, &mut next_sku);
        warehouses[(i % WAREHOUSES) as usize].items.push(item);
    }
    let (mut pruned, mut sold) = (0i64, 0i64);
    for i in 0..operations {
        let w = (random.next() % WAREHOUSES) as usize;
        let kind = random.next() % 10;
        if kind < 6 {
            let len = warehouses[w].items.len();
            if len > 0 {
                let position = (random.next() % len as i64) as usize;
                let delta = random.next() % 21 - 10;
                warehouses[w].items[position].adjust(delta);
            }
        } else if kind < 8 {
            let len = warehouses[w].items.len();
            if len > 0 {
                let destination = (random.next() % WAREHOUSES) as usize;
                let position = (random.next() % len as i64) as usize;
                let item = warehouses[w].items.swap_remove(position);
                warehouses[w].moves.push(item.sku);
                warehouses[destination].items.push(item);
            }
        } else if kind == 8 {
            let item = new_item(&mut random, &mut next_sku);
            warehouses[w].items.push(item);
        } else {
            let len = warehouses[w].items.len();
            if len > 0 {
                let position = (random.next() % len as i64) as usize;
                sold += warehouses[w].items.swap_remove(position).quantity;
            }
        }
        if i % 1024 == 1023 {
            let before = warehouses[w].items.len();
            warehouses[w].items.retain(|item| item.quantity > 0);
            pruned += (before - warehouses[w].items.len()) as i64;
        }
    }
    let mut out = std::io::stdout().lock();
    let (mut units, mut values) = ([0i64; CATEGORIES], [0i64; CATEGORIES]);
    let (mut history_sum, mut move_sum) = (0i64, 0i64);
    let mut ranked: Vec<(i64, i64)> = Vec::new();
    for house in &warehouses {
        for &sku in &house.moves { move_sum = (move_sum * 31 + sku) % 1000000007; }
        for item in &house.items {
            units[item.category as usize] += item.quantity;
            values[item.category as usize] += item.quantity * item.price;
            let changes = item.history.len() as i64 + item.history.iter().map(|&d| d as i64).sum::<i64>();
            history_sum = (history_sum * 31 + changes + 1000) % 1000000007;
            ranked.push((item.sku, item.quantity * item.price));
        }
        writeln!(out, "{} {} {}", house.name, house.items.len(), house.moves.len()).unwrap();
    }
    for c in 0..CATEGORIES { writeln!(out, "category {} {} {}", c, units[c], values[c]).unwrap(); }
    ranked.sort_unstable_by(|a, b| b.1.cmp(&a.1).then(a.0.cmp(&b.0)));
    let top = ranked.iter().take(100).fold(0i64, |top, r| (top * 31 + r.0) % 1000000007);
    writeln!(out, "{} {} {} {}\n{} {} {}", ranked.len(), next_sku, pruned, sold, history_sum, move_sum, top).unwrap();
}
