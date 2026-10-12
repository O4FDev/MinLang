#define __BITS_PER_LONG (__SIZEOF_LONG__ * 8)
#define _NSIG		64
#define _NSIG_BPW	__BITS_PER_LONG
#define _NSIG_WORDS	(_NSIG / _NSIG_BPW)
#define SA_RESTORER	0x04000000
#define __ARCH_HAS_SA_RESTORER
typedef void (*__sighandler_t)(int);
typedef void (*__sigrestore_t)(void);
typedef struct {
	unsigned long sig[_NSIG_WORDS];
} sigset_t;
struct sigaction {
#ifndef __ARCH_HAS_IRIX_SIGACTION
	__sighandler_t	sa_handler;
	unsigned long	sa_flags;
#else
	unsigned int	sa_flags;
	__sighandler_t	sa_handler;
#endif
#ifdef __ARCH_HAS_SA_RESTORER
	__sigrestore_t sa_restorer;
#endif
	sigset_t	sa_mask;	/* mask last for extensibility */
};
