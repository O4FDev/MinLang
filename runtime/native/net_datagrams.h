/* Included by net.c. Batch wire formats are internal native ABI, not network
 * protocols. Linux mmsg and portable non-blocking fallbacks preserve packets. */
enum { NET_BATCH_LIMIT = 64, NET_DATAGRAM_LIMIT = 65507 };
static uint32_t batch_u32(const unsigned char *p) {
    return (uint32_t)p[0] | (uint32_t)p[1] << 8 | (uint32_t)p[2] << 16 | (uint32_t)p[3] << 24;
}
static MinyarBytes *batch_send_result(unsigned status, int code, unsigned count) {
    MinyarBytes *b = minyar_bytes_new(16);
    result_status(b, status, code);
    put32((unsigned char *)b->bytes + 8, count);
    return b;
}
/* Peer addresses come from receiveBatchResult. AI_NUMERICHOST guarantees this
 * packet path cannot initiate DNS; a server's socket stays unconnected. */
MinyarBytes *minyar_net_sendToResult(long long connection, const MinyarText *host, long long port,
                                     const MinyarBytes *data) {
    if (!valid_socket(connection) || port < 1 || port > 65535 || host->byte_length < 1 ||
        host->byte_length > 255 || data->byte_length < 0 || data->byte_length > NET_DATAGRAM_LIMIT)
        return batch_send_result(NET_FAILURE, BAD_ARGUMENT, 0);
    for (long long i = 0; i < host->byte_length; i++)
        if (host->bytes[i] < 33 || host->bytes[i] > 126)
            return batch_send_result(NET_FAILURE, BAD_ARGUMENT, 0);
    int type = 0;
    socklen_t type_length = sizeof(type);
    if (getsockopt((socket_t)connection, SOL_SOCKET, SO_TYPE, (char *)&type, &type_length))
        return batch_send_result(NET_FAILURE, socket_error(), 0);
    if (type != SOCK_DGRAM)
        return batch_send_result(NET_FAILURE, BAD_ARGUMENT, 0);
    char name[256], service[6];
    memcpy(name, host->bytes, (size_t)host->byte_length);
    name[host->byte_length] = 0;
    snprintf(service, sizeof(service), "%lld", port);
    struct addrinfo hints = {0}, *found = NULL;
    hints.ai_family = AF_UNSPEC;
    hints.ai_socktype = SOCK_DGRAM;
    hints.ai_flags = AI_NUMERICHOST | AI_NUMERICSERV;
    if (getaddrinfo(name, service, &hints, &found))
        return batch_send_result(NET_FAILURE, BAD_ARGUMENT, 0);
    long long sent = -1;
    int code = BAD_ARGUMENT;
#ifdef _WIN32
    if (!minyar_net_nonBlocking(connection, true)) {
        code = socket_error();
        freeaddrinfo(found);
        return batch_send_result(NET_FAILURE, code, 0);
    }
#endif
    for (struct addrinfo *peer = found; peer; peer = peer->ai_next) {
        do {
            int flags = 0;
#ifndef _WIN32
            flags = MSG_DONTWAIT;
#ifdef MSG_NOSIGNAL
            flags |= MSG_NOSIGNAL;
#endif
#endif
            sent = sendto((socket_t)connection, (const char *)data->bytes, (int)data->byte_length,
                          flags, peer->ai_addr, (socklen_t)peer->ai_addrlen);
            code = sent < 0 ? socket_error() : 0;
        } while (sent < 0 && interrupted(code));
        if (sent >= 0 || would_block(code))
            break;
    }
    freeaddrinfo(found);
    return batch_send_result(sent < 0 ? (would_block(code) ? NET_WOULD_BLOCK : NET_FAILURE)
                                      : NET_OK,
                             code, sent < 0 ? 0 : (unsigned)sent);
}
MinyarBytes *minyar_net_sendBatchResult(long long connection, const MinyarBytes *packets) {
    if (!valid_socket(connection) || packets->byte_length < 4)
        return batch_send_result(NET_FAILURE, BAD_ARGUMENT, 0);
    unsigned count = batch_u32(packets->bytes);
    if (count > NET_BATCH_LIMIT)
        return batch_send_result(NET_FAILURE, BAD_ARGUMENT, 0);
    const unsigned char *payload[NET_BATCH_LIMIT];
    unsigned sizes[NET_BATCH_LIMIT];
    size_t at = 4, length = (size_t)packets->byte_length;
    for (unsigned i = 0; i < count; i++) {
        if (length - at < 4)
            return batch_send_result(NET_FAILURE, BAD_ARGUMENT, 0);
        sizes[i] = batch_u32(packets->bytes + at);
        at += 4;
        if (sizes[i] > NET_DATAGRAM_LIMIT || sizes[i] > length - at)
            return batch_send_result(NET_FAILURE, BAD_ARGUMENT, 0);
        payload[i] = packets->bytes + at;
        at += sizes[i];
    }
    if (at != length)
        return batch_send_result(NET_FAILURE, BAD_ARGUMENT, 0);
    if (!count)
        return batch_send_result(NET_OK, 0, 0);
    int code = 0, sent = 0;
#ifdef __linux__
    struct mmsghdr messages[NET_BATCH_LIMIT] = {0};
    struct iovec segments[NET_BATCH_LIMIT];
    for (unsigned i = 0; i < count; i++) {
        segments[i] = (struct iovec){(void *)payload[i], sizes[i]};
        messages[i].msg_hdr.msg_iov = &segments[i];
        messages[i].msg_hdr.msg_iovlen = 1;
    }
    do {
        sent = sendmmsg((socket_t)connection, messages, count, MSG_DONTWAIT | MSG_NOSIGNAL);
        code = sent < 0 ? socket_error() : 0;
    } while (sent < 0 && interrupted(code));
#else
#ifdef _WIN32
    if (!minyar_net_nonBlocking(connection, true))
        return batch_send_result(NET_FAILURE, socket_error(), 0);
#endif
    for (unsigned i = 0; i < count; i++) {
        long long wrote;
        do {
#ifdef _WIN32
            wrote = send((socket_t)connection, (const char *)payload[i], (int)sizes[i], 0);
#else
            wrote = send((socket_t)connection, payload[i], sizes[i], MSG_DONTWAIT);
#endif
            code = wrote < 0 ? socket_error() : 0;
        } while (wrote < 0 && interrupted(code));
        if (wrote < 0) {
            if (!sent)
                sent = -1;
            break;
        }
        sent++;
    }
#endif
    if (sent < 0)
        return batch_send_result(would_block(code) ? NET_WOULD_BLOCK : NET_FAILURE, code, 0);
    return batch_send_result(NET_OK, 0, (unsigned)sent);
}
static void append_datagram(MinyarBytes *result, const unsigned char *payload, unsigned length,
                            const struct sockaddr_storage *source, socklen_t source_length,
                            bool truncated) {
    char name[128] = "", service[16] = "";
    int error = getnameinfo((const struct sockaddr *)source, source_length, name, sizeof(name),
                            service, sizeof(service), NI_NUMERICHOST | NI_NUMERICSERV);
    if (error)
        minyar_native_stop("a UDP socket returned an invalid source address.");
    size_t name_length = strlen(name);
    unsigned char *p = minyar_bytes_extend(result, 16 + (long long)name_length + length);
    put32(p, length);
    put32(p + 4, truncated ? NET_TRUNCATED : NET_OK);
    put32(p + 8, (uint32_t)strtoul(service, NULL, 10));
    put32(p + 12, (uint32_t)name_length);
    memcpy(p + 16, name, name_length);
    memcpy(p + 16 + name_length, payload, length);
}
MinyarBytes *minyar_net_receiveBatchResult(long long connection, long long maximum,
                                           long long limit) {
    MinyarBytes *result = minyar_bytes_new(12);
    if (!valid_socket(connection) || maximum <= 0 || maximum > NET_BATCH_LIMIT || limit <= 0 ||
        limit > 65535) {
        result_status(result, NET_FAILURE, BAD_ARGUMENT);
        return result;
    }
    unsigned char *storage = malloc((size_t)maximum * (size_t)limit);
    if (!storage)
        minyar_native_stop("the computer ran out of memory.");
    int code = 0, received = 0;
#ifdef __linux__
    struct mmsghdr messages[NET_BATCH_LIMIT] = {0};
    struct iovec segments[NET_BATCH_LIMIT];
    struct sockaddr_storage addresses[NET_BATCH_LIMIT];
    for (long long i = 0; i < maximum; i++) {
        segments[i] = (struct iovec){storage + (size_t)i * (size_t)limit, (size_t)limit};
        messages[i].msg_hdr.msg_iov = &segments[i];
        messages[i].msg_hdr.msg_iovlen = 1;
        messages[i].msg_hdr.msg_name = &addresses[i];
        messages[i].msg_hdr.msg_namelen = sizeof(addresses[i]);
    }
    do {
        received = recvmmsg((socket_t)connection, messages, (unsigned)maximum, MSG_DONTWAIT, NULL);
        code = received < 0 ? socket_error() : 0;
    } while (received < 0 && interrupted(code));
    for (int i = 0; i < received; i++)
        append_datagram(result, segments[i].iov_base, messages[i].msg_len, &addresses[i],
                        messages[i].msg_hdr.msg_namelen,
                        (messages[i].msg_hdr.msg_flags & MSG_TRUNC) != 0);
#else
#ifdef _WIN32
    if (!minyar_net_nonBlocking(connection, true)) {
        free(storage);
        result_status(result, NET_FAILURE, socket_error());
        return result;
    }
#endif
    while (received < maximum) {
        struct sockaddr_storage source;
        socklen_t size = sizeof(source);
        long long count;
        bool truncated = false;
        do {
#ifdef _WIN32
            count = recvfrom((socket_t)connection, (char *)storage, (int)limit, 0,
                             (struct sockaddr *)&source, &size);
            code = count < 0 ? socket_error() : 0;
            if (code == WSAEMSGSIZE) {
                count = limit;
                truncated = true;
                code = 0;
            }
#else
            struct iovec segment = {storage, (size_t)limit};
            struct msghdr message = {0};
            message.msg_iov = &segment;
            message.msg_iovlen = 1;
            message.msg_name = &source;
            message.msg_namelen = size;
            count = recvmsg((socket_t)connection, &message, MSG_DONTWAIT);
            code = count < 0 ? socket_error() : 0;
            size = message.msg_namelen;
            truncated = (message.msg_flags & MSG_TRUNC) != 0;
#endif
        } while (count < 0 && interrupted(code));
        if (count < 0) {
            if (!received)
                received = -1;
            break;
        }
        append_datagram(result, storage, (unsigned)count, &source, size, truncated);
        received++;
    }
#endif
    free(storage);
    if (received < 0)
        result_status(result, would_block(code) ? NET_WOULD_BLOCK : NET_FAILURE, code);
    else {
        result_status(result, NET_OK, 0);
        put32((unsigned char *)result->bytes + 8, (unsigned)received);
    }
    return result;
}
