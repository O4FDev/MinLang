// C++ peer for main.min: warehouses hold vectors of items by value; each item
// owns a small vector of recent stock changes.
#include <algorithm>
#include <array>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <string>
#include <vector>

constexpr int CATEGORIES = 12, WAREHOUSES = 16;
struct Item { int64_t sku, category, quantity, price; std::vector<int32_t> history; };
struct Warehouse { std::string name; std::vector<Item> items; std::vector<int64_t> moves; };
struct Ranked { int64_t sku, value; };

static int64_t state = 4242, next_sku = 0;
static int64_t next_random() { state = (state * 1103515245 + 12345) % 2147483648LL; return state / 16; }

static Item new_item() {
    Item item{next_sku++, 0, 0, 0, {}};
    item.category = next_random() % CATEGORIES;
    item.quantity = next_random() % 50;
    item.price = 100 + next_random() % 9900;
    return item;
}
static void adjust(Item &item, int64_t delta) {
    item.quantity = std::max<int64_t>(0, item.quantity + delta);
    item.history.push_back((int32_t)delta);
    if (item.history.size() > 16) item.history.erase(item.history.begin(), item.history.end() - 8);
}
static Item take(Warehouse &w, size_t position) {
    Item item = std::move(w.items[position]);
    if (position + 1 != w.items.size()) w.items[position] = std::move(w.items.back());
    w.items.pop_back();
    return item;
}

int main(int argc, char **argv) {
    const int64_t operations = argc > 1 ? std::atoll(argv[1]) : 0;
    std::array<Warehouse, WAREHOUSES> warehouses;
    for (int w = 0; w < WAREHOUSES; w++) warehouses[w].name = "wh-" + std::to_string(w);
    for (int64_t i = 0; i < operations / 10; i++) warehouses[i % WAREHOUSES].items.push_back(new_item());
    int64_t pruned = 0, sold = 0;
    for (int64_t i = 0; i < operations; i++) {
        Warehouse &w = warehouses[next_random() % WAREHOUSES];
        int64_t kind = next_random() % 10;
        if (kind < 6) {
            if (!w.items.empty()) { Item &item = w.items[next_random() % w.items.size()]; adjust(item, next_random() % 21 - 10); }
        } else if (kind < 8) {
            if (!w.items.empty()) {
                Warehouse &destination = warehouses[next_random() % WAREHOUSES];
                Item item = take(w, next_random() % w.items.size());
                w.moves.push_back(item.sku);
                destination.items.push_back(std::move(item));
            }
        } else if (kind == 8) {
            w.items.push_back(new_item());
        } else if (!w.items.empty()) {
            sold += take(w, next_random() % w.items.size()).quantity;
        }
        if (i % 1024 == 1023) {
            size_t before = w.items.size();
            std::erase_if(w.items, [](const Item &item) { return item.quantity <= 0; });
            pruned += (int64_t)(before - w.items.size());
        }
    }
    std::array<int64_t, CATEGORIES> units{}, values{};
    int64_t history_sum = 0, move_sum = 0;
    std::vector<Ranked> ranked;
    for (const Warehouse &house : warehouses) {
        for (int64_t sku : house.moves) move_sum = (move_sum * 31 + sku) % 1000000007;
        for (const Item &item : house.items) {
            units[item.category] += item.quantity;
            values[item.category] += item.quantity * item.price;
            int64_t changes = (int64_t)item.history.size();
            for (int32_t delta : item.history) changes += delta;
            history_sum = (history_sum * 31 + changes + 1000) % 1000000007;
            ranked.push_back({item.sku, item.quantity * item.price});
        }
        std::printf("%s %zu %zu\n", house.name.c_str(), house.items.size(), house.moves.size());
    }
    for (int c = 0; c < CATEGORIES; c++) std::printf("category %d %lld %lld\n", c, (long long)units[c], (long long)values[c]);
    std::sort(ranked.begin(), ranked.end(), [](const Ranked &a, const Ranked &b) { return a.value != b.value ? a.value > b.value : a.sku < b.sku; });
    int64_t top = 0;
    for (size_t i = 0; i < ranked.size() && i < 100; i++) top = (top * 31 + ranked[i].sku) % 1000000007;
    std::printf("%zu %lld %lld %lld\n%lld %lld %lld\n", ranked.size(), (long long)next_sku, (long long)pruned, (long long)sold,
                (long long)history_sum, (long long)move_sum, (long long)top);
    return 0;
}
