/* Deliberately malformed peers for the public HTTP client contract. */
#include <arpa/inet.h>
#include <pthread.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <time.h>
#include <unistd.h>

static void pause_ms(long ms) {
    struct timespec delay = {ms / 1000, ms % 1000 * 1000000};
    nanosleep(&delay, NULL);
}
static void send_all(int fd, const char *bytes, size_t length) {
    while (length) {
        ssize_t sent = send(fd, bytes, length, 0);
        if (sent <= 0) return;
        bytes += sent; length -= (size_t)sent;
    }
}
static void text(int fd, const char *message) { send_all(fd, message, strlen(message)); }
static void *serve(void *raw) {
    int fd = (int)(long)raw;
    char request[4096] = {0}; size_t used = 0;
    while (!strstr(request, "\r\n\r\n") && used < sizeof request - 1) {
        ssize_t count = recv(fd, request + used, sizeof request - 1 - used, 0);
        if (count <= 0) { close(fd); return NULL; }
        used += (size_t)count; request[used] = 0;
    }
    char method[16], path[128];
    if (sscanf(request, "%15s %127s", method, path) != 2) { close(fd); return NULL; }
    if (!strcmp(path, "/truncated")) text(fd, "HTTP/1.1 200 OK\r\nContent-Length: 100\r\n\r\nhi");
    else if (!strcmp(path, "/bad-status")) text(fd, "HTTP/1.1 XYZ OK\r\nContent-Length: 2\r\n\r\nhi");
    else if (!strcmp(path, "/bad-version")) text(fd, "garbage!!200 OK\r\nContent-Length: 2\r\n\r\nhi");
    else if (!strcmp(path, "/bad-utf8")) text(fd, "HTTP/1.1 200 OK\r\nX-Test: \xff\r\n\r\nhi");
    else if (!strcmp(path, "/bare-lf")) text(fd, "HTTP/1.1 200 OK\nX: value\r\n\r\nhi");
    else if (!strcmp(path, "/bad-name")) text(fd, "HTTP/1.1 200 OK\r\nBad Name: value\r\n\r\nhi");
    else if (!strcmp(path, "/bad-length")) text(fd, "HTTP/1.1 200 OK\r\nContent-Length: -1\r\n\r\nhi");
    else if (!strcmp(path, "/overflow")) text(fd, "HTTP/1.1 200 OK\r\nContent-Length: 99999999999999999999999\r\n\r\nhi");
    else if (!strcmp(path, "/conflicting")) text(fd, "HTTP/1.1 200 OK\r\nContent-Length: 2\r\nContent-Length: 3\r\n\r\nhi");
    else if (!strcmp(path, "/duplicate")) text(fd, "HTTP/1.1 200 OK\r\nContent-Length: 2\r\ncontent-length: 2\r\n\r\nhi");
    else if (!strcmp(path, "/extra")) text(fd, "HTTP/1.1 200 OK\r\nContent-Length: 1\r\n\r\nhi");
    else if (!strcmp(path, "/chunked")) text(fd, "HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n2\r\nhi\r\n0\r\n\r\n");
    else if (!strcmp(path, "/informational")) text(fd, "HTTP/1.1 100 Continue\r\n\r\nHTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\nhi");
    else if (!strcmp(path, "/upgrade")) text(fd, "HTTP/1.1 101 Switching Protocols\r\n\r\n");
    else if (!strcmp(path, "/204")) text(fd, "HTTP/1.1 204 No Content\r\n\r\n");
    else if (!strcmp(path, "/205")) text(fd, "HTTP/1.1 205 Reset Content\r\nContent-Length: 0\r\n\r\n");
    else if (!strcmp(path, "/truncated-205")) text(fd, "HTTP/1.1 205 Reset Content\r\nContent-Length: 100\r\n\r\n");
    else if (!strcmp(path, "/content-205")) text(fd, "HTTP/1.1 205 Reset Content\r\n\r\nx");
    else if (!strcmp(path, "/304")) text(fd, "HTTP/1.1 304 Not Modified\r\nContent-Length: 100\r\n\r\n");
    else if (!strcmp(path, "/head")) text(fd, "HTTP/1.1 200 OK\r\nContent-Length: 100\r\n\r\n");
    else if (!strcmp(path, "/split")) {
        text(fd, "HTTP/1."); pause_ms(5);
        text(fd, "1 200 OK\r\nContent-Len"); pause_ms(5);
        text(fd, "gth: 2\r\n\r"); pause_ms(5); text(fd, "\nhi");
    } else if (!strcmp(path, "/keep-open")) {
        text(fd, "HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\nhi"); pause_ms(1500);
    } else if (!strcmp(path, "/oversize")) text(fd, "HTTP/1.1 200 OK\r\nContent-Length: 9\r\n\r\n123456789");
    else if (!strcmp(path, "/close")) text(fd, "HTTP/1.0 200 OK\r\n\r\nhi");
    else if (!strcmp(path, "/binary")) {
        static const char binary[] = "HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\n\xff\0";
        send_all(fd, binary, sizeof binary - 1);
    } else if (!strcmp(path, "/redirect")) {
        pause_ms(300); text(fd, "HTTP/1.1 302 Found\r\nLocation: /drip\r\nContent-Length: 0\r\n\r\n");
    } else if (!strcmp(path, "/drip")) {
        text(fd, "HTTP/1.1 200 OK\r\nContent-Length: 4\r\n\r\n");
        for (int i = 0; i < 4; ++i) { pause_ms(350); text(fd, "x"); }
    } else text(fd, "HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\nhi");
    close(fd); return NULL;
}
int main(void) {
    signal(SIGPIPE, SIG_IGN);
    int listener = socket(AF_INET, SOCK_STREAM, 0);
    struct sockaddr_in address = {.sin_family = AF_INET, .sin_addr.s_addr = htonl(INADDR_LOOPBACK)};
    socklen_t size = sizeof address;
    if (listener < 0 || bind(listener, (struct sockaddr *)&address, size) || listen(listener, 32) ||
        getsockname(listener, (struct sockaddr *)&address, &size)) { perror("listen"); return 1; }
    printf("READY %d\n", ntohs(address.sin_port)); fflush(stdout);
    for (;;) {
        int fd = accept(listener, NULL, NULL);
        if (fd < 0) return 1;
        pthread_t thread;
        if (pthread_create(&thread, NULL, serve, (void *)(long)fd)) { close(fd); return 1; }
        pthread_detach(thread);
    }
}
