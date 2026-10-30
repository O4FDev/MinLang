// C++ peer for main.min: parse request lines, look up users, format JSON responses.
#include <charconv>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <string>
#include <string_view>
#include <unordered_map>

struct User { int64_t id; std::string name, email; int64_t age, score; };

static void append_int(std::string &out, int64_t v) {
    char digits[24];
    auto r = std::to_chars(digits, digits + sizeof digits, v);
    out.append(digits, r.ptr);
}

int main(int argc, char **argv) {
    int64_t requests = argc > 1 ? std::atoll(argv[1]) : 0;
    std::unordered_map<int64_t, User> users;
    users.reserve(16384);
    for (int64_t id = 0; id < 10000; id++) {
        std::string n = "user" + std::to_string(id);
        users.emplace(id * 7, User{id * 7, n, n + "@example.com", 18 + id % 60, (id * 7919) % 100000});
    }
    int64_t bytes = 0, found = 0, seed = 42;
    std::string line, response;
    line.reserve(64); response.reserve(256);
    for (int64_t request = 0; request < requests; request++) {
        seed = (seed * 1103515245 + 12345) % 2147483648LL;
        line.assign("GET /users/");
        append_int(line, seed % 80000);
        line.append(" HTTP/1.1");
        std::string_view view(line);
        size_t first = view.find(' '), second = view.find(' ', first + 1);
        std::string_view path = view.substr(first + 1, second - first - 1);
        if (!path.starts_with("/users/")) continue;
        int64_t id = 0;
        std::from_chars(path.data() + 7, path.data() + path.size(), id);
        auto it = users.find(id);
        response.clear();
        if (it != users.end()) {
            const User &u = it->second;
            response.append("{\"id\":"); append_int(response, u.id);
            response.append(",\"name\":\""); response.append(u.name);
            response.append("\",\"email\":\""); response.append(u.email);
            response.append("\",\"age\":"); append_int(response, u.age);
            response.append(",\"score\":"); append_int(response, u.score);
            response.push_back('}');
            found++;
        } else {
            response.append("{\"error\":\"not found\",\"id\":"); append_int(response, id); response.push_back('}');
        }
        bytes += (int64_t)response.size();
    }
    std::printf("%lld\n%lld\n", (long long)found, (long long)bytes);
    return 0;
}
