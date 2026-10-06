/* Included after the frozen round2 fixture, with its original main disabled. */
static void round3_stats(void) {
    struct rusage usage;
    assert(getrusage(RUSAGE_SELF, &usage) == 0);
    long long rss = (long long)usage.ru_maxrss;
#ifndef __APPLE__
    rss *= 1024;
#endif
    printf("{\"malloc_calls\":%zu,\"sizes\":[%zu,%zu,%zu],\"read_calls\":%zu,"
           "\"open_calls\":%zu,\"write_calls\":%zu,\"close_calls\":%zu,"
           "\"pending\":%d,\"peak_rss_bytes\":%lld}\n",
           malloc_calls, round3_sizes[0], round3_sizes[1], round3_sizes[2], read_calls,
           open_calls, write_calls, close_calls, screenshot_path[0] != 0, rss);
}

int main(int argc, char **argv) {
    _Static_assert(sizeof(size_t) == 8 && sizeof(int) == 4, "Supported native ABI");
    assert(atexit(round3_stats) == 0);
    if (argc == 3 && !strcmp(argv[1], "tiny")) {
        unsigned char reference[120];
        FILE *input = fopen(argv[2], "rb");
        assert(input && fread(reference, 1, sizeof(reference), input) == sizeof(reference));
        assert(fgetc(input) == EOF && fclose(input) == 0);
        MinyarBytes vertices = {.bytes = reference, .byte_length = sizeof(reference)};
        window = (GLFWwindow *)(uintptr_t)1;
        assert(minyar_graphics_createMesh() == 1);
        /* Constants selected by the seam recipe, never inferred from renderer fields. */
        assert(generated_array == 1 && generated_buffer == ROUND3_BUFFER_START);
        assert(arrays[1] && buffers[ROUND3_BUFFER_START].used);
        assert(array_buffer[1] == ROUND3_BUFFER_START);
        minyar_graphics_updateMesh(1, &vertices);
        assert(bound_buffer == ROUND3_BUFFER_START && uploads == 1);
        assert(buffers[ROUND3_BUFFER_START].length == sizeof(reference));
        assert(!memcmp(round3_uploaded, reference, sizeof(reference)));
        minyar_graphics_drawMesh(1);
        assert(draws == 1 && last_draw_array == 1 && last_draw_count == 3);
        assert(array_buffer[last_draw_array] == ROUND3_BUFFER_START);
        assert(!memcmp(round3_uploaded, reference, sizeof(reference)));
        minyar_graphics_deleteMesh(1);
        assert(!array_live && !buffer_live && !arrays[1] && !buffers[ROUND3_BUFFER_START].used);
        free(meshes);
        puts("{\"tiny\":true,\"array\":1,\"buffer\":" ROUND3_BUFFER_TEXT
             ",\"bytes\":120,\"vertices\":3,\"uploads\":1,\"draws\":1,\"deleted\":true}");
        return 0;
    }
    if (argc == 4 && !strcmp(argv[1], "dimensions")) {
        round3_size_probe = 1;
        framebuffer_width = (int)strtol(argv[2], NULL, 0);
        framebuffer_height = (int)strtol(argv[3], NULL, 0);
        strcpy(screenshot_path, "round3-never-created.png");
        write_screenshot();
        /* Nonpositive dimensions defer; positive dimensions must stop at injected OOM. */
        assert(framebuffer_width < 1 || framebuffer_height < 1);
        assert(!malloc_calls && !read_calls && !open_calls && !write_calls && screenshot_path[0]);
        return 0;
    }
    if (argc == 3 && !strcmp(argv[1], "chunk-header")) {
        size_t length = (size_t)strtoull(argv[2], NULL, 0);
        round3_header_probe = 1;
        /* Escape on the first actual header write, before any payload access/CRC. */
        if (!setjmp(round3_header_jump))
            png_chunk(NULL, "IDAT", NULL, length);
        printf("{\"header\":\"%02x%02x%02x%02x49444154\",\"length\":%zu}\n",
               round3_header[0], round3_header[1], round3_header[2], round3_header[3], length);
        return length > UINT32_C(0x7fffffff) ? 2 : 0;
    }
    if (argc == 5 && !strcmp(argv[1], "small-png")) {
        framebuffer_width = (int)strtol(argv[2], NULL, 0);
        framebuffer_height = (int)strtol(argv[3], NULL, 0);
        assert(framebuffer_width > 0 && framebuffer_width <= 16384);
        assert(framebuffer_height > 0 && framebuffer_height <= 64);
        assert(strlen(argv[4]) < sizeof(screenshot_path));
        strcpy(screenshot_path, argv[4]);
        write_screenshot();
        assert(!screenshot_path[0] && !live_bytes);
        return 0;
    }
    assert(!"unknown round3 mode");
}
