#include <arpa/inet.h>
#include <errno.h>
#include <netinet/in.h>
#include <openssl/err.h>
#include <openssl/ssl.h>
#include <poll.h>
#include <pthread.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/time.h>
#include <time.h>
#include <unistd.h>

#define RESPONSE "HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\nok"
#define REQUEST "GET /heartbeat HTTP/1.1\r\nHost: fixture\r\n\r\n"
#define REQUEST_LIMIT 65536

static char large[70000];
static const char response[] = RESPONSE;

struct server;
struct connection {
    int fd;
    SSL *ssl;
    int member;
    int reading;
    long reads;
    int writes[64];
    int write_count;
    struct server *server;
    struct connection *next;
};
struct server {
    SSL_CTX *context;
    int listener;
    int port;
    pthread_t acceptor;
    pthread_mutex_t lock;
    pthread_cond_t changed;
    long connections, responses, malformed, oversized, closed, slow;
    char unexpected[4096];
    int unexpected_count;
    struct connection *all;
    int retained;
    int workers;
    int stopping;
    long finished;
    long last_reads;
    int last_writes[64];
    int last_write_count;
};

static void note_unexpected(struct server *server, const char *text) {
    size_t used = strlen(server->unexpected);
    snprintf(server->unexpected + used, sizeof server->unexpected - used, "%s\"%s\"", server->unexpected_count ? ", " : "", text);
    server->unexpected_count++;
}

static int send_part(struct connection *item, const char *data, int length) {
    if (item->write_count < 64) item->writes[item->write_count++] = length;
    return SSL_write(item->ssl, data, length) == length;
}

static int ends_request(const char *buffer, size_t used) {
    for (size_t index = 3; index < used; index++)
        if (buffer[index - 3] == '\r' && buffer[index - 2] == '\n' && buffer[index - 1] == '\r' && buffer[index] == '\n') return (int)index + 1;
    return 0;
}

static void pause_unless_stopping(struct server *server, int milliseconds) {
    for (int waited = 0; waited < milliseconds; waited += 10) {
        pthread_mutex_lock(&server->lock);
        int stopping = server->stopping;
        pthread_mutex_unlock(&server->lock);
        if (stopping) return;
        poll(NULL, 0, 10);
    }
}

static void *serve_connection(void *argument) {
    struct connection *item = argument;
    struct server *server = item->server;
    struct timeval handshake = {10, 0}, unlimited = {0, 0};
    setsockopt(item->fd, SOL_SOCKET, SO_RCVTIMEO, &handshake, sizeof handshake);
    if (SSL_accept(item->ssl) == 1) {
        setsockopt(item->fd, SOL_SOCKET, SO_RCVTIMEO, &unlimited, sizeof unlimited);
        pthread_mutex_lock(&server->lock);
        long identity = ++server->connections;
        item->member = 1;
        server->retained++;
        pthread_cond_broadcast(&server->changed);
        pthread_mutex_unlock(&server->lock);
        X509 *peer = SSL_get1_peer_certificate(item->ssl);
        char buffer[REQUEST_LIMIT + 1];
        size_t used = 0;
        int requests = 0;
        if (!peer) {
            pthread_mutex_lock(&server->lock);
            note_unexpected(server, "peer lacked mutual TLS identity");
            pthread_mutex_unlock(&server->lock);
        }
        while (peer) {
            int length;
            while ((length = ends_request(buffer, used)) == 0) {
                if (used >= REQUEST_LIMIT) {
                    pthread_mutex_lock(&server->lock);
                    note_unexpected(server, "request header exceeded 64 KiB");
                    pthread_mutex_unlock(&server->lock);
                    goto finish;
                }
                pthread_mutex_lock(&server->lock);
                item->reading = 1;
                pthread_cond_broadcast(&server->changed);
                pthread_mutex_unlock(&server->lock);
                int got = SSL_read(item->ssl, buffer + used, (int)(REQUEST_LIMIT - used));
                pthread_mutex_lock(&server->lock);
                item->reading = 0;
                pthread_mutex_unlock(&server->lock);
                if (got <= 0) goto finish;
                used += (size_t)got;
            }
            item->reads++;
            if (strncmp(buffer, "GET /heartbeat HTTP/1.1\r\n", 25) != 0) {
                pthread_mutex_lock(&server->lock);
                note_unexpected(server, "request was not a heartbeat");
                pthread_mutex_unlock(&server->lock);
                goto finish;
            }
            memmove(buffer, buffer + length, used - (size_t)length);
            used -= (size_t)length;
            requests++;
            if (requests == 1 && identity % 19 == 0) {
                pthread_mutex_lock(&server->lock);
                server->oversized++;
                pthread_mutex_unlock(&server->lock);
                const char *head = "HTTP/1.1 200 OK\r\nContent-Length: 70000\r\n\r\n";
                if (!send_part(item, head, (int)strlen(head)) || !send_part(item, large, (int)sizeof large)) goto finish;
            } else if (requests == 1 && identity % 11 == 0) {
                char malformed[300];
                int size = snprintf(malformed, sizeof malformed, "HTTP/1.1 nope\r\nMalformed\r\n\r\n");
                memset(malformed + size, '?', 256);
                pthread_mutex_lock(&server->lock);
                server->malformed++;
                pthread_mutex_unlock(&server->lock);
                if (!send_part(item, malformed, size + 256)) goto finish;
            } else if (requests == 7) {
                pthread_mutex_lock(&server->lock);
                server->closed++;
                pthread_mutex_unlock(&server->lock);
                break;
            } else {
                if (requests == 2 && identity % 13 == 0) {
                    pthread_mutex_lock(&server->lock);
                    server->slow++;
                    pthread_mutex_unlock(&server->lock);
                    pause_unless_stopping(server, 1000);
                }
                if (!send_part(item, response, 7) || !send_part(item, response + 7, (int)sizeof response - 8)) goto finish;
                pthread_mutex_lock(&server->lock);
                server->responses++;
                pthread_mutex_unlock(&server->lock);
            }
        }
    finish:
        if (peer) X509_free(peer);
    }
    SSL_shutdown(item->ssl);
    pthread_mutex_lock(&server->lock);
    struct connection **link = &server->all;
    while (*link && *link != item) link = &(*link)->next;
    if (*link) *link = item->next;
    if (item->member) {
        server->retained--;
        server->finished++;
        server->last_reads = item->reads;
        server->last_write_count = item->write_count;
        memcpy(server->last_writes, item->writes, sizeof item->writes);
    }
    server->workers--;
    pthread_cond_broadcast(&server->changed);
    pthread_mutex_unlock(&server->lock);
    SSL_free(item->ssl);
    close(item->fd);
    free(item);
    return NULL;
}

static void *accept_loop(void *argument) {
    struct server *server = argument;
    for (;;) {
        struct pollfd ready = {server->listener, POLLIN, 0};
        int count = poll(&ready, 1, 100);
        pthread_mutex_lock(&server->lock);
        int stopping = server->stopping;
        pthread_mutex_unlock(&server->lock);
        if (stopping) return NULL;
        if (count <= 0) continue;
        int fd = accept(server->listener, NULL, NULL);
        if (fd < 0) continue;
        struct connection *item = calloc(1, sizeof *item);
        item->fd = fd;
        item->server = server;
        item->ssl = SSL_new(server->context);
        SSL_set_fd(item->ssl, fd);
        pthread_mutex_lock(&server->lock);
        item->next = server->all;
        server->all = item;
        server->workers++;
        pthread_mutex_unlock(&server->lock);
        pthread_t thread;
        if (pthread_create(&thread, NULL, serve_connection, item) == 0) pthread_detach(thread);
        else serve_connection(item);
    }
}

static int select_alpn(SSL *ssl, const unsigned char **out, unsigned char *length, const unsigned char *in, unsigned int size, void *argument) {
    (void)ssl;
    (void)argument;
    for (unsigned int offset = 0; offset < size;) {
        unsigned int item = in[offset];
        if (offset + 1 + item > size) break;
        if (item == 8 && memcmp(in + offset + 1, "http/1.1", 8) == 0) {
            *out = in + offset + 1;
            *length = (unsigned char)item;
            return SSL_TLSEXT_ERR_OK;
        }
        offset += 1 + item;
    }
    return SSL_TLSEXT_ERR_NOACK;
}

static int start_server(struct server *server, const char *certificate, const char *key, const char *root) {
    memset(server, 0, sizeof *server);
    pthread_mutex_init(&server->lock, NULL);
    pthread_cond_init(&server->changed, NULL);
    server->context = SSL_CTX_new(TLS_server_method());
    SSL_CTX_set_min_proto_version(server->context, TLS1_3_VERSION);
    SSL_CTX_set_max_proto_version(server->context, TLS1_3_VERSION);
    if (SSL_CTX_use_certificate_chain_file(server->context, certificate) != 1 || SSL_CTX_use_PrivateKey_file(server->context, key, SSL_FILETYPE_PEM) != 1 ||
        SSL_CTX_load_verify_locations(server->context, root, NULL) != 1) return 0;
    SSL_CTX_set_verify(server->context, SSL_VERIFY_PEER | SSL_VERIFY_FAIL_IF_NO_PEER_CERT, NULL);
    SSL_CTX_set_alpn_select_cb(server->context, select_alpn, NULL);
    server->listener = socket(AF_INET, SOCK_STREAM, 0);
    int one = 1;
    setsockopt(server->listener, SOL_SOCKET, SO_REUSEADDR, &one, sizeof one);
    struct sockaddr_in address;
    memset(&address, 0, sizeof address);
    address.sin_family = AF_INET;
    address.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
    socklen_t size = sizeof address;
    if (bind(server->listener, (struct sockaddr *)&address, sizeof address) != 0 || listen(server->listener, 512) != 0 ||
        getsockname(server->listener, (struct sockaddr *)&address, &size) != 0) return 0;
    server->port = ntohs(address.sin_port);
    return pthread_create(&server->acceptor, NULL, accept_loop, server) == 0;
}

// Cancels every active connection and waits until each worker has released it.
static void stop_server(struct server *server) {
    pthread_mutex_lock(&server->lock);
    server->stopping = 1;
    for (struct connection *item = server->all; item; item = item->next) shutdown(item->fd, SHUT_RDWR);
    pthread_mutex_unlock(&server->lock);
    pthread_join(server->acceptor, NULL);
    close(server->listener);
    pthread_mutex_lock(&server->lock);
    while (server->workers > 0) pthread_cond_wait(&server->changed, &server->lock);
    pthread_mutex_unlock(&server->lock);
    SSL_CTX_free(server->context);
}

static void stats_json(struct server *server, char *out, size_t size) {
    snprintf(out, size, "{\"connections\": %ld, \"responses\": %ld, \"malformed\": %ld, \"oversized\": %ld, \"closed\": %ld, \"slow\": %ld}",
             server->connections, server->responses, server->malformed, server->oversized, server->closed, server->slow);
}

static void publish(struct server *server, const char *path) {
    char text[512], temporary[4096];
    pthread_mutex_lock(&server->lock);
    stats_json(server, text, sizeof text);
    pthread_mutex_unlock(&server->lock);
    snprintf(temporary, sizeof temporary, "%s.tmp", path);
    FILE *file = fopen(temporary, "w");
    if (!file) return;
    fprintf(file, "%s\n", text);
    fclose(file);
    rename(temporary, path);
}

static int serve(char **argv) {
    sigset_t signals;
    sigemptyset(&signals);
    sigaddset(&signals, SIGTERM);
    sigaddset(&signals, SIGINT);
    pthread_sigmask(SIG_BLOCK, &signals, NULL);
    signal(SIGPIPE, SIG_IGN);
    static struct server server;
    if (!start_server(&server, argv[2], argv[3], argv[4])) {
        ERR_print_errors_fp(stderr);
        return 1;
    }
    printf("READY %d\n", server.port);
    fflush(stdout);
    for (;;) {
        publish(&server, argv[5]);
        struct timespec second = {1, 0};
#ifdef __linux__
        if (sigtimedwait(&signals, NULL, &second) > 0) break;
#else
        int received = 0;
        nanosleep(&second, NULL);
        if (sigpending(&signals) == 0 && (sigismember(&signals, SIGTERM) || sigismember(&signals, SIGINT))) { sigwait(&signals, &received); break; }
        sigemptyset(&signals);
        sigaddset(&signals, SIGTERM);
        sigaddset(&signals, SIGINT);
#endif
    }
    stop_server(&server);
    publish(&server, argv[5]);
    char text[512];
    stats_json(&server, text, sizeof text);
    printf("{\"stats\": %s, \"unexpected\": [%s], \"retained\": %d}\n", text, server.unexpected, server.retained);
    return 0;
}

static int connect_client(SSL_CTX *context, int port, SSL **ssl) {
    int fd = socket(AF_INET, SOCK_STREAM, 0);
    struct sockaddr_in address;
    memset(&address, 0, sizeof address);
    address.sin_family = AF_INET;
    address.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
    address.sin_port = htons((unsigned short)port);
    struct timeval timeout = {5, 0};
    setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO, &timeout, sizeof timeout);
    if (connect(fd, (struct sockaddr *)&address, sizeof address) != 0) return -1;
    *ssl = SSL_new(context);
    SSL_set_fd(*ssl, fd);
    SSL_set_tlsext_host_name(*ssl, "localhost");
    if (SSL_connect(*ssl) != 1) return -1;
    return fd;
}

static int read_exact(SSL *ssl, char *buffer, int length) {
    int used = 0;
    while (used < length) {
        int got = SSL_read(ssl, buffer + used, length - used);
        if (got <= 0) return 0;
        used += got;
    }
    return 1;
}

static int wait_for(struct server *server, int finished, int reading) {
    struct timespec deadline;
    clock_gettime(CLOCK_REALTIME, &deadline);
    deadline.tv_sec += 5;
    pthread_mutex_lock(&server->lock);
    int ok = 0;
    for (;;) {
        int active = server->all && server->all->reading;
        if ((finished && server->finished >= 1) || (reading && active)) {
            ok = 1;
            break;
        }
        if (pthread_cond_timedwait(&server->changed, &server->lock, &deadline) == ETIMEDOUT) break;
    }
    pthread_mutex_unlock(&server->lock);
    return ok;
}

// Exercises every connection outcome against the maintained connection
// handler; each case has its own server so its identity is one.
static int self_test(char **argv) {
    signal(SIGPIPE, SIG_IGN);
    const char *cases[] = {"normal", "eof", "reset_body", "ssl_body", "cancel_body", "unexpected_body"};
    SSL_CTX *client = SSL_CTX_new(TLS_client_method());
    SSL_CTX_set_min_proto_version(client, TLS1_3_VERSION);
    if (SSL_CTX_use_certificate_chain_file(client, argv[5]) != 1 || SSL_CTX_use_PrivateKey_file(client, argv[6], SSL_FILETYPE_PEM) != 1 ||
        SSL_CTX_load_verify_locations(client, argv[4], NULL) != 1) {
        ERR_print_errors_fp(stderr);
        return 1;
    }
    SSL_CTX_set_verify(client, SSL_VERIFY_PEER, NULL);
    printf("[");
    for (size_t index = 0; index < sizeof cases / sizeof *cases; index++) {
        const char *name = cases[index];
        static struct server server;
        if (!start_server(&server, argv[2], argv[3], argv[4])) {
            ERR_print_errors_fp(stderr);
            return 1;
        }
        SSL *ssl = NULL;
        int fd = connect_client(client, server.port, &ssl);
        int received = 0, completed = 0, member_before_cancel = -1;
        if (fd >= 0) {
            if (strcmp(name, "normal") == 0) {
                char buffer[64];
                for (int request = 0; request < 7; request++) {
                    if (SSL_write(ssl, REQUEST, (int)strlen(REQUEST)) <= 0) break;
                    if (request < 6 && read_exact(ssl, buffer, (int)strlen(RESPONSE)) && memcmp(buffer, RESPONSE, strlen(RESPONSE)) == 0) received++;
                }
                completed = wait_for(&server, 1, 0) && SSL_read(ssl, buffer, 1) <= 0;
            } else if (strcmp(name, "eof") == 0) {
                SSL_shutdown(ssl);
                shutdown(fd, SHUT_WR);
                completed = wait_for(&server, 1, 0);
            } else if (strcmp(name, "reset_body") == 0) {
                SSL_write(ssl, "GET /heart", 10);
                wait_for(&server, 0, 1);
                struct linger reset = {1, 0};
                setsockopt(fd, SOL_SOCKET, SO_LINGER, &reset, sizeof reset);
                close(fd);
                fd = -1;
                completed = wait_for(&server, 1, 0);
            } else if (strcmp(name, "ssl_body") == 0) {
                wait_for(&server, 0, 1);
                char garbage[64];
                memset(garbage, 0x16, sizeof garbage);
                completed = write(fd, garbage, sizeof garbage) == (ssize_t)sizeof garbage && wait_for(&server, 1, 0);
            } else if (strcmp(name, "cancel_body") == 0) {
                completed = wait_for(&server, 0, 1);
                pthread_mutex_lock(&server.lock);
                member_before_cancel = server.retained;
                pthread_mutex_unlock(&server.lock);
            } else {
                const char *wrong = "POST /x HTTP/1.1\r\n\r\n";
                SSL_write(ssl, wrong, (int)strlen(wrong));
                completed = wait_for(&server, 1, 0);
            }
        }
        stop_server(&server);
        if (ssl) SSL_free(ssl);
        if (fd >= 0) close(fd);
        char stats[512];
        stats_json(&server, stats, sizeof stats);
        printf("%s{\"name\": \"%s\", \"completed\": %s, \"received\": %d, \"membership_before_cancel\": %d, \"retained\": %d, \"workers\": %d, \"reads\": %ld, \"writes\": [",
               index ? ", " : "", name, completed ? "true" : "false", received, member_before_cancel, server.retained, server.workers, server.last_reads);
        for (int write_index = 0; write_index < server.last_write_count; write_index++) printf("%s%d", write_index ? ", " : "", server.last_writes[write_index]);
        printf("], \"stats\": %s, \"unexpected\": [%s]}", stats, server.unexpected);
    }
    printf("]\n");
    SSL_CTX_free(client);
    return 0;
}

int main(int argc, char **argv) {
    memset(large, 'x', sizeof large);
    if (argc == 6 && strcmp(argv[1], "serve") == 0) return serve(argv);
    if (argc == 7 && strcmp(argv[1], "self-test") == 0) return self_test(argv);
    fprintf(stderr, "usage: tls-soak-peer serve CERT KEY ROOT STATUS | self-test CERT KEY ROOT CLIENT-CERT CLIENT-KEY\n");
    return 2;
}
