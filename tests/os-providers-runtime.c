#include "../runtime/minyar_native.h"
#include <arpa/inet.h>

long long minyar_osproviderstest_version(const MinyarBytes *value) {
    char text[256];
    long long length = value->byte_length;
    if (length <= 0 || length >= 256) return 0;
    for (long long i = 0; i < length; i++) {
        if (value->bytes[i] == 0 || value->bytes[i] > 127) return 0;
        text[i] = (char)value->bytes[i];
    }
    text[length] = 0;
    unsigned char address[16];
    if (inet_pton(AF_INET, text, address) == 1) return 4;
    if (inet_pton(AF_INET6, text, address) == 1) return 6;
    return 0;
}

MinyarText *minyar_osproviderstest_text(const MinyarBytes *address) {
    char text[INET6_ADDRSTRLEN];
    int family = address->byte_length == 4 ? AF_INET : AF_INET6;
    if ((address->byte_length != 4 && address->byte_length != 16) || !inet_ntop(family, address->bytes, text, sizeof(text)))
        minyar_native_stop("invalid inet_ntop oracle address");
    return minyar_native_copy_text((const unsigned char *)text, (long long)strlen(text));
}
