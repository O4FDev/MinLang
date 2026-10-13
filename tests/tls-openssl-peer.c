#include <arpa/inet.h>
#include <netinet/in.h>
#include <openssl/err.h>
#include <openssl/ssl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/time.h>
#include <unistd.h>

static const char *expected_name;
static int check_name;

static void report(const char *phase) {
    unsigned long code;
    printf("ERROR %s", phase);
    while ((code = ERR_get_error()) != 0) {
        char text[256];
        ERR_error_string_n(code, text, sizeof text);
        printf(" %s", text);
    }
    printf("\n");
    fflush(stdout);
}

static void limit(int fd, int seconds) {
    struct timeval timeout = {seconds, 0};
    setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO, &timeout, sizeof timeout);
    setsockopt(fd, SOL_SOCKET, SO_SNDTIMEO, &timeout, sizeof timeout);
}

static int alpn(SSL *ssl, const unsigned char **out, unsigned char *length, const unsigned char *in, unsigned int size, void *argument) {
    const char *wanted = argument;
    unsigned int offset = 0;
    (void)ssl;
    while (offset < size) {
        unsigned int item = in[offset];
        if (offset + 1 + item > size) break;
        if (item == strlen(wanted) && memcmp(in + offset + 1, wanted, item) == 0) {
            *out = in + offset + 1;
            *length = (unsigned char)item;
            return SSL_TLSEXT_ERR_OK;
        }
        offset += 1 + item;
    }
    return SSL_TLSEXT_ERR_NOACK;
}

static int servername(SSL *ssl, int *alert, void *argument) {
    const char *name = SSL_get_servername(ssl, TLSEXT_NAMETYPE_host_name);
    (void)argument;
    printf("SNI %s\n", name ? name : "-");
    fflush(stdout);
    if (!check_name) return SSL_TLSEXT_ERR_OK;
    if ((name == NULL) != (expected_name[0] == '\0') || (name && strcmp(name, expected_name) != 0)) {
        *alert = SSL_AD_UNRECOGNIZED_NAME;
        return SSL_TLSEXT_ERR_ALERT_FATAL;
    }
    return SSL_TLSEXT_ERR_OK;
}

static unsigned char *protocols(const char *name, unsigned int *size) {
    size_t length = strlen(name);
    unsigned char *wire = malloc(length + 1);
    if (!wire) exit(2);
    wire[0] = (unsigned char)length;
    memcpy(wire + 1, name, length);
    *size = (unsigned int)length + 1;
    return wire;
}

static int serve(int argc, char **argv) {
    if (argc != 8) return 2;
    const char *chain = argv[2], *key = argv[3], *protocol = argv[4], *roots = argv[5], *name = argv[6], *body_path = argv[7];
    FILE *file = fopen(body_path, "rb");
    if (!file) return 2;
    static char body[1 << 20];
    size_t body_length = fread(body, 1, sizeof body, file);
    fclose(file);
    SSL_CTX *context = SSL_CTX_new(TLS_server_method());
    SSL_CTX_set_min_proto_version(context, TLS1_3_VERSION);
    SSL_CTX_set_max_proto_version(context, TLS1_3_VERSION);
    SSL_CTX_set_alpn_select_cb(context, alpn, (void *)protocol);
    if (strcmp(name, "*") != 0) {
        check_name = 1;
        expected_name = strcmp(name, "-") == 0 ? "" : name;
        SSL_CTX_set_tlsext_servername_callback(context, servername);
    }
    if (SSL_CTX_use_certificate_chain_file(context, chain) != 1 || SSL_CTX_use_PrivateKey_file(context, key, SSL_FILETYPE_PEM) != 1) {
        report("credentials");
        return 2;
    }
    if (strcmp(roots, "-") != 0) {
        if (SSL_CTX_load_verify_locations(context, roots, NULL) != 1) { report("roots"); return 2; }
        SSL_CTX_set_verify(context, SSL_VERIFY_PEER | SSL_VERIFY_FAIL_IF_NO_PEER_CERT, NULL);
    }
    int listener = socket(AF_INET, SOCK_STREAM, 0);
    struct sockaddr_in address;
    memset(&address, 0, sizeof address);
    address.sin_family = AF_INET;
    address.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
    socklen_t length = sizeof address;
    if (listener < 0 || bind(listener, (struct sockaddr *)&address, sizeof address) != 0 || listen(listener, 1) != 0 ||
        getsockname(listener, (struct sockaddr *)&address, &length) != 0) return 2;
    printf("READY %d\n", ntohs(address.sin_port));
    fflush(stdout);
    limit(listener, 10);
    int connection = accept(listener, NULL, NULL);
    close(listener);
    if (connection < 0) { printf("ERROR accept\n"); return 0; }
    limit(connection, 10);
    SSL *ssl = SSL_new(context);
    SSL_set_fd(ssl, connection);
    if (SSL_accept(ssl) != 1) {
        report("handshake");
        close(connection);
        return 0;
    }
    X509 *peer = SSL_get1_peer_certificate(ssl);
    printf("PEER %s\n", peer ? "present" : "absent");
    fflush(stdout);
    X509_free(peer);
    char request[65536];
    size_t received = 0;
    while (received < sizeof request - 1) {
        int count = SSL_read(ssl, request + received, (int)(sizeof request - 1 - received));
        if (count <= 0) { report("request"); close(connection); return 0; }
        received += (size_t)count;
        request[received] = 0;
        if (strstr(request, "\r\n\r\n")) break;
    }
    char head[128];
    int head_length = snprintf(head, sizeof head, "HTTP/1.1 200 OK\r\nConnection: close\r\nContent-Length: %zu\r\n\r\n", body_length);
    if (SSL_write(ssl, head, head_length) != head_length || (body_length && SSL_write(ssl, body, (int)body_length) != (int)body_length)) report("response");
    SSL_shutdown(ssl);
    SSL_free(ssl);
    close(connection);
    SSL_CTX_free(context);
    printf("DONE\n");
    return 0;
}

static int client(int argc, char **argv) {
    if (argc != 10) return 2;
    int port = atoi(argv[2]);
    const char *roots = argv[3], *host = argv[4], *protocol = argv[5], *groups = argv[6], *certificate = argv[7], *key = argv[8], *data = argv[9];
    SSL_CTX *context = SSL_CTX_new(TLS_client_method());
    SSL_CTX_set_min_proto_version(context, TLS1_3_VERSION);
    SSL_CTX_set_max_proto_version(context, TLS1_3_VERSION);
    unsigned int wire_length;
    unsigned char *wire = protocols(protocol, &wire_length);
    SSL_CTX_set_alpn_protos(context, wire, wire_length);
    if (strcmp(groups, "-") != 0 && SSL_CTX_set1_groups_list(context, groups) != 1) { report("groups"); return 2; }
    if (SSL_CTX_load_verify_locations(context, roots, NULL) != 1) { report("roots"); return 2; }
    SSL_CTX_set_verify(context, SSL_VERIFY_PEER, NULL);
    if (strcmp(certificate, "-") != 0 &&
        (SSL_CTX_use_certificate_chain_file(context, certificate) != 1 || SSL_CTX_use_PrivateKey_file(context, key, SSL_FILETYPE_PEM) != 1)) {
        report("identity");
        return 2;
    }
    int fd = socket(AF_INET, SOCK_STREAM, 0);
    struct sockaddr_in address;
    memset(&address, 0, sizeof address);
    address.sin_family = AF_INET;
    address.sin_port = htons((unsigned short)port);
    address.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
    limit(fd, 5);
    if (fd < 0 || connect(fd, (struct sockaddr *)&address, sizeof address) != 0) { fprintf(stderr, "connect failed\n"); return 1; }
    SSL *ssl = SSL_new(context);
    SSL_set_fd(ssl, fd);
    SSL_set_tlsext_host_name(ssl, host);
    SSL_set1_host(ssl, host);
    if (SSL_connect(ssl) != 1) { report("handshake"); return 1; }
    if (data[0] && SSL_write(ssl, data, (int)strlen(data)) != (int)strlen(data)) { report("write"); return 1; }
    char buffer[1024];
    int count = SSL_read(ssl, buffer, sizeof buffer);
    if (count <= 0) { report("read"); return 1; }
    fwrite(buffer, 1, (size_t)count, stdout);
    SSL_free(ssl);
    close(fd);
    SSL_CTX_free(context);
    free(wire);
    return 0;
}

int main(int argc, char **argv) {
    if (argc > 1 && strcmp(argv[1], "server") == 0) return serve(argc, argv);
    if (argc > 1 && strcmp(argv[1], "client") == 0) return client(argc, argv);
    fprintf(stderr, "usage: server CHAIN KEY ALPN ROOTS|- SNI|*|- BODY | client PORT ROOTS HOST ALPN GROUPS|- CERT|- KEY|- DATA\n");
    return 2;
}
