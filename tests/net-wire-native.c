#include <arpa/inet.h>
#include <netinet/in.h>
#include <string.h>
#include <sys/socket.h>
#include <unistd.h>

long long minyar_netwire_connectBuffered(long long port, long long receiveBuffer) {
    int fd = socket(AF_INET, SOCK_STREAM, 0);
    if (fd < 0) return -1;
    int size = (int)receiveBuffer;
    if (receiveBuffer > 0 && setsockopt(fd, SOL_SOCKET, SO_RCVBUF, &size, sizeof size) != 0) { close(fd); return -1; }
    struct sockaddr_in address;
    memset(&address, 0, sizeof address);
    address.sin_family = AF_INET;
    address.sin_port = htons((unsigned short)port);
    address.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
    if (connect(fd, (struct sockaddr *)&address, sizeof address) != 0) { close(fd); return -1; }
    return fd;
}
long long minyar_netwire_receiveBufferNative(long long fd, long long bytes) {
    int size = (int)bytes;
    return setsockopt((int)fd, SOL_SOCKET, SO_RCVBUF, &size, sizeof size);
}
long long minyar_netwire_shutdownWriteNative(long long fd) {
    return shutdown((int)fd, SHUT_WR);
}
