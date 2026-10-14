#include <arpa/inet.h>
#include <errno.h>
#include <netinet/in.h>
#include <poll.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/time.h>
#include <time.h>
#include <unistd.h>

static volatile sig_atomic_t stopping;

static void stop(int signal_number) {
    (void)signal_number;
    stopping = 1;
}

static int bound(int type) {
    int fd = socket(AF_INET, type, 0);
    struct sockaddr_in address;
    memset(&address, 0, sizeof address);
    address.sin_family = AF_INET;
    address.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
    if (fd < 0 || bind(fd, (struct sockaddr *)&address, sizeof address) != 0) {
        perror("bind");
        exit(2);
    }
    return fd;
}

static int port_of(int fd) {
    struct sockaddr_in address;
    socklen_t length = sizeof address;
    if (getsockname(fd, (struct sockaddr *)&address, &length) != 0) {
        perror("getsockname");
        exit(2);
    }
    return ntohs(address.sin_port);
}

static double monotonic(void) {
    struct timespec now;
    clock_gettime(CLOCK_MONOTONIC, &now);
    return (double)now.tv_sec + (double)now.tv_nsec / 1e9;
}

int main(int argc, char **argv) {
    if (argc != 4 || (strcmp(argv[2], "0") != 0 && strcmp(argv[2], "1") != 0) || (strcmp(argv[3], "0") != 0 && strcmp(argv[3], "1") != 0)) {
        fprintf(stderr, "usage: udp-blackhole SERVER_PORT BLOCKED(0|1) CONTROL(0|1)\n");
        return 2;
    }
    struct sigaction action;
    memset(&action, 0, sizeof action);
    action.sa_handler = stop;
    sigaction(SIGTERM, &action, NULL);
    sigaction(SIGINT, &action, NULL);
    signal(SIGPIPE, SIG_IGN);
    int blocked = argv[2][0] == '1';
    int front = bound(SOCK_DGRAM);
    int back = bound(SOCK_DGRAM);
    int listener = -1;
    if (argv[3][0] == '1') {
        listener = bound(SOCK_STREAM);
        if (listen(listener, 1) != 0) {
            perror("listen");
            return 2;
        }
    }
    struct sockaddr_in server;
    memset(&server, 0, sizeof server);
    server.sin_family = AF_INET;
    server.sin_port = htons((unsigned short)atoi(argv[1]));
    server.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
    struct sockaddr_in client;
    memset(&client, 0, sizeof client);
    int have_client = 0;
    long long forwarded = 0, dropped = 0, blocked_dropped = 0;
    char events[256] = "", failures[512] = "";
    printf("READY %d %d\n", port_of(front), listener >= 0 ? port_of(listener) : 0);
    fflush(stdout);
    static unsigned char packet[65536];
    while (!stopping) {
        struct pollfd watched[3] = {{front, POLLIN, 0}, {back, POLLIN, 0}, {listener, POLLIN, 0}};
        int count = poll(watched, listener >= 0 ? 3 : 2, 1000);
        if (count < 0) {
            if (errno == EINTR) continue;
            perror("poll");
            return 2;
        }
        for (int index = 0; index < 2; index++) {
            if (!(watched[index].revents & POLLIN)) continue;
            struct sockaddr_in source;
            socklen_t length = sizeof source;
            ssize_t size = recvfrom(watched[index].fd, packet, sizeof packet, 0, (struct sockaddr *)&source, &length);
            if (size < 0) continue;
            if (index == 0) {
                client = source;
                have_client = 1;
            } else if (!have_client) {
                continue;
            }
            if (blocked) {
                dropped++;
                blocked_dropped++;
                continue;
            }
            if (index == 0) {
                sendto(back, packet, (size_t)size, 0, (struct sockaddr *)&server, sizeof server);
            } else {
                sendto(front, packet, (size_t)size, 0, (struct sockaddr *)&client, sizeof client);
            }
            forwarded++;
        }
        if (listener >= 0 && (watched[2].revents & POLLIN)) {
            int connection = accept(listener, NULL, NULL);
            if (connection < 0) continue;
            struct timeval timeout = {3, 0};
            setsockopt(connection, SOL_SOCKET, SO_RCVTIMEO, &timeout, sizeof timeout);
            unsigned char byte = 0;
            if (recv(connection, &byte, 1, 0) != 1 || byte != 'B') {
                snprintf(failures, sizeof failures, "\"unexpected blackhole control\"");
            } else {
                blocked = 1;
                snprintf(events, sizeof events, "{\"event\": \"UDP_BLOCKED\", \"monotonic\": %.6f}", monotonic());
                send(connection, "B", 1, 0);
            }
            close(connection);
            close(listener);
            listener = -1;
        }
    }
    printf("{\"forwarded\": %lld, \"dropped\": %lld, \"blocked_dropped\": %lld, \"blocked\": %s, \"events\": [%s], \"failures\": [%s]}\n",
           forwarded, dropped, blocked_dropped, blocked ? "true" : "false", events, failures);
    fflush(stdout);
    return 0;
}
