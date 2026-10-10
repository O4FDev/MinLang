"""Research-only transformations of a frozen runtime; never edit production.

FIFO keeps the oldest object active until it finishes. LIFO can preempt its
parent with a newly retired child. All incremental variants retain the same
three-way frame/chunk/object scheduler and per-field accounting.
"""

POLICIES = ('current', 'fair-unit', 'fifo', 'lifo', 'eager')


def replace_once(source, old, new):
    if source.count(old) != 1:
        raise ValueError(f'runtime structure changed: expected one {old[:70]!r}')
    return source.replace(old, new)


def replace_function(source, signature, replacement):
    if source.count(signature) != 1:
        raise ValueError(f'runtime structure changed: {signature}')
    start = source.index(signature)
    opening = source.index('{', start)
    depth = 1
    end = opening + 1
    # These particular functions contain no brace characters inside literals.
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[:start] + replacement + source[end:]


UNIT_POLL = '''size_t minyar_rc_poll(size_t budget) {
    if (budget > MINYAR_RC_POLL_BUDGET) budget = MINYAR_RC_POLL_BUDGET;
    size_t work = 0;
    while (work < budget && rc_pending_count) {
        unsigned queue = rc_bounded_next_queue;
        for (unsigned tries = 0; tries < 3; tries++) {
            if ((queue == 0 && (rc_bounded_active || rc_bounded_head || rc_bounded_recent_head)) ||
                (queue == 1 && rc_bounded_frame_head) ||
                (queue == 2 && rc_bounded_chunk_head)) break;
            queue = (queue + 1) % 3;
        }
        rc_bounded_next_queue = (queue + 1) % 3;
        if (queue == 0) rc_bounded_object_unit();
        else if (queue == 1) rc_bounded_frame_unit();
        else rc_bounded_chunk_unit();
        work++;
    }
#ifdef MINYAR_RC_TESTING
    rc_bounded_last_work = work;
#endif
    return work;
}'''


def transform(source, policy):
    if policy not in POLICIES:
        raise ValueError(policy)
    if policy in ('current', 'eager'):
        return source
    source = replace_function(source, 'size_t minyar_rc_poll(size_t budget) {', UNIT_POLL)
    if policy == 'fifo':
        source = replace_once(source, '''    object->ownership |= (size_t)(uintptr_t)rc_bounded_recent_head;
    rc_bounded_recent_head = object;
    if (!rc_bounded_recent_tail) rc_bounded_recent_tail = object;''', '''    if (rc_bounded_tail)
        rc_bounded_tail->ownership |= (size_t)(uintptr_t)object;
    else rc_bounded_head = object;
    rc_bounded_tail = object;''')
        source = replace_function(source, 'static void rc_bounded_object_unit(void) {',
                                  'static void rc_bounded_object_unit(void) { rc_bounded_old_object_unit(); }')
    elif policy == 'lifo':
        source = replace_function(source, 'static void rc_bounded_object_unit(void) {',
                                  'static void rc_bounded_object_unit(void) { rc_bounded_recent_object_unit(); }')
    return source
