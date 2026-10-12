/* Included by system_process.h on Windows. No shell or inherited ambient env;
 * only explicitly selected inheritable standard handles cross the boundary. */
static wchar_t *system_full_path(const wchar_t *value) {
    DWORD count = GetFullPathNameW(value, 0, NULL, NULL);
    if (!count) { system_error = system_windows_error(GetLastError()); return NULL; }
    wchar_t *result = malloc((size_t)count * sizeof(*result));
    if (!result) { system_error = ENOMEM; return NULL; }
    DWORD written = GetFullPathNameW(value, count, result, NULL);
    if (!written || written >= count) {
        system_error = written ? EAGAIN : system_windows_error(GetLastError()); free(result); return NULL;
    }
    return result;
}
static wchar_t *system_quote(wchar_t *out, const wchar_t *value) {
    *out++ = L'"';
    while (*value) {
        size_t slashes = 0;
        while (*value == L'\\') { slashes++; value++; }
        size_t copies = (*value == L'"' || !*value) ? slashes * 2 : slashes;
        while (copies--) *out++ = L'\\';
        if (*value == L'"') *out++ = L'\\';
        if (*value) *out++ = *value++;
    }
    *out++ = L'"'; return out;
}
static size_t system_quote_length(const wchar_t *value) {
    size_t length = 2;
    while (*value) {
        size_t slashes = 0;
        while (*value == L'\\') { slashes++; value++; }
        length += (*value == L'"' || !*value) ? slashes * 2 : slashes;
        if (*value == L'"') length++;
        if (*value) { length++; value++; }
    }
    return length;
}
static int system_env_compare(const void *left, const void *right) {
    int compared = CompareStringOrdinal(*(wchar_t *const *)left, -1, *(wchar_t *const *)right, -1, TRUE);
    return compared == CSTR_LESS_THAN ? -1 : (compared == CSTR_GREATER_THAN ? 1 : 0);
}
static const wchar_t *system_env_equals(const wchar_t *value) { return wcschr(value + (*value == L'='), L'='); }
static int system_windows_spawn(SystemProcess *process, const char *path, SystemVector *argv, SystemVector *envp, const char *cwd) {
    system_error = 0;
    wchar_t *executable = system_wide(path), *working = NULL, *command = NULL, *block = NULL;
    wchar_t **arguments = calloc(argv->count, sizeof(*arguments)), **environment = calloc(envp->count + 1, sizeof(*environment));
    STARTUPINFOEXW startup; PROCESS_INFORMATION created;
    memset(&startup, 0, sizeof(startup)); memset(&created, 0, sizeof(created));
    HANDLE handles[3] = {NULL, NULL, NULL}; size_t handle_count = 0;
    bool attributes_ready = false;
    if (!executable || !arguments || !environment) { if (!system_error) system_error = ENOMEM; goto done; }
    /* Drive-relative names (C:foo) have ambiguous cwd semantics; reject them. */
    if (executable[0] && executable[1] == L':' && executable[2] != L'/' && executable[2] != L'\\') {
        system_error = EINVAL; goto done;
    }
    if (*cwd) {
        wchar_t *wide = system_wide(cwd);
        if (!wide) goto done;
        working = system_full_path(wide); free(wide); if (!working) goto done;
        DWORD attributes = GetFileAttributesW(working);
        if (attributes == INVALID_FILE_ATTRIBUTES) { system_error = system_windows_error(GetLastError()); goto done; }
        if (!(attributes & FILE_ATTRIBUTE_DIRECTORY)) { system_error = ENOTDIR; goto done; }
    }
    if (working && executable[0] != L'/' && executable[0] != L'\\' && executable[1] != L':') {
        size_t length = wcslen(working) + wcslen(executable) + 2;
        wchar_t *combined = malloc(length * sizeof(*combined));
        if (!combined) { system_error = ENOMEM; goto done; }
        wcscpy(combined, working); wcscat(combined, L"\\"); wcscat(combined, executable);
        free(executable); executable = combined;
    }
    wchar_t *absolute = system_full_path(executable);
    if (!absolute) goto done;
    free(executable); executable = absolute;
    size_t command_length = 1;
    for (size_t i = 0; i < argv->count; i++) {
        arguments[i] = system_wide(argv->values[i]); if (!arguments[i]) goto done;
        /* argv[0] has different CRT parsing: quote it without slash escaping. */
        if (!i && wcschr(arguments[i], L'"')) { system_error = EINVAL; goto done; }
        size_t length = i ? system_quote_length(arguments[i]) + 1 : wcslen(arguments[i]) + 2;
        if (length >= 32767 || command_length > 32767 - length) { system_error = E2BIG; goto done; }
        command_length += length;
    }
    command = malloc(command_length * sizeof(*command));
    if (!command) { system_error = ENOMEM; goto done; }
    wchar_t *out = command;
    for (size_t i = 0; i < argv->count; i++) {
        if (i) *out++ = L' ';
        if (i) out = system_quote(out, arguments[i]);
        else { *out++ = L'"'; size_t n = wcslen(arguments[i]); memcpy(out, arguments[i], n * sizeof(*out)); out += n; *out++ = L'"'; }
    }
    *out = 0;
    size_t env_length = envp->count ? 1 : 2;
    for (size_t i = 0; i < envp->count; i++) {
        environment[i] = system_wide(envp->values[i]); if (!environment[i]) goto done;
        size_t length = wcslen(environment[i]) + 1;
        if (length > SYSTEM_VECTOR_LIMIT/2 - env_length) { system_error = E2BIG; goto done; }
        env_length += length;
    }
    qsort(environment, envp->count, sizeof(*environment), system_env_compare);
    for (size_t i = 1; i < envp->count; i++) {
        int left = (int)(system_env_equals(environment[i-1]) - environment[i-1]);
        int right = (int)(system_env_equals(environment[i]) - environment[i]);
        if (CompareStringOrdinal(environment[i-1], left, environment[i], right, TRUE) == CSTR_EQUAL) {
            system_error = EINVAL; goto done;
        }
    }
    block = calloc(env_length, sizeof(*block));
    if (!block) { system_error = ENOMEM; goto done; }
    out = block;
    for (size_t i = 0; i < envp->count; i++) {
        size_t length = wcslen(environment[i]) + 1; memcpy(out, environment[i], length * sizeof(*out)); out += length;
    }
    DWORD standard[] = {STD_INPUT_HANDLE, STD_OUTPUT_HANDLE, STD_ERROR_HANDLE};
    HANDLE *selected[] = {&startup.StartupInfo.hStdInput, &startup.StartupInfo.hStdOutput, &startup.StartupInfo.hStdError};
    for (unsigned i = 0; i < 3; i++) {
        HANDLE original = GetStdHandle(standard[i]); DWORD flags;
        if (!original || original == INVALID_HANDLE_VALUE) continue;
        if (!GetHandleInformation(original, &flags)) { system_error = system_windows_error(GetLastError()); goto done; }
        if (!(flags & HANDLE_FLAG_INHERIT)) continue;
        if (!DuplicateHandle(GetCurrentProcess(), original, GetCurrentProcess(), &handles[handle_count],
                             0, TRUE, DUPLICATE_SAME_ACCESS)) { system_error = system_windows_error(GetLastError()); goto done; }
        *selected[i] = handles[handle_count++];
    }
    SIZE_T size = 0;
    InitializeProcThreadAttributeList(NULL, 1, 0, &size);
    startup.lpAttributeList = malloc(size);
    if (!startup.lpAttributeList) { system_error = ENOMEM; goto done; }
    if (!InitializeProcThreadAttributeList(startup.lpAttributeList, 1, 0, &size)) {
        system_error = system_windows_error(GetLastError()); goto done;
    }
    attributes_ready = true;
    if (handle_count && !UpdateProcThreadAttribute(startup.lpAttributeList, 0, PROC_THREAD_ATTRIBUTE_HANDLE_LIST,
                                                  handles, handle_count * sizeof(HANDLE), NULL, NULL)) {
        system_error = system_windows_error(GetLastError()); goto done;
    }
    startup.StartupInfo.cb = sizeof(startup); startup.StartupInfo.dwFlags = STARTF_USESTDHANDLES;
    if (!CreateProcessW(executable, command, NULL, NULL, handle_count ? TRUE : FALSE,
                         EXTENDED_STARTUPINFO_PRESENT | CREATE_UNICODE_ENVIRONMENT, block, working,
                         &startup.StartupInfo, &created)) { system_error = system_windows_error(GetLastError()); goto done; }
    CloseHandle(created.hThread); process->process = created.hProcess; process->pid = created.dwProcessId;
done:
    if (attributes_ready) DeleteProcThreadAttributeList(startup.lpAttributeList);
    free(startup.lpAttributeList);
    for (size_t i = 0; i < handle_count; i++) CloseHandle(handles[i]);
    if (arguments) for (size_t i = 0; i < argv->count; i++) free(arguments[i]);
    if (environment) for (size_t i = 0; i < envp->count; i++) free(environment[i]);
    free(arguments); free(environment); free(executable); free(working); free(command); free(block);
    return system_error;
}
