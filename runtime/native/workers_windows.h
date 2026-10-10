/* Windows coordinator owns stable OVERLAPPED state and copied frame buffers.
 * Registry growth never moves a pending operation or its data. Child ends
 * are synchronous, and only the three selected standard handles inherit. */
#ifndef _WIN32_WINNT
#define _WIN32_WINNT 0x0601
#endif
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <wchar.h>

typedef struct WorkerFrame {
    struct WorkerFrame *next;
    size_t length, sent;
    unsigned char bytes[];
} WorkerFrame;
typedef struct WorkerProcess {
    HANDLE process, job, input, output;
    OVERLAPPED read, write;
    WorkerFrame *first, *last;
    size_t queued, message_received;
    unsigned char *message;
    uint32_t generation, message_length;
    unsigned char header[4];
    unsigned header_received;
    int read_pending, write_pending, eof;
    DWORD failed;
} WorkerProcess;
static WorkerProcess **worker_processes;
static size_t worker_capacity;
static uint32_t worker_generation;
static uint64_t worker_pipe_identity;
static int worker_cleanup_installed;

static void worker_destroy(WorkerProcess *worker) {
    if (!worker)
        return;
    if (worker->process)
        TerminateProcess(worker->process, 1);
    if (worker->read_pending) {
        DWORD count;
        CancelIoEx(worker->output, &worker->read);
        GetOverlappedResult(worker->output, &worker->read, &count, TRUE);
    }
    if (worker->write_pending) {
        DWORD count;
        CancelIoEx(worker->input, &worker->write);
        GetOverlappedResult(worker->input, &worker->write, &count, TRUE);
    }
    if (worker->input)
        CloseHandle(worker->input);
    if (worker->output)
        CloseHandle(worker->output);
    if (worker->read.hEvent)
        CloseHandle(worker->read.hEvent);
    if (worker->write.hEvent)
        CloseHandle(worker->write.hEvent);
    if (worker->job)
        CloseHandle(worker->job);
    if (worker->process) {
        WaitForSingleObject(worker->process, INFINITE);
        CloseHandle(worker->process);
    }
    while (worker->first) {
        WorkerFrame *next = worker->first->next;
        free(worker->first);
        worker->first = next;
    }
    free(worker->message);
    free(worker);
}
static void worker_cleanup(void) {
    for (size_t at = 0; at < worker_capacity; at++)
        worker_destroy(worker_processes[at]);
    free(worker_processes);
    worker_processes = NULL;
    worker_capacity = 0;
}
static WorkerProcess *worker_lookup(long long handle) {
    uint64_t identity = (uint64_t)handle;
    uint32_t slot = (uint32_t)identity, generation = (uint32_t)(identity >> 32);
    if (handle <= 0 || !slot || slot > worker_capacity)
        return NULL;
    WorkerProcess *worker = worker_processes[slot - 1];
    return worker && worker->generation == generation ? worker : NULL;
}
static wchar_t *worker_text(const MinyarText *text) {
    if (text->byte_length < 0 || text->byte_length > 1024 * 1024 ||
        memchr(text->bytes, 0, (size_t)text->byte_length)) {
        SetLastError(ERROR_INVALID_PARAMETER);
        return NULL;
    }
    int count = text->byte_length
                    ? MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, (const char *)text->bytes,
                                          (int)text->byte_length, NULL, 0)
                    : 0;
    if (text->byte_length && !count)
        return NULL;
    wchar_t *value = malloc(((size_t)count + 1) * sizeof(*value));
    if (!value) {
        SetLastError(ERROR_NOT_ENOUGH_MEMORY);
        return NULL;
    }
    if (count && MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, (const char *)text->bytes,
                                     (int)text->byte_length, value, count) != count) {
        DWORD code = GetLastError();
        free(value);
        SetLastError(code);
        return NULL;
    }
    value[count] = 0;
    return value;
}
/* C/CommandLineToArgvW quoting: double trailing backslashes, and add one
 * escape before a quote. No shell, interpolation, or ANSI conversion. */
static wchar_t *worker_quote(wchar_t *out, const wchar_t *value) {
    *out++ = L'"';
    while (*value) {
        size_t slashes = 0;
        while (*value == L'\\') {
            slashes++;
            value++;
        }
        size_t copies = (*value == L'"' || !*value) ? 2 * slashes : slashes;
        while (copies--)
            *out++ = L'\\';
        if (*value == L'"')
            *out++ = L'\\';
        if (*value)
            *out++ = *value++;
    }
    *out++ = L'"';
    return out;
}
static DWORD worker_pipe(HANDLE *parent, HANDLE *child, int input) {
    wchar_t name[128];
    swprintf(name, sizeof(name) / sizeof(*name), L"\\\\.\\pipe\\minyar-worker-%lu-%llu",
             (unsigned long)GetCurrentProcessId(), (unsigned long long)++worker_pipe_identity);
    HANDLE server = CreateNamedPipeW(name,
                                     (input ? PIPE_ACCESS_OUTBOUND : PIPE_ACCESS_INBOUND) |
                                         FILE_FLAG_OVERLAPPED | FILE_FLAG_FIRST_PIPE_INSTANCE,
                                     PIPE_TYPE_BYTE | PIPE_READMODE_BYTE | PIPE_WAIT |
                                         PIPE_REJECT_REMOTE_CLIENTS,
                                     1, 65536, 65536, 0, NULL);
    if (server == INVALID_HANDLE_VALUE)
        return GetLastError();
    SECURITY_ATTRIBUTES security = {sizeof(security), NULL, TRUE};
    HANDLE client = CreateFileW(name, input ? GENERIC_READ : GENERIC_WRITE, 0, &security,
                                OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, NULL);
    if (client == INVALID_HANDLE_VALUE) {
        DWORD code = GetLastError();
        CloseHandle(server);
        return code;
    }
    OVERLAPPED connected = {0};
    connected.hEvent = CreateEventW(NULL, TRUE, FALSE, NULL);
    DWORD code = connected.hEvent ? 0 : GetLastError();
    if (!code && !ConnectNamedPipe(server, &connected)) {
        code = GetLastError();
        if (code == ERROR_PIPE_CONNECTED)
            code = 0;
        else if (code == ERROR_IO_PENDING) {
            DWORD count;
            code = GetOverlappedResult(server, &connected, &count, TRUE) ? 0 : GetLastError();
        }
    }
    if (connected.hEvent)
        CloseHandle(connected.hEvent);
    if (code) {
        CloseHandle(server);
        CloseHandle(client);
        return code;
    }
    *parent = server;
    *child = client;
    return 0;
}
static MinyarBytes *worker_spawn(const wchar_t *path, const wchar_t *mode) {
    size_t length = wcslen(path) + wcslen(mode);
    if (!*path || length > 32700 || worker_generation == INT32_MAX)
        return worker_scalar(WORK_FAILURE, ERROR_BAD_LENGTH, 0);
    wchar_t *command = malloc((2 * length + 64) * sizeof(*command));
    WorkerProcess *worker = calloc(1, sizeof(*worker));
    if (!command || !worker) {
        free(command);
        free(worker);
        return worker_scalar(WORK_FAILURE, ERROR_NOT_ENOUGH_MEMORY, 0);
    }
    wchar_t *end = worker_quote(command, path);
    const wchar_t marker[] = L" --minyar-worker ";
    memcpy(end, marker, (sizeof(marker) / sizeof(*marker) - 1) * sizeof(*end));
    end += sizeof(marker) / sizeof(*marker) - 1;
    end = worker_quote(end, mode);
    *end = 0;
    DWORD code = (size_t)(end - command) >= 32767 ? ERROR_BAD_LENGTH : 0;
    HANDLE child_input = NULL, child_output = NULL, child_error = NULL;
    if (!code)
        code = worker_pipe(&worker->input, &child_input, 1);
    if (!code)
        code = worker_pipe(&worker->output, &child_output, 0);
    if (!code) {
        HANDLE error = GetStdHandle(STD_ERROR_HANDLE);
        if (!error || error == INVALID_HANDLE_VALUE) {
            SECURITY_ATTRIBUTES security = {sizeof(security), NULL, TRUE};
            child_error = CreateFileW(L"NUL", GENERIC_WRITE, FILE_SHARE_READ | FILE_SHARE_WRITE,
                                      &security, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, NULL);
            if (child_error == INVALID_HANDLE_VALUE) {
                child_error = NULL;
                code = GetLastError();
            }
        } else if (!DuplicateHandle(GetCurrentProcess(), error, GetCurrentProcess(), &child_error,
                                    0, TRUE, DUPLICATE_SAME_ACCESS))
            code = GetLastError();
    }
    if (!code) {
        worker->read.hEvent = CreateEventW(NULL, TRUE, FALSE, NULL);
        worker->write.hEvent = CreateEventW(NULL, TRUE, FALSE, NULL);
        if (!worker->read.hEvent || !worker->write.hEvent)
            code = GetLastError();
    }
    STARTUPINFOEXW startup = {0};
    startup.StartupInfo.cb = sizeof(startup);
    startup.StartupInfo.dwFlags = STARTF_USESTDHANDLES;
    startup.StartupInfo.hStdInput = child_input;
    startup.StartupInfo.hStdOutput = child_output;
    startup.StartupInfo.hStdError = child_error;
    SIZE_T attributes_size = 0;
    int attributes_initialized = 0;
    if (!code) {
        InitializeProcThreadAttributeList(NULL, 1, 0, &attributes_size);
        startup.lpAttributeList = malloc(attributes_size);
        if (!startup.lpAttributeList)
            code = ERROR_NOT_ENOUGH_MEMORY;
        else if (!InitializeProcThreadAttributeList(startup.lpAttributeList, 1, 0,
                                                    &attributes_size))
            code = GetLastError();
        else
            attributes_initialized = 1;
    }
    HANDLE inherited[] = {child_input, child_output, child_error};
    if (!code &&
        !UpdateProcThreadAttribute(startup.lpAttributeList, 0, PROC_THREAD_ATTRIBUTE_HANDLE_LIST,
                                   inherited, sizeof(inherited), NULL, NULL))
        code = GetLastError();
    if (!code) {
        worker->job = CreateJobObjectW(NULL, NULL);
        JOBOBJECT_EXTENDED_LIMIT_INFORMATION limits = {0};
        limits.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;
        if (!worker->job || !SetInformationJobObject(worker->job, JobObjectExtendedLimitInformation,
                                                     &limits, sizeof(limits)))
            code = GetLastError();
    }
    PROCESS_INFORMATION process = {0};
    if (!code && !CreateProcessW(path, command, NULL, NULL, TRUE,
                                 EXTENDED_STARTUPINFO_PRESENT | CREATE_SUSPENDED, NULL, NULL,
                                 &startup.StartupInfo, &process))
        code = GetLastError();
    if (process.hProcess)
        worker->process = process.hProcess;
    if (!code && !AssignProcessToJobObject(worker->job, worker->process))
        code = GetLastError();
    if (!code && ResumeThread(process.hThread) == (DWORD)-1)
        code = GetLastError();
    if (process.hThread)
        CloseHandle(process.hThread);
    if (attributes_initialized)
        DeleteProcThreadAttributeList(startup.lpAttributeList);
    free(startup.lpAttributeList);
    free(command);
    if (child_input)
        CloseHandle(child_input);
    if (child_output)
        CloseHandle(child_output);
    if (child_error)
        CloseHandle(child_error);
    if (code) {
        worker_destroy(worker);
        return worker_scalar(WORK_FAILURE, (int)code, 0);
    }
    size_t slot = 0;
    while (slot < worker_capacity && worker_processes[slot])
        slot++;
    if (slot == worker_capacity) {
        size_t capacity = worker_capacity ? worker_capacity * 2 : 8;
        WorkerProcess **grown =
            capacity > UINT32_MAX ? NULL : realloc(worker_processes, capacity * sizeof(*grown));
        if (!grown) {
            worker_destroy(worker);
            return worker_scalar(WORK_FAILURE, ERROR_NOT_ENOUGH_MEMORY, 0);
        }
        memset(grown + worker_capacity, 0, (capacity - worker_capacity) * sizeof(*grown));
        worker_processes = grown;
        worker_capacity = capacity;
    }
    worker->generation = ++worker_generation;
    worker_processes[slot] = worker;
    if (!worker_cleanup_installed) {
        atexit(worker_cleanup);
        worker_cleanup_installed = 1;
    }
    return worker_scalar(WORK_OK, 0,
                         (long long)(((uint64_t)worker->generation << 32) | (slot + 1)));
}
bool minyar_workers_supported(void) {
    return true;
}
MinyarBytes *minyar_workers_spawnNative(const MinyarText *path, const MinyarText *mode) {
    wchar_t *executable = worker_text(path);
    if (!executable)
        return worker_scalar(WORK_FAILURE, (int)GetLastError(), 0);
    wchar_t *argument = worker_text(mode);
    if (!argument) {
        DWORD code = GetLastError();
        free(executable);
        return worker_scalar(WORK_FAILURE, (int)code, 0);
    }
    MinyarBytes *result = worker_spawn(executable, argument);
    free(executable);
    free(argument);
    return result;
}
MinyarBytes *minyar_workers_spawnSelfNative(const MinyarText *mode) {
    wchar_t executable[32768];
    DWORD length = GetModuleFileNameW(NULL, executable, sizeof(executable) / sizeof(*executable));
    if (!length || length >= sizeof(executable) / sizeof(*executable))
        return worker_scalar(WORK_FAILURE, length ? ERROR_INSUFFICIENT_BUFFER : (int)GetLastError(),
                             0);
    wchar_t *argument = worker_text(mode);
    if (!argument)
        return worker_scalar(WORK_FAILURE, (int)GetLastError(), 0);
    MinyarBytes *result = worker_spawn(executable, argument);
    free(argument);
    return result;
}
static void worker_advance(WorkerProcess *worker, DWORD count) {
    WorkerFrame *frame = worker->first;
    if (!count || !frame || count > frame->length - frame->sent) {
        worker->failed = ERROR_BROKEN_PIPE;
        return;
    }
    frame->sent += count;
    worker->queued -= count;
    if (frame->sent == frame->length) {
        worker->first = frame->next;
        if (!worker->first)
            worker->last = NULL;
        free(frame);
    }
}
static DWORD worker_flush(WorkerProcess *worker) {
    while (worker->first && !worker->failed) {
        DWORD count = 0;
        if (worker->write_pending) {
            if (!GetOverlappedResult(worker->input, &worker->write, &count, FALSE)) {
                DWORD code = GetLastError();
                if (code == ERROR_IO_INCOMPLETE)
                    return 0;
                worker->failed = code;
                return code;
            }
            worker->write_pending = 0;
            worker_advance(worker, count);
            continue;
        }
        WorkerFrame *frame = worker->first;
        DWORD length =
            frame->length - frame->sent > 4096 ? 4096 : (DWORD)(frame->length - frame->sent);
        HANDLE event = worker->write.hEvent;
        memset(&worker->write, 0, sizeof(worker->write));
        worker->write.hEvent = event;
        ResetEvent(event);
        if (WriteFile(worker->input, frame->bytes + frame->sent, length, &count, &worker->write))
            worker_advance(worker, count);
        else {
            DWORD code = GetLastError();
            if (code == ERROR_IO_PENDING) {
                worker->write_pending = 1;
                return 0;
            }
            worker->failed = code;
        }
    }
    return worker->failed;
}
MinyarBytes *minyar_workers_sendNative(long long handle, const MinyarBytes *message) {
    WorkerProcess *worker = worker_lookup(handle);
    if (!worker)
        return worker_scalar(WORK_FAILURE, ERROR_INVALID_HANDLE, 0);
    if (worker->failed || worker->eof)
        return worker_scalar(WORK_FAILURE,
                             (int)(worker->failed ? worker->failed : ERROR_BROKEN_PIPE), 0);
    if (message->byte_length < 0 || message->byte_length > WORK_MAX_MESSAGE)
        return worker_scalar(WORK_FAILURE, ERROR_BAD_LENGTH, 0);
    if (worker_flush(worker))
        return worker_scalar(WORK_FAILURE, (int)worker->failed, 0);
    size_t length = (size_t)message->byte_length + 4;
    if (worker->queued > WORK_MAX_QUEUE - length)
        return worker_scalar(WORK_BLOCK, ERROR_NO_DATA, 0);
    WorkerFrame *frame = malloc(sizeof(*frame) + length);
    if (!frame)
        return worker_scalar(WORK_FAILURE, ERROR_NOT_ENOUGH_MEMORY, 0);
    frame->next = NULL;
    frame->length = length;
    frame->sent = 0;
    worker_put32(frame->bytes, (uint32_t)message->byte_length);
    if (message->byte_length)
        memcpy(frame->bytes + 4, message->bytes, (size_t)message->byte_length);
    if (worker->last)
        worker->last->next = frame;
    else
        worker->first = frame;
    worker->last = frame;
    worker->queued += length;
    DWORD code = worker_flush(worker);
    return worker_scalar(code ? WORK_FAILURE : WORK_OK, (int)code, message->byte_length);
}
static void worker_received(WorkerProcess *worker, DWORD count) {
    if (!count) {
        if (worker->header_received || worker->message_received)
            worker->failed = ERROR_INVALID_DATA;
        else
            worker->eof = 1;
        return;
    }
    if (worker->header_received < 4) {
        worker->header_received += count;
        if (worker->header_received == 4) {
            worker->message_length = worker_get32(worker->header);
            if (worker->message_length > WORK_MAX_MESSAGE) {
                worker->failed = ERROR_BAD_LENGTH;
                return;
            }
            worker->message = malloc(worker->message_length ? worker->message_length : 1);
            if (!worker->message)
                worker->failed = ERROR_NOT_ENOUGH_MEMORY;
        }
    } else
        worker->message_received += count;
}
MinyarBytes *minyar_workers_receiveNative(long long handle, long long timeout) {
    WorkerProcess *worker = worker_lookup(handle);
    if (!worker)
        return worker_data(WORK_FAILURE, ERROR_INVALID_HANDLE, NULL, 0);
    if (timeout < -1 || timeout > INT_MAX)
        return worker_data(WORK_FAILURE, ERROR_INVALID_PARAMETER, NULL, 0);
    ULONGLONG deadline = timeout < 0 ? 0 : GetTickCount64() + (ULONGLONG)timeout;
    for (;;) {
        if (worker->failed)
            return worker_data(WORK_FAILURE, (int)worker->failed, NULL, 0);
        if (worker->header_received == 4 && worker->message_received == worker->message_length) {
            MinyarBytes *result = worker_data(WORK_OK, 0, worker->message, worker->message_length);
            free(worker->message);
            worker->message = NULL;
            worker->header_received = 0;
            worker->message_received = 0;
            worker->message_length = 0;
            return result;
        }
        if (worker->eof)
            return worker_data(WORK_EOF, 0, NULL, 0);
        if (worker_flush(worker))
            continue;
        DWORD count = 0, code = 0;
        if (worker->read_pending) {
            if (GetOverlappedResult(worker->output, &worker->read, &count, FALSE)) {
                worker->read_pending = 0;
                worker_received(worker, count);
                continue;
            }
            code = GetLastError();
            if (code != ERROR_IO_INCOMPLETE)
                worker->read_pending = 0;
        } else {
            void *target = worker->header_received < 4
                               ? (void *)(worker->header + worker->header_received)
                               : (void *)(worker->message + worker->message_received);
            DWORD remaining = worker->header_received < 4
                                  ? 4 - worker->header_received
                                  : worker->message_length - (DWORD)worker->message_received;
            HANDLE event = worker->read.hEvent;
            memset(&worker->read, 0, sizeof(worker->read));
            worker->read.hEvent = event;
            ResetEvent(event);
            if (ReadFile(worker->output, target, remaining, &count, &worker->read)) {
                worker_received(worker, count);
                continue;
            }
            code = GetLastError();
            if (code == ERROR_IO_PENDING)
                worker->read_pending = 1;
        }
        if (code == ERROR_BROKEN_PIPE || code == ERROR_PIPE_NOT_CONNECTED) {
            worker_received(worker, 0);
            continue;
        }
        if (code != ERROR_IO_PENDING && code != ERROR_IO_INCOMPLETE) {
            worker->failed = code;
            continue;
        }
        ULONGLONG now = GetTickCount64();
        if (timeout >= 0 && now >= deadline)
            return worker_data(WORK_BLOCK, ERROR_NO_DATA, NULL, 0);
        HANDLE events[] = {worker->read.hEvent, worker->write.hEvent};
        DWORD wait = timeout < 0 ? INFINITE : (DWORD)(deadline - now);
        DWORD result = WaitForMultipleObjects(worker->write_pending ? 2 : 1, events, FALSE, wait);
        if (result == WAIT_FAILED)
            worker->failed = GetLastError();
    }
}
MinyarBytes *minyar_workers_closeNative(long long handle) {
    WorkerProcess *worker = worker_lookup(handle);
    if (!worker)
        return worker_scalar(WORK_FAILURE, ERROR_INVALID_HANDLE, 0);
    worker_processes[(uint32_t)(uint64_t)handle - 1] = NULL;
    worker_destroy(worker);
    return worker_scalar(WORK_OK, 0, 1);
}
static DWORD worker_read_exact(HANDLE descriptor, void *buffer, size_t size, int *clean_eof) {
    size_t at = 0;
    while (at < size) {
        DWORD count = 0;
        if (!ReadFile(descriptor, (unsigned char *)buffer + at, (DWORD)(size - at), &count, NULL)) {
            DWORD code = GetLastError();
            if (code != ERROR_BROKEN_PIPE)
                return code;
        }
        if (!count) {
            *clean_eof = at == 0;
            return ERROR_INVALID_DATA;
        }
        at += count;
    }
    return 0;
}
MinyarBytes *minyar_workers_readMessageNative(void) {
    unsigned char header[4];
    int clean_eof = 0;
    DWORD code = worker_read_exact(GetStdHandle(STD_INPUT_HANDLE), header, 4, &clean_eof);
    if (code)
        return worker_data(clean_eof ? WORK_EOF : WORK_FAILURE, clean_eof ? 0 : (int)code, NULL, 0);
    uint32_t length = worker_get32(header);
    if (length > WORK_MAX_MESSAGE)
        return worker_data(WORK_FAILURE, ERROR_BAD_LENGTH, NULL, 0);
    unsigned char *message = malloc(length ? length : 1);
    if (!message)
        return worker_data(WORK_FAILURE, ERROR_NOT_ENOUGH_MEMORY, NULL, 0);
    code = worker_read_exact(GetStdHandle(STD_INPUT_HANDLE), message, length, &clean_eof);
    MinyarBytes *result = worker_data(code ? WORK_FAILURE : WORK_OK, (int)code,
                                      code ? NULL : message, code ? 0 : length);
    free(message);
    return result;
}
static DWORD worker_write_exact(HANDLE descriptor, const void *buffer, size_t size) {
    size_t at = 0;
    while (at < size) {
        DWORD count = 0;
        if (!WriteFile(descriptor, (const unsigned char *)buffer + at, (DWORD)(size - at), &count,
                       NULL))
            return GetLastError();
        if (!count)
            return ERROR_BROKEN_PIPE;
        at += count;
    }
    return 0;
}
MinyarBytes *minyar_workers_replyNative(const MinyarBytes *message) {
    if (message->byte_length < 0 || message->byte_length > WORK_MAX_MESSAGE)
        return worker_scalar(WORK_FAILURE, ERROR_BAD_LENGTH, 0);
    unsigned char header[4];
    worker_put32(header, (uint32_t)message->byte_length);
    DWORD code = worker_write_exact(GetStdHandle(STD_OUTPUT_HANDLE), header, 4);
    if (!code)
        code = worker_write_exact(GetStdHandle(STD_OUTPUT_HANDLE), message->bytes,
                                  (size_t)message->byte_length);
    return worker_scalar(code ? WORK_FAILURE : WORK_OK, (int)code, message->byte_length);
}
