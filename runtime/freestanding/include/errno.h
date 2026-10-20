/* The freestanding file stubs do not set errno; callers use EIO when it is 0. */
#ifndef MINYAR_FREESTANDING_ERRNO_H
#define MINYAR_FREESTANDING_ERRNO_H

#define EIO 5
#define EINVAL 22
#define EFBIG 27

extern int errno;

#endif
