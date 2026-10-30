// C++ peer for main.min: records in a vector, filtered, grouped and ranked.
#include <algorithm>
#include <array>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <vector>

struct Order { int64_t id, customer, region, price, quantity, discount; };
struct Ranked { int64_t id, total; };

int main(int argc, char **argv) {
    int64_t count = argc > 1 ? std::atoll(argv[1]) : 0, seed = 12345;
    std::vector<Order> orders;
    orders.reserve(count);
    for (int64_t i = 0; i < count; i++) {
        seed = (seed * 1103515245 + 12345) % 2147483648LL;
        int64_t price = 100 + (seed / 64) % 9900;
        seed = (seed * 1103515245 + 12345) % 2147483648LL;
        orders.push_back({i, (seed / 16) % 50000, (seed / 8) % 16, price, 1 + (seed / 256) % 7, (seed / 7) % 500});
    }
    int64_t checksum = 0;
    for (int64_t pass = 0; pass < 20; pass++) {
        std::array<int64_t, 16> regions{};
        int64_t large = 0;
        for (const Order &o : orders) {
            int64_t total = o.price * o.quantity - o.discount;
            if (total > 5000 + pass * 100) { regions[o.region] += total; large++; }
        }
        for (int64_t r : regions) checksum = (checksum * 31 + r) % 1000000007;
        checksum = (checksum + large) % 1000000007;
    }
    std::vector<Ranked> ranked;
    for (const Order &o : orders)
        if (o.customer % 10 == 0) ranked.push_back({o.id, o.price * o.quantity - o.discount});
    std::sort(ranked.begin(), ranked.end(), [](const Ranked &a, const Ranked &b) {
        return a.total != b.total ? a.total > b.total : a.id < b.id;
    });
    for (int i = 0; i < 100; i++) checksum = (checksum * 31 + ranked[i].id) % 1000000007;
    std::printf("%zu\n%lld\n", ranked.size(), (long long)checksum);
    return 0;
}
