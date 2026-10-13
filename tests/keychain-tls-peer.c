#include <arpa/inet.h>
#include <errno.h>
#include <netinet/in.h>
#include <openssl/err.h>
#include <openssl/pem.h>
#include <openssl/ssl.h>
#include <openssl/x509.h>
#include <poll.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/time.h>
#include <sys/wait.h>
#include <unistd.h>

static unsigned char expected[EVP_MAX_MD_SIZE];
static unsigned int expected_length;
static int spy_port;

static void report(const char *event) {
    printf("%s\n", event);
    fflush(stdout);
}

static int listener(int *port) {
    int fd = socket(AF_INET, SOCK_STREAM, 0);
    int one = 1;
    struct sockaddr_in address;
    socklen_t length = sizeof address;
    if (fd < 0) return -1;
    setsockopt(fd, SOL_SOCKET, SO_REUSEADDR, &one, sizeof one);
    memset(&address, 0, sizeof address);
    address.sin_family = AF_INET;
    address.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
    if (bind(fd, (struct sockaddr *)&address, sizeof address) != 0 || listen(fd, 16) != 0 ||
        getsockname(fd, (struct sockaddr *)&address, &length) != 0) {
        close(fd);
        return -1;
    }
    *port = ntohs(address.sin_port);
    return fd;
}

static SSL_CTX *context(const char *certificate, const char *key, const char *client, int verified) {
    SSL_CTX *result = SSL_CTX_new(TLS_server_method());
    if (!result) return NULL;
    if (verified && SSL_CTX_set_min_proto_version(result, TLS1_3_VERSION) != 1) return NULL;
    if (SSL_CTX_use_certificate_chain_file(result, certificate) != 1 ||
        SSL_CTX_use_PrivateKey_file(result, key, SSL_FILETYPE_PEM) != 1) return NULL;
    if (verified) {
        if (SSL_CTX_load_verify_locations(result, client, NULL) != 1) return NULL;
        SSL_CTX_set_verify(result, SSL_VERIFY_PEER | SSL_VERIFY_FAIL_IF_NO_PEER_CERT, NULL);
    }
    return result;
}

static int read_request(SSL *ssl, char *path, size_t size) {
    char buffer[8192];
    size_t used = 0;
    while (used < sizeof buffer - 1) {
        int count = SSL_read(ssl, buffer + used, (int)(sizeof buffer - 1 - used));
        if (count <= 0) return -1;
        used += (size_t)count;
        buffer[used] = '\0';
        if (strstr(buffer, "\r\n\r\n")) break;
    }
    if (strncmp(buffer, "GET ", 4) != 0) return -1;
    const char *start = buffer + 4;
    const char *end = strchr(start, ' ');
    if (!end || (size_t)(end - start) >= size) return -1;
    memcpy(path, start, (size_t)(end - start));
    path[end - start] = '\0';
    return 0;
}

static void respond(SSL *ssl, const char *response) {
    SSL_write(ssl, response, (int)strlen(response));
}

static void serve(int connection, SSL_CTX *tls, int verified) {
    struct timeval timeout = {10, 0};
    char path[1024];
    char response[512];
    setsockopt(connection, SOL_SOCKET, SO_RCVTIMEO, &timeout, sizeof timeout);
    setsockopt(connection, SOL_SOCKET, SO_SNDTIMEO, &timeout, sizeof timeout);
    SSL *ssl = SSL_new(tls);
    if (!ssl || SSL_set_fd(ssl, connection) != 1 || SSL_accept(ssl) != 1 || read_request(ssl, path, sizeof path) != 0) {
        report(verified ? "HANDSHAKE-OR-REQUEST-FAILED" : "SPY-HANDSHAKE-OR-REQUEST-FAILED");
        return;
    }
    if (!verified) {
        report("SPIED");
        respond(ssl, "HTTP/1.0 200 OK\r\nContent-Length: 2\r\n\r\nok");
        SSL_shutdown(ssl);
        return;
    }
    X509 *peer = SSL_get1_peer_certificate(ssl);
    unsigned char digest[EVP_MAX_MD_SIZE];
    unsigned int digest_length = 0;
    int matched = peer && X509_digest(peer, EVP_sha256(), digest, &digest_length) == 1 &&
                  digest_length == expected_length && memcmp(digest, expected, digest_length) == 0;
    X509_free(peer);
    if (!matched) {
        report("CLIENT-CERTIFICATE-MISMATCH");
        return;
    }
    report("ACCEPTED");
    if (strcmp(path, "/redirect") == 0) {
        snprintf(response, sizeof response,
                 "HTTP/1.0 302 Found\r\nLocation: https://127.0.0.1:%d/\r\nContent-Length: 0\r\n\r\n", spy_port);
        respond(ssl, response);
    } else {
        respond(ssl, "HTTP/1.0 200 OK\r\nContent-Length: 2\r\nConnection: close\r\n\r\nok");
    }
    SSL_shutdown(ssl);
}

int main(int argc, char **argv) {
    if (argc != 4) {
        fprintf(stderr, "usage: %s SERVER.pem SERVER.key CLIENT.pem\n", argv[0]);
        return 2;
    }
    signal(SIGPIPE, SIG_IGN);
    signal(SIGCHLD, SIG_IGN);
    alarm(300);
    FILE *client = fopen(argv[3], "r");
    X509 *certificate = client ? PEM_read_X509(client, NULL, NULL, NULL) : NULL;
    if (client) fclose(client);
    if (!certificate || X509_digest(certificate, EVP_sha256(), expected, &expected_length) != 1) {
        fprintf(stderr, "cannot read the client certificate\n");
        return 1;
    }
    X509_free(certificate);
    SSL_CTX *verified = context(argv[1], argv[2], argv[3], 1);
    SSL_CTX *spy = context(argv[1], argv[2], argv[3], 0);
    if (!verified || !spy) {
        ERR_print_errors_fp(stderr);
        return 1;
    }
    int main_port = 0;
    int main_fd = listener(&main_port);
    int spy_fd = listener(&spy_port);
    if (main_fd < 0 || spy_fd < 0) {
        perror("listen");
        return 1;
    }
    printf("READY %d %d\n", main_port, spy_port);
    fflush(stdout);
    for (;;) {
        struct pollfd sockets[2] = {{main_fd, POLLIN, 0}, {spy_fd, POLLIN, 0}};
        if (poll(sockets, 2, -1) < 0) {
            if (errno == EINTR) continue;
            perror("poll");
            return 1;
        }
        for (int index = 0; index < 2; index++) {
            if (!(sockets[index].revents & POLLIN)) continue;
            int connection = accept(sockets[index].fd, NULL, NULL);
            if (connection < 0) continue;
            pid_t child = fork();
            if (child == 0) {
                close(main_fd);
                close(spy_fd);
                serve(connection, index == 0 ? verified : spy, index == 0);
                close(connection);
                _exit(0);
            }
            close(connection);
        }
    }
}
