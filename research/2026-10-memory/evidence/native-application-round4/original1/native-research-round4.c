/* Appended to the retained distinct-namespace fixture by the round4 wrapper. */
static void round4_stats(void) {
    (void)round3_stats;
    printf("{\"malloc_calls\":%zu,\"sizes\":[%zu,%zu,%zu],\"allocated_bytes\":%zu,"
           "\"live_bytes\":%zu,\"read_calls\":%zu,\"open_calls\":%zu,"
           "\"write_calls\":%zu,\"close_calls\":%zu,\"pending\":%d}\n",
           malloc_calls, round3_sizes[0], round3_sizes[1], round3_sizes[2], allocated_bytes,
           live_bytes, read_calls, open_calls, write_calls, close_calls, screenshot_path[0] != 0);
}

int main(int argc, char **argv) {
    if (argc >= 2 && (!strcmp(argv[1], "png-fault") || !strcmp(argv[1], "png-retry"))) {
        assert(argc == 5);
        assert(atexit(round4_stats) == 0);
        window = (GLFWwindow *)(uintptr_t)1;
        MinyarText path = {.bytes = (const unsigned char *)argv[4],
                           .byte_length = (long long)strlen(argv[4])};
        assert(path.byte_length < (long long)sizeof(screenshot_path));
        minyar_graphics_saveScreenshot(&path);
        if (!strcmp(argv[1], "png-fault")) {
            failed_call = (size_t)strtoul(argv[2], NULL, 0);
            round4_io_fault = (int)strtol(argv[3], NULL, 0);
        } else {
            framebuffer_width = (int)strtol(argv[2], NULL, 0);
            framebuffer_height = (int)strtol(argv[3], NULL, 0);
            assert(framebuffer_width == 0 || framebuffer_height == 0);
            write_screenshot();
            assert(!malloc_calls && !read_calls && !open_calls && !write_calls && !close_calls);
            assert(!strcmp(screenshot_path, argv[4]));
            FILE *absent = fopen(argv[4], "rb");
            assert(!absent);
        }
        framebuffer_width = framebuffer_height = 8;
        write_screenshot();
        assert(!strcmp(argv[1], "png-retry"));
        assert(!screenshot_path[0] && !live_bytes);
        assert(malloc_calls == 3 && read_calls == 1 && open_calls == 1);
        assert(write_calls == 9 && close_calls == 1);
        return 0;
    }
    return round3_entry(argc, argv);
}
