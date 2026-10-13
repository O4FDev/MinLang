#include <arpa/inet.h>
#include <netinet/in.h>
#include <pthread.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include <sys/socket.h>
#include <sys/stat.h>
#include <sys/time.h>
#include <time.h>
#include <unistd.h>

typedef struct { unsigned char *query; size_t query_length; long long delay_us; unsigned char *body; size_t body_length; } Entry;

static Entry *entries;
static size_t entry_count;
static const char *control;
static pthread_mutex_t lock = PTHREAD_MUTEX_INITIALIZER;

static long long monotonic_us(void) {
    struct timespec now;
    clock_gettime(CLOCK_MONOTONIC, &now);
    return (long long)now.tv_sec * 1000000 + now.tv_nsec / 1000;
}

static void pause_us(long long microseconds) {
    struct timespec pause = {microseconds / 1000000, (microseconds % 1000000) * 1000};
    nanosleep(&pause, NULL);
}

static uint64_t read_number(FILE *file, int bytes) {
    uint64_t value = 0;
    for (int index = 0; index < bytes; index++) {
        int byte = fgetc(file);
        if (byte == EOF) exit(2);
        value = value << 8 | (uint64_t)byte;
    }
    return value;
}

static unsigned char *read_bytes(FILE *file, size_t length) {
    unsigned char *data = malloc(length + 1);
    if (!data || fread(data, 1, length, file) != length) exit(2);
    data[length] = 0;
    return data;
}

static void load(const char *path) {
    FILE *file = fopen(path, "rb");
    if (!file) exit(2);
    entry_count = (size_t)read_number(file, 4);
    entries = calloc(entry_count, sizeof *entries);
    for (size_t index = 0; index < entry_count; index++) {
        entries[index].query_length = (size_t)read_number(file, 4);
        entries[index].query = read_bytes(file, entries[index].query_length);
        entries[index].delay_us = (long long)read_number(file, 8);
        entries[index].body_length = (size_t)read_number(file, 4);
        entries[index].body = read_bytes(file, entries[index].body_length);
    }
    fclose(file);
}

static void send_all(int fd, const void *data, size_t length) {
    const char *bytes = data;
    while (length > 0) {
        ssize_t sent = send(fd, bytes, length, MSG_NOSIGNAL);
        if (sent <= 0) return;
        bytes += sent;
        length -= (size_t)sent;
    }
}

static int hex(int character) {
    if (character >= '0' && character <= '9') return character - '0';
    if (character >= 'a' && character <= 'f') return character - 'a' + 10;
    if (character >= 'A' && character <= 'F') return character - 'A' + 10;
    return -1;
}

static size_t unquote(const char *source, size_t length, unsigned char *target) {
    size_t used = 0;
    for (size_t index = 0; index < length; index++) {
        if (source[index] == '+') target[used++] = ' ';
        else if (source[index] == '%' && index + 2 < length && hex(source[index + 1]) >= 0 && hex(source[index + 2]) >= 0) {
            target[used++] = (unsigned char)(hex(source[index + 1]) * 16 + hex(source[index + 2]));
            index += 2;
        } else target[used++] = (unsigned char)source[index];
    }
    return used;
}

static int blocked(const unsigned char *query, size_t length) {
    char path[4096];
    snprintf(path, sizeof path, "%s/block", control);
    FILE *file = fopen(path, "rb");
    if (!file) return 0;
    unsigned char held[8192];
    size_t size = fread(held, 1, sizeof held, file);
    fclose(file);
    return size == length && memcmp(held, query, length) == 0;
}

static void *serve(void *argument) {
    int fd = (int)(long)argument;
    char request[16384];
    size_t used = 0;
    request[0] = 0;
    while (!strstr(request, "\r\n\r\n")) {
        if (used >= sizeof request - 1) { close(fd); return NULL; }
        ssize_t count = recv(fd, request + used, sizeof request - 1 - used, 0);
        if (count <= 0) { close(fd); return NULL; }
        used += (size_t)count;
        request[used] = 0;
    }
    char path[8192];
    if (sscanf(request, "%*s %8191s", path) != 1) { close(fd); return NULL; }
    pthread_mutex_lock(&lock);
    printf("CALL %s\n", path);
    fflush(stdout);
    pthread_mutex_unlock(&lock);
    unsigned char query[8192];
    size_t query_length = 0;
    int found_query = 0;
    char *question = strchr(path, '?');
    if (question) {
        char *fragment = strchr(question, '#');
        if (fragment) *fragment = 0;
        for (char *part = question + 1; part && *part;) {
            char *next = strchr(part, '&');
            size_t length = next ? (size_t)(next - part) : strlen(part);
            char *equals = memchr(part, '=', length);
            if (equals) {
                unsigned char name[8192];
                size_t name_length = unquote(part, (size_t)(equals - part), name);
                if (!found_query && name_length == 1 && name[0] == 'q') {
                    query_length = unquote(equals + 1, length - (size_t)(equals + 1 - part), query);
                    found_query = 1;
                }
            }
            part = next ? next + 1 : NULL;
        }
    }
    Entry *entry = NULL;
    for (size_t index = 0; index < entry_count; index++) {
        if (entries[index].query_length == query_length && memcmp(entries[index].query, query, query_length) == 0) { entry = &entries[index]; break; }
    }
    if (blocked(query, query_length)) {
        char release[4096];
        snprintf(release, sizeof release, "%s/release", control);
        long long deadline = monotonic_us() + 4000000;
        struct stat status;
        while (stat(release, &status) != 0 && monotonic_us() < deadline) pause_us(5000);
    }
    if (entry) pause_us(entry->delay_us);
    const unsigned char *body = entry ? entry->body : (const unsigned char *)"unknown query";
    size_t body_length = entry ? entry->body_length : 13;
    char head[256];
    int head_length = snprintf(head, sizeof head, "HTTP/1.1 %s\r\ncontent-type: application/json\r\ncontent-length: %zu\r\nconnection: close\r\n\r\n",
                               entry ? "200 OK" : "404 Not Found", body_length);
    send_all(fd, head, (size_t)head_length);
    send_all(fd, body, body_length);
    close(fd);
    return NULL;
}

static int server(const char *table) {
    load(table);
    int listener = socket(AF_INET, SOCK_STREAM, 0);
    int enabled = 1;
    setsockopt(listener, SOL_SOCKET, SO_REUSEADDR, &enabled, sizeof enabled);
    struct sockaddr_in address;
    memset(&address, 0, sizeof address);
    address.sin_family = AF_INET;
    address.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
    socklen_t length = sizeof address;
    if (listener < 0 || bind(listener, (struct sockaddr *)&address, sizeof address) != 0 || listen(listener, 128) != 0 ||
        getsockname(listener, (struct sockaddr *)&address, &length) != 0) return 2;
    printf("READY %d\n", ntohs(address.sin_port));
    fflush(stdout);
    for (;;) {
        int fd = accept(listener, NULL, NULL);
        if (fd < 0) continue;
        pthread_t thread;
        if (pthread_create(&thread, NULL, serve, (void *)(long)fd) != 0) { close(fd); continue; }
        pthread_detach(thread);
    }
}

static int fetch(int port, const char *list, const char *output, long long timeout_ms, long long budget_ms) {
    FILE *paths = fopen(list, "rb");
    if (!paths) return 2;
    char path[8192];
    static unsigned char response[8 << 20];
    long long begun = monotonic_us();
    for (long index = 0; fgets(path, sizeof path, paths); index++) {
        path[strcspn(path, "\n")] = 0;
        long long started = monotonic_us();
        long long limit = timeout_ms;
        if (budget_ms > 0) {
            long long remaining = budget_ms - (started - begun) / 1000;
            if (remaining <= 0) { printf("%ld ERROR deadline\n", index); return 1; }
            if (remaining < limit) limit = remaining;
        }
        int fd = socket(AF_INET, SOCK_STREAM, 0);
        struct timeval timeout = {limit / 1000, (limit % 1000) * 1000};
        setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO, &timeout, sizeof timeout);
        setsockopt(fd, SOL_SOCKET, SO_SNDTIMEO, &timeout, sizeof timeout);
        struct sockaddr_in address;
        memset(&address, 0, sizeof address);
        address.sin_family = AF_INET;
        address.sin_port = htons((unsigned short)port);
        address.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
        if (fd < 0 || connect(fd, (struct sockaddr *)&address, sizeof address) != 0) { printf("%ld ERROR connect\n", index); return 1; }
        char request[9000];
        int request_length = snprintf(request, sizeof request, "GET %s HTTP/1.1\r\nHost: 127.0.0.1:%d\r\nAccept-Encoding: identity\r\nConnection: close\r\n\r\n", path, port);
        send_all(fd, request, (size_t)request_length);
        size_t used = 0;
        for (;;) {
            ssize_t count = recv(fd, response + used, sizeof response - used, 0);
            if (count < 0) { printf("%ld ERROR receive\n", index); return 1; }
            if (count == 0) break;
            used += (size_t)count;
            if (used == sizeof response) { printf("%ld ERROR oversized\n", index); return 1; }
        }
        close(fd);
        long long elapsed = monotonic_us() - started;
        unsigned char *end = NULL;
        for (size_t at = 0; at + 4 <= used; at++) if (memcmp(response + at, "\r\n\r\n", 4) == 0) { end = response + at; break; }
        if (!end) { printf("%ld ERROR headers\n", index); return 1; }
        *end = 0;
        int status = 0;
        sscanf((char *)response, "HTTP/%*s %d", &status);
        char cache[64] = "-";
        long long declared = -1;
        for (char *line = strstr((char *)response, "\r\n"); line; line = strstr(line + 2, "\r\n")) {
            if (strncasecmp(line + 2, "x-cache:", 8) == 0) sscanf(line + 10, " %63[^\r\n]", cache);
            if (strncasecmp(line + 2, "content-length:", 15) == 0) declared = atoll(line + 17);
        }
        size_t body_length = used - (size_t)(end + 4 - response);
        char name[4096];
        snprintf(name, sizeof name, "%s/%ld.body", output, index);
        FILE *body = fopen(name, "wb");
        if (!body || fwrite(end + 4, 1, body_length, body) != body_length || fclose(body) != 0) return 2;
        printf("%ld %d %lld %lld %zu %s\n", index, status, elapsed, declared, body_length, cache);
        fflush(stdout);
    }
    fclose(paths);
    printf("DONE\n");
    return 0;
}

int main(int argc, char **argv) {
    if (argc == 4 && strcmp(argv[1], "serve") == 0) {
        control = argv[3];
        return server(argv[2]);
    }
    if (argc == 7 && strcmp(argv[1], "fetch") == 0) return fetch(atoi(argv[2]), argv[3], argv[4], atoll(argv[5]), atoll(argv[6]));
    fprintf(stderr, "usage: replay serve TABLE CONTROL | fetch PORT PATHS OUTPUT TIMEOUT_MS BUDGET_MS\n");
    return 2;
}
