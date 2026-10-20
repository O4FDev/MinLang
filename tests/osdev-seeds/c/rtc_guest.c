/* External hardware control. Compile with -include ACTUAL_IMMUTABLE_COMPARATOR.
 * No decoder, stable-read algorithm or port adapter is copied into this file.
 * Runs on the boot CPU through the actual Minyar OS x86 loader/entry/runtime.
 */
#include <stdio.h>

#ifdef RTC_COMPARATOR_CLI
#error "The guest must include production comparator code without its host CLI."
#endif

int main(void) {
    puts("OSDEV RTC START");
    puts("C comparator: immutable rtc_read with rtc_cmos_read_port");
    struct RtcResult result = rtc_read(rtc_cmos_read_port, NULL, 128);
    if (result.error != RTC_OK) {
        fprintf(stderr, "C comparator RTC error %d\n", (int)result.error);
        return 1;
    }
    struct Calendar value = result.calendar;
    printf("OSDEV RTC %d %d %d %d %d %d\n", value.year, value.month,
           value.day, value.hour, value.minute, value.second);
    puts("OSDEV RTC PASS");
    return 0;
}
