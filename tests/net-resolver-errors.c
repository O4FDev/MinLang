/* Deterministic resolver failures must replace the numeric error from the
 * previous operation. The real socket provider and ownership runtime link. */
#ifndef _GNU_SOURCE
#define _GNU_SOURCE 1
#endif
#include <errno.h>
#include <assert.h>
#ifdef _WIN32
#include <winsock2.h>
#include <ws2tcpip.h>
#else
#include <netdb.h>
#endif

static int resolver_failure;
static int failed_lookup(const char *host, const char *service,
                         const struct addrinfo *hints, struct addrinfo **result) {
    (void)host; (void)service; (void)hints; (void)result;
    errno = EACCES;
    return resolver_failure;
}
#define getaddrinfo failed_lookup
#include "../runtime/native/net.c"
#undef getaddrinfo

int main(void) {
    MinyarText host = {(const unsigned char *)"fixture.invalid", 15, 0, NULL, NULL};
    resolver_failure = EAI_NONAME;
    assert(minyar_net_connect(&host, 80) == -1);
#ifdef _WIN32
    assert(minyar_net_lastErrorCode() == -(long long)EAI_NONAME);
#else
    assert(minyar_net_lastErrorCode() == -EINVAL);
    resolver_failure = EAI_SYSTEM;
    assert(minyar_net_connect(&host, 80) == -1);
    assert(minyar_net_lastErrorCode() == -EACCES);
#endif
    assert(minyar_net_listen(&host, 80, 0) == -1);
#ifdef _WIN32
    assert(minyar_net_lastErrorCode() == -WSAEINVAL);
#else
    assert(minyar_net_lastErrorCode() == -EINVAL);
#endif
    resolver_failure = EAI_NONAME;
    assert(minyar_net_connect(&host, 80) == -1);
    assert(minyar_net_lastErrorCode() != 0);
    puts("resolver numeric errors verified");
    return 0;
}
