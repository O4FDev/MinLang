/* The same pinned primitives and provider ABI as hosted builds. No sockets,
 * certificate trust, clock, asymmetric certificate signer or AES are added. */
#ifndef MINYAR_FREESTANDING_PROVIDERS_H
#define MINYAR_FREESTANDING_PROVIDERS_H
#include "minyar_native.h"
#include "minyar_ip_literal.h"
#include "../vendor/monocypher/monocypher.c"
#include "native/securecrypto.c"

long long minyar_net_ipVersion(const MinyarText *address) {
    return minyar_ip_literal_version(address->bytes, address->byte_length);
}
#endif
