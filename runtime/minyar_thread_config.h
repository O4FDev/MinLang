/* The ordinary runtime keeps its existing storage and ownership ABI. */
#ifndef MINYAR_THREAD_CONFIG_H
#define MINYAR_THREAD_CONFIG_H

/* Numeric contract: absent/0 is ordinary storage; 1 enables thread domains. */
#ifndef MINYAR_THREADED
#define MINYAR_THREADED 0
#endif
#if MINYAR_THREADED != 0 && MINYAR_THREADED != 1
#error MINYAR_THREADED must be 0 or 1.
#endif
_Static_assert(MINYAR_THREADED == 0 || MINYAR_THREADED == 1,
               "MINYAR_THREADED must be 0 or 1");

#if MINYAR_THREADED
#if defined(MINYAR_COMPILER_ARENA)
#error The compiler arena cannot be used by managed threads.
#endif
#if defined(MINYAR_BOUNDED_HEAP) || defined(MINYAR_LAZY_HEAP)
#error Managed threads require the system or eager heap.
#endif
#if defined(MINYAR_BOUNDED_RC) && !defined(MINYAR_SYSTEM_HEAP)
#error Managed threads with bounded RC require the system heap.
#endif
#define MINYAR_THREAD_LOCAL _Thread_local
#else
#define MINYAR_THREAD_LOCAL
#endif

#endif
