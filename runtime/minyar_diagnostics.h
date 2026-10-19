/* Compiler diagnostics use raw stderr and best-effort source reads. Neither
 * helper runs on a successful compiler path. Source files may be unavailable
 * when a tool checks an in-memory syntax tree; keep its location and message. */
void minyar_runtime_diagnosticWrite(const MinyarText *text) {
    (void)fwrite(text->bytes, 1, (size_t)text->byte_length, stderr);
    (void)fflush(stderr);
}

MinyarText *minyar_runtime_diagnosticSource(const MinyarText *path_text) {
    char *path = text_as_path(path_text);
    FILE *file = open_text_path(path, "rb");
#if defined(MINYAR_BOUNDED_RC) && !defined(MINYAR_COMPILER_ARENA)
    rc_heap_deallocate(path);
#else
    free(path);
#endif
    if (!file) return copy_c_text("");
    long long length = text_file_length(file);
    unsigned char *bytes = new_bytes(length);
    size_t received = fread(bytes, 1, (size_t)length, file);
    int closed = fclose(file);
    if (received != (size_t)length || closed != 0) return copy_c_text("");
    bytes[length] = 0;
    validate_text_bytes(bytes, length);
    return new_text(bytes, length, -1);
}
