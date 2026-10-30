// C++ peer for main.min: Game of Life on a padded byte grid, then BFS shortest
// paths and connected components over the open cells.
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <vector>

static constexpr int step_y[4] = {0, 1, 0, -1}, step_x[4] = {1, 0, -1, 0};

int main(int argc, char **argv) {
    const int side = argc > 1 ? std::atoi(argv[1]) : 0, wide = side + 2;
    std::vector<uint8_t> cells((size_t)wide * wide), next((size_t)wide * wide);
    int64_t seed = 2024;
    for (int y = 0; y < side; y++)
        for (int x = 0; x < side; x++) {
            seed = (seed * 1103515245 + 12345) % 2147483648LL;
            cells[(y + 1) * wide + x + 1] = (seed / 65536) % 3 == 0;
        }
    int64_t checksum = 0, alive = 0;
    for (int generation = 0; generation < 12; generation++) {
        alive = 0;
        for (int y = 1; y <= side; y++) {
            const uint8_t *up = &cells[(y - 1) * wide], *mid = &cells[y * wide], *down = &cells[(y + 1) * wide];
            uint8_t *out = &next[y * wide];
            for (int x = 1; x <= side; x++) {
                int around = up[x - 1] + up[x] + up[x + 1] + mid[x - 1] + mid[x + 1] + down[x - 1] + down[x] + down[x + 1];
                uint8_t live = around == 3 || (around == 2 && mid[x]);
                out[x] = live;
                alive += live;
            }
        }
        cells.swap(next);
        checksum = (checksum * 31 + alive) % 1000000007;
    }
    std::printf("%lld\n%lld\n", (long long)checksum, (long long)alive);
    const size_t n = (size_t)side * side;
    std::vector<uint8_t> walls(n);
    for (int y = 0; y < side; y++)
        for (int x = 0; x < side; x++) walls[(size_t)y * side + x] = cells[(y + 1) * wide + x + 1];
    walls[0] = 0; walls[n - 1] = 0;
    std::vector<int32_t> distance(n, -1), queue;
    queue.reserve(n);
    int64_t total = 0;
    queue.push_back(0); distance[0] = 0;
    for (size_t head = 0; head < queue.size(); head++) {
        int at = queue[head], y = at / side, x = at % side, here = distance[at];
        total += here;
        for (int k = 0; k < 4; k++) {
            int ny = y + step_y[k], nx = x + step_x[k];
            if (ny < 0 || ny >= side || nx < 0 || nx >= side) continue;
            int to = ny * side + nx;
            if (!walls[to] && distance[to] < 0) { distance[to] = here + 1; queue.push_back(to); }
        }
    }
    std::printf("%zu %lld %d\n", queue.size(), (long long)total, distance[n - 1]);
    std::vector<int32_t> label(n, 0);
    int count = 0; size_t largest = 0;
    for (size_t start = 0; start < n; start++) {
        if (walls[start] || label[start]) continue;
        label[start] = ++count;
        queue.clear(); queue.push_back((int32_t)start);
        for (size_t head = 0; head < queue.size(); head++) {
            int at = queue[head], y = at / side, x = at % side;
            for (int k = 0; k < 4; k++) {
                int ny = y + step_y[k], nx = x + step_x[k];
                if (ny < 0 || ny >= side || nx < 0 || nx >= side) continue;
                int to = ny * side + nx;
                if (!walls[to] && !label[to]) { label[to] = count; queue.push_back(to); }
            }
        }
        if (queue.size() > largest) largest = queue.size();
    }
    std::printf("%d %zu\n", count, largest);
    return 0;
}
