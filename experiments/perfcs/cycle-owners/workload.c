/* Public-API native workload: this object is shared by every runtime link.
 * Runtime layout and accounting globals are deliberately absent here. */
#include <errno.h>
#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef struct MinyarRecord MinyarRecord;
extern MinyarRecord *minyar_record_new_scalar(long long fields);
extern void minyar_record_set_scalar(MinyarRecord *, long long, long long);
extern long long minyar_record_get(const MinyarRecord *, long long);
extern void minyar_rc_enter(long long locals);
extern void minyar_rc_local(long long index, void *value);
extern void minyar_rc_release(void *value);
extern void minyar_rc_keep(void *value);
extern void minyar_rc_leave(void);
extern void perfcs_owner_prepare(int active);
extern void perfcs_owner_finish(int active);

int main(int argc, char **argv) {
    if (argc != 4 || (strcmp(argv[1], "active") && strcmp(argv[1], "inactive")) ||
        (strcmp(argv[2], "frame") && strcmp(argv[2], "chunk"))) {
        fprintf(stderr, "usage: workload active|inactive frame|chunk iterations\n");
        return 2;
    }
    char *end;
    errno = 0;
    unsigned long long iterations = strtoull(argv[3], &end, 10);
    if (errno || *end || argv[3][0] < '0' || argv[3][0] > '9' ||
        !iterations || iterations > 10000000ULL) {
        fprintf(stderr, "iterations must be in 1..10000000\n");
        return 2;
    }
    int active = !strcmp(argv[1], "active");
    int frame = !strcmp(argv[2], "frame");
    uint64_t sum = 0, serial = 0;
    perfcs_owner_prepare(active);
    for (unsigned long long iteration = 0; iteration < iterations; ++iteration) {
        minyar_rc_enter(frame ? 8 : 0);
        for (long long slot = 0; slot < 8; ++slot) {
            MinyarRecord *value = minyar_record_new_scalar(1);
            minyar_record_set_scalar(value, 0, (long long)serial++);
            sum += (uint64_t)minyar_record_get(value, 0);
            if (frame) {
                minyar_rc_local(slot, value);
                minyar_rc_release(value);
            } else {
                minyar_rc_keep(value);
            }
        }
        minyar_rc_leave();
    }
    perfcs_owner_finish(active);
    uint64_t count = UINT64_C(8) * iterations;
    if (serial != count || sum != count * (count - 1) / 2) {
        fprintf(stderr, "independent scalar sum failed\n");
        return 1;
    }
    printf("%" PRIu64 "\n", sum);
    return 0;
}
