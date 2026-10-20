/* TEST ONLY: call the actual static runtime decoder with fixed numeric oracles.
 * No encoder or decoder is reimplemented here. See the preparation report for
 * the legacy structural encoding and independent boundary arithmetic. */
#ifdef NDEBUG
#undef NDEBUG
#endif
#include "minyar_runtime.c"
#include <assert.h>

int main(void) {
#ifdef _WIN32
    assert(_setmode(_fileno(stdout), _O_BINARY) != -1);
#endif
    /* All five escape tags, both sides of the skipped bucket, maximum indexes. */
    assert(map_record_enum_value(-513LL) == 1000000000LL);
    assert(map_record_enum_value(-514LL) == 1000000001LL);
    assert(map_record_enum_value(-515LL) == 1000000002LL);
    assert(map_record_enum_value(-516LL) == 1000000003LL);
    assert(map_record_enum_value(-519LL) == 1000000004LL);
    assert(map_record_enum_value(-15998415991LL) == 1000087999LL);
    assert(map_record_enum_value(-16001600513LL) == 1000088000LL);
    assert(map_record_enum_value(-16001600514LL) == 1000088001LL);
    assert(map_record_enum_value(-3240000015991LL) == 1000098999LL);

    /* Reserved primitive children 19..31; columns are key tags 1, 2, 3, 4, 7. */
    static const long long reserved_scalars[][5] = {
        {-305LL, -306LL, -307LL, -308LL, -311LL}, /* child 19 */
        {-321LL, -322LL, -323LL, -324LL, -327LL}, /* child 20 */
        {-337LL, -338LL, -339LL, -340LL, -343LL}, /* child 21 */
        {-353LL, -354LL, -355LL, -356LL, -359LL}, /* child 22 */
        {-369LL, -370LL, -371LL, -372LL, -375LL}, /* child 23 */
        {-385LL, -386LL, -387LL, -388LL, -391LL}, /* child 24 */
        {-401LL, -402LL, -403LL, -404LL, -407LL}, /* child 25 */
        {-417LL, -418LL, -419LL, -420LL, -423LL}, /* child 26 */
        {-433LL, -434LL, -435LL, -436LL, -439LL}, /* child 27 */
        {-449LL, -450LL, -451LL, -452LL, -455LL}, /* child 28 */
        {-465LL, -466LL, -467LL, -468LL, -471LL}, /* child 29 */
        {-481LL, -482LL, -483LL, -484LL, -487LL}, /* child 30 */
        {-497LL, -498LL, -499LL, -500LL, -503LL}, /* child 31 */
    };
    for (size_t row = 0; row < sizeof(reserved_scalars) / sizeof(reserved_scalars[0]); ++row)
        for (size_t column = 0; column < 5; ++column)
            assert(map_record_enum_value(reserved_scalars[row][column]) == 0);

    /* One ordinary positive List layer of each reserved child; columns are key tags 1, 2, 3, 4, 7. */
    static const long long address_lists[][5] = {
        {-1600305LL, -1600306LL, -1600307LL, -1600308LL, -1600311LL}, /* child 100019 */
        {-1600321LL, -1600322LL, -1600323LL, -1600324LL, -1600327LL}, /* child 100020 */
        {-1600337LL, -1600338LL, -1600339LL, -1600340LL, -1600343LL}, /* child 100021 */
        {-1600353LL, -1600354LL, -1600355LL, -1600356LL, -1600359LL}, /* child 100022 */
        {-1600369LL, -1600370LL, -1600371LL, -1600372LL, -1600375LL}, /* child 100023 */
        {-1600385LL, -1600386LL, -1600387LL, -1600388LL, -1600391LL}, /* child 100024 */
        {-1600401LL, -1600402LL, -1600403LL, -1600404LL, -1600407LL}, /* child 100025 */
        {-1600417LL, -1600418LL, -1600419LL, -1600420LL, -1600423LL}, /* child 100026 */
        {-1600433LL, -1600434LL, -1600435LL, -1600436LL, -1600439LL}, /* child 100027 */
        {-1600449LL, -1600450LL, -1600451LL, -1600452LL, -1600455LL}, /* child 100028 */
        {-1600465LL, -1600466LL, -1600467LL, -1600468LL, -1600471LL}, /* child 100029 */
        {-1600481LL, -1600482LL, -1600483LL, -1600484LL, -1600487LL}, /* child 100030 */
        {-1600497LL, -1600498LL, -1600499LL, -1600500LL, -1600503LL}, /* child 100031 */
    };
    for (size_t row = 0; row < sizeof(address_lists) / sizeof(address_lists[0]); ++row)
        for (size_t column = 0; column < 5; ++column)
            assert(map_record_enum_value(address_lists[row][column]) == 0);

    /* 64 ordinary positive List layers of each reserved child; columns are key tags 1, 2, 3, 4, 7. */
    static const long long deep_address_lists[][5] = {
        {-102400305LL, -102400306LL, -102400307LL, -102400308LL, -102400311LL}, /* child 6400019 */
        {-102400321LL, -102400322LL, -102400323LL, -102400324LL, -102400327LL}, /* child 6400020 */
        {-102400337LL, -102400338LL, -102400339LL, -102400340LL, -102400343LL}, /* child 6400021 */
        {-102400353LL, -102400354LL, -102400355LL, -102400356LL, -102400359LL}, /* child 6400022 */
        {-102400369LL, -102400370LL, -102400371LL, -102400372LL, -102400375LL}, /* child 6400023 */
        {-102400385LL, -102400386LL, -102400387LL, -102400388LL, -102400391LL}, /* child 6400024 */
        {-102400401LL, -102400402LL, -102400403LL, -102400404LL, -102400407LL}, /* child 6400025 */
        {-102400417LL, -102400418LL, -102400419LL, -102400420LL, -102400423LL}, /* child 6400026 */
        {-102400433LL, -102400434LL, -102400435LL, -102400436LL, -102400439LL}, /* child 6400027 */
        {-102400449LL, -102400450LL, -102400451LL, -102400452LL, -102400455LL}, /* child 6400028 */
        {-102400465LL, -102400466LL, -102400467LL, -102400468LL, -102400471LL}, /* child 6400029 */
        {-102400481LL, -102400482LL, -102400483LL, -102400484LL, -102400487LL}, /* child 6400030 */
        {-102400497LL, -102400498LL, -102400499LL, -102400500LL, -102400503LL}, /* child 6400031 */
    };
    for (size_t row = 0; row < sizeof(deep_address_lists) / sizeof(deep_address_lists[0]); ++row)
        for (size_t column = 0; column < 5; ++column)
            assert(map_record_enum_value(deep_address_lists[row][column]) == 0);

    static const long long other_non_escapes[] = {
        /* Non-escape tags 0, 5 and 6 at the first hole child 32. */
        -512LL, -517LL, -518LL,
        /* Ordinary record-key Map<Integer value> and Set<Integer>. */
        -1608005LL, -22LL,
        /* Negative child -32 (List<Text>) under every builtin key tag. */
        -505LL, -506LL, -507LL, -508LL, -511LL,
        /* First skipped enum child 1000000032 under every builtin key tag. */
        -16000000513LL, -16000000514LL, -16000000515LL, -16000000516LL, -16000000519LL,
        /* Last skipped hole child 1000000999 under every builtin key tag. */
        -16000015985LL, -16000015986LL, -16000015987LL, -16000015988LL, -16000015991LL,
        /* Ordinary positive record child 1000, outside the hole interval. */
        -16001LL, -16002LL, -16003LL, -16004LL, -16007LL,
        /* First out-of-domain rank: pair 9801000000, child 202500100032. */
        -3240001600513LL, -3240001600514LL, -3240001600515LL, -3240001600516LL, -3240001600519LL,
    };
    for (size_t index = 0; index < sizeof(other_non_escapes) / sizeof(other_non_escapes[0]); ++index)
        assert(map_record_enum_value(other_non_escapes[index]) == 0);
    puts("Choice runtime codec: literal nominal IDs and rejection boundaries passed");
    return 0;
}
