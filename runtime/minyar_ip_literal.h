/* Strict inet_pton-style classification without sockets or hosted C headers. */
#ifndef MINYAR_IP_LITERAL_H
#define MINYAR_IP_LITERAL_H
#include <stddef.h>

static int minyar_literal_ipv4(const unsigned char *text, size_t length) {
    size_t at = 0;
    for (int part = 0; part < 4; part++) {
        size_t start = at;
        unsigned value = 0;
        while (at < length && text[at] >= '0' && text[at] <= '9') {
            value = value * 10 + text[at++] - '0';
            if (at - start > 3 || value > 255) return 0;
        }
        if (at == start || (at - start > 1 && text[start] == '0')) return 0;
        if (part == 3) return at == length;
        if (at == length || text[at++] != '.') return 0;
    }
    return 0;
}

static int minyar_literal_ipv6(const unsigned char *text, size_t length) {
    size_t at = 0;
    unsigned groups = 0;
    int compressed = 0;
    if (text[0] == ':') {
        if (length < 2 || text[1] != ':') return 0;
        compressed = 1;
        at = 2;
        if (at == length) return 1;
    }
    while (at < length) {
        size_t start = at;
        int dotted = 0;
        while (at < length && text[at] != ':') {
            if (text[at] == '.') dotted = 1;
            at++;
        }
        if (dotted) {
            /* An embedded IPv4 address is the final two 16-bit groups. */
            if (at != length || !minyar_literal_ipv4(text + start, length - start)) return 0;
            groups += 2;
            break;
        }
        if (at == start || at - start > 4) return 0;
        for (size_t i = start; i < at; i++) {
            unsigned char c = text[i];
            if (!((c >= '0' && c <= '9') || (c >= 'a' && c <= 'f') ||
                  (c >= 'A' && c <= 'F'))) return 0;
        }
        if (++groups > 8) return 0;
        if (at == length) break;
        at++;
        if (at < length && text[at] == ':') {
            if (compressed) return 0;
            compressed = 1;
            at++;
        } else if (at == length) {
            return 0;
        }
    }
    return compressed ? groups < 8 : groups == 8;
}

static long long minyar_ip_literal_version(const unsigned char *text, long long length) {
    /* Match the hosted provider's length and embedded-NUL contract. */
    if (length <= 0 || length >= 256) return 0;
    for (size_t i = 0; i < (size_t)length; i++) {
        if (text[i] == 0) return 0;
    }
    if (minyar_literal_ipv4(text, (size_t)length)) return 4;
    return minyar_literal_ipv6(text, (size_t)length) ? 6 : 0;
}
#endif
