#include <arpa/inet.h>
#include <netinet/in.h>
#include <pthread.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include <sys/socket.h>
#include <sys/time.h>
#include <time.h>
#include <unistd.h>

static pthread_mutex_t lock = PTHREAD_MUTEX_INITIALIZER;
static int package;
static int counted;

static void pause_ms(long milliseconds) {
    struct timespec pause = {milliseconds / 1000, (milliseconds % 1000) * 1000000};
    nanosleep(&pause, NULL);
}

static void pause_us(long microseconds) {
    struct timespec pause = {microseconds / 1000000, (microseconds % 1000000) * 1000};
    nanosleep(&pause, NULL);
}

static void send_all(int fd, const char *data, size_t length) {
    while (length > 0) {
        ssize_t sent = send(fd, data, length, MSG_NOSIGNAL);
        if (sent <= 0) return;
        data += sent;
        length -= (size_t)sent;
    }
}

static void respond(int fd, int status, const char *reason, const char *type, const char *body, const char *extra) {
    char head[512];
    int length = snprintf(head, sizeof head, "HTTP/1.1 %d %s\r\nContent-Type: %s\r\nContent-Length: %zu\r\nX-Minyar: yes\r\n%s\r\n",
                          status, reason, type, strlen(body), extra);
    send_all(fd, head, (size_t)length);
    send_all(fd, body, strlen(body));
}

static int field(const char *request, const char *name, char *value, size_t size) {
    size_t name_length = strlen(name);
    for (const char *line = strstr(request, "\r\n"); line && line[2] && line[2] != '\r'; line = strstr(line + 2, "\r\n")) {
        if (strncasecmp(line + 2, name, name_length) == 0 && line[2 + name_length] == ':') {
            const char *start = line + 3 + name_length;
            while (*start == ' ') start++;
            size_t length = strcspn(start, "\r\n");
            if (length >= size) length = size - 1;
            memcpy(value, start, length);
            value[length] = 0;
            return 1;
        }
    }
    value[0] = 0;
    return 0;
}

static void bounded(int fd, const char *path) {
    if (strcmp(path, "/header-drip") == 0) {
        const char *prefix = "HTTP/1.0 200 OK\r\nX-Fill: ";
        const char *suffix = "\r\nContent-Length: 0\r\n\r\n";
        send_all(fd, prefix, strlen(prefix));
        for (int index = 0; index < 16000; index++) {
            send_all(fd, "a", 1);
            pause_us(20);
        }
        send_all(fd, suffix, strlen(suffix));
        return;
    }
    int huge = strcmp(path, "/huge") == 0;
    char head[256];
    snprintf(head, sizeof head, "HTTP/1.0 200 OK\r\nContent-Length: %s\r\n\r\n", huge ? "999999999999999999999" : "4");
    send_all(fd, head, strlen(head));
    if (strcmp(path, "/drip") == 0) {
        for (const char *byte = "good"; *byte; byte++) {
            send_all(fd, byte, 1);
            pause_ms(40);
        }
    } else if (huge) {
        static char body[131072];
        memset(body, 'x', sizeof body);
        send_all(fd, body, sizeof body);
    } else {
        send_all(fd, "good", 4);
    }
}

static void served(int fd, const char *method, const char *path, const char *request, const char *body) {
    if (strcmp(method, "POST") == 0) {
        char raw[128], test[256], value[256] = "", reply[1024];
        field(request, "X-Test", raw, sizeof raw);
        size_t used = 0;
        for (const unsigned char *byte = (const unsigned char *)raw; *byte; byte++) {
            if (*byte < 0x80) {
                test[used++] = (char)*byte;
            } else {
                test[used++] = (char)(0xc0 | (*byte >> 6));
                test[used++] = (char)(0x80 | (*byte & 0x3f));
            }
        }
        test[used] = 0;
        const char *key = strstr(body, "\"a\"");
        if (key) {
            const char *open = strchr(key + 3, '"');
            const char *close = open ? strchr(open + 1, '"') : NULL;
            if (close && (size_t)(close - open - 1) < sizeof value) {
                memcpy(value, open + 1, (size_t)(close - open - 1));
                value[close - open - 1] = 0;
            }
        }
        snprintf(reply, sizeof reply, "{\"method\": \"POST\", \"test\": \"%s\", \"body\": \"%s\"}", test, value);
        respond(fd, 201, "Created", "application/json", reply, "");
    } else if (strcmp(method, "DELETE") == 0) {
        respond(fd, 404, "Not Found", "text/plain; charset=utf-8", "missing", "");
    } else if (strcmp(path, "/plain") == 0) {
        respond(fd, 200, "OK", "text/plain; charset=utf-8", "h\xc3\xa9llo", "");
    } else if (strcmp(path, "/stream") == 0) {
        const char *head = "HTTP/1.1 200 OK\r\nContent-Type: application/x-ndjson\r\nTransfer-Encoding: chunked\r\n\r\n";
        send_all(fd, head, strlen(head));
        const char *pieces[] = {"caf", "\xc3", "\xa9 ", "done"};
        for (int index = 0; index < 4; index++) {
            char chunk[64];
            int length = snprintf(chunk, sizeof chunk, "%zx\r\n%s\r\n", strlen(pieces[index]), pieces[index]);
            send_all(fd, chunk, (size_t)length);
            pause_ms(150);
        }
        send_all(fd, "0\r\n\r\n", 5);
    } else if (strcmp(path, "/counted") == 0) {
        char data[32], head[256];
        pthread_mutex_lock(&lock);
        snprintf(data, sizeof data, "%d", ++counted);
        pthread_mutex_unlock(&lock);
        int length = snprintf(head, sizeof head, "HTTP/1.1 200 OK\r\nContent-Length: %zu\r\nCache-Control: public, max-age=600\r\n\r\n%s", strlen(data), data);
        send_all(fd, head, (size_t)length);
    } else if (strcmp(path, "/slow") == 0) {
        pause_ms(2000);
        respond(fd, 200, "OK", "text/plain; charset=utf-8", "late", "");
    } else {
        respond(fd, 404, "Not Found", "text/plain; charset=utf-8", "no", "");
    }
}

static void *serve(void *argument) {
    int fd = (int)(long)argument;
    struct timeval timeout = {10, 0};
    setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO, &timeout, sizeof timeout);
    char request[65536];
    request[0] = 0;
    size_t used = 0;
    for (;;) {
        char *end;
        while (!(end = strstr(request, "\r\n\r\n")) || used == 0) {
            if (used >= sizeof request - 1) { close(fd); return NULL; }
            ssize_t count = recv(fd, request + used, sizeof request - 1 - used, 0);
            if (count <= 0) { close(fd); return NULL; }
            used += (size_t)count;
            request[used] = 0;
        }
        char method[16], path[8192], host[1024], length_text[32];
        if (sscanf(request, "%15s %8191s", method, path) != 2) { close(fd); return NULL; }
        if (strcmp(path, "/upload-stall") == 0) {
            pause_ms(1500);
            close(fd);
            return NULL;
        }
        field(request, "Host", host, sizeof host);
        size_t head_length = (size_t)(end - request) + 4;
        size_t body_length = field(request, "Content-Length", length_text, sizeof length_text) ? (size_t)strtoul(length_text, NULL, 10) : 0;
        if (body_length > sizeof request - 1 - head_length) { close(fd); return NULL; }
        while (used < head_length + body_length) {
            ssize_t count = recv(fd, request + used, sizeof request - 1 - used, 0);
            if (count <= 0) { close(fd); return NULL; }
            used += (size_t)count;
            request[used] = 0;
        }
        char body[65536];
        memcpy(body, request + head_length, body_length);
        body[body_length] = 0;
        pthread_mutex_lock(&lock);
        printf("REQUEST %s %s\n", path, host);
        fflush(stdout);
        pthread_mutex_unlock(&lock);
        if (!package) {
            bounded(fd, path);
            close(fd);
            return NULL;
        }
        served(fd, method, path, request, body);
        memmove(request, request + head_length + body_length, used - head_length - body_length);
        used -= head_length + body_length;
        request[used] = 0;
    }
}

int main(int argc, char **argv) {
    if (argc != 3 || (strcmp(argv[1], "bounded") != 0 && strcmp(argv[1], "package") != 0) || (strcmp(argv[2], "4") != 0 && strcmp(argv[2], "6") != 0)) {
        fprintf(stderr, "usage: http-peer bounded|package 4|6\n");
        return 2;
    }
    package = strcmp(argv[1], "package") == 0;
    int six = argv[2][0] == '6';
    int listener = socket(six ? AF_INET6 : AF_INET, SOCK_STREAM, 0);
    int enabled = 1;
    setsockopt(listener, SOL_SOCKET, SO_REUSEADDR, &enabled, sizeof enabled);
    struct sockaddr_storage storage;
    memset(&storage, 0, sizeof storage);
    socklen_t length;
    if (six) {
        struct sockaddr_in6 *address = (struct sockaddr_in6 *)&storage;
        address->sin6_family = AF_INET6;
        address->sin6_addr = in6addr_loopback;
        length = sizeof *address;
    } else {
        struct sockaddr_in *address = (struct sockaddr_in *)&storage;
        address->sin_family = AF_INET;
        address->sin_addr.s_addr = htonl(INADDR_LOOPBACK);
        length = sizeof *address;
    }
    if (listener < 0 || bind(listener, (struct sockaddr *)&storage, length) != 0 || listen(listener, 64) != 0 ||
        getsockname(listener, (struct sockaddr *)&storage, &length) != 0) {
        perror("listen");
        return 2;
    }
    int port = six ? ntohs(((struct sockaddr_in6 *)&storage)->sin6_port) : ntohs(((struct sockaddr_in *)&storage)->sin_port);
    printf("READY %d\n", port);
    fflush(stdout);
    for (;;) {
        int fd = accept(listener, NULL, NULL);
        if (fd < 0) continue;
        pthread_t thread;
        if (pthread_create(&thread, NULL, serve, (void *)(long)fd) != 0) { close(fd); continue; }
        pthread_detach(thread);
    }
}
