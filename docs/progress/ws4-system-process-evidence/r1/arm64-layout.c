typedef __UINT64_TYPE__ uint64_t;
typedef struct SystemKernelAction {
    unsigned long handler, flags;
#ifdef __x86_64__
    unsigned long restorer;
#endif
    uint64_t mask;
} SystemKernelAction;
const unsigned long review_action_size = sizeof(SystemKernelAction);
const unsigned long review_mask_offset = __builtin_offsetof(SystemKernelAction, mask);
struct KernelArm64Action { unsigned long handler, flags, restorer; uint64_t mask; };
const unsigned long kernel_action_size = sizeof(struct KernelArm64Action);
const unsigned long kernel_mask_offset = __builtin_offsetof(struct KernelArm64Action, mask);
#ifdef REQUIRE_KERNEL_ABI
_Static_assert(sizeof(SystemKernelAction) == sizeof(struct KernelArm64Action), "rt_sigaction kernel action size mismatch");
_Static_assert(__builtin_offsetof(SystemKernelAction, mask) == __builtin_offsetof(struct KernelArm64Action, mask), "rt_sigaction kernel mask offset mismatch");
#endif
