	.section	__TEXT,__text,regular,pure_instructions
	.build_version macos, 26, 0	sdk_version 26, 2
	.globl	_minyar_stack_enter             ; -- Begin function minyar_stack_enter
	.p2align	2
_minyar_stack_enter:                    ; @minyar_stack_enter
	.cfi_startproc
; %bb.0:
	sub	sp, sp, #32
	stp	x29, x30, [sp, #16]             ; 16-byte Folded Spill
	add	x29, sp, #16
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
	adrp	x8, __MergedGlobals@PAGE
	ldrb	w8, [x8, __MergedGlobals@PAGEOFF]
	tbz	w8, #0, LBB0_6
LBB0_1:
	adrp	x8, _minyar_call_depth@PAGE
	ldr	x9, [x8, _minyar_call_depth@PAGEOFF]
	lsr	x10, x9, #20
	cbnz	x10, LBB0_7
; %bb.2:
Lloh0:
	adrp	x11, __MergedGlobals@PAGE+8
Lloh1:
	add	x11, x11, __MergedGlobals@PAGEOFF+8
	ldp	x10, x11, [x11]
	cmp	x10, #0
	ccmp	x11, #0, #4, ne
	cset	w12, eq
	cmp	x9, #8, lsl #12                 ; =32768
	b.lo	LBB0_4
; %bb.3:
	tbnz	w12, #0, LBB0_7
LBB0_4:
	sub	x12, x29, #1
	sub	x13, x12, x10
	cmp	x13, #32, lsl #12               ; =131072
	ccmp	x12, x10, #0, ls
	ccmp	x11, x12, #0, hs
	b.hi	LBB0_7
; %bb.5:
	add	x9, x9, #1
	str	x9, [x8, _minyar_call_depth@PAGEOFF]
	ldp	x29, x30, [sp, #16]             ; 16-byte Folded Reload
	add	sp, sp, #32
	ret
LBB0_6:
	bl	_minyar_find_stack_bounds
	b	LBB0_1
LBB0_7:
	bl	_minyar_stack_enter.cold.1
	.loh AdrpAdd	Lloh0, Lloh1
	.cfi_endproc
                                        ; -- End function
	.p2align	2                               ; -- Begin function minyar_find_stack_bounds
_minyar_find_stack_bounds:              ; @minyar_find_stack_bounds
	.cfi_startproc
; %bb.0:
	stp	x20, x19, [sp, #-32]!           ; 16-byte Folded Spill
	stp	x29, x30, [sp, #16]             ; 16-byte Folded Spill
	add	x29, sp, #16
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
	.cfi_offset w19, -24
	.cfi_offset w20, -32
Lloh2:
	adrp	x20, __MergedGlobals@PAGE
Lloh3:
	add	x20, x20, __MergedGlobals@PAGEOFF
	mov	w8, #1                          ; =0x1
	strb	w8, [x20]
	bl	_pthread_self
	bl	_pthread_get_stackaddr_np
	mov	x19, x0
	bl	_pthread_self
	bl	_pthread_get_stacksize_np
	str	x19, [x20, #16]
	cmp	x0, x19
	b.hi	LBB1_2
; %bb.1:
	sub	x8, x19, x0
	adrp	x9, __MergedGlobals@PAGE+8
	str	x8, [x9, __MergedGlobals@PAGEOFF+8]
LBB1_2:
	ldp	x29, x30, [sp, #16]             ; 16-byte Folded Reload
	b	_OUTLINED_FUNCTION_2
	.loh AdrpAdd	Lloh2, Lloh3
	.cfi_endproc
                                        ; -- End function
	.p2align	2                               ; -- Begin function minyar_stop
_minyar_stop:                           ; @minyar_stop
	.cfi_startproc
; %bb.0:
	sub	sp, sp, #32
	stp	x29, x30, [sp, #16]             ; 16-byte Folded Spill
	add	x29, sp, #16
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
Lloh4:
	adrp	x8, ___stderrp@GOTPAGE
Lloh5:
	ldr	x8, [x8, ___stderrp@GOTPAGEOFF]
Lloh6:
	ldr	x8, [x8]
	str	x0, [sp]
Lloh7:
	adrp	x1, l_.str.47@PAGE
Lloh8:
	add	x1, x1, l_.str.47@PAGEOFF
	mov	x0, x8
	bl	_fprintf
	bl	_OUTLINED_FUNCTION_0
	.loh AdrpAdd	Lloh7, Lloh8
	.loh AdrpLdrGotLdr	Lloh4, Lloh5, Lloh6
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_stack_leave             ; -- Begin function minyar_stack_leave
	.p2align	2
_minyar_stack_leave:                    ; @minyar_stack_leave
	.cfi_startproc
; %bb.0:
	adrp	x8, _minyar_call_depth@PAGE
	ldr	x9, [x8, _minyar_call_depth@PAGEOFF]
	cbz	x9, LBB3_2
; %bb.1:
	sub	x9, x9, #1
	str	x9, [x8, _minyar_call_depth@PAGEOFF]
	ret
LBB3_2:
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
	bl	_minyar_stack_leave.cold.1
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_rc_retain               ; -- Begin function minyar_rc_retain
	.p2align	2
_minyar_rc_retain:                      ; @minyar_rc_retain
	.cfi_startproc
; %bb.0:
	cbz	x0, LBB4_4
; %bb.1:
	ldur	x8, [x0, #-8]
	cmp	x8, #8
	b.lo	LBB4_4
; %bb.2:
	cmn	x8, #8
	b.hs	LBB4_5
; %bb.3:
	add	x8, x8, #8
	stur	x8, [x0, #-8]
LBB4_4:
	ret
LBB4_5:
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
	bl	_minyar_rc_retain.cold.1
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_rc_poll                 ; -- Begin function minyar_rc_poll
	.p2align	2
_minyar_rc_poll:                        ; @minyar_rc_poll
	.cfi_startproc
; %bb.0:
	stp	x28, x27, [sp, #-96]!           ; 16-byte Folded Spill
	stp	x26, x25, [sp, #16]             ; 16-byte Folded Spill
	stp	x24, x23, [sp, #32]             ; 16-byte Folded Spill
	stp	x22, x21, [sp, #48]             ; 16-byte Folded Spill
	stp	x20, x19, [sp, #64]             ; 16-byte Folded Spill
	stp	x29, x30, [sp, #80]             ; 16-byte Folded Spill
	add	x29, sp, #80
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
	.cfi_offset w19, -24
	.cfi_offset w20, -32
	.cfi_offset w21, -40
	.cfi_offset w22, -48
	.cfi_offset w23, -56
	.cfi_offset w24, -64
	.cfi_offset w25, -72
	.cfi_offset w26, -80
	.cfi_offset w27, -88
	.cfi_offset w28, -96
	mov	w8, #32                         ; =0x20
	cmp	x0, #32
	csel	x21, x0, x8, lo
	adrp	x23, _rc_bounded_frame_head@PAGE
	ldr	x9, [x23, _rc_bounded_frame_head@PAGEOFF]
	adrp	x24, _rc_bounded_chunk_head@PAGE
	ldr	x10, [x24, _rc_bounded_chunk_head@PAGEOFF]
	cmp	x0, #0
	adrp	x26, _rc_pending_count@PAGE
	ldr	x22, [x26, _rc_pending_count@PAGEOFF]
	ccmp	x22, #0, #4, ne
	cset	w8, ne
	mov	x19, #0                         ; =0x0
	orr	x9, x9, x10
	cbz	x9, LBB5_47
; %bb.1:
	cbz	w8, LBB5_79
; %bb.2:
	adrp	x25, _rc_bounded_next_queue@PAGE
	adrp	x27, _rc_bounded_head@PAGE
	adrp	x28, _rc_bounded_recent_head@PAGE
LBB5_3:                                 ; =>This Inner Loop Header: Depth=1
	ldr	w10, [x25, _rc_bounded_next_queue@PAGEOFF]
	ldr	x20, [x23, _rc_bounded_frame_head@PAGEOFF]
	cmp	x20, #0
	cset	w8, ne
	ldr	x0, [x24, _rc_bounded_chunk_head@PAGEOFF]
Lloh9:
	adrp	x9, _rc_bounded_active@PAGE
Lloh10:
	ldr	x9, [x9, _rc_bounded_active@PAGEOFF]
	ldr	x11, [x27, _rc_bounded_head@PAGEOFF]
	orr	x9, x9, x11
	ldr	x11, [x28, _rc_bounded_recent_head@PAGEOFF]
	orr	x9, x9, x11
	cmp	x9, #0
	cset	w9, ne
	cbz	w10, LBB5_9
; %bb.4:                                ;   in Loop: Header=BB5_3 Depth=1
	cmp	w10, #1
	ccmp	x20, #0, #4, eq
	b.ne	LBB5_14
; %bb.5:                                ;   in Loop: Header=BB5_3 Depth=1
	cmp	w10, #2
	ccmp	x0, #0, #4, eq
	b.ne	LBB5_24
; %bb.6:                                ;   in Loop: Header=BB5_3 Depth=1
	add	w10, w10, #1
	mov	w11, #43691                     ; =0xaaab
	movk	w11, #43690, lsl #16
	umull	x11, w10, w11
	lsr	x11, x11, #33
	add	w11, w11, w11, lsl #1
	subs	w10, w10, w11
	b.ne	LBB5_12
; %bb.7:                                ;   in Loop: Header=BB5_3 Depth=1
	tbnz	w9, #0, LBB5_10
; %bb.8:                                ;   in Loop: Header=BB5_3 Depth=1
	mov	w10, #0                         ; =0x0
	mov	w9, #1                          ; =0x1
	tbnz	w8, #0, LBB5_14
	b	LBB5_38
LBB5_9:                                 ;   in Loop: Header=BB5_3 Depth=1
	cbz	w9, LBB5_11
LBB5_10:                                ;   in Loop: Header=BB5_3 Depth=1
	mov	w8, #1                          ; =0x1
	str	w8, [x25, _rc_bounded_next_queue@PAGEOFF]
	bl	_rc_bounded_object_unit
	b	LBB5_45
LBB5_11:                                ;   in Loop: Header=BB5_3 Depth=1
	mov	w10, #1                         ; =0x1
LBB5_12:                                ;   in Loop: Header=BB5_3 Depth=1
	cmp	w10, #1
	b.ne	LBB5_22
; %bb.13:                               ;   in Loop: Header=BB5_3 Depth=1
	cbz	x20, LBB5_22
LBB5_14:                                ;   in Loop: Header=BB5_3 Depth=1
	mov	w8, #2                          ; =0x2
	str	w8, [x25, _rc_bounded_next_queue@PAGEOFF]
LBB5_15:                                ;   in Loop: Header=BB5_3 Depth=1
	ldr	x8, [x20, #16]
	cbz	x8, LBB5_17
; %bb.16:                               ;   in Loop: Header=BB5_3 Depth=1
	sub	x8, x8, #1
	str	x8, [x20, #16]
	ldr	x9, [x20, #8]
	ldr	x10, [x20, #24]
	add	x10, x9, x10, lsl #3
	ldr	x8, [x10, x8, lsl #3]
	ldr	x8, [x9, x8, lsl #3]
	and	x0, x8, #0xfffffffffffffffe
	bl	_rc_drop
	b	LBB5_45
LBB5_17:                                ;   in Loop: Header=BB5_3 Depth=1
	ldr	x8, [x20]
	str	x8, [x23, _rc_bounded_frame_head@PAGEOFF]
	cbz	x8, LBB5_33
; %bb.18:                               ;   in Loop: Header=BB5_3 Depth=1
	ldr	x0, [x20, #8]
	cbz	x0, LBB5_34
LBB5_19:                                ;   in Loop: Header=BB5_3 Depth=1
	ldr	x8, [x20, #24]
	lsl	x10, x8, #4
	add	x9, x10, #64
	cmp	x9, #64, lsl #12                ; =262144
	b.hi	LBB5_21
; %bb.20:                               ;   in Loop: Header=BB5_3 Depth=1
Lloh11:
	adrp	x8, _rc_bounded_cached_frame_bytes@PAGE
Lloh12:
	ldr	x8, [x8, _rc_bounded_cached_frame_bytes@PAGEOFF]
	mov	w11, #262080                    ; =0x3ffc0
	sub	x10, x11, x10
	cmp	x8, x10
	b.ls	LBB5_43
LBB5_21:                                ;   in Loop: Header=BB5_3 Depth=1
Lloh13:
	adrp	x8, _rc_heap_allocation_count@PAGE
Lloh14:
	ldr	x8, [x8, _rc_heap_allocation_count@PAGEOFF]
	sub	x26, x8, #1
	bl	_free
	adrp	x9, _rc_heap_allocation_count@PAGE
	b	LBB5_36
LBB5_22:                                ;   in Loop: Header=BB5_3 Depth=1
	cmp	w10, #2
	b.ne	LBB5_30
; %bb.23:                               ;   in Loop: Header=BB5_3 Depth=1
	cbz	x0, LBB5_30
LBB5_24:                                ;   in Loop: Header=BB5_3 Depth=1
	str	wzr, [x25, _rc_bounded_next_queue@PAGEOFF]
LBB5_25:                                ;   in Loop: Header=BB5_3 Depth=1
	ldr	x8, [x0, #8]
	cbz	x8, LBB5_27
; %bb.26:                               ;   in Loop: Header=BB5_3 Depth=1
	sub	x8, x8, #1
	add	x9, x0, x8, lsl #3
	str	x8, [x0, #8]
	ldr	x0, [x9, #16]
	bl	_rc_drop
	b	LBB5_45
LBB5_27:                                ;   in Loop: Header=BB5_3 Depth=1
	ldr	x8, [x0]
	str	x8, [x24, _rc_bounded_chunk_head@PAGEOFF]
	cbnz	x8, LBB5_29
; %bb.28:                               ;   in Loop: Header=BB5_3 Depth=1
	adrp	x8, _rc_bounded_chunk_tail@PAGE
	str	xzr, [x8, _rc_bounded_chunk_tail@PAGEOFF]
LBB5_29:                                ;   in Loop: Header=BB5_3 Depth=1
	adrp	x9, _rc_heap_allocation_count@PAGE
	ldr	x8, [x9, _rc_heap_allocation_count@PAGEOFF]
	sub	x8, x8, #1
	str	x8, [x9, _rc_heap_allocation_count@PAGEOFF]
	bl	_free
	b	LBB5_44
LBB5_30:                                ;   in Loop: Header=BB5_3 Depth=1
	cmp	w10, #2
	b.ne	LBB5_37
; %bb.31:                               ;   in Loop: Header=BB5_3 Depth=1
	tbnz	w9, #0, LBB5_10
; %bb.32:                               ;   in Loop: Header=BB5_3 Depth=1
	mov	w9, #0                          ; =0x0
	b	LBB5_39
LBB5_33:                                ;   in Loop: Header=BB5_3 Depth=1
	adrp	x8, _rc_bounded_frame_tail@PAGE
	str	xzr, [x8, _rc_bounded_frame_tail@PAGEOFF]
	ldr	x0, [x20, #8]
	cbnz	x0, LBB5_19
LBB5_34:                                ;   in Loop: Header=BB5_3 Depth=1
Lloh15:
	adrp	x8, _rc_bounded_cached_frame_bytes@PAGE
Lloh16:
	ldr	x8, [x8, _rc_bounded_cached_frame_bytes@PAGEOFF]
	mov	w9, #65473                      ; =0xffc1
	movk	w9, #3, lsl #16
	cmp	x8, x9
	b.lo	LBB5_42
; %bb.35:                               ;   in Loop: Header=BB5_3 Depth=1
	adrp	x9, _rc_heap_allocation_count@PAGE
	ldr	x26, [x9, _rc_heap_allocation_count@PAGEOFF]
LBB5_36:                                ;   in Loop: Header=BB5_3 Depth=1
	sub	x8, x26, #1
	str	x8, [x9, _rc_heap_allocation_count@PAGEOFF]
	mov	x0, x20
	bl	_free
	adrp	x26, _rc_pending_count@PAGE
	b	LBB5_44
LBB5_37:                                ;   in Loop: Header=BB5_3 Depth=1
	mov	w8, #0                          ; =0x0
	mov	w9, #2                          ; =0x2
	mov	w10, #1                         ; =0x1
	tbnz	w8, #0, LBB5_14
LBB5_38:                                ;   in Loop: Header=BB5_3 Depth=1
	cmp	x0, #0
	csel	w8, wzr, w10, eq
	tbnz	w8, #0, LBB5_24
LBB5_39:                                ;   in Loop: Header=BB5_3 Depth=1
	add	w8, w9, #1
	sub	w10, w9, #2
	cmp	w8, #3
	csinc	w8, w10, w9, hs
	add	w9, w8, #1
	cmp	w9, #3
	csinc	w9, wzr, w8, eq
	str	w9, [x25, _rc_bounded_next_queue@PAGEOFF]
	cmp	w8, #1
	b.eq	LBB5_15
; %bb.40:                               ;   in Loop: Header=BB5_3 Depth=1
	cbnz	w8, LBB5_25
; %bb.41:                               ;   in Loop: Header=BB5_3 Depth=1
	bl	_rc_bounded_object_unit
	b	LBB5_45
LBB5_42:                                ;   in Loop: Header=BB5_3 Depth=1
	mov	w9, #64                         ; =0x40
LBB5_43:                                ;   in Loop: Header=BB5_3 Depth=1
	adrp	x11, _rc_free_frames@PAGE
	ldr	x10, [x11, _rc_free_frames@PAGEOFF]
	str	x10, [x20]
	str	x20, [x11, _rc_free_frames@PAGEOFF]
	add	x8, x9, x8
	adrp	x9, _rc_bounded_cached_frame_bytes@PAGE
	str	x8, [x9, _rc_bounded_cached_frame_bytes@PAGEOFF]
LBB5_44:                                ;   in Loop: Header=BB5_3 Depth=1
	sub	x8, x22, #1
	str	x8, [x26, _rc_pending_count@PAGEOFF]
LBB5_45:                                ;   in Loop: Header=BB5_3 Depth=1
	add	x19, x19, #1
	cmp	x19, x21
	b.hs	LBB5_79
; %bb.46:                               ;   in Loop: Header=BB5_3 Depth=1
	ldr	x22, [x26, _rc_pending_count@PAGEOFF]
	cbnz	x22, LBB5_3
	b	LBB5_79
LBB5_47:
	cbz	w8, LBB5_79
; %bb.48:
	adrp	x24, _rc_bounded_recent_head@PAGE
	adrp	x25, _rc_bounded_cursor@PAGE
	adrp	x26, _rc_bounded_recent_turn@PAGE
	adrp	x28, _rc_heap_allocation_count@PAGE
	adrp	x23, _rc_object_count@PAGE
LBB5_49:                                ; =>This Loop Header: Depth=1
                                        ;     Child Loop BB5_57 Depth 2
                                        ;     Child Loop BB5_70 Depth 2
	sub	x27, x21, x19
Lloh17:
	adrp	x8, _rc_bounded_active@PAGE
Lloh18:
	ldr	x20, [x8, _rc_bounded_active@PAGEOFF]
	ldr	x8, [x24, _rc_bounded_recent_head@PAGEOFF]
	cmp	x27, #2
	b.lo	LBB5_62
; %bb.50:                               ;   in Loop: Header=BB5_49 Depth=1
	cmp	x22, #1
	b.ne	LBB5_62
; %bb.51:                               ;   in Loop: Header=BB5_49 Depth=1
	cbnz	x20, LBB5_62
; %bb.52:                               ;   in Loop: Header=BB5_49 Depth=1
Lloh19:
	adrp	x9, _rc_bounded_head@PAGE
Lloh20:
	ldr	x9, [x9, _rc_bounded_head@PAGEOFF]
	cmp	x9, #0
	csel	x0, x8, x9, eq
	cbz	x0, LBB5_74
; %bb.53:                               ;   in Loop: Header=BB5_49 Depth=1
	ldr	x8, [x0]
	and	x8, x8, #0x7
	cmp	x8, #4
	b.ne	LBB5_74
; %bb.54:                               ;   in Loop: Header=BB5_49 Depth=1
	mov	x9, x0
	ldr	x8, [x9, #8]!
	cmp	x8, #1
	b.ne	LBB5_74
; %bb.55:                               ;   in Loop: Header=BB5_49 Depth=1
	mov	x8, x0
	ldrb	w10, [x8, #24]!
	cmp	w10, #1
	b.hi	LBB5_74
; %bb.56:                               ;   in Loop: Header=BB5_49 Depth=1
Lloh21:
	adrp	x10, _rc_bounded_head@PAGE
	str	xzr, [x10, _rc_bounded_head@PAGEOFF]
Lloh22:
	adrp	x10, _rc_bounded_recent_tail@PAGE
	str	xzr, [x10, _rc_bounded_recent_tail@PAGEOFF]
	str	xzr, [x24, _rc_bounded_recent_head@PAGEOFF]
	mov	w10, #4                         ; =0x4
	str	x10, [x0]
	adrp	x10, _rc_bounded_active@PAGE
	str	x0, [x10, _rc_bounded_active@PAGEOFF]
	mov	w10, #1                         ; =0x1
	str	x10, [x25, _rc_bounded_cursor@PAGEOFF]
	cmp	x27, #4
	b.lo	LBB5_65
LBB5_57:                                ;   Parent Loop BB5_49 Depth=1
                                        ; =>  This Inner Loop Header: Depth=2
	ldrb	w10, [x8]
	tbz	w10, #0, LBB5_65
; %bb.58:                               ;   in Loop: Header=BB5_57 Depth=2
	ldr	x22, [x9, #8]
	cbz	x22, LBB5_65
; %bb.59:                               ;   in Loop: Header=BB5_57 Depth=2
	mov	x20, x22
	ldr	x10, [x20, #-8]!
	cmp	x10, #12
	b.ne	LBB5_65
; %bb.60:                               ;   in Loop: Header=BB5_57 Depth=2
	ldr	x10, [x22]
	cmp	x10, #1
	b.ne	LBB5_65
; %bb.61:                               ;   in Loop: Header=BB5_57 Depth=2
	mov	w8, #4                          ; =0x4
	stur	x8, [x22, #-8]
	ldr	x8, [x0, #8]
	add	x8, x8, x8, lsl #3
	adrp	x10, _rc_bytes@PAGE
	ldr	x9, [x10, _rc_bytes@PAGEOFF]
	sub	x8, x9, x8
	sub	x8, x8, #16
	str	x8, [x10, _rc_bytes@PAGEOFF]
	ldr	x8, [x28, _rc_heap_allocation_count@PAGEOFF]
	sub	x8, x8, #1
	str	x8, [x28, _rc_heap_allocation_count@PAGEOFF]
	bl	_free
	ldr	x8, [x23, _rc_object_count@PAGEOFF]
	sub	x8, x8, #1
	str	x8, [x23, _rc_object_count@PAGEOFF]
	add	x8, x22, #16
	adrp	x9, _rc_bounded_active@PAGE
	str	x20, [x9, _rc_bounded_active@PAGEOFF]
	add	x19, x19, #2
	sub	x27, x27, #2
	mov	x0, x20
	mov	x9, x22
	cmp	x27, #3
	b.hi	LBB5_57
	b	LBB5_66
LBB5_62:                                ;   in Loop: Header=BB5_49 Depth=1
	cmp	x8, #0
	ccmp	x20, #0, #4, eq
	b.eq	LBB5_74
; %bb.63:                               ;   in Loop: Header=BB5_49 Depth=1
	ldr	x8, [x20]
	and	x8, x8, #0x7
	cmp	x8, #3
	b.ne	LBB5_74
; %bb.64:                               ;   in Loop: Header=BB5_49 Depth=1
	ldr	x9, [x20, #16]
	ldr	x8, [x25, _rc_bounded_cursor@PAGEOFF]
	sub	x9, x9, x8
	cmp	x27, x9
	csel	x22, x27, x9, lo
	add	x27, x22, x8
	cmp	x8, x27
	b.lo	LBB5_70
	b	LBB5_73
LBB5_65:                                ;   in Loop: Header=BB5_49 Depth=1
	mov	x22, x9
	mov	x20, x0
LBB5_66:                                ;   in Loop: Header=BB5_49 Depth=1
	ldr	w9, [x26, _rc_bounded_recent_turn@PAGEOFF]
	eor	w10, w9, #0x1
	str	w10, [x26, _rc_bounded_recent_turn@PAGEOFF]
	ldrb	w8, [x8]
	tbz	w8, #0, LBB5_68
; %bb.67:                               ;   in Loop: Header=BB5_49 Depth=1
	ldr	x0, [x22, #8]
	bl	_rc_drop
	ldr	w8, [x26, _rc_bounded_recent_turn@PAGEOFF]
	eor	w9, w8, #0x1
LBB5_68:                                ;   in Loop: Header=BB5_49 Depth=1
	str	w9, [x26, _rc_bounded_recent_turn@PAGEOFF]
	ldr	x8, [x20, #8]
	add	x8, x8, x8, lsl #3
	adrp	x10, _rc_bytes@PAGE
	ldr	x9, [x10, _rc_bytes@PAGEOFF]
	sub	x8, x9, x8
	sub	x8, x8, #16
	str	x8, [x10, _rc_bytes@PAGEOFF]
	ldr	x8, [x28, _rc_heap_allocation_count@PAGEOFF]
	sub	x8, x8, #1
	str	x8, [x28, _rc_heap_allocation_count@PAGEOFF]
	mov	x0, x20
	bl	_free
	ldr	x8, [x23, _rc_object_count@PAGEOFF]
	sub	x8, x8, #1
	str	x8, [x23, _rc_object_count@PAGEOFF]
	adrp	x9, _rc_pending_count@PAGE
	ldr	x8, [x9, _rc_pending_count@PAGEOFF]
	sub	x8, x8, #1
	str	x8, [x9, _rc_pending_count@PAGEOFF]
	adrp	x8, _rc_bounded_active@PAGE
	str	xzr, [x8, _rc_bounded_active@PAGEOFF]
	add	x19, x19, #2
	b	LBB5_75
LBB5_69:                                ;   in Loop: Header=BB5_70 Depth=2
	mov	x0, x8
	bl	_rc_drop
	ldr	x9, [x24, _rc_bounded_recent_head@PAGEOFF]
	ldr	x8, [x25, _rc_bounded_cursor@PAGEOFF]
	cmp	x9, #0
	ccmp	x8, x27, #2, eq
	b.hs	LBB5_73
LBB5_70:                                ;   Parent Loop BB5_49 Depth=1
                                        ; =>  This Inner Loop Header: Depth=2
	add	x19, x19, #1
	ldr	w9, [x26, _rc_bounded_recent_turn@PAGEOFF]
	eor	w9, w9, #0x1
	str	w9, [x26, _rc_bounded_recent_turn@PAGEOFF]
	ldr	x9, [x20, #8]
	add	x10, x8, #1
	str	x10, [x25, _rc_bounded_cursor@PAGEOFF]
	ldr	x8, [x9, x8, lsl #3]
	cbz	x8, LBB5_69
; %bb.71:                               ;   in Loop: Header=BB5_70 Depth=2
	sub	x0, x8, #8
	ldr	x9, [x0]
	cmp	x9, #13
	b.ne	LBB5_69
; %bb.72:                               ;   in Loop: Header=BB5_70 Depth=2
	ldr	x8, [x8]
	adrp	x10, _rc_bytes@PAGE
	ldr	x9, [x10, _rc_bytes@PAGEOFF]
	sub	x8, x9, x8, lsl #3
	sub	x8, x8, #16
	str	x8, [x10, _rc_bytes@PAGEOFF]
	ldr	x8, [x28, _rc_heap_allocation_count@PAGEOFF]
	sub	x8, x8, #1
	str	x8, [x28, _rc_heap_allocation_count@PAGEOFF]
	bl	_free
	ldr	x8, [x23, _rc_object_count@PAGEOFF]
	sub	x8, x8, #1
	str	x8, [x23, _rc_object_count@PAGEOFF]
	ldr	x8, [x25, _rc_bounded_cursor@PAGEOFF]
	cmp	x8, x27
	b.lo	LBB5_70
LBB5_73:                                ;   in Loop: Header=BB5_49 Depth=1
	cbnz	x22, LBB5_75
LBB5_74:                                ;   in Loop: Header=BB5_49 Depth=1
	bl	_rc_bounded_object_unit
	add	x19, x19, #1
LBB5_75:                                ;   in Loop: Header=BB5_49 Depth=1
	cmp	x19, x21
	b.hs	LBB5_77
; %bb.76:                               ;   in Loop: Header=BB5_49 Depth=1
Lloh23:
	adrp	x8, _rc_pending_count@PAGE
Lloh24:
	ldr	x22, [x8, _rc_pending_count@PAGEOFF]
	cbnz	x22, LBB5_49
LBB5_77:
	cbz	x19, LBB5_79
; %bb.78:
	mov	w8, #1                          ; =0x1
	adrp	x9, _rc_bounded_next_queue@PAGE
	str	w8, [x9, _rc_bounded_next_queue@PAGEOFF]
LBB5_79:
	adrp	x8, _rc_bounded_last_work@PAGE
	str	x19, [x8, _rc_bounded_last_work@PAGEOFF]
	mov	x0, x19
	ldp	x29, x30, [sp, #80]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp, #64]             ; 16-byte Folded Reload
	ldp	x22, x21, [sp, #48]             ; 16-byte Folded Reload
	ldp	x24, x23, [sp, #32]             ; 16-byte Folded Reload
	ldp	x26, x25, [sp, #16]             ; 16-byte Folded Reload
	ldp	x28, x27, [sp], #96             ; 16-byte Folded Reload
	ret
	.loh AdrpLdr	Lloh9, Lloh10
	.loh AdrpLdr	Lloh11, Lloh12
	.loh AdrpLdr	Lloh13, Lloh14
	.loh AdrpLdr	Lloh15, Lloh16
	.loh AdrpLdr	Lloh17, Lloh18
	.loh AdrpLdr	Lloh19, Lloh20
	.loh AdrpAdrp	Lloh21, Lloh22
	.loh AdrpLdr	Lloh23, Lloh24
	.cfi_endproc
                                        ; -- End function
	.p2align	2                               ; -- Begin function rc_bounded_finish_object
_rc_bounded_finish_object:              ; @rc_bounded_finish_object
	.cfi_startproc
; %bb.0:
	stp	x22, x21, [sp, #-48]!           ; 16-byte Folded Spill
	stp	x20, x19, [sp, #16]             ; 16-byte Folded Spill
	stp	x29, x30, [sp, #32]             ; 16-byte Folded Spill
	add	x29, sp, #32
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
	.cfi_offset w19, -24
	.cfi_offset w20, -32
	.cfi_offset w21, -40
	.cfi_offset w22, -48
	sub	w8, w1, #2
	cmp	w8, #2
	ccmp	w1, #6, #4, hs
	adrp	x20, _rc_bytes@PAGE
	adrp	x19, _rc_heap_allocation_count@PAGE
	b.ne	LBB6_4
; %bb.1:
	ldr	x8, [x0, #8]
	ldr	x21, [x20, _rc_bytes@PAGEOFF]
	cbz	x8, LBB6_3
; %bb.2:
	ldr	x9, [x8, #-8]!
	sub	x9, x21, x9
	sub	x21, x9, #8
	ldr	x9, [x19, _rc_heap_allocation_count@PAGEOFF]
	sub	x9, x9, #1
	str	x9, [x19, _rc_heap_allocation_count@PAGEOFF]
	mov	x22, x0
	mov	x0, x8
	bl	_free
	mov	x0, x22
LBB6_3:
	sub	x8, x21, #32
	b	LBB6_13
LBB6_4:
	cmp	w1, #1
	b.ne	LBB6_7
; %bb.5:
	ldr	x8, [x0, #40]
	cbz	x8, LBB6_8
; %bb.6:
	ldr	x21, [x20, _rc_bytes@PAGEOFF]
	b	LBB6_10
LBB6_7:
	ldr	x8, [x0, #8]
	cmp	w1, #4
	mov	x9, #-9                         ; =0xfffffffffffffff7
	cinc	x9, x9, ne
	ldr	x10, [x20, _rc_bytes@PAGEOFF]
	madd	x8, x8, x9, x10
	sub	x8, x8, #16
	b	LBB6_13
LBB6_8:
	ldr	x8, [x0, #8]
	ldr	x21, [x20, _rc_bytes@PAGEOFF]
	cbz	x8, LBB6_10
; %bb.9:
	ldr	x9, [x8, #-8]!
	sub	x9, x21, x9
	sub	x21, x9, #8
	ldr	x9, [x19, _rc_heap_allocation_count@PAGEOFF]
	sub	x9, x9, #1
	str	x9, [x19, _rc_heap_allocation_count@PAGEOFF]
	mov	x22, x0
	mov	x0, x8
	bl	_free
	mov	x0, x22
LBB6_10:
	ldr	x8, [x0, #32]
	cbz	x8, LBB6_12
; %bb.11:
	ldr	x9, [x8, #-8]!
	sub	x9, x21, x9
	sub	x21, x9, #8
	ldr	x9, [x19, _rc_heap_allocation_count@PAGEOFF]
	sub	x9, x9, #1
	str	x9, [x19, _rc_heap_allocation_count@PAGEOFF]
	mov	x22, x0
	mov	x0, x8
	bl	_free
	mov	x0, x22
LBB6_12:
	sub	x8, x21, #48
LBB6_13:
	str	x8, [x20, _rc_bytes@PAGEOFF]
	ldr	x8, [x19, _rc_heap_allocation_count@PAGEOFF]
	sub	x8, x8, #1
	str	x8, [x19, _rc_heap_allocation_count@PAGEOFF]
	bl	_free
	adrp	x8, _rc_object_count@PAGE
	ldr	x9, [x8, _rc_object_count@PAGEOFF]
	sub	x9, x9, #1
	str	x9, [x8, _rc_object_count@PAGEOFF]
	ldp	x29, x30, [sp, #32]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp, #16]             ; 16-byte Folded Reload
	ldp	x22, x21, [sp], #48             ; 16-byte Folded Reload
	ret
	.cfi_endproc
                                        ; -- End function
	.p2align	2                               ; -- Begin function rc_drop
_rc_drop:                               ; @rc_drop
	.cfi_startproc
; %bb.0:
	cbz	x0, LBB7_26
; %bb.1:
	stp	x26, x25, [sp, #-80]!           ; 16-byte Folded Spill
	stp	x24, x23, [sp, #16]             ; 16-byte Folded Spill
	stp	x22, x21, [sp, #32]             ; 16-byte Folded Spill
	stp	x20, x19, [sp, #48]             ; 16-byte Folded Spill
	stp	x29, x30, [sp, #64]             ; 16-byte Folded Spill
	add	x29, sp, #64
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
	.cfi_offset w19, -24
	.cfi_offset w20, -32
	.cfi_offset w21, -40
	.cfi_offset w22, -48
	.cfi_offset w23, -56
	.cfi_offset w24, -64
	.cfi_offset w25, -72
	.cfi_offset w26, -80
	mov	x20, x0
	ldr	x8, [x0, #-8]!
	cmp	x8, #13
	b.ne	LBB7_4
; %bb.2:
	ldr	x8, [x20]
	adrp	x9, _rc_bytes@PAGE
	ldr	x10, [x9, _rc_bytes@PAGEOFF]
	sub	x8, x10, x8, lsl #3
	sub	x8, x8, #16
	str	x8, [x9, _rc_bytes@PAGEOFF]
	adrp	x8, _rc_heap_allocation_count@PAGE
	ldr	x9, [x8, _rc_heap_allocation_count@PAGEOFF]
	sub	x9, x9, #1
	str	x9, [x8, _rc_heap_allocation_count@PAGEOFF]
	bl	_free
	adrp	x8, _rc_object_count@PAGE
	ldr	x9, [x8, _rc_object_count@PAGEOFF]
	sub	x9, x9, #1
	str	x9, [x8, _rc_object_count@PAGEOFF]
LBB7_3:
	mov	w0, #1                          ; =0x1
	b	LBB7_25
LBB7_4:
	subs	x9, x8, #8
	b.lo	LBB7_24
; %bb.5:
	str	x9, [x0]
	cmp	x9, #7
	b.hi	LBB7_24
; %bb.6:
	and	w1, w8, #0x7
	cmp	w1, #1
	b.ne	LBB7_9
; %bb.7:
	ldr	x19, [x20, #32]
	adrp	x22, _rc_bytes@PAGE
	adrp	x21, _rc_heap_allocation_count@PAGE
	cbz	x19, LBB7_14
; %bb.8:
	ldr	x24, [x22, _rc_bytes@PAGEOFF]
	ldr	x23, [x21, _rc_heap_allocation_count@PAGEOFF]
	b	LBB7_16
LBB7_9:
	and	w8, w8, #0x3
	cmp	w8, #2
	b.ne	LBB7_11
LBB7_10:
	bl	_rc_bounded_finish_object
	b	LBB7_3
LBB7_11:
	cmp	w1, #4
	b.eq	LBB7_22
; %bb.12:
	cmp	w1, #3
	b.ne	LBB7_23
; %bb.13:
	ldr	x8, [x20, #8]
	cbnz	x8, LBB7_23
	b	LBB7_10
LBB7_14:
	ldr	x8, [x20]
	ldr	x24, [x22, _rc_bytes@PAGEOFF]
	ldr	x23, [x21, _rc_heap_allocation_count@PAGEOFF]
	cbz	x8, LBB7_16
; %bb.15:
	ldr	x9, [x8, #-8]!
	sub	x9, x24, x9
	sub	x24, x9, #8
	sub	x23, x23, #1
	mov	x25, x0
	mov	x0, x8
	bl	_free
	mov	x0, x25
LBB7_16:
	ldr	x8, [x20, #24]
	cbz	x8, LBB7_18
; %bb.17:
	ldr	x9, [x8, #-8]!
	sub	x9, x24, x9
	sub	x24, x9, #8
	sub	x23, x23, #1
	mov	x20, x0
	mov	x0, x8
	bl	_free
	mov	x0, x20
LBB7_18:
	sub	x8, x24, #48
	str	x8, [x22, _rc_bytes@PAGEOFF]
	sub	x8, x23, #1
	str	x8, [x21, _rc_heap_allocation_count@PAGEOFF]
	bl	_free
	adrp	x8, _rc_object_count@PAGE
	ldr	x9, [x8, _rc_object_count@PAGEOFF]
	sub	x9, x9, #1
	str	x9, [x8, _rc_object_count@PAGEOFF]
	cbz	x19, LBB7_3
; %bb.19:
	ldr	x8, [x19, #-8]!
	subs	x8, x8, #8
	b.lo	LBB7_3
; %bb.20:
	str	x8, [x19]
	cmp	x8, #7
	b.hi	LBB7_3
; %bb.21:
	mov	x0, x19
	bl	_rc_bounded_enqueue
	b	LBB7_3
LBB7_22:
	ldr	x8, [x20]
	cbz	x8, LBB7_10
LBB7_23:
	bl	_rc_bounded_enqueue
LBB7_24:
	mov	w0, #0                          ; =0x0
LBB7_25:
	ldp	x29, x30, [sp, #64]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp, #48]             ; 16-byte Folded Reload
	ldp	x22, x21, [sp, #32]             ; 16-byte Folded Reload
	ldp	x24, x23, [sp, #16]             ; 16-byte Folded Reload
	ldp	x26, x25, [sp], #80             ; 16-byte Folded Reload
LBB7_26:
	ret
	.cfi_endproc
                                        ; -- End function
	.p2align	2                               ; -- Begin function rc_bounded_object_unit
_rc_bounded_object_unit:                ; @rc_bounded_object_unit
	.cfi_startproc
; %bb.0:
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
Lloh25:
	adrp	x8, _rc_bounded_active@PAGE
Lloh26:
	ldr	x9, [x8, _rc_bounded_active@PAGEOFF]
	adrp	x11, _rc_bounded_head@PAGE
	ldr	x10, [x11, _rc_bounded_head@PAGEOFF]
Lloh27:
	adrp	x8, _rc_bounded_recent_head@PAGE
	ldr	x0, [x8, _rc_bounded_recent_head@PAGEOFF]
	orr	x12, x9, x10
	cbz	x12, LBB8_8
; %bb.1:
	adrp	x11, _rc_bounded_recent_turn@PAGE
	ldr	w12, [x11, _rc_bounded_recent_turn@PAGEOFF]
	eor	w13, w12, #0x1
	str	w13, [x11, _rc_bounded_recent_turn@PAGEOFF]
	cmp	w12, #0
	ccmp	x0, #0, #4, ne
	b.eq	LBB8_9
; %bb.2:
	cmp	x9, #0
	ccmp	x10, #0, #0, ne
	b.ne	LBB8_5
; %bb.3:
	ldr	x10, [x9]
	and	x10, x10, #0x7
	cmp	x10, #4
	b.ne	LBB8_5
; %bb.4:
	ldr	x9, [x9, #8]
Lloh28:
	adrp	x10, _rc_bounded_cursor@PAGE
Lloh29:
	ldr	x10, [x10, _rc_bounded_cursor@PAGEOFF]
	cmp	x9, #1
	ccmp	x10, #1, #0, eq
	b.eq	LBB8_9
LBB8_5:
	ldr	x11, [x0]
	and	w1, w11, #0x7
	and	x9, x11, #0x7
	cmp	x9, #1
	b.eq	LBB8_21
; %bb.6:
	cmp	x9, #3
	b.ne	LBB8_10
; %bb.7:
	ldr	x10, [x0, #24]
	cmp	w1, #4
	b.ne	LBB8_14
	b	LBB8_22
LBB8_8:
	str	x0, [x11, _rc_bounded_head@PAGEOFF]
	adrp	x9, _rc_bounded_recent_tail@PAGE
	ldr	x10, [x9, _rc_bounded_recent_tail@PAGEOFF]
	adrp	x11, _rc_bounded_tail@PAGE
	str	x10, [x11, _rc_bounded_tail@PAGEOFF]
	str	xzr, [x9, _rc_bounded_recent_tail@PAGEOFF]
	str	xzr, [x8, _rc_bounded_recent_head@PAGEOFF]
	adrp	x8, _rc_bounded_recent_turn@PAGE
	ldr	w9, [x8, _rc_bounded_recent_turn@PAGEOFF]
	eor	w9, w9, #0x1
	str	w9, [x8, _rc_bounded_recent_turn@PAGEOFF]
LBB8_9:
	ldp	x29, x30, [sp], #16             ; 16-byte Folded Reload
	b	_rc_bounded_old_object_unit
LBB8_10:
	ldr	x14, [x0, #8]
	cbz	x14, LBB8_21
; %bb.11:
	mov	x12, #0                         ; =0x0
	mov	x10, #0                         ; =0x0
	add	x13, x0, x14, lsl #3
	add	x13, x13, #16
	sub	x14, x14, #1
	mov	w15, #9                         ; =0x9
	cmp	x14, #9
	csel	x14, x14, x15, lo
	lsl	x15, x14, #3
	sub	x14, x15, x14
	add	x14, x14, #7
LBB8_12:                                ; =>This Inner Loop Header: Depth=1
	ldrb	w15, [x13], #1
	lsr	x15, x15, #1
	lsl	x15, x15, x12
	orr	x10, x15, x10
	add	x12, x12, #7
	cmp	x14, x12
	b.ne	LBB8_12
; %bb.13:
	cmp	w1, #4
	b.eq	LBB8_22
LBB8_14:
	cmp	w1, #3
	b.ne	LBB8_25
; %bb.15:
	mov	x12, x0
	ldr	x13, [x12, #16]!
	cmp	x10, x13
	b.hs	LBB8_25
; %bb.16:
	ldr	x11, [x0, #8]
	ldr	x8, [x11, x10, lsl #3]
	cmp	x9, #1
	b.eq	LBB8_32
; %bb.17:
	add	x10, x10, #1
	cmp	x9, #3
	b.eq	LBB8_31
; %bb.18:
	mov	x9, #0                          ; =0x0
	add	x11, x12, x11, lsl #3
LBB8_19:                                ; =>This Inner Loop Header: Depth=1
	ldrb	w12, [x11, x9]
	bfi	w12, w10, #1, #31
	strb	w12, [x11, x9]
	cmp	x9, #8
	b.hi	LBB8_32
; %bb.20:                               ;   in Loop: Header=BB8_19 Depth=1
	lsr	x10, x10, #7
	add	x9, x9, #1
	ldr	x12, [x0, #8]
	cmp	x9, x12
	b.lo	LBB8_19
	b	LBB8_32
LBB8_21:
	mov	x10, #0                         ; =0x0
	cmp	w1, #4
	b.ne	LBB8_14
LBB8_22:
	ldr	x12, [x0, #8]
	cmp	x10, x12
	b.hs	LBB8_25
; %bb.23:
	add	x8, x0, #16
	add	x11, x8, x12, lsl #3
	ldrb	w12, [x11, x10]
	tbnz	w12, #0, LBB8_28
; %bb.24:
	mov	x8, #0                          ; =0x0
	b	LBB8_29
LBB8_25:
	ands	x9, x11, #0xfffffffffffffff8
	str	x9, [x8, _rc_bounded_recent_head@PAGEOFF]
	b.ne	LBB8_27
; %bb.26:
	adrp	x8, _rc_bounded_recent_tail@PAGE
	str	xzr, [x8, _rc_bounded_recent_tail@PAGEOFF]
LBB8_27:
	bl	_rc_bounded_finish_object
	adrp	x8, _rc_pending_count@PAGE
	ldr	x9, [x8, _rc_pending_count@PAGEOFF]
	sub	x9, x9, #1
	str	x9, [x8, _rc_pending_count@PAGEOFF]
	ldp	x29, x30, [sp], #16             ; 16-byte Folded Reload
	ret
LBB8_28:
	ldr	x8, [x8, x10, lsl #3]
LBB8_29:
	cmp	x9, #1
	b.eq	LBB8_32
; %bb.30:
	add	x10, x10, #1
	cmp	x9, #3
	b.ne	LBB8_33
LBB8_31:
	str	x10, [x0, #24]
LBB8_32:
	mov	x0, x8
	ldp	x29, x30, [sp], #16             ; 16-byte Folded Reload
	b	_rc_drop
LBB8_33:
	mov	x9, #0                          ; =0x0
LBB8_34:                                ; =>This Inner Loop Header: Depth=1
	ldrb	w12, [x11, x9]
	bfi	w12, w10, #1, #31
	strb	w12, [x11, x9]
	cmp	x9, #8
	b.hi	LBB8_32
; %bb.35:                               ;   in Loop: Header=BB8_34 Depth=1
	lsr	x10, x10, #7
	add	x9, x9, #1
	ldr	x12, [x0, #8]
	cmp	x9, x12
	b.lo	LBB8_34
	b	LBB8_32
	.loh AdrpAdrp	Lloh25, Lloh27
	.loh AdrpLdr	Lloh25, Lloh26
	.loh AdrpLdr	Lloh28, Lloh29
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_rc_release              ; -- Begin function minyar_rc_release
	.p2align	2
_minyar_rc_release:                     ; @minyar_rc_release
	.cfi_startproc
; %bb.0:
	stp	x20, x19, [sp, #-32]!           ; 16-byte Folded Spill
	stp	x29, x30, [sp, #16]             ; 16-byte Folded Spill
	add	x29, sp, #16
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
	.cfi_offset w19, -24
	.cfi_offset w20, -32
	bl	_rc_drop
	mov	x19, x0
Lloh30:
	adrp	x8, _rc_pending_count@PAGE
Lloh31:
	ldr	x8, [x8, _rc_pending_count@PAGEOFF]
	adrp	x20, _rc_bounded_last_work@PAGE
	cbz	x8, LBB9_2
; %bb.1:
	mov	w8, #32                         ; =0x20
	sub	w0, w8, w19
	bl	_minyar_rc_poll
	ldr	x8, [x20, _rc_bounded_last_work@PAGEOFF]
LBB9_2:
	add	x8, x8, w19, uxtw
	str	x8, [x20, _rc_bounded_last_work@PAGEOFF]
	ldp	x29, x30, [sp, #16]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp], #32             ; 16-byte Folded Reload
	ret
	.loh AdrpLdr	Lloh30, Lloh31
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_rc_enter                ; -- Begin function minyar_rc_enter
	.p2align	2
_minyar_rc_enter:                       ; @minyar_rc_enter
	.cfi_startproc
; %bb.0:
	stp	x20, x19, [sp, #-32]!           ; 16-byte Folded Spill
	stp	x29, x30, [sp, #16]             ; 16-byte Folded Spill
	add	x29, sp, #16
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
	.cfi_offset w19, -24
	.cfi_offset w20, -32
	mov	x19, x0
	mov	w0, #32                         ; =0x20
	bl	_minyar_rc_poll
	adrp	x8, _rc_free_frames@PAGE
	ldr	x20, [x8, _rc_free_frames@PAGEOFF]
	cbz	x20, LBB10_3
; %bb.1:
	ldp	x9, x10, [x20]
	str	x9, [x8, _rc_free_frames@PAGEOFF]
	adrp	x8, _rc_bounded_cached_frame_bytes@PAGE
	ldr	x9, [x8, _rc_bounded_cached_frame_bytes@PAGEOFF]
	sub	x9, x9, #64
	str	x9, [x8, _rc_bounded_cached_frame_bytes@PAGEOFF]
	cbz	x10, LBB10_5
; %bb.2:
	ldr	x10, [x20, #24]
	sub	x9, x9, x10, lsl #4
	str	x9, [x8, _rc_bounded_cached_frame_bytes@PAGEOFF]
	b	LBB10_5
LBB10_3:
	mov	w0, #1                          ; =0x1
	mov	w1, #64                         ; =0x40
	bl	_calloc
	cbz	x0, LBB10_16
; %bb.4:
	mov	x20, x0
	adrp	x8, _rc_heap_allocation_count@PAGE
	ldr	x9, [x8, _rc_heap_allocation_count@PAGEOFF]
	add	x9, x9, #1
	str	x9, [x8, _rc_heap_allocation_count@PAGEOFF]
LBB10_5:
	lsr	x8, x19, #60
	cbnz	x8, LBB10_16
; %bb.6:
	ldr	x8, [x20, #24]
	cmp	x8, x19
	b.hs	LBB10_9
; %bb.7:
	ldr	x0, [x20, #8]
	lsl	x1, x19, #4
	cbz	x0, LBB10_11
; %bb.8:
	bl	_realloc
	cbnz	x0, LBB10_13
	b	LBB10_16
LBB10_9:
	cbz	x19, LBB10_15
; %bb.10:
	ldr	x0, [x20, #8]
	b	LBB10_14
LBB10_11:
	mov	x0, x1
	bl	_malloc
	cbz	x0, LBB10_16
; %bb.12:
	adrp	x8, _rc_heap_allocation_count@PAGE
	ldr	x9, [x8, _rc_heap_allocation_count@PAGEOFF]
	add	x9, x9, #1
	str	x9, [x8, _rc_heap_allocation_count@PAGEOFF]
LBB10_13:
	str	x0, [x20, #8]
	str	x19, [x20, #24]
LBB10_14:
	lsl	x1, x19, #3
	bl	_bzero
LBB10_15:
	str	x19, [x20, #16]
	stp	xzr, xzr, [x20, #48]
	adrp	x8, _rc_frames@PAGE
	ldr	x9, [x8, _rc_frames@PAGEOFF]
	str	x9, [x20]
	str	x20, [x8, _rc_frames@PAGEOFF]
	ldp	x29, x30, [sp, #16]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp], #32             ; 16-byte Folded Reload
	ret
LBB10_16:
	bl	_out_of_memory
	.cfi_endproc
                                        ; -- End function
	.p2align	2                               ; -- Begin function out_of_memory
_out_of_memory:                         ; @out_of_memory
	.cfi_startproc
; %bb.0:
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
Lloh32:
	adrp	x0, l_.str.48@PAGE
Lloh33:
	add	x0, x0, l_.str.48@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh32, Lloh33
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_rc_leave                ; -- Begin function minyar_rc_leave
	.p2align	2
_minyar_rc_leave:                       ; @minyar_rc_leave
	.cfi_startproc
; %bb.0:
Lloh34:
	adrp	x9, _rc_frames@PAGE
	ldr	x8, [x9, _rc_frames@PAGEOFF]
	ldr	x10, [x8]
	str	x10, [x9, _rc_frames@PAGEOFF]
	mov	x10, x8
	ldr	x11, [x10, #32]!
Lloh35:
	adrp	x9, _rc_pending_count@PAGE
	cbz	x11, LBB12_2
; %bb.1:
	adrp	x12, _rc_bounded_chunk_tail@PAGE
	ldr	x13, [x12, _rc_bounded_chunk_tail@PAGEOFF]
Lloh36:
	adrp	x14, _rc_bounded_chunk_head@PAGE
Lloh37:
	add	x14, x14, _rc_bounded_chunk_head@PAGEOFF
	cmp	x13, #0
	csel	x13, x14, x13, eq
	str	x11, [x13]
	ldp	x11, x13, [x8, #40]
	str	x11, [x12, _rc_bounded_chunk_tail@PAGEOFF]
	tst	x13, #0x7
	ldr	x11, [x9, _rc_pending_count@PAGEOFF]
	add	x11, x11, x13, lsr #3
	cinc	x11, x11, ne
	str	x11, [x9, _rc_pending_count@PAGEOFF]
	stp	xzr, xzr, [x10, #8]
	str	xzr, [x10]
LBB12_2:
	ldr	x10, [x8, #56]
	str	x10, [x8, #16]
	str	xzr, [x8]
	adrp	x10, _rc_bounded_frame_tail@PAGE
	ldr	x11, [x10, _rc_bounded_frame_tail@PAGEOFF]
Lloh38:
	adrp	x12, _rc_bounded_frame_head@PAGE
Lloh39:
	add	x12, x12, _rc_bounded_frame_head@PAGEOFF
	cmp	x11, #0
	csel	x11, x12, x11, eq
	str	x8, [x11]
	str	x8, [x10, _rc_bounded_frame_tail@PAGEOFF]
	ldr	x8, [x9, _rc_pending_count@PAGEOFF]
	add	x8, x8, #1
	str	x8, [x9, _rc_pending_count@PAGEOFF]
	mov	w0, #32                         ; =0x20
	b	_minyar_rc_poll
	.loh AdrpAdrp	Lloh34, Lloh35
	.loh AdrpAdd	Lloh36, Lloh37
	.loh AdrpAdd	Lloh38, Lloh39
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_rc_keep                 ; -- Begin function minyar_rc_keep
	.p2align	2
_minyar_rc_keep:                        ; @minyar_rc_keep
	.cfi_startproc
; %bb.0:
	stp	x22, x21, [sp, #-48]!           ; 16-byte Folded Spill
	stp	x20, x19, [sp, #16]             ; 16-byte Folded Spill
	stp	x29, x30, [sp, #32]             ; 16-byte Folded Spill
	add	x29, sp, #32
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
	.cfi_offset w19, -24
	.cfi_offset w20, -32
	.cfi_offset w21, -40
	.cfi_offset w22, -48
	cbz	x0, LBB13_12
; %bb.1:
	mov	x8, x0
	ldur	x9, [x0, #-8]
	cmp	x9, #8
	b.lo	LBB13_12
; %bb.2:
Lloh40:
	adrp	x9, _rc_frames@PAGE
Lloh41:
	ldr	x19, [x9, _rc_frames@PAGEOFF]
	ldr	x0, [x19, #40]
	adrp	x20, _rc_pending_count@PAGE
	cbz	x0, LBB13_4
; %bb.3:
	ldr	x9, [x0, #8]
	cmp	x9, #8
	b.ne	LBB13_9
LBB13_4:
	ldr	x9, [x20, _rc_pending_count@PAGEOFF]
	cbz	x9, LBB13_6
; %bb.5:
	mov	x21, x8
	mov	w0, #32                         ; =0x20
	bl	_minyar_rc_poll
	b	LBB13_7
LBB13_6:
	mov	x21, x8
	adrp	x8, _rc_bounded_last_work@PAGE
	str	xzr, [x8, _rc_bounded_last_work@PAGEOFF]
LBB13_7:
	mov	w0, #80                         ; =0x50
	bl	_malloc
	cbz	x0, LBB13_13
; %bb.8:
	mov	x9, #0                          ; =0x0
	adrp	x8, _rc_heap_allocation_count@PAGE
	ldr	x10, [x8, _rc_heap_allocation_count@PAGEOFF]
	add	x10, x10, #1
	str	x10, [x8, _rc_heap_allocation_count@PAGEOFF]
	stp	xzr, xzr, [x0]
	ldr	x8, [x19, #40]
	add	x10, x19, #32
	cmp	x8, #0
	csel	x8, x10, x8, eq
	str	x0, [x8]
	str	x0, [x19, #40]
	mov	x8, x21
LBB13_9:
	add	x10, x0, x9, lsl #3
	add	x9, x9, #1
	str	x9, [x0, #8]
	str	x8, [x10, #16]
	ldr	x8, [x19, #48]
	add	x8, x8, #1
	str	x8, [x19, #48]
	ldr	x8, [x20, _rc_pending_count@PAGEOFF]
	cbz	x8, LBB13_11
; %bb.10:
	mov	w0, #32                         ; =0x20
	ldp	x29, x30, [sp, #32]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp, #16]             ; 16-byte Folded Reload
	ldp	x22, x21, [sp], #48             ; 16-byte Folded Reload
	b	_minyar_rc_poll
LBB13_11:
	adrp	x8, _rc_bounded_last_work@PAGE
	str	xzr, [x8, _rc_bounded_last_work@PAGEOFF]
LBB13_12:
	ldp	x29, x30, [sp, #32]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp, #16]             ; 16-byte Folded Reload
	ldp	x22, x21, [sp], #48             ; 16-byte Folded Reload
	ret
LBB13_13:
	bl	_out_of_memory
	.loh AdrpLdr	Lloh40, Lloh41
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_rc_local_take           ; -- Begin function minyar_rc_local_take
	.p2align	2
_minyar_rc_local_take:                  ; @minyar_rc_local_take
	.cfi_startproc
; %bb.0:
Lloh42:
	adrp	x8, _rc_frames@PAGE
Lloh43:
	ldr	x10, [x8, _rc_frames@PAGEOFF]
	ldr	x9, [x10, #8]
	ldr	x8, [x9, x0, lsl #3]
	cbz	x1, LBB14_4
; %bb.1:
	tbnz	w8, #0, LBB14_4
; %bb.2:
	ldr	x11, [x10, #24]
	add	x11, x9, x11, lsl #3
	ldr	x12, [x10, #56]
	add	x13, x12, #1
	str	x13, [x10, #56]
	str	x0, [x11, x12, lsl #3]
LBB14_3:
	orr	x10, x1, #0x1
	str	x10, [x9, x0, lsl #3]
	b	LBB14_6
LBB14_4:
	tbnz	w8, #0, LBB14_3
; %bb.5:
	cbnz	x1, LBB14_3
LBB14_6:
	stp	x20, x19, [sp, #-32]!           ; 16-byte Folded Spill
	stp	x29, x30, [sp, #16]             ; 16-byte Folded Spill
	add	x29, sp, #16
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
	.cfi_offset w19, -24
	.cfi_offset w20, -32
	and	x0, x8, #0xfffffffffffffffe
	bl	_rc_drop
	mov	x19, x0
Lloh44:
	adrp	x8, _rc_pending_count@PAGE
Lloh45:
	ldr	x8, [x8, _rc_pending_count@PAGEOFF]
	adrp	x20, _rc_bounded_last_work@PAGE
	cbz	x8, LBB14_8
; %bb.7:
	mov	w8, #32                         ; =0x20
	sub	w0, w8, w19
	bl	_minyar_rc_poll
	ldr	x8, [x20, _rc_bounded_last_work@PAGEOFF]
LBB14_8:
	add	x8, x8, w19, uxtw
	str	x8, [x20, _rc_bounded_last_work@PAGEOFF]
	ldp	x29, x30, [sp, #16]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp], #32             ; 16-byte Folded Reload
	ret
	.loh AdrpLdr	Lloh42, Lloh43
	.loh AdrpLdr	Lloh44, Lloh45
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_rc_local_move           ; -- Begin function minyar_rc_local_move
	.p2align	2
_minyar_rc_local_move:                  ; @minyar_rc_local_move
	.cfi_startproc
; %bb.0:
Lloh46:
	adrp	x8, _rc_frames@PAGE
Lloh47:
	ldr	x8, [x8, _rc_frames@PAGEOFF]
	ldr	x8, [x8, #8]
	ldr	x9, [x8, x0, lsl #3]
	and	x9, x9, #0x1
	str	x9, [x8, x0, lsl #3]
	ret
	.loh AdrpLdr	Lloh46, Lloh47
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_rc_local                ; -- Begin function minyar_rc_local
	.p2align	2
_minyar_rc_local:                       ; @minyar_rc_local
	.cfi_startproc
; %bb.0:
	stp	x20, x19, [sp, #-32]!           ; 16-byte Folded Spill
	stp	x29, x30, [sp, #16]             ; 16-byte Folded Spill
	add	x29, sp, #16
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
	.cfi_offset w19, -24
	.cfi_offset w20, -32
	cbz	x1, LBB16_4
; %bb.1:
	ldur	x8, [x1, #-8]
	cmp	x8, #8
	b.lo	LBB16_4
; %bb.2:
	cmn	x8, #8
	b.hs	LBB16_13
; %bb.3:
	add	x8, x8, #8
	stur	x8, [x1, #-8]
LBB16_4:
Lloh48:
	adrp	x8, _rc_frames@PAGE
Lloh49:
	ldr	x10, [x8, _rc_frames@PAGEOFF]
	ldr	x9, [x10, #8]
	ldr	x8, [x9, x0, lsl #3]
	cbz	x1, LBB16_8
; %bb.5:
	tbnz	w8, #0, LBB16_8
; %bb.6:
	ldr	x11, [x10, #24]
	add	x11, x9, x11, lsl #3
	ldr	x12, [x10, #56]
	add	x13, x12, #1
	str	x13, [x10, #56]
	str	x0, [x11, x12, lsl #3]
LBB16_7:
	orr	x10, x1, #0x1
	str	x10, [x9, x0, lsl #3]
	b	LBB16_10
LBB16_8:
	tbnz	w8, #0, LBB16_7
; %bb.9:
	cbnz	x1, LBB16_7
LBB16_10:
	and	x0, x8, #0xfffffffffffffffe
	bl	_rc_drop
	mov	x19, x0
Lloh50:
	adrp	x8, _rc_pending_count@PAGE
Lloh51:
	ldr	x8, [x8, _rc_pending_count@PAGEOFF]
	adrp	x20, _rc_bounded_last_work@PAGE
	cbz	x8, LBB16_12
; %bb.11:
	mov	w8, #32                         ; =0x20
	sub	w0, w8, w19
	bl	_minyar_rc_poll
	ldr	x8, [x20, _rc_bounded_last_work@PAGEOFF]
LBB16_12:
	add	x8, x8, w19, uxtw
	str	x8, [x20, _rc_bounded_last_work@PAGEOFF]
	ldp	x29, x30, [sp, #16]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp], #32             ; 16-byte Folded Reload
	ret
LBB16_13:
	bl	_minyar_rc_local.cold.1
	.loh AdrpLdr	Lloh48, Lloh49
	.loh AdrpLdr	Lloh50, Lloh51
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_rc_borrow               ; -- Begin function minyar_rc_borrow
	.p2align	2
_minyar_rc_borrow:                      ; @minyar_rc_borrow
	.cfi_startproc
; %bb.0:
	cbz	x0, LBB17_4
; %bb.1:
	ldur	x8, [x0, #-8]
	cmp	x8, #8
	b.lo	LBB17_4
; %bb.2:
	cmn	x8, #8
	b.hs	LBB17_5
; %bb.3:
	add	x8, x8, #8
	stur	x8, [x0, #-8]
LBB17_4:
	b	_minyar_rc_keep
LBB17_5:
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
	bl	_minyar_rc_borrow.cold.1
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_rc_step                 ; -- Begin function minyar_rc_step
	.p2align	2
_minyar_rc_step:                        ; @minyar_rc_step
	.cfi_startproc
; %bb.0:
Lloh52:
	adrp	x8, _rc_frames@PAGE
Lloh53:
	ldr	x9, [x8, _rc_frames@PAGEOFF]
	mov	x8, x9
	ldr	x10, [x8, #32]!
	cbz	x10, LBB18_2
; %bb.1:
	adrp	x11, _rc_bounded_chunk_tail@PAGE
	ldr	x12, [x11, _rc_bounded_chunk_tail@PAGEOFF]
Lloh54:
	adrp	x13, _rc_bounded_chunk_head@PAGE
Lloh55:
	add	x13, x13, _rc_bounded_chunk_head@PAGEOFF
	cmp	x12, #0
	csel	x12, x13, x12, eq
	str	x10, [x12]
	ldp	x10, x9, [x9, #40]
	str	x10, [x11, _rc_bounded_chunk_tail@PAGEOFF]
	tst	x9, #0x7
	adrp	x10, _rc_pending_count@PAGE
	ldr	x11, [x10, _rc_pending_count@PAGEOFF]
	add	x9, x11, x9, lsr #3
	cinc	x9, x9, ne
	str	x9, [x10, _rc_pending_count@PAGEOFF]
	stp	xzr, xzr, [x8, #8]
	str	xzr, [x8]
LBB18_2:
	mov	w0, #32                         ; =0x20
	b	_minyar_rc_poll
	.loh AdrpLdr	Lloh52, Lloh53
	.loh AdrpAdd	Lloh54, Lloh55
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_exit                    ; -- Begin function minyar_exit
	.p2align	2
_minyar_exit:                           ; @minyar_exit
	.cfi_startproc
; %bb.0:
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
                                        ; kill: def $w0 killed $w0 killed $x0
	bl	_exit
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_list_new                ; -- Begin function minyar_list_new
	.p2align	2
_minyar_list_new:                       ; @minyar_list_new
	.cfi_startproc
; %bb.0:
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
Lloh56:
	adrp	x8, _rc_pending_count@PAGE
Lloh57:
	ldr	x8, [x8, _rc_pending_count@PAGEOFF]
	cbz	x8, LBB20_2
; %bb.1:
	mov	w0, #32                         ; =0x20
	bl	_minyar_rc_poll
	b	LBB20_3
LBB20_2:
	adrp	x8, _rc_bounded_last_work@PAGE
	str	xzr, [x8, _rc_bounded_last_work@PAGEOFF]
LBB20_3:
	mov	w0, #32                         ; =0x20
	bl	_malloc
	cbz	x0, LBB20_5
; %bb.4:
	adrp	x8, _rc_heap_allocation_count@PAGE
	ldr	x9, [x8, _rc_heap_allocation_count@PAGEOFF]
	add	x9, x9, #1
	str	x9, [x8, _rc_heap_allocation_count@PAGEOFF]
	mov	w8, #10                         ; =0xa
	str	x8, [x0]
Lloh58:
	adrp	x8, _rc_object_count@PAGE
	ldr	x9, [x8, _rc_object_count@PAGEOFF]
	add	x9, x9, #1
	str	x9, [x8, _rc_object_count@PAGEOFF]
Lloh59:
	adrp	x8, _rc_bytes@PAGE
	ldr	x9, [x8, _rc_bytes@PAGEOFF]
	add	x9, x9, #32
	str	x9, [x8, _rc_bytes@PAGEOFF]
	stp	xzr, xzr, [x0, #16]
	str	xzr, [x0, #8]!
	ldp	x29, x30, [sp], #16             ; 16-byte Folded Reload
	ret
LBB20_5:
	bl	_out_of_memory
	.loh AdrpLdr	Lloh56, Lloh57
	.loh AdrpAdrp	Lloh58, Lloh59
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_list_references         ; -- Begin function minyar_list_references
	.p2align	2
_minyar_list_references:                ; @minyar_list_references
	.cfi_startproc
; %bb.0:
	ldur	x8, [x0, #-8]
	and	w9, w8, #0x7
	cmp	w9, #3
	ccmp	w9, #6, #4, ne
	b.ne	LBB21_2
; %bb.1:
	ret
LBB21_2:
	and	x8, x8, #0xfffffffffffffff8
	ldr	x9, [x0, #8]
	mov	w10, #3                         ; =0x3
	mov	w11, #6                         ; =0x6
	cmp	x9, #0
	csel	x9, x11, x10, eq
	orr	x8, x9, x8
	stur	x8, [x0, #-8]
	ret
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_list_add                ; -- Begin function minyar_list_add
	.p2align	2
_minyar_list_add:                       ; @minyar_list_add
	.cfi_startproc
; %bb.0:
	stp	x20, x19, [sp, #-32]!           ; 16-byte Folded Spill
	stp	x29, x30, [sp, #16]             ; 16-byte Folded Spill
	add	x29, sp, #16
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
	.cfi_offset w19, -24
	.cfi_offset w20, -32
	ldp	x8, x9, [x0, #8]
	cmp	x8, x9
	b.eq	LBB22_15
LBB22_1:
	ldur	x8, [x0, #-8]
	and	w9, w8, #0x7
	cmp	w9, #2
	b.ne	LBB22_3
; %bb.2:
	ldp	x8, x9, [x0]
	add	x10, x9, #1
	str	x10, [x0, #8]
	str	x1, [x8, x9, lsl #3]
	b	LBB22_14
LBB22_3:
	cbz	x1, LBB22_7
; %bb.4:
	cmp	w9, #6
	b.ne	LBB22_7
; %bb.5:
	ldur	x9, [x1, #-8]
	cmp	x9, #8
	b.lo	LBB22_12
; %bb.6:
	and	x8, x8, #0xfffffffffffffff8
	orr	x8, x8, #0x3
	stur	x8, [x0, #-8]
	b	LBB22_9
LBB22_7:
	cbz	x1, LBB22_12
; %bb.8:
	cmp	w9, #3
	b.ne	LBB22_12
LBB22_9:
	ldur	x8, [x1, #-8]
	cmp	x8, #8
	b.lo	LBB22_12
; %bb.10:
	cmn	x8, #8
	b.hs	LBB22_16
; %bb.11:
	add	x8, x8, #8
	stur	x8, [x1, #-8]
LBB22_12:
	ldp	x8, x9, [x0]
	add	x10, x9, #1
	str	x10, [x0, #8]
	str	x1, [x8, x9, lsl #3]
Lloh60:
	adrp	x8, _rc_pending_count@PAGE
Lloh61:
	ldr	x8, [x8, _rc_pending_count@PAGEOFF]
	cbz	x8, LBB22_14
; %bb.13:
	mov	w0, #32                         ; =0x20
	ldp	x29, x30, [sp, #16]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp], #32             ; 16-byte Folded Reload
	b	_minyar_rc_poll
LBB22_14:
	ldp	x29, x30, [sp, #16]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp], #32             ; 16-byte Folded Reload
	ret
LBB22_15:
	mov	x19, x0
	mov	x20, x1
	bl	_list_grow
	mov	x0, x19
	mov	x1, x20
	b	LBB22_1
LBB22_16:
	bl	_minyar_list_add.cold.1
	.loh AdrpLdr	Lloh60, Lloh61
	.cfi_endproc
                                        ; -- End function
	.p2align	2                               ; -- Begin function list_grow
_list_grow:                             ; @list_grow
	.cfi_startproc
; %bb.0:
	stp	x20, x19, [sp, #-32]!           ; 16-byte Folded Spill
	stp	x29, x30, [sp, #16]             ; 16-byte Folded Spill
	add	x29, sp, #16
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
	.cfi_offset w19, -24
	.cfi_offset w20, -32
	ldr	x8, [x0, #16]
	tbnz	x8, #63, LBB23_4
; %bb.1:
	lsr	x9, x8, #61
	cbnz	x9, LBB23_4
; %bb.2:
	cmp	x8, #4095
	mov	w9, #1                          ; =0x1
	cinc	x9, x9, hi
	lsl	x9, x8, x9
	mov	w10, #2                         ; =0x2
	cmp	x8, #0
	csel	x20, x10, x9, eq
	cmp	x8, x20
	lsr	x8, x20, #61
	ccmp	x8, #0, #0, ls
	b.ne	LBB23_4
; %bb.3:
	mov	x19, x0
	ldr	x0, [x0]
	lsl	x1, x20, #3
	bl	_rc_reallocate_data
	str	x0, [x19]
	str	x20, [x19, #16]
	ldp	x29, x30, [sp, #16]             ; 16-byte Folded Reload
	b	_OUTLINED_FUNCTION_2
LBB23_4:
Lloh62:
	adrp	x0, l_.str.3@PAGE
Lloh63:
	add	x0, x0, l_.str.3@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh62, Lloh63
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_list_add_take           ; -- Begin function minyar_list_add_take
	.p2align	2
_minyar_list_add_take:                  ; @minyar_list_add_take
	.cfi_startproc
; %bb.0:
	stp	x20, x19, [sp, #-32]!           ; 16-byte Folded Spill
	stp	x29, x30, [sp, #16]             ; 16-byte Folded Spill
	add	x29, sp, #16
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
	.cfi_offset w19, -24
	.cfi_offset w20, -32
	ldp	x8, x9, [x0, #8]
	cmp	x8, x9
	b.eq	LBB24_10
LBB24_1:
	ldur	x8, [x0, #-8]
	and	w9, w8, #0x7
	cmp	w9, #2
	b.ne	LBB24_3
; %bb.2:
	ldp	x8, x9, [x0]
	add	x10, x9, #1
	str	x10, [x0, #8]
	str	x1, [x8, x9, lsl #3]
	b	LBB24_9
LBB24_3:
	cbz	x1, LBB24_7
; %bb.4:
	cmp	w9, #6
	b.ne	LBB24_7
; %bb.5:
	ldur	x9, [x1, #-8]
	cmp	x9, #8
	b.lo	LBB24_7
; %bb.6:
	and	x8, x8, #0xfffffffffffffff8
	orr	x8, x8, #0x3
	stur	x8, [x0, #-8]
LBB24_7:
	ldp	x8, x9, [x0]
	add	x10, x9, #1
	str	x10, [x0, #8]
	str	x1, [x8, x9, lsl #3]
Lloh64:
	adrp	x8, _rc_pending_count@PAGE
Lloh65:
	ldr	x8, [x8, _rc_pending_count@PAGEOFF]
	cbz	x8, LBB24_9
; %bb.8:
	mov	w0, #32                         ; =0x20
	ldp	x29, x30, [sp, #16]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp], #32             ; 16-byte Folded Reload
	b	_minyar_rc_poll
LBB24_9:
	ldp	x29, x30, [sp, #16]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp], #32             ; 16-byte Folded Reload
	ret
LBB24_10:
	mov	x19, x0
	mov	x20, x1
	bl	_list_grow
	mov	x0, x19
	mov	x1, x20
	b	LBB24_1
	.loh AdrpLdr	Lloh64, Lloh65
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_list_length             ; -- Begin function minyar_list_length
	.p2align	2
_minyar_list_length:                    ; @minyar_list_length
	.cfi_startproc
; %bb.0:
	ldr	x0, [x0, #8]
	ret
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_list_get                ; -- Begin function minyar_list_get
	.p2align	2
_minyar_list_get:                       ; @minyar_list_get
	.cfi_startproc
; %bb.0:
	ldr	x8, [x0, #8]
	cmp	x8, x1
	b.ls	LBB26_2
; %bb.1:
	ldr	x8, [x0]
	ldr	x0, [x8, x1, lsl #3]
	ret
LBB26_2:
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
	mov	x0, x1
	mov	x1, x8
	bl	_list_position_stop
	.cfi_endproc
                                        ; -- End function
	.p2align	2                               ; -- Begin function list_position_stop
_list_position_stop:                    ; @list_position_stop
	.cfi_startproc
; %bb.0:
	sub	sp, sp, #160
	stp	x29, x30, [sp, #144]            ; 16-byte Folded Spill
	add	x29, sp, #144
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
	stp	x0, x1, [sp]
Lloh66:
	adrp	x2, l_.str.49@PAGE
Lloh67:
	add	x2, x2, l_.str.49@PAGEOFF
	add	x0, sp, #16
	mov	w1, #128                        ; =0x80
	bl	_snprintf
	add	x0, sp, #16
	bl	_minyar_stop
	.loh AdrpAdd	Lloh66, Lloh67
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_list_set                ; -- Begin function minyar_list_set
	.p2align	2
_minyar_list_set:                       ; @minyar_list_set
	.cfi_startproc
; %bb.0:
	mov	w3, #1                          ; =0x1
	b	_minyar_list_set_owned
	.cfi_endproc
                                        ; -- End function
	.p2align	2                               ; -- Begin function minyar_list_set_owned
_minyar_list_set_owned:                 ; @minyar_list_set_owned
	.cfi_startproc
; %bb.0:
	stp	x20, x19, [sp, #-32]!           ; 16-byte Folded Spill
	stp	x29, x30, [sp, #16]             ; 16-byte Folded Spill
	add	x29, sp, #16
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
	.cfi_offset w19, -24
	.cfi_offset w20, -32
	ldr	x8, [x0, #8]
	cmp	x8, x1
	b.ls	LBB29_16
; %bb.1:
	ldur	x8, [x0, #-8]
	and	w9, w8, #0x7
	cbz	x2, LBB29_5
; %bb.2:
	cmp	w9, #6
	b.ne	LBB29_5
; %bb.3:
	ldur	x9, [x2, #-8]
	cmp	x9, #8
	b.lo	LBB29_14
; %bb.4:
	and	x8, x8, #0xfffffffffffffff8
	orr	x8, x8, #0x3
	stur	x8, [x0, #-8]
	b	LBB29_6
LBB29_5:
	cmp	w9, #3
	b.ne	LBB29_14
LBB29_6:
	cbz	x2, LBB29_11
; %bb.7:
	cbz	w3, LBB29_11
; %bb.8:
	ldur	x8, [x2, #-8]
	cmp	x8, #8
	b.lo	LBB29_11
; %bb.9:
	cmn	x8, #8
	b.hs	LBB29_17
; %bb.10:
	add	x8, x8, #8
	stur	x8, [x2, #-8]
LBB29_11:
	ldr	x8, [x0]
	ldr	x0, [x8, x1, lsl #3]
	str	x2, [x8, x1, lsl #3]
	bl	_rc_drop
	mov	x19, x0
Lloh68:
	adrp	x8, _rc_pending_count@PAGE
Lloh69:
	ldr	x8, [x8, _rc_pending_count@PAGEOFF]
	adrp	x20, _rc_bounded_last_work@PAGE
	cbz	x8, LBB29_13
; %bb.12:
	mov	w8, #32                         ; =0x20
	sub	w0, w8, w19
	bl	_minyar_rc_poll
	ldr	x8, [x20, _rc_bounded_last_work@PAGEOFF]
LBB29_13:
	add	x8, x8, w19, uxtw
	str	x8, [x20, _rc_bounded_last_work@PAGEOFF]
	b	LBB29_15
LBB29_14:
	ldr	x8, [x0]
	str	x2, [x8, x1, lsl #3]
LBB29_15:
	ldp	x29, x30, [sp, #16]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp], #32             ; 16-byte Folded Reload
	ret
LBB29_16:
	mov	x0, x1
	mov	x1, x8
	bl	_list_position_stop
LBB29_17:
	bl	_minyar_list_set_owned.cold.1
	.loh AdrpLdr	Lloh68, Lloh69
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_list_set_take           ; -- Begin function minyar_list_set_take
	.p2align	2
_minyar_list_set_take:                  ; @minyar_list_set_take
	.cfi_startproc
; %bb.0:
	stp	x20, x19, [sp, #-32]!           ; 16-byte Folded Spill
	stp	x29, x30, [sp, #16]             ; 16-byte Folded Spill
	add	x29, sp, #16
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
	.cfi_offset w19, -24
	.cfi_offset w20, -32
	ldr	x8, [x0, #8]
	cmp	x8, x1
	b.ls	LBB30_11
; %bb.1:
	ldur	x8, [x0, #-8]
	and	w9, w8, #0x7
	cbz	x2, LBB30_5
; %bb.2:
	cmp	w9, #6
	b.ne	LBB30_5
; %bb.3:
	ldur	x9, [x2, #-8]
	cmp	x9, #8
	b.lo	LBB30_9
; %bb.4:
	and	x8, x8, #0xfffffffffffffff8
	orr	x8, x8, #0x3
	stur	x8, [x0, #-8]
	b	LBB30_6
LBB30_5:
	cmp	w9, #3
	b.ne	LBB30_9
LBB30_6:
	ldr	x8, [x0]
	ldr	x0, [x8, x1, lsl #3]
	str	x2, [x8, x1, lsl #3]
	bl	_rc_drop
	mov	x19, x0
Lloh70:
	adrp	x8, _rc_pending_count@PAGE
Lloh71:
	ldr	x8, [x8, _rc_pending_count@PAGEOFF]
	adrp	x20, _rc_bounded_last_work@PAGE
	cbz	x8, LBB30_8
; %bb.7:
	mov	w8, #32                         ; =0x20
	sub	w0, w8, w19
	bl	_minyar_rc_poll
	ldr	x8, [x20, _rc_bounded_last_work@PAGEOFF]
LBB30_8:
	add	x8, x8, w19, uxtw
	str	x8, [x20, _rc_bounded_last_work@PAGEOFF]
	b	LBB30_10
LBB30_9:
	ldr	x8, [x0]
	str	x2, [x8, x1, lsl #3]
LBB30_10:
	ldp	x29, x30, [sp, #16]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp], #32             ; 16-byte Folded Reload
	ret
LBB30_11:
	mov	x0, x1
	mov	x1, x8
	bl	_list_position_stop
	.loh AdrpLdr	Lloh70, Lloh71
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_list_appended           ; -- Begin function minyar_list_appended
	.p2align	2
_minyar_list_appended:                  ; @minyar_list_appended
	.cfi_startproc
; %bb.0:
	stp	x26, x25, [sp, #-80]!           ; 16-byte Folded Spill
	stp	x24, x23, [sp, #16]             ; 16-byte Folded Spill
	stp	x22, x21, [sp, #32]             ; 16-byte Folded Spill
	stp	x20, x19, [sp, #48]             ; 16-byte Folded Spill
	stp	x29, x30, [sp, #64]             ; 16-byte Folded Spill
	add	x29, sp, #64
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
	.cfi_offset w19, -24
	.cfi_offset w20, -32
	.cfi_offset w21, -40
	.cfi_offset w22, -48
	.cfi_offset w23, -56
	.cfi_offset w24, -64
	.cfi_offset w25, -72
	.cfi_offset w26, -80
	mov	x22, x3
	mov	x24, x2
	mov	x19, x1
	mov	x23, x0
	adrp	x25, _rc_pending_count@PAGE
	ldr	x8, [x25, _rc_pending_count@PAGEOFF]
	cbz	x8, LBB31_2
; %bb.1:
	mov	w0, #32                         ; =0x20
	bl	_minyar_rc_poll
	b	LBB31_3
LBB31_2:
	adrp	x8, _rc_bounded_last_work@PAGE
	str	xzr, [x8, _rc_bounded_last_work@PAGEOFF]
LBB31_3:
	mov	w0, #32                         ; =0x20
	bl	_malloc
	cbz	x0, LBB31_31
; %bb.4:
	mov	x21, x0
	adrp	x8, _rc_heap_allocation_count@PAGE
	ldr	x9, [x8, _rc_heap_allocation_count@PAGEOFF]
	add	x9, x9, #1
	str	x9, [x8, _rc_heap_allocation_count@PAGEOFF]
	mov	w8, #10                         ; =0xa
	str	x8, [x0]
Lloh72:
	adrp	x8, _rc_object_count@PAGE
	ldr	x9, [x8, _rc_object_count@PAGEOFF]
	add	x9, x9, #1
	str	x9, [x8, _rc_object_count@PAGEOFF]
Lloh73:
	adrp	x8, _rc_bytes@PAGE
	ldr	x9, [x8, _rc_bytes@PAGEOFF]
	add	x9, x9, #32
	str	x9, [x8, _rc_bytes@PAGEOFF]
	mov	x20, x0
	str	xzr, [x20, #8]!
	stp	xzr, xzr, [x0, #16]
	cbz	x24, LBB31_6
; %bb.5:
	mov	w8, #14                         ; =0xe
	str	x8, [x21]
LBB31_6:
	ldr	x8, [x23, #8]
	mov	x9, #9223372036854775807        ; =0x7fffffffffffffff
	cmp	x8, x9
	b.eq	LBB31_32
; %bb.7:
	ldr	x9, [x25, _rc_pending_count@PAGEOFF]
	orr	x24, x9, x24
	cbz	x9, LBB31_24
; %bb.8:
	tbnz	x8, #63, LBB31_10
LBB31_9:                                ; =>This Inner Loop Header: Depth=1
	add	x0, x21, #8
	bl	_list_grow
	ldr	x8, [x21, #24]
	ldr	x9, [x23, #8]
	cmp	x8, x9
	b.le	LBB31_9
LBB31_10:
	ldr	x8, [x23, #8]
	cbz	x24, LBB31_25
LBB31_11:
	cmp	x8, #1
	b.lt	LBB31_14
; %bb.12:
	mov	x24, #0                         ; =0x0
LBB31_13:                               ; =>This Inner Loop Header: Depth=1
	ldr	x8, [x23]
	ldr	x1, [x8, x24, lsl #3]
	mov	x0, x20
	bl	_minyar_list_add
	add	x24, x24, #1
	ldr	x8, [x23, #8]
	cmp	x24, x8
	b.lt	LBB31_13
LBB31_14:
	cbz	x22, LBB31_28
LBB31_15:
	ldp	x8, x9, [x21, #16]
	cmp	x8, x9
	b.eq	LBB31_30
LBB31_16:
	ldr	x8, [x21]
	and	w9, w8, #0x7
	cmp	w9, #2
	b.ne	LBB31_18
; %bb.17:
	ldp	x8, x9, [x21, #8]
	add	x10, x9, #1
	str	x10, [x21, #16]
	str	x19, [x8, x9, lsl #3]
	b	LBB31_29
LBB31_18:
	cbz	x19, LBB31_22
; %bb.19:
	cmp	w9, #6
	b.ne	LBB31_22
; %bb.20:
	ldur	x9, [x19, #-8]
	cmp	x9, #8
	b.lo	LBB31_22
; %bb.21:
	and	x8, x8, #0xfffffffffffffff8
	orr	x8, x8, #0x3
	str	x8, [x21]
LBB31_22:
	ldp	x8, x9, [x21, #8]
	add	x10, x9, #1
	str	x10, [x21, #16]
	str	x19, [x8, x9, lsl #3]
	ldr	x8, [x25, _rc_pending_count@PAGEOFF]
	cbz	x8, LBB31_29
; %bb.23:
	mov	w0, #32                         ; =0x20
	bl	_minyar_rc_poll
	b	LBB31_29
LBB31_24:
	add	x1, x8, #1
	mov	x0, x20
	bl	_list_reserve
	ldr	x8, [x23, #8]
	cbnz	x24, LBB31_11
LBB31_25:
	cbz	x8, LBB31_27
; %bb.26:
	ldr	x0, [x20]
	ldr	x1, [x23]
	lsl	x2, x8, #3
	bl	_memcpy
	ldr	x8, [x23, #8]
LBB31_27:
	str	x8, [x21, #16]
	cbnz	x22, LBB31_15
LBB31_28:
	mov	x0, x20
	mov	x1, x19
	bl	_minyar_list_add
LBB31_29:
	mov	x0, x20
	ldp	x29, x30, [sp, #64]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp, #48]             ; 16-byte Folded Reload
	ldp	x22, x21, [sp, #32]             ; 16-byte Folded Reload
	ldp	x24, x23, [sp, #16]             ; 16-byte Folded Reload
	ldp	x26, x25, [sp], #80             ; 16-byte Folded Reload
	ret
LBB31_30:
	mov	x0, x20
	bl	_list_grow
	b	LBB31_16
LBB31_31:
	bl	_out_of_memory
LBB31_32:
	bl	_minyar_list_appended.cold.1
	.loh AdrpAdrp	Lloh72, Lloh73
	.cfi_endproc
                                        ; -- End function
	.p2align	2                               ; -- Begin function list_reserve
_list_reserve:                          ; @list_reserve
	.cfi_startproc
; %bb.0:
	stp	x20, x19, [sp, #-32]!           ; 16-byte Folded Spill
	stp	x29, x30, [sp, #16]             ; 16-byte Folded Spill
	add	x29, sp, #16
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
	.cfi_offset w19, -24
	.cfi_offset w20, -32
	mov	x19, x0
	ldr	x8, [x0, #16]
	cmp	x8, x1
	b.ge	LBB32_5
; %bb.1:
	mov	w9, #1                          ; =0x1
	mov	w10, #2                         ; =0x2
	mov	x20, x8
LBB32_2:                                ; =>This Inner Loop Header: Depth=1
	tbnz	x20, #63, LBB32_8
; %bb.3:                                ;   in Loop: Header=BB32_2 Depth=1
	lsr	x11, x20, #61
	cbnz	x11, LBB32_8
; %bb.4:                                ;   in Loop: Header=BB32_2 Depth=1
	cmp	x20, #4095
	cinc	x11, x9, hi
	lsl	x11, x20, x11
	cmp	x20, #0
	csel	x20, x10, x11, eq
	cmp	x20, x1
	b.lt	LBB32_2
	b	LBB32_6
LBB32_5:
	mov	x20, x8
LBB32_6:
	cmp	x8, x20
	lsr	x8, x20, #61
	ccmp	x8, #0, #0, le
	b.ne	LBB32_8
; %bb.7:
	ldr	x0, [x19]
	lsl	x1, x20, #3
	bl	_rc_reallocate_data
	str	x0, [x19]
	str	x20, [x19, #16]
	ldp	x29, x30, [sp, #16]             ; 16-byte Folded Reload
	b	_OUTLINED_FUNCTION_2
LBB32_8:
Lloh74:
	adrp	x0, l_.str.3@PAGE
Lloh75:
	add	x0, x0, l_.str.3@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh74, Lloh75
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_record_new              ; -- Begin function minyar_record_new
	.p2align	2
_minyar_record_new:                     ; @minyar_record_new
	.cfi_startproc
; %bb.0:
	stp	x22, x21, [sp, #-48]!           ; 16-byte Folded Spill
	stp	x20, x19, [sp, #16]             ; 16-byte Folded Spill
	stp	x29, x30, [sp, #32]             ; 16-byte Folded Spill
	add	x29, sp, #32
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
	.cfi_offset w19, -24
	.cfi_offset w20, -32
	.cfi_offset w21, -40
	.cfi_offset w22, -48
	lsr	x8, x0, #61
	cbnz	x8, LBB33_8
; %bb.1:
	mov	x19, x0
	mov	x8, #7280                       ; =0x1c70
	movk	x8, #29127, lsl #16
	movk	x8, #50972, lsl #32
	movk	x8, #7281, lsl #48
	cmp	x0, x8
	b.hs	LBB33_7
; %bb.2:
	add	x20, x19, x19, lsl #3
Lloh76:
	adrp	x8, _rc_pending_count@PAGE
Lloh77:
	ldr	x8, [x8, _rc_pending_count@PAGEOFF]
	cbz	x8, LBB33_4
; %bb.3:
	mov	w0, #32                         ; =0x20
	bl	_minyar_rc_poll
	b	LBB33_5
LBB33_4:
	adrp	x8, _rc_bounded_last_work@PAGE
	str	xzr, [x8, _rc_bounded_last_work@PAGEOFF]
LBB33_5:
	add	x21, x20, #16
	mov	x0, x21
	bl	_malloc
	cbz	x0, LBB33_7
; %bb.6:
	adrp	x8, _rc_heap_allocation_count@PAGE
	ldr	x9, [x8, _rc_heap_allocation_count@PAGEOFF]
	add	x9, x9, #1
	str	x9, [x8, _rc_heap_allocation_count@PAGEOFF]
	mov	w9, #12                         ; =0xc
	mov	x8, x0
	str	x9, [x8], #16
Lloh78:
	adrp	x9, _rc_object_count@PAGE
	ldr	x10, [x9, _rc_object_count@PAGEOFF]
	add	x10, x10, #1
	str	x10, [x9, _rc_object_count@PAGEOFF]
Lloh79:
	adrp	x9, _rc_bytes@PAGE
	ldr	x10, [x9, _rc_bytes@PAGEOFF]
	add	x10, x10, x21
	str	x10, [x9, _rc_bytes@PAGEOFF]
	mov	x21, x0
	mov	x0, x8
	mov	x1, x20
	bl	_bzero
	str	x19, [x21, #8]!
	mov	x0, x21
	ldp	x29, x30, [sp, #32]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp, #16]             ; 16-byte Folded Reload
	ldp	x22, x21, [sp], #48             ; 16-byte Folded Reload
	ret
LBB33_7:
	bl	_out_of_memory
LBB33_8:
	bl	_minyar_record_new.cold.1
	.loh AdrpLdr	Lloh76, Lloh77
	.loh AdrpAdrp	Lloh78, Lloh79
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_record_new_scalar       ; -- Begin function minyar_record_new_scalar
	.p2align	2
_minyar_record_new_scalar:              ; @minyar_record_new_scalar
	.cfi_startproc
; %bb.0:
	stp	x22, x21, [sp, #-48]!           ; 16-byte Folded Spill
	stp	x20, x19, [sp, #16]             ; 16-byte Folded Spill
	stp	x29, x30, [sp, #32]             ; 16-byte Folded Spill
	add	x29, sp, #32
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
	.cfi_offset w19, -24
	.cfi_offset w20, -32
	.cfi_offset w21, -40
	.cfi_offset w22, -48
	lsr	x8, x0, #61
	cbnz	x8, LBB34_8
; %bb.1:
	mov	x19, x0
	mov	x8, #2305843009213693950        ; =0x1ffffffffffffffe
	cmp	x0, x8
	b.hs	LBB34_7
; %bb.2:
	lsl	x20, x19, #3
Lloh80:
	adrp	x8, _rc_pending_count@PAGE
Lloh81:
	ldr	x8, [x8, _rc_pending_count@PAGEOFF]
	cbz	x8, LBB34_4
; %bb.3:
	mov	w0, #32                         ; =0x20
	bl	_minyar_rc_poll
	b	LBB34_5
LBB34_4:
	adrp	x8, _rc_bounded_last_work@PAGE
	str	xzr, [x8, _rc_bounded_last_work@PAGEOFF]
LBB34_5:
	add	x21, x20, #16
	mov	x0, x21
	bl	_malloc
	cbz	x0, LBB34_7
; %bb.6:
	adrp	x8, _rc_heap_allocation_count@PAGE
	ldr	x9, [x8, _rc_heap_allocation_count@PAGEOFF]
	add	x9, x9, #1
	str	x9, [x8, _rc_heap_allocation_count@PAGEOFF]
	mov	w9, #13                         ; =0xd
	mov	x8, x0
	str	x9, [x8], #16
Lloh82:
	adrp	x9, _rc_object_count@PAGE
	ldr	x10, [x9, _rc_object_count@PAGEOFF]
	add	x10, x10, #1
	str	x10, [x9, _rc_object_count@PAGEOFF]
Lloh83:
	adrp	x9, _rc_bytes@PAGE
	ldr	x10, [x9, _rc_bytes@PAGEOFF]
	add	x10, x10, x21
	str	x10, [x9, _rc_bytes@PAGEOFF]
	mov	x21, x0
	mov	x0, x8
	mov	x1, x20
	bl	_bzero
	str	x19, [x21, #8]!
	mov	x0, x21
	ldp	x29, x30, [sp, #32]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp, #16]             ; 16-byte Folded Reload
	ldp	x22, x21, [sp], #48             ; 16-byte Folded Reload
	ret
LBB34_7:
	bl	_out_of_memory
LBB34_8:
	bl	_minyar_record_new_scalar.cold.1
	.loh AdrpLdr	Lloh80, Lloh81
	.loh AdrpAdrp	Lloh82, Lloh83
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_record_get              ; -- Begin function minyar_record_get
	.p2align	2
_minyar_record_get:                     ; @minyar_record_get
	.cfi_startproc
; %bb.0:
	ldr	x8, [x0]
	cmp	x8, x1
	b.ls	LBB35_2
; %bb.1:
	add	x8, x0, x1, lsl #3
	ldr	x0, [x8, #8]
	ret
LBB35_2:
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
	mov	x0, x1
	mov	x1, x8
	bl	_list_position_stop
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_record_set_scalar       ; -- Begin function minyar_record_set_scalar
	.p2align	2
_minyar_record_set_scalar:              ; @minyar_record_set_scalar
	.cfi_startproc
; %bb.0:
	ldr	x8, [x0]
	cmp	x8, x1
	b.ls	LBB36_2
; %bb.1:
	add	x8, x0, x1, lsl #3
	str	x2, [x8, #8]
	ret
LBB36_2:
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
	mov	x0, x1
	mov	x1, x8
	bl	_list_position_stop
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_record_set              ; -- Begin function minyar_record_set
	.p2align	2
_minyar_record_set:                     ; @minyar_record_set
	.cfi_startproc
; %bb.0:
	ldr	x8, [x0]
	cmp	x8, x1
	b.ls	LBB37_4
; %bb.1:
	add	x8, x0, x1, lsl #3
	str	x2, [x8, #8]
	ldur	x8, [x0, #-8]
	and	x8, x8, #0x7
	cmp	x8, #4
	b.ne	LBB37_3
; %bb.2:
	mov	w0, #32                         ; =0x20
	b	_minyar_rc_poll
LBB37_3:
	ret
LBB37_4:
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
	mov	x0, x1
	mov	x1, x8
	bl	_list_position_stop
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_record_set_take         ; -- Begin function minyar_record_set_take
	.p2align	2
_minyar_record_set_take:                ; @minyar_record_set_take
	.cfi_startproc
; %bb.0:
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
	ldr	x8, [x0]
	cmp	x8, x1
	b.ls	LBB38_5
; %bb.1:
	add	x9, x0, #8
	add	x8, x9, x8, lsl #3
	mov	w10, #1                         ; =0x1
	strb	w10, [x8, x1]
	ldr	x8, [x0]
	cmp	x8, x1
	b.ls	LBB38_5
; %bb.2:
	str	x2, [x9, x1, lsl #3]
	ldur	x8, [x0, #-8]
	and	x8, x8, #0x7
	cmp	x8, #4
	b.ne	LBB38_4
; %bb.3:
	mov	w0, #32                         ; =0x20
	ldp	x29, x30, [sp], #16             ; 16-byte Folded Reload
	b	_minyar_rc_poll
LBB38_4:
	ldp	x29, x30, [sp], #16             ; 16-byte Folded Reload
	ret
LBB38_5:
	mov	x0, x1
	mov	x1, x8
	bl	_list_position_stop
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_record_set_reference    ; -- Begin function minyar_record_set_reference
	.p2align	2
_minyar_record_set_reference:           ; @minyar_record_set_reference
	.cfi_startproc
; %bb.0:
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
	cbz	x2, LBB39_4
; %bb.1:
	ldur	x8, [x2, #-8]
	cmp	x8, #8
	b.lo	LBB39_4
; %bb.2:
	cmn	x8, #8
	b.hs	LBB39_10
; %bb.3:
	add	x8, x8, #8
	stur	x8, [x2, #-8]
LBB39_4:
	ldr	x8, [x0]
	cmp	x8, x1
	b.ls	LBB39_9
; %bb.5:
	add	x9, x0, #8
	add	x8, x9, x8, lsl #3
	mov	w10, #1                         ; =0x1
	strb	w10, [x8, x1]
	ldr	x8, [x0]
	cmp	x8, x1
	b.ls	LBB39_9
; %bb.6:
	str	x2, [x9, x1, lsl #3]
	ldur	x8, [x0, #-8]
	and	x8, x8, #0x7
	cmp	x8, #4
	b.ne	LBB39_8
; %bb.7:
	mov	w0, #32                         ; =0x20
	ldp	x29, x30, [sp], #16             ; 16-byte Folded Reload
	b	_minyar_rc_poll
LBB39_8:
	ldp	x29, x30, [sp], #16             ; 16-byte Folded Reload
	ret
LBB39_9:
	mov	x0, x1
	mov	x1, x8
	bl	_list_position_stop
LBB39_10:
	bl	_minyar_record_set_reference.cold.1
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_record_replace          ; -- Begin function minyar_record_replace
	.p2align	2
_minyar_record_replace:                 ; @minyar_record_replace
	.cfi_startproc
; %bb.0:
	stp	x20, x19, [sp, #-32]!           ; 16-byte Folded Spill
	stp	x29, x30, [sp, #16]             ; 16-byte Folded Spill
	add	x29, sp, #16
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
	.cfi_offset w19, -24
	.cfi_offset w20, -32
	ldr	x8, [x0]
	cmp	x8, x1
	b.ls	LBB40_9
; %bb.1:
	cbz	x2, LBB40_6
; %bb.2:
	cbnz	x3, LBB40_6
; %bb.3:
	ldur	x8, [x2, #-8]
	cmp	x8, #8
	b.lo	LBB40_6
; %bb.4:
	cmn	x8, #8
	b.hs	LBB40_10
; %bb.5:
	add	x8, x8, #8
	stur	x8, [x2, #-8]
LBB40_6:
	add	x8, x0, x1, lsl #3
	ldr	x0, [x8, #8]
	str	x2, [x8, #8]
	bl	_rc_drop
	mov	x19, x0
Lloh84:
	adrp	x8, _rc_pending_count@PAGE
Lloh85:
	ldr	x8, [x8, _rc_pending_count@PAGEOFF]
	adrp	x20, _rc_bounded_last_work@PAGE
	cbz	x8, LBB40_8
; %bb.7:
	mov	w8, #32                         ; =0x20
	sub	w0, w8, w19
	bl	_minyar_rc_poll
	ldr	x8, [x20, _rc_bounded_last_work@PAGEOFF]
LBB40_8:
	add	x8, x8, w19, uxtw
	str	x8, [x20, _rc_bounded_last_work@PAGEOFF]
	ldp	x29, x30, [sp, #16]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp], #32             ; 16-byte Folded Reload
	ret
LBB40_9:
	mov	x0, x1
	mov	x1, x8
	bl	_list_position_stop
LBB40_10:
	bl	_minyar_record_replace.cold.1
	.loh AdrpLdr	Lloh84, Lloh85
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_print_text              ; -- Begin function minyar_print_text
	.p2align	2
_minyar_print_text:                     ; @minyar_print_text
	.cfi_startproc
; %bb.0:
	stp	x20, x19, [sp, #-32]!           ; 16-byte Folded Spill
	stp	x29, x30, [sp, #16]             ; 16-byte Folded Spill
	add	x29, sp, #16
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
	.cfi_offset w19, -24
	.cfi_offset w20, -32
	mov	x19, x0
	ldr	x0, [x0]
	ldr	x2, [x19, #8]
Lloh86:
	adrp	x20, ___stdoutp@GOTPAGE
Lloh87:
	ldr	x20, [x20, ___stdoutp@GOTPAGEOFF]
	ldr	x3, [x20]
	mov	w1, #1                          ; =0x1
	bl	_fwrite
	ldr	x8, [x19, #8]
	cmp	x0, x8
	b.ne	LBB41_4
; %bb.1:
	mov	w0, #10                         ; =0xa
	bl	_putchar
	cmn	w0, #1
	b.eq	LBB41_4
; %bb.2:
	ldr	x0, [x20]
	bl	_fflush
	cmn	w0, #1
	b.eq	LBB41_4
; %bb.3:
	ldp	x29, x30, [sp, #16]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp], #32             ; 16-byte Folded Reload
	ret
LBB41_4:
	bl	_output_error
	.loh AdrpLdrGot	Lloh86, Lloh87
	.cfi_endproc
                                        ; -- End function
	.p2align	2                               ; -- Begin function output_error
_output_error:                          ; @output_error
	.cfi_startproc
; %bb.0:
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
Lloh88:
	adrp	x0, l_.str.51@PAGE
Lloh89:
	add	x0, x0, l_.str.51@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh88, Lloh89
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_fail                    ; -- Begin function minyar_fail
	.p2align	2
_minyar_fail:                           ; @minyar_fail
	.cfi_startproc
; %bb.0:
	stp	x20, x19, [sp, #-32]!           ; 16-byte Folded Spill
	stp	x29, x30, [sp, #16]             ; 16-byte Folded Spill
	add	x29, sp, #16
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
	.cfi_offset w19, -24
	.cfi_offset w20, -32
	mov	x19, x0
Lloh90:
	adrp	x20, ___stderrp@GOTPAGE
Lloh91:
	ldr	x20, [x20, ___stderrp@GOTPAGEOFF]
	ldr	x1, [x20]
Lloh92:
	adrp	x0, l_.str.4@PAGE
Lloh93:
	add	x0, x0, l_.str.4@PAGEOFF
	bl	_fputs
	ldp	x0, x2, [x19]
	ldr	x3, [x20]
	mov	w1, #1                          ; =0x1
	bl	_fwrite
	ldr	x1, [x20]
	mov	w0, #10                         ; =0xa
	bl	_fputc
	mov	w0, #1                          ; =0x1
	bl	_exit
	.loh AdrpAdd	Lloh92, Lloh93
	.loh AdrpLdrGot	Lloh90, Lloh91
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_print_integer           ; -- Begin function minyar_print_integer
	.p2align	2
_minyar_print_integer:                  ; @minyar_print_integer
	.cfi_startproc
; %bb.0:
	sub	sp, sp, #32
	stp	x29, x30, [sp, #16]             ; 16-byte Folded Spill
	add	x29, sp, #16
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
	str	x0, [sp]
Lloh94:
	adrp	x0, l_.str.5@PAGE
Lloh95:
	add	x0, x0, l_.str.5@PAGEOFF
	bl	_printf
	tbnz	w0, #31, LBB44_3
; %bb.1:
Lloh96:
	adrp	x8, ___stdoutp@GOTPAGE
Lloh97:
	ldr	x8, [x8, ___stdoutp@GOTPAGEOFF]
Lloh98:
	ldr	x0, [x8]
	bl	_fflush
	cmn	w0, #1
	b.eq	LBB44_3
; %bb.2:
	ldp	x29, x30, [sp, #16]             ; 16-byte Folded Reload
	add	sp, sp, #32
	ret
LBB44_3:
	bl	_output_error
	.loh AdrpAdd	Lloh94, Lloh95
	.loh AdrpLdrGotLdr	Lloh96, Lloh97, Lloh98
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_print_character         ; -- Begin function minyar_print_character
	.p2align	2
_minyar_print_character:                ; @minyar_print_character
	.cfi_startproc
; %bb.0:
	sub	sp, sp, #48
	stp	x20, x19, [sp, #16]             ; 16-byte Folded Spill
	stp	x29, x30, [sp, #32]             ; 16-byte Folded Spill
	add	x29, sp, #32
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
	.cfi_offset w19, -24
	.cfi_offset w20, -32
	lsr	w8, w0, #16
	cmp	w8, #16
	b.hi	LBB45_14
; %bb.1:
	and	w9, w0, #0x1ff800
	mov	w10, #55296                     ; =0xd800
	cmp	w9, w10
	b.eq	LBB45_14
; %bb.2:
	cmp	w0, #127
	b.hi	LBB45_4
; %bb.3:
	strb	w0, [sp, #12]
	mov	w19, #1                         ; =0x1
	b	LBB45_9
LBB45_4:
	cmp	w0, #2047
	b.hi	LBB45_6
; %bb.5:
	lsr	w8, w0, #6
	orr	w8, w8, #0xc0
	strb	w8, [sp, #12]
	mov	w8, #128                        ; =0x80
	bfxil	w8, w0, #0, #6
	strb	w8, [sp, #13]
	mov	w19, #2                         ; =0x2
	b	LBB45_9
LBB45_6:
	cbnz	w8, LBB45_8
; %bb.7:
	lsr	w8, w0, #12
	orr	w8, w8, #0xe0
	strb	w8, [sp, #12]
	mov	w8, #128                        ; =0x80
	mov	w9, #128                        ; =0x80
	bfxil	w9, w0, #6, #6
	strb	w9, [sp, #13]
	bfxil	w8, w0, #0, #6
	strb	w8, [sp, #14]
	mov	w19, #3                         ; =0x3
	b	LBB45_9
LBB45_8:
	lsr	w8, w0, #18
	orr	w8, w8, #0xf0
	strb	w8, [sp, #12]
	mov	w8, #128                        ; =0x80
	mov	w9, #128                        ; =0x80
	bfxil	w9, w0, #12, #6
	strb	w9, [sp, #13]
	mov	w9, #128                        ; =0x80
	bfxil	w9, w0, #6, #6
	strb	w9, [sp, #14]
	bfxil	w8, w0, #0, #6
	strb	w8, [sp, #15]
	mov	w19, #4                         ; =0x4
LBB45_9:
Lloh99:
	adrp	x20, ___stdoutp@GOTPAGE
Lloh100:
	ldr	x20, [x20, ___stdoutp@GOTPAGEOFF]
	ldr	x3, [x20]
	add	x0, sp, #12
	mov	w1, #1                          ; =0x1
	mov	x2, x19
	bl	_fwrite
	cmp	x0, x19
	b.ne	LBB45_13
; %bb.10:
	mov	w0, #10                         ; =0xa
	bl	_putchar
	cmn	w0, #1
	b.eq	LBB45_13
; %bb.11:
	ldr	x0, [x20]
	bl	_fflush
	cmn	w0, #1
	b.eq	LBB45_13
; %bb.12:
	ldp	x29, x30, [sp, #32]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp, #16]             ; 16-byte Folded Reload
	add	sp, sp, #48
	ret
LBB45_13:
	bl	_output_error
LBB45_14:
	bl	_minyar_print_character.cold.1
	.loh AdrpLdrGot	Lloh99, Lloh100
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_print_boolean           ; -- Begin function minyar_print_boolean
	.p2align	2
_minyar_print_boolean:                  ; @minyar_print_boolean
	.cfi_startproc
; %bb.0:
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
Lloh101:
	adrp	x8, l_.str.7@PAGE
Lloh102:
	add	x8, x8, l_.str.7@PAGEOFF
Lloh103:
	adrp	x9, l_.str.6@PAGE
Lloh104:
	add	x9, x9, l_.str.6@PAGEOFF
	cmp	w0, #0
	csel	x0, x9, x8, ne
	bl	_puts
	cmn	w0, #1
	b.eq	LBB46_3
; %bb.1:
Lloh105:
	adrp	x8, ___stdoutp@GOTPAGE
Lloh106:
	ldr	x8, [x8, ___stdoutp@GOTPAGEOFF]
Lloh107:
	ldr	x0, [x8]
	bl	_fflush
	cmn	w0, #1
	b.eq	LBB46_3
; %bb.2:
	ldp	x29, x30, [sp], #16             ; 16-byte Folded Reload
	ret
LBB46_3:
	bl	_output_error
	.loh AdrpAdd	Lloh103, Lloh104
	.loh AdrpAdd	Lloh101, Lloh102
	.loh AdrpLdrGotLdr	Lloh105, Lloh106, Lloh107
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_texts_are_equal         ; -- Begin function minyar_texts_are_equal
	.p2align	2
_minyar_texts_are_equal:                ; @minyar_texts_are_equal
	.cfi_startproc
; %bb.0:
	cmp	x0, x1
	b.eq	LBB47_14
; %bb.1:
	ldr	x2, [x0, #8]
	ldr	x8, [x1, #8]
	cmp	x2, x8
	b.ne	LBB47_4
; %bb.2:
	ldr	x0, [x0]
	ldr	x1, [x1]
	cmp	x2, #17
	b.lo	LBB47_5
; %bb.3:
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
	bl	_memcmp
	cmp	w0, #0
	cset	w0, eq
	ldp	x29, x30, [sp], #16             ; 16-byte Folded Reload
	ret
LBB47_4:
	mov	w0, #0                          ; =0x0
	ret
LBB47_5:
	cmp	x2, #8
	b.lo	LBB47_7
; %bb.6:
	ldr	x8, [x0]
	ldr	x9, [x1]
	add	x10, x0, x2
	ldur	x10, [x10, #-8]
	add	x11, x1, x2
	ldur	x11, [x11, #-8]
	cmp	x8, x9
	ccmp	x10, x11, #0, eq
	cset	w0, eq
	ret
LBB47_7:
	cmp	x2, #4
	b.lo	LBB47_9
; %bb.8:
	ldr	w8, [x0]
	ldr	w9, [x1]
	add	x10, x0, x2
	ldur	w10, [x10, #-4]
	add	x11, x1, x2
	ldur	w11, [x11, #-4]
	b	LBB47_11
LBB47_9:
	cmp	x2, #2
	b.lo	LBB47_12
; %bb.10:
	ldrh	w8, [x0]
	ldrh	w9, [x1]
	add	x10, x0, x2
	ldurh	w10, [x10, #-2]
	and	w10, w10, #0xffff
	add	x11, x1, x2
	ldurh	w11, [x11, #-2]
	and	w11, w11, #0xffff
LBB47_11:
	cmp	w8, w9
	ccmp	w10, w11, #0, eq
	cset	w0, eq
	ret
LBB47_12:
	cbz	x2, LBB47_14
; %bb.13:
	ldrb	w8, [x0]
	ldrb	w9, [x1]
	cmp	w8, w9
	cset	w0, eq
	ret
LBB47_14:
	mov	w0, #1                          ; =0x1
	ret
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_join_text               ; -- Begin function minyar_join_text
	.p2align	2
_minyar_join_text:                      ; @minyar_join_text
	.cfi_startproc
; %bb.0:
	ldr	x8, [x0, #8]
	ldr	x9, [x1, #8]
	eor	x9, x9, #0x7fffffffffffffff
	cmp	x8, x9
	b.gt	LBB48_2
; %bb.1:
	b	_join_by_copying
LBB48_2:
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
	bl	_join_too_large
	.cfi_endproc
                                        ; -- End function
	.p2align	2                               ; -- Begin function join_too_large
_join_too_large:                        ; @join_too_large
	.cfi_startproc
; %bb.0:
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
Lloh108:
	adrp	x0, l_.str.52@PAGE
Lloh109:
	add	x0, x0, l_.str.52@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh108, Lloh109
	.cfi_endproc
                                        ; -- End function
	.p2align	2                               ; -- Begin function join_by_copying
_join_by_copying:                       ; @join_by_copying
	.cfi_startproc
; %bb.0:
	stp	x28, x27, [sp, #-96]!           ; 16-byte Folded Spill
	stp	x26, x25, [sp, #16]             ; 16-byte Folded Spill
	stp	x24, x23, [sp, #32]             ; 16-byte Folded Spill
	stp	x22, x21, [sp, #48]             ; 16-byte Folded Spill
	stp	x20, x19, [sp, #64]             ; 16-byte Folded Spill
	stp	x29, x30, [sp, #80]             ; 16-byte Folded Spill
	add	x29, sp, #80
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
	.cfi_offset w19, -24
	.cfi_offset w20, -32
	.cfi_offset w21, -40
	.cfi_offset w22, -48
	.cfi_offset w23, -56
	.cfi_offset w24, -64
	.cfi_offset w25, -72
	.cfi_offset w26, -80
	.cfi_offset w27, -88
	.cfi_offset w28, -96
	mov	x20, x1
	mov	x21, x0
	ldr	x8, [x0, #8]
	ldr	x9, [x1, #8]
	add	x24, x9, x8
	add	x23, x24, #1
	adrp	x26, _rc_pending_count@PAGE
	ldr	x8, [x26, _rc_pending_count@PAGEOFF]
	cbz	x8, LBB50_2
; %bb.1:
	mov	w0, #32                         ; =0x20
	bl	_minyar_rc_poll
	cmn	x23, #8
	b.lo	LBB50_3
	b	LBB50_31
LBB50_2:
	adrp	x8, _rc_bounded_last_work@PAGE
	str	xzr, [x8, _rc_bounded_last_work@PAGEOFF]
	cmn	x23, #8
	b.hs	LBB50_31
LBB50_3:
	add	x22, x24, #9
	mov	x0, x22
	bl	_malloc
	cbz	x0, LBB50_31
; %bb.4:
	mov	x19, x0
	adrp	x27, _rc_heap_allocation_count@PAGE
	ldr	x8, [x27, _rc_heap_allocation_count@PAGEOFF]
	add	x8, x8, #1
	str	x8, [x27, _rc_heap_allocation_count@PAGEOFF]
	str	x23, [x19], #8
	adrp	x25, _rc_bytes@PAGE
	ldr	x8, [x25, _rc_bytes@PAGEOFF]
	add	x8, x8, x22
	str	x8, [x25, _rc_bytes@PAGEOFF]
	ldp	x1, x22, [x21]
	cmp	x22, #17
	b.lo	LBB50_6
; %bb.5:
	mov	x0, x19
	mov	x2, x22
	bl	_memcpy
	b	LBB50_14
LBB50_6:
	cmp	x22, #8
	b.lo	LBB50_8
; %bb.7:
	ldr	x8, [x1]
	add	x9, x1, x22
	ldur	x9, [x9, #-8]
	str	x8, [x19]
	add	x8, x19, x22
	stur	x9, [x8, #-8]
	b	LBB50_14
LBB50_8:
	cmp	x22, #4
	b.lo	LBB50_10
; %bb.9:
	ldr	w8, [x1]
	add	x9, x1, x22
	ldur	w9, [x9, #-4]
	str	w8, [x19]
	add	x8, x19, x22
	stur	w9, [x8, #-4]
	b	LBB50_14
LBB50_10:
	cmp	x22, #2
	b.lo	LBB50_12
; %bb.11:
	ldrh	w8, [x1]
	add	x9, x1, x22
	ldurh	w9, [x9, #-2]
	strh	w8, [x19]
	add	x8, x19, x22
	sturh	w9, [x8, #-2]
	b	LBB50_14
LBB50_12:
	cmp	x22, #1
	b.ne	LBB50_14
; %bb.13:
	ldrb	w8, [x1]
	strb	w8, [x19]
LBB50_14:
	add	x0, x19, x22
	ldp	x1, x23, [x20]
	cmp	x23, #17
	b.lo	LBB50_16
; %bb.15:
	mov	x2, x23
	bl	_memcpy
	b	LBB50_24
LBB50_16:
	cmp	x23, #8
	b.lo	LBB50_18
; %bb.17:
	ldr	x8, [x1]
	add	x9, x1, x23
	ldur	x9, [x9, #-8]
	str	x8, [x0]
	add	x8, x0, x23
	stur	x9, [x8, #-8]
	b	LBB50_24
LBB50_18:
	cmp	x23, #4
	b.lo	LBB50_20
; %bb.19:
	ldr	w8, [x1]
	add	x9, x1, x23
	ldur	w9, [x9, #-4]
	str	w8, [x0]
	add	x8, x0, x23
	stur	w9, [x8, #-4]
	b	LBB50_24
LBB50_20:
	cmp	x23, #2
	b.lo	LBB50_22
; %bb.21:
	ldrh	w8, [x1]
	add	x9, x1, x23
	ldurh	w9, [x9, #-2]
	strh	w8, [x0]
	add	x8, x0, x23
	sturh	w9, [x8, #-2]
	b	LBB50_24
LBB50_22:
	cmp	x23, #1
	b.ne	LBB50_24
; %bb.23:
	ldrb	w8, [x1]
	strb	w8, [x0]
LBB50_24:
	strb	wzr, [x19, x24]
	ldr	x8, [x21, #16]
	cmp	x8, x22
	b.ne	LBB50_27
; %bb.25:
	ldr	x8, [x20, #16]
	cmp	x8, x23
	csinv	x20, x24, xzr, eq
	ldr	x8, [x26, _rc_pending_count@PAGEOFF]
	cbz	x8, LBB50_28
LBB50_26:
	mov	w0, #32                         ; =0x20
	bl	_minyar_rc_poll
	b	LBB50_29
LBB50_27:
	mov	x20, #-1                        ; =0xffffffffffffffff
	ldr	x8, [x26, _rc_pending_count@PAGEOFF]
	cbnz	x8, LBB50_26
LBB50_28:
	adrp	x8, _rc_bounded_last_work@PAGE
	str	xzr, [x8, _rc_bounded_last_work@PAGEOFF]
LBB50_29:
	mov	w0, #48                         ; =0x30
	bl	_malloc
	cbz	x0, LBB50_31
; %bb.30:
	ldr	x8, [x27, _rc_heap_allocation_count@PAGEOFF]
	add	x8, x8, #1
	str	x8, [x27, _rc_heap_allocation_count@PAGEOFF]
	mov	w8, #9                          ; =0x9
	str	x8, [x0]
	adrp	x8, _rc_object_count@PAGE
	ldr	x9, [x8, _rc_object_count@PAGEOFF]
	add	x9, x9, #1
	str	x9, [x8, _rc_object_count@PAGEOFF]
	ldr	x8, [x25, _rc_bytes@PAGEOFF]
	add	x9, x8, #48
	mov	x8, x0
	str	x19, [x8, #8]!
	str	x9, [x25, _rc_bytes@PAGEOFF]
	stp	x24, x20, [x0, #16]
	stp	xzr, xzr, [x0, #32]
	mov	x0, x8
	ldp	x29, x30, [sp, #80]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp, #64]             ; 16-byte Folded Reload
	ldp	x22, x21, [sp, #48]             ; 16-byte Folded Reload
	ldp	x24, x23, [sp, #32]             ; 16-byte Folded Reload
	ldp	x26, x25, [sp, #16]             ; 16-byte Folded Reload
	ldp	x28, x27, [sp], #96             ; 16-byte Folded Reload
	ret
LBB50_31:
	bl	_out_of_memory
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_join_text_take_left     ; -- Begin function minyar_join_text_take_left
	.p2align	2
_minyar_join_text_take_left:            ; @minyar_join_text_take_left
	.cfi_startproc
; %bb.0:
	stp	x24, x23, [sp, #-64]!           ; 16-byte Folded Spill
	stp	x22, x21, [sp, #16]             ; 16-byte Folded Spill
	stp	x20, x19, [sp, #32]             ; 16-byte Folded Spill
	stp	x29, x30, [sp, #48]             ; 16-byte Folded Spill
	add	x29, sp, #48
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
	.cfi_offset w19, -24
	.cfi_offset w20, -32
	.cfi_offset w21, -40
	.cfi_offset w22, -48
	.cfi_offset w23, -56
	.cfi_offset w24, -64
	ldr	x21, [x0, #8]
	ldr	x19, [x1, #8]
	eor	x8, x19, #0x7fffffffffffffff
	cmp	x21, x8
	b.gt	LBB51_27
; %bb.1:
	ldur	x8, [x0, #-8]
	cmp	x8, #9
	b.ne	LBB51_3
; %bb.2:
	ldr	x8, [x0, #32]
	cbz	x8, LBB51_7
LBB51_3:
	mov	x20, x0
	bl	_join_by_copying
	mov	x19, x0
	mov	x0, x20
	bl	_rc_drop
	mov	x20, x0
Lloh110:
	adrp	x8, _rc_pending_count@PAGE
Lloh111:
	ldr	x8, [x8, _rc_pending_count@PAGEOFF]
	adrp	x21, _rc_bounded_last_work@PAGE
	cbz	x8, LBB51_5
; %bb.4:
	mov	w8, #32                         ; =0x20
	sub	w0, w8, w20
	bl	_minyar_rc_poll
	ldr	x8, [x21, _rc_bounded_last_work@PAGEOFF]
LBB51_5:
	add	x8, x8, w20, uxtw
	str	x8, [x21, _rc_bounded_last_work@PAGEOFF]
	mov	x0, x19
LBB51_6:
	ldp	x29, x30, [sp, #48]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp, #32]             ; 16-byte Folded Reload
	ldp	x22, x21, [sp, #16]             ; 16-byte Folded Reload
	ldp	x24, x23, [sp], #64             ; 16-byte Folded Reload
	ret
LBB51_7:
	add	x22, x19, x21
	ldr	x20, [x0]
	add	x8, x22, #1
	ldur	x9, [x20, #-8]
	cmp	x8, x9
	mov	x23, x0
	mov	x24, x1
	b.ls	LBB51_9
; %bb.8:
	lsl	x10, x9, #1
	cmp	x9, #0
	csinv	x9, x10, xzr, ge
	cmp	x9, x8
	csel	x1, x9, x8, hi
	mov	x0, x20
	bl	_rc_reallocate_data
	mov	x1, x24
	mov	x20, x0
	mov	x0, x23
LBB51_9:
	mov	x8, x20
	cmp	x1, x0
	b.eq	LBB51_11
; %bb.10:
	ldr	x8, [x1]
LBB51_11:
	add	x9, x20, x21
	cmp	x19, #17
	b.lo	LBB51_13
; %bb.12:
	mov	x0, x9
	mov	x1, x8
	mov	x2, x19
	bl	_memcpy
	mov	x1, x24
	mov	x0, x23
	b	LBB51_21
LBB51_13:
	cmp	x19, #8
	b.lo	LBB51_15
; %bb.14:
	ldr	x10, [x8]
	add	x8, x8, x19
	ldur	x8, [x8, #-8]
	str	x10, [x9]
	add	x9, x9, x19
	stur	x8, [x9, #-8]
	b	LBB51_21
LBB51_15:
	cmp	x19, #4
	b.lo	LBB51_17
; %bb.16:
	ldr	w10, [x8]
	add	x8, x8, x19
	ldur	w8, [x8, #-4]
	str	w10, [x9]
	add	x9, x9, x19
	stur	w8, [x9, #-4]
	b	LBB51_21
LBB51_17:
	cmp	x19, #2
	b.lo	LBB51_19
; %bb.18:
	ldrh	w10, [x8]
	add	x8, x8, x19
	ldurh	w8, [x8, #-2]
	strh	w10, [x9]
	add	x9, x9, x19
	sturh	w8, [x9, #-2]
	b	LBB51_21
LBB51_19:
	cmp	x19, #1
	b.ne	LBB51_21
; %bb.20:
	ldrb	w8, [x8]
	strb	w8, [x9]
LBB51_21:
	strb	wzr, [x20, x22]
	ldr	x8, [x0, #24]
	cbz	x8, LBB51_23
; %bb.22:
	ldr	x9, [x8, #-8]!
	adrp	x10, _rc_bytes@PAGE
	ldr	x11, [x10, _rc_bytes@PAGEOFF]
	sub	x9, x11, x9
	sub	x9, x9, #8
	str	x9, [x10, _rc_bytes@PAGEOFF]
	adrp	x9, _rc_heap_allocation_count@PAGE
	ldr	x10, [x9, _rc_heap_allocation_count@PAGEOFF]
	sub	x10, x10, #1
	str	x10, [x9, _rc_heap_allocation_count@PAGEOFF]
	mov	x0, x8
	bl	_free
	mov	x1, x24
	mov	x0, x23
LBB51_23:
	stp	x20, x22, [x0]
	ldr	x8, [x0, #16]
	cmp	x8, x21
	b.ne	LBB51_25
; %bb.24:
	ldr	x8, [x1, #16]
	cmp	x8, x19
	b.eq	LBB51_26
LBB51_25:
	mov	x22, #-1                        ; =0xffffffffffffffff
LBB51_26:
	stp	x22, xzr, [x0, #16]
	b	LBB51_6
LBB51_27:
	bl	_join_too_large
	.loh AdrpLdr	Lloh110, Lloh111
	.cfi_endproc
                                        ; -- End function
	.p2align	2                               ; -- Begin function rc_reallocate_data
_rc_reallocate_data:                    ; @rc_reallocate_data
	.cfi_startproc
; %bb.0:
	stp	x22, x21, [sp, #-48]!           ; 16-byte Folded Spill
	stp	x20, x19, [sp, #16]             ; 16-byte Folded Spill
	stp	x29, x30, [sp, #32]             ; 16-byte Folded Spill
	add	x29, sp, #32
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
	.cfi_offset w19, -24
	.cfi_offset w20, -32
	.cfi_offset w21, -40
	.cfi_offset w22, -48
	mov	x19, x1
Lloh112:
	adrp	x8, _rc_pending_count@PAGE
Lloh113:
	ldr	x8, [x8, _rc_pending_count@PAGEOFF]
	adrp	x21, _rc_bytes@PAGE
	cbz	x0, LBB52_3
; %bb.1:
	cbz	x8, LBB52_5
; %bb.2:
	mov	x20, x0
	mov	w0, #32                         ; =0x20
	bl	_minyar_rc_poll
	mov	x0, x20
	cmn	x19, #8
	b.lo	LBB52_6
	b	LBB52_12
LBB52_3:
	cbz	x8, LBB52_8
; %bb.4:
	mov	w0, #32                         ; =0x20
	bl	_minyar_rc_poll
	cmn	x19, #8
	b.lo	LBB52_9
	b	LBB52_12
LBB52_5:
	adrp	x8, _rc_bounded_last_work@PAGE
	str	xzr, [x8, _rc_bounded_last_work@PAGEOFF]
	cmn	x19, #8
	b.hs	LBB52_12
LBB52_6:
	ldr	x8, [x0, #-8]!
	ldr	x9, [x21, _rc_bytes@PAGEOFF]
	sub	x20, x9, x8
	str	x20, [x21, _rc_bytes@PAGEOFF]
	add	x1, x19, #8
	bl	_realloc
	cbz	x0, LBB52_12
; %bb.7:
	str	x19, [x0]
	add	x8, x20, x19
	b	LBB52_11
LBB52_8:
	adrp	x8, _rc_bounded_last_work@PAGE
	str	xzr, [x8, _rc_bounded_last_work@PAGEOFF]
	cmn	x19, #8
	b.hs	LBB52_12
LBB52_9:
	add	x20, x19, #8
	mov	x0, x20
	bl	_malloc
	cbz	x0, LBB52_12
; %bb.10:
	adrp	x8, _rc_heap_allocation_count@PAGE
	ldr	x9, [x8, _rc_heap_allocation_count@PAGEOFF]
	add	x9, x9, #1
	str	x9, [x8, _rc_heap_allocation_count@PAGEOFF]
	str	x19, [x0]
	ldr	x8, [x21, _rc_bytes@PAGEOFF]
	add	x8, x8, x20
LBB52_11:
	str	x8, [x21, _rc_bytes@PAGEOFF]
	add	x0, x0, #8
	ldp	x29, x30, [sp, #32]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp, #16]             ; 16-byte Folded Reload
	ldp	x22, x21, [sp], #48             ; 16-byte Folded Reload
	ret
LBB52_12:
	bl	_out_of_memory
	.loh AdrpLdr	Lloh112, Lloh113
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_join_texts              ; -- Begin function minyar_join_texts
	.p2align	2
_minyar_join_texts:                     ; @minyar_join_texts
	.cfi_startproc
; %bb.0:
	stp	x28, x27, [sp, #-96]!           ; 16-byte Folded Spill
	stp	x26, x25, [sp, #16]             ; 16-byte Folded Spill
	stp	x24, x23, [sp, #32]             ; 16-byte Folded Spill
	stp	x22, x21, [sp, #48]             ; 16-byte Folded Spill
	stp	x20, x19, [sp, #64]             ; 16-byte Folded Spill
	stp	x29, x30, [sp, #80]             ; 16-byte Folded Spill
	add	x29, sp, #80
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
	.cfi_offset w19, -24
	.cfi_offset w20, -32
	.cfi_offset w21, -40
	.cfi_offset w22, -48
	.cfi_offset w23, -56
	.cfi_offset w24, -64
	.cfi_offset w25, -72
	.cfi_offset w26, -80
	.cfi_offset w27, -88
	.cfi_offset w28, -96
	mov	x20, x0
	ldr	x8, [x0, #8]
	cmp	x8, #1
	b.lt	LBB53_4
; %bb.1:
	mov	x22, #0                         ; =0x0
	ldr	x9, [x20]
LBB53_2:                                ; =>This Inner Loop Header: Depth=1
	ldr	x10, [x9], #8
	ldr	x10, [x10, #8]
	eor	x11, x22, #0x7fffffffffffffff
	cmp	x10, x11
	b.gt	LBB53_27
; %bb.3:                                ;   in Loop: Header=BB53_2 Depth=1
	add	x22, x10, x22
	subs	x8, x8, #1
	b.ne	LBB53_2
	b	LBB53_5
LBB53_4:
	mov	x22, #0                         ; =0x0
LBB53_5:
	add	x23, x22, #1
	adrp	x24, _rc_pending_count@PAGE
	ldr	x8, [x24, _rc_pending_count@PAGEOFF]
	cbz	x8, LBB53_7
; %bb.6:
	mov	w0, #32                         ; =0x20
	bl	_minyar_rc_poll
	cmn	x23, #8
	b.lo	LBB53_8
	b	LBB53_28
LBB53_7:
	adrp	x8, _rc_bounded_last_work@PAGE
	str	xzr, [x8, _rc_bounded_last_work@PAGEOFF]
	cmn	x23, #8
	b.hs	LBB53_28
LBB53_8:
	add	x21, x22, #9
	mov	x0, x21
	bl	_malloc
	cbz	x0, LBB53_28
; %bb.9:
	mov	x19, x0
	adrp	x25, _rc_heap_allocation_count@PAGE
	ldr	x8, [x25, _rc_heap_allocation_count@PAGEOFF]
	add	x8, x8, #1
	str	x8, [x25, _rc_heap_allocation_count@PAGEOFF]
	str	x23, [x19], #8
	adrp	x23, _rc_bytes@PAGE
	ldr	x8, [x23, _rc_bytes@PAGEOFF]
	add	x8, x8, x21
	str	x8, [x23, _rc_bytes@PAGEOFF]
	ldr	x21, [x20, #8]
	cmp	x21, #1
	b.lt	LBB53_22
; %bb.10:
	mov	x26, #0                         ; =0x0
	ldr	x20, [x20]
	b	LBB53_13
LBB53_11:                               ;   in Loop: Header=BB53_13 Depth=1
	bl	_memcpy
LBB53_12:                               ;   in Loop: Header=BB53_13 Depth=1
	ldr	x8, [x27, #8]
	add	x26, x8, x26
	subs	x21, x21, #1
	b.eq	LBB53_22
LBB53_13:                               ; =>This Inner Loop Header: Depth=1
	ldr	x27, [x20], #8
	add	x0, x19, x26
	ldp	x1, x2, [x27]
	cmp	x2, #17
	b.hs	LBB53_11
; %bb.14:                               ;   in Loop: Header=BB53_13 Depth=1
	cmp	x2, #8
	b.lo	LBB53_16
; %bb.15:                               ;   in Loop: Header=BB53_13 Depth=1
	ldr	x8, [x1]
	add	x9, x1, x2
	ldur	x9, [x9, #-8]
	str	x8, [x0]
	add	x8, x0, x2
	stur	x9, [x8, #-8]
	b	LBB53_12
LBB53_16:                               ;   in Loop: Header=BB53_13 Depth=1
	cmp	x2, #4
	b.lo	LBB53_18
; %bb.17:                               ;   in Loop: Header=BB53_13 Depth=1
	ldr	w8, [x1]
	add	x9, x1, x2
	ldur	w9, [x9, #-4]
	str	w8, [x0]
	add	x8, x0, x2
	stur	w9, [x8, #-4]
	b	LBB53_12
LBB53_18:                               ;   in Loop: Header=BB53_13 Depth=1
	cmp	x2, #2
	b.lo	LBB53_20
; %bb.19:                               ;   in Loop: Header=BB53_13 Depth=1
	ldrh	w8, [x1]
	add	x9, x1, x2
	ldurh	w9, [x9, #-2]
	strh	w8, [x0]
	add	x8, x0, x2
	sturh	w9, [x8, #-2]
	b	LBB53_12
LBB53_20:                               ;   in Loop: Header=BB53_13 Depth=1
	cmp	x2, #1
	b.ne	LBB53_12
; %bb.21:                               ;   in Loop: Header=BB53_13 Depth=1
	ldrb	w8, [x1]
	strb	w8, [x0]
	b	LBB53_12
LBB53_22:
	strb	wzr, [x19, x22]
	ldr	x8, [x24, _rc_pending_count@PAGEOFF]
	cbz	x8, LBB53_24
; %bb.23:
	mov	w0, #32                         ; =0x20
	bl	_minyar_rc_poll
	b	LBB53_25
LBB53_24:
	adrp	x8, _rc_bounded_last_work@PAGE
	str	xzr, [x8, _rc_bounded_last_work@PAGEOFF]
LBB53_25:
	mov	w0, #48                         ; =0x30
	bl	_malloc
	cbz	x0, LBB53_28
; %bb.26:
	ldr	x8, [x25, _rc_heap_allocation_count@PAGEOFF]
	add	x8, x8, #1
	str	x8, [x25, _rc_heap_allocation_count@PAGEOFF]
	mov	w8, #9                          ; =0x9
	str	x8, [x0]
	adrp	x8, _rc_object_count@PAGE
	ldr	x9, [x8, _rc_object_count@PAGEOFF]
	add	x9, x9, #1
	str	x9, [x8, _rc_object_count@PAGEOFF]
	ldr	x8, [x23, _rc_bytes@PAGEOFF]
	add	x8, x8, #48
	str	x8, [x23, _rc_bytes@PAGEOFF]
	mov	x8, x0
	str	x19, [x8, #8]!
	mov	x9, #-1                         ; =0xffffffffffffffff
	stp	x22, x9, [x0, #16]
	stp	xzr, xzr, [x0, #32]
	mov	x0, x8
	ldp	x29, x30, [sp, #80]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp, #64]             ; 16-byte Folded Reload
	ldp	x22, x21, [sp, #48]             ; 16-byte Folded Reload
	ldp	x24, x23, [sp, #32]             ; 16-byte Folded Reload
	ldp	x26, x25, [sp, #16]             ; 16-byte Folded Reload
	ldp	x28, x27, [sp], #96             ; 16-byte Folded Reload
	ret
LBB53_27:
	bl	_join_too_large
LBB53_28:
	bl	_out_of_memory
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_text_length             ; -- Begin function minyar_text_length
	.p2align	2
_minyar_text_length:                    ; @minyar_text_length
	.cfi_startproc
; %bb.0:
	stp	x20, x19, [sp, #-32]!           ; 16-byte Folded Spill
	stp	x29, x30, [sp, #16]             ; 16-byte Folded Spill
	add	x29, sp, #16
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
	.cfi_offset w19, -24
	.cfi_offset w20, -32
	mov	x19, x0
	ldr	x0, [x0, #16]
	tbnz	x0, #63, LBB54_2
LBB54_1:
	ldp	x29, x30, [sp, #16]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp], #32             ; 16-byte Folded Reload
	ret
LBB54_2:
	mov	x0, x19
	bl	_build_text_index
	ldr	x0, [x19, #16]
	b	LBB54_1
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_text_byte_length        ; -- Begin function minyar_text_byte_length
	.p2align	2
_minyar_text_byte_length:               ; @minyar_text_byte_length
	.cfi_startproc
; %bb.0:
	ldr	x0, [x0, #8]
	ret
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_text_character_at       ; -- Begin function minyar_text_character_at
	.p2align	2
_minyar_text_character_at:              ; @minyar_text_character_at
	.cfi_startproc
; %bb.0:
	ldr	x8, [x0, #16]
	tbnz	x8, #63, LBB56_4
; %bb.1:
	cmp	x8, x1
	b.ls	LBB56_4
; %bb.2:
	ldr	x8, [x0, #24]
	cbnz	x8, LBB56_5
; %bb.3:
	ldr	x8, [x0]
	ldrb	w0, [x8, x1]
	ret
LBB56_4:
	b	_character_at_slowly
LBB56_5:
	b	_indexed_character_at
	.cfi_endproc
                                        ; -- End function
	.p2align	2                               ; -- Begin function character_at_slowly
_character_at_slowly:                   ; @character_at_slowly
	.cfi_startproc
; %bb.0:
	stp	x20, x19, [sp, #-32]!           ; 16-byte Folded Spill
	stp	x29, x30, [sp, #16]             ; 16-byte Folded Spill
	add	x29, sp, #16
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
	.cfi_offset w19, -24
	.cfi_offset w20, -32
	tbnz	x1, #63, LBB57_7
; %bb.1:
	mov	x19, x1
	mov	x20, x0
	ldr	x8, [x0, #16]
	tbnz	x8, #63, LBB57_5
LBB57_2:
	cmp	x8, x19
	b.le	LBB57_8
; %bb.3:
	ldr	x8, [x20, #24]
	cbnz	x8, LBB57_6
; %bb.4:
	ldr	x8, [x20]
	ldrb	w0, [x8, x19]
	ldp	x29, x30, [sp, #16]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp], #32             ; 16-byte Folded Reload
	ret
LBB57_5:
	mov	x0, x20
	bl	_build_text_index
	ldr	x8, [x20, #16]
	b	LBB57_2
LBB57_6:
	mov	x0, x20
	mov	x1, x19
	ldp	x29, x30, [sp, #16]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp], #32             ; 16-byte Folded Reload
	b	_indexed_character_at
LBB57_7:
	bl	_negative_text_position
LBB57_8:
	bl	_position_outside_text
	.cfi_endproc
                                        ; -- End function
	.p2align	2                               ; -- Begin function indexed_character_at
_indexed_character_at:                  ; @indexed_character_at
	.cfi_startproc
; %bb.0:
	sub	sp, sp, #64
	stp	x22, x21, [sp, #16]             ; 16-byte Folded Spill
	stp	x20, x19, [sp, #32]             ; 16-byte Folded Spill
	stp	x29, x30, [sp, #48]             ; 16-byte Folded Spill
	add	x29, sp, #48
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
	.cfi_offset w19, -24
	.cfi_offset w20, -32
	.cfi_offset w21, -40
	.cfi_offset w22, -48
	mov	x21, x1
	mov	x20, x0
	bl	_indexed_byte_offset
	mov	x19, x0
	ldp	x8, x9, [x20]
	sub	x1, x9, x0
	add	x0, x8, x0
	bl	_OUTLINED_FUNCTION_1
	adrp	x8, _text_decode_count@PAGE
	ldr	x9, [x8, _text_decode_count@PAGEOFF]
	add	x9, x9, #1
	str	x9, [x8, _text_decode_count@PAGEOFF]
	mov	w8, #64                         ; =0x40
	ldp	x12, x9, [x20, #8]
	sdiv	x11, x9, x8
	add	x9, x11, #1
	add	x10, x21, #1
	mov	w8, #-1                         ; =0xffffffff
	cmp	x12, x8
	b.gt	LBB58_2
; %bb.1:
	ldr	x8, [x20, #24]
	str	w10, [x8, x9, lsl #2]
	add	x9, x11, #2
	ldr	x10, [sp, #8]
	add	x10, x10, x19
	b	LBB58_3
LBB58_2:
	ldr	x8, [x20, #24]
	str	x10, [x8, x9, lsl #3]
	ldp	x11, x9, [x20, #8]
	mov	w10, #64                        ; =0x40
	sdiv	x9, x9, x10
	add	x9, x9, #2
	ldr	x10, [sp, #8]
	add	x10, x10, x19
	mov	w12, #-1                        ; =0xffffffff
	cmp	x11, x12
	b.gt	LBB58_4
LBB58_3:
	str	w10, [x8, x9, lsl #2]
	b	LBB58_5
LBB58_4:
	str	x10, [x8, x9, lsl #3]
LBB58_5:
	ldp	x29, x30, [sp, #48]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp, #32]             ; 16-byte Folded Reload
	ldp	x22, x21, [sp, #16]             ; 16-byte Folded Reload
	add	sp, sp, #64
	ret
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_text_slice              ; -- Begin function minyar_text_slice
	.p2align	2
_minyar_text_slice:                     ; @minyar_text_slice
	.cfi_startproc
; %bb.0:
	stp	x28, x27, [sp, #-96]!           ; 16-byte Folded Spill
	stp	x26, x25, [sp, #16]             ; 16-byte Folded Spill
	stp	x24, x23, [sp, #32]             ; 16-byte Folded Spill
	stp	x22, x21, [sp, #48]             ; 16-byte Folded Spill
	stp	x20, x19, [sp, #64]             ; 16-byte Folded Spill
	stp	x29, x30, [sp, #80]             ; 16-byte Folded Spill
	add	x29, sp, #80
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
	.cfi_offset w19, -24
	.cfi_offset w20, -32
	.cfi_offset w21, -40
	.cfi_offset w22, -48
	.cfi_offset w23, -56
	.cfi_offset w24, -64
	.cfi_offset w25, -72
	.cfi_offset w26, -80
	.cfi_offset w27, -88
	.cfi_offset w28, -96
	mov	x19, x2
	mov	x21, x1
	mov	x20, x0
	ldr	x8, [x0, #16]
	tbnz	x8, #63, LBB59_29
; %bb.1:
	tbnz	x21, #63, LBB59_30
LBB59_2:
	subs	x24, x19, x21
	b.lt	LBB59_30
; %bb.3:
	ldr	x8, [x20, #16]
	cmp	x8, x19
	b.lt	LBB59_30
; %bb.4:
	ldr	x8, [x20, #24]
	cbz	x8, LBB59_6
; %bb.5:
	mov	x0, x20
	mov	x1, x21
	bl	_indexed_byte_offset
	mov	x21, x0
	mov	x0, x20
	mov	x1, x19
	bl	_indexed_byte_offset
	mov	x19, x0
LBB59_6:
	sub	x19, x19, x21
	ldr	x8, [x20, #32]
	cmp	x8, #0
	csel	x22, x20, x8, eq
	cbnz	x21, LBB59_11
; %bb.7:
	ldr	x8, [x20, #8]
	cmp	x19, x8
	b.ne	LBB59_11
; %bb.8:
	ldur	x8, [x20, #-8]
	cmp	x8, #8
	b.lo	LBB59_28
; %bb.9:
	cmn	x8, #8
	b.hs	LBB59_33
; %bb.10:
	add	x8, x8, #8
	stur	x8, [x20, #-8]
	b	LBB59_28
LBB59_11:
	ldr	x8, [x22, #8]
	lsl	x9, x19, #3
	cmp	x8, #1, lsl #12                 ; =4096
	ccmp	x9, x8, #2, gt
	b.lo	LBB59_14
; %bb.12:
	ldr	x20, [x20]
	cmp	x19, x24
	csinv	x23, x24, xzr, eq
Lloh114:
	adrp	x8, _rc_pending_count@PAGE
Lloh115:
	ldr	x8, [x8, _rc_pending_count@PAGEOFF]
	cbz	x8, LBB59_16
; %bb.13:
	mov	w0, #32                         ; =0x20
	bl	_minyar_rc_poll
	b	LBB59_17
LBB59_14:
	add	x25, x19, #1
	adrp	x26, _rc_pending_count@PAGE
	ldr	x8, [x26, _rc_pending_count@PAGEOFF]
	cbz	x8, LBB59_21
; %bb.15:
	mov	w0, #32                         ; =0x20
	bl	_minyar_rc_poll
	cmn	x25, #8
	b.lo	LBB59_22
	b	LBB59_31
LBB59_16:
	adrp	x8, _rc_bounded_last_work@PAGE
	str	xzr, [x8, _rc_bounded_last_work@PAGEOFF]
LBB59_17:
	mov	w0, #48                         ; =0x30
	bl	_malloc
	cbz	x0, LBB59_31
; %bb.18:
	add	x8, x20, x21
	adrp	x9, _rc_heap_allocation_count@PAGE
	ldr	x10, [x9, _rc_heap_allocation_count@PAGEOFF]
	add	x10, x10, #1
	str	x10, [x9, _rc_heap_allocation_count@PAGEOFF]
	mov	w9, #9                          ; =0x9
	str	x9, [x0]
Lloh116:
	adrp	x9, _rc_object_count@PAGE
	ldr	x10, [x9, _rc_object_count@PAGEOFF]
	add	x10, x10, #1
	str	x10, [x9, _rc_object_count@PAGEOFF]
Lloh117:
	adrp	x9, _rc_bytes@PAGE
	ldr	x10, [x9, _rc_bytes@PAGEOFF]
	add	x10, x10, #48
	str	x10, [x9, _rc_bytes@PAGEOFF]
	mov	x20, x0
	str	x8, [x20, #8]!
	stp	x19, x23, [x0, #16]
	stp	xzr, x22, [x0, #32]
	ldur	x8, [x22, #-8]
	cmp	x8, #8
	b.lo	LBB59_28
; %bb.19:
	cmn	x8, #8
	b.hs	LBB59_32
; %bb.20:
	add	x8, x8, #8
	stur	x8, [x22, #-8]
	b	LBB59_28
LBB59_21:
	adrp	x8, _rc_bounded_last_work@PAGE
	str	xzr, [x8, _rc_bounded_last_work@PAGEOFF]
	cmn	x25, #8
	b.hs	LBB59_31
LBB59_22:
	add	x23, x19, #9
	mov	x0, x23
	bl	_malloc
	cbz	x0, LBB59_31
; %bb.23:
	mov	x22, x0
	adrp	x27, _rc_heap_allocation_count@PAGE
	ldr	x8, [x27, _rc_heap_allocation_count@PAGEOFF]
	add	x8, x8, #1
	str	x25, [x22], #8
	str	x8, [x27, _rc_heap_allocation_count@PAGEOFF]
	adrp	x25, _rc_bytes@PAGE
	ldr	x8, [x25, _rc_bytes@PAGEOFF]
	add	x8, x8, x23
	str	x8, [x25, _rc_bytes@PAGEOFF]
	ldr	x8, [x20]
	add	x1, x8, x21
	mov	x0, x22
	mov	x2, x19
	bl	_memcpy
	strb	wzr, [x22, x19]
	cmp	x19, x24
	csinv	x21, x24, xzr, eq
	ldr	x8, [x26, _rc_pending_count@PAGEOFF]
	cbz	x8, LBB59_25
; %bb.24:
	mov	w0, #32                         ; =0x20
	bl	_minyar_rc_poll
	b	LBB59_26
LBB59_25:
	adrp	x8, _rc_bounded_last_work@PAGE
	str	xzr, [x8, _rc_bounded_last_work@PAGEOFF]
LBB59_26:
	mov	w0, #48                         ; =0x30
	bl	_malloc
	cbz	x0, LBB59_31
; %bb.27:
	ldr	x8, [x27, _rc_heap_allocation_count@PAGEOFF]
	add	x8, x8, #1
	str	x8, [x27, _rc_heap_allocation_count@PAGEOFF]
	mov	w8, #9                          ; =0x9
	str	x8, [x0]
	adrp	x8, _rc_object_count@PAGE
	ldr	x9, [x8, _rc_object_count@PAGEOFF]
	add	x9, x9, #1
	str	x9, [x8, _rc_object_count@PAGEOFF]
	ldr	x8, [x25, _rc_bytes@PAGEOFF]
	add	x8, x8, #48
	str	x8, [x25, _rc_bytes@PAGEOFF]
	mov	x20, x0
	str	x22, [x20, #8]!
	stp	x19, x21, [x0, #16]
	stp	xzr, xzr, [x0, #32]
LBB59_28:
	mov	x0, x20
	ldp	x29, x30, [sp, #80]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp, #64]             ; 16-byte Folded Reload
	ldp	x22, x21, [sp, #48]             ; 16-byte Folded Reload
	ldp	x24, x23, [sp, #32]             ; 16-byte Folded Reload
	ldp	x26, x25, [sp, #16]             ; 16-byte Folded Reload
	ldp	x28, x27, [sp], #96             ; 16-byte Folded Reload
	ret
LBB59_29:
	mov	x0, x20
	bl	_build_text_index
	tbz	x21, #63, LBB59_2
LBB59_30:
	bl	_slice_outside_text
LBB59_31:
	bl	_out_of_memory
LBB59_32:
	bl	_minyar_text_slice.cold.1
LBB59_33:
	bl	_minyar_text_slice.cold.2
	.loh AdrpLdr	Lloh114, Lloh115
	.loh AdrpAdrp	Lloh116, Lloh117
	.cfi_endproc
                                        ; -- End function
	.p2align	2                               ; -- Begin function slice_outside_text
_slice_outside_text:                    ; @slice_outside_text
	.cfi_startproc
; %bb.0:
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
Lloh118:
	adrp	x0, l_.str.57@PAGE
Lloh119:
	add	x0, x0, l_.str.57@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh118, Lloh119
	.cfi_endproc
                                        ; -- End function
	.p2align	2                               ; -- Begin function indexed_byte_offset
_indexed_byte_offset:                   ; @indexed_byte_offset
	.cfi_startproc
; %bb.0:
	sub	sp, sp, #96
	stp	x26, x25, [sp, #16]             ; 16-byte Folded Spill
	stp	x24, x23, [sp, #32]             ; 16-byte Folded Spill
	stp	x22, x21, [sp, #48]             ; 16-byte Folded Spill
	stp	x20, x19, [sp, #64]             ; 16-byte Folded Spill
	stp	x29, x30, [sp, #80]             ; 16-byte Folded Spill
	add	x29, sp, #80
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
	.cfi_offset w19, -24
	.cfi_offset w20, -32
	.cfi_offset w21, -40
	.cfi_offset w22, -48
	.cfi_offset w23, -56
	.cfi_offset w24, -64
	.cfi_offset w25, -72
	.cfi_offset w26, -80
	mov	x19, x1
	mov	x20, x0
	lsr	x10, x1, #6
	and	x9, x1, #0xffffffffffffffc0
	ldr	x8, [x0, #8]
	ldr	x11, [x0, #24]
	mov	w12, #-1                        ; =0xffffffff
	cmp	x8, x12
	b.gt	LBB61_2
; %bb.1:
	ldr	w23, [x11, x10, lsl #2]
	ldr	x10, [x20, #16]
	add	x12, x10, #63
	cmp	x10, #0
	csel	x10, x12, x10, lt
	asr	x12, x10, #6
	add	x22, x12, #1
	ldr	w10, [x11, x22, lsl #2]
	add	x21, x12, #2
	ldr	w0, [x11, x21, lsl #2]
	b	LBB61_3
LBB61_2:
	ldr	x23, [x11, x10, lsl #3]
	ldr	x10, [x20, #16]
	add	x12, x10, #63
	cmp	x10, #0
	csel	x10, x12, x10, lt
	asr	x12, x10, #6
	add	x22, x12, #1
	ldr	x10, [x11, x22, lsl #3]
	add	x21, x12, #2
	ldr	x0, [x11, x21, lsl #3]
LBB61_3:
	cmp	x10, x9
	cset	w11, ge
	cmp	x10, x19
	cset	w12, le
	tst	w11, w12
	csel	x11, x0, x23, ne
	csel	x12, x10, x9, ne
	subs	x13, x10, x19
	b.gt	LBB61_5
; %bb.4:
	mov	x23, x11
	mov	x9, x12
	b	LBB61_6
LBB61_5:
	and	x11, x19, #0x3f
	cmp	x13, x11
	b.le	LBB61_11
LBB61_6:
	subs	x24, x19, x9
	b.le	LBB61_10
; %bb.7:
	adrp	x25, _text_decode_count@PAGE
LBB61_8:                                ; =>This Inner Loop Header: Depth=1
	ldp	x8, x9, [x20]
	sub	x1, x9, x23
	add	x0, x8, x23
	add	x2, sp, #8
	bl	_decode_character
	ldr	x8, [x25, _text_decode_count@PAGEOFF]
	add	x8, x8, #1
	str	x8, [x25, _text_decode_count@PAGEOFF]
	ldr	x8, [sp, #8]
	add	x23, x8, x23
	subs	x24, x24, #1
	b.ne	LBB61_8
; %bb.9:
	ldr	x8, [x20, #8]
LBB61_10:
	mov	x0, x23
	b	LBB61_15
LBB61_11:
	adrp	x9, _text_decode_count@PAGE
	ldr	x11, [x9, _text_decode_count@PAGEOFF]
	ldr	x12, [x20]
	add	x11, x10, x11
	sub	x12, x12, #1
LBB61_12:                               ; =>This Inner Loop Header: Depth=1
	ldrb	w13, [x12, x0]
	sub	x0, x0, #1
	and	w13, w13, #0xc0
	cmp	w13, #128
	b.eq	LBB61_12
; %bb.13:                               ;   in Loop: Header=BB61_12 Depth=1
	sub	x10, x10, #1
	cmp	x10, x19
	b.gt	LBB61_12
; %bb.14:
	sub	x10, x11, x19
	str	x10, [x9, _text_decode_count@PAGEOFF]
LBB61_15:
	mov	w9, #-1                         ; =0xffffffff
	cmp	x8, x9
	b.gt	LBB61_17
; %bb.16:
	ldr	x8, [x20, #24]
	str	w19, [x8, x22, lsl #2]
	str	w0, [x8, x21, lsl #2]
	b	LBB61_20
LBB61_17:
	ldr	x8, [x20, #24]
	str	x19, [x8, x22, lsl #3]
	ldr	x9, [x20, #8]
	mov	w10, #-1                        ; =0xffffffff
	cmp	x9, x10
	b.gt	LBB61_19
; %bb.18:
	str	w0, [x8, x21, lsl #2]
	b	LBB61_20
LBB61_19:
	str	x0, [x8, x21, lsl #3]
LBB61_20:
	ldp	x29, x30, [sp, #80]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp, #64]             ; 16-byte Folded Reload
	ldp	x22, x21, [sp, #48]             ; 16-byte Folded Reload
	ldp	x24, x23, [sp, #32]             ; 16-byte Folded Reload
	ldp	x26, x25, [sp, #16]             ; 16-byte Folded Reload
	add	sp, sp, #96
	ret
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_integer_text            ; -- Begin function minyar_integer_text
	.p2align	2
_minyar_integer_text:                   ; @minyar_integer_text
	.cfi_startproc
; %bb.0:
	stp	x20, x19, [sp, #-32]!           ; 16-byte Folded Spill
	stp	x29, x30, [sp, #16]             ; 16-byte Folded Spill
	add	x29, sp, #16
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
	.cfi_offset w19, -24
	.cfi_offset w20, -32
	mov	x19, x0
	lsr	x9, x0, #15
	cbnz	x9, LBB62_3
; %bb.1:
Lloh120:
	adrp	x20, _minyar_integer_text.integer_cache@PAGE
Lloh121:
	add	x20, x20, _minyar_integer_text.integer_cache@PAGEOFF
	ldr	x0, [x20, x19, lsl #3]
	cbz	x0, LBB62_4
LBB62_2:
	ldp	x29, x30, [sp, #16]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp], #32             ; 16-byte Folded Reload
	ret
LBB62_3:
	mov	x0, x19
	ldp	x29, x30, [sp, #16]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp], #32             ; 16-byte Folded Reload
	b	_format_integer_text
LBB62_4:
	mov	x0, x19
	bl	_format_integer_text
	str	x0, [x20, x19, lsl #3]
	mov	w8, #1                          ; =0x1
	stur	x8, [x0, #-8]
	adrp	x8, _rc_immortal_object_count@PAGE
	ldr	x9, [x8, _rc_immortal_object_count@PAGEOFF]
	add	x9, x9, #1
	str	x9, [x8, _rc_immortal_object_count@PAGEOFF]
	b	LBB62_2
	.loh AdrpAdd	Lloh120, Lloh121
	.cfi_endproc
                                        ; -- End function
	.p2align	2                               ; -- Begin function format_integer_text
_format_integer_text:                   ; @format_integer_text
	.cfi_startproc
; %bb.0:
	sub	sp, sp, #96
	stp	x22, x21, [sp, #48]             ; 16-byte Folded Spill
	stp	x20, x19, [sp, #64]             ; 16-byte Folded Spill
	stp	x29, x30, [sp, #80]             ; 16-byte Folded Spill
	add	x29, sp, #80
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
	.cfi_offset w19, -24
	.cfi_offset w20, -32
	.cfi_offset w21, -40
	.cfi_offset w22, -48
Lloh122:
	adrp	x8, ___stack_chk_guard@GOTPAGE
Lloh123:
	ldr	x8, [x8, ___stack_chk_guard@GOTPAGEOFF]
Lloh124:
	ldr	x8, [x8]
	str	x8, [sp, #40]
	add	x10, sp, #8
	add	x8, x10, #32
	cmp	x0, #0
	cneg	x9, x0, mi
	add	x19, x10, #31
	mov	w10, #10                        ; =0xa
LBB63_1:                                ; =>This Inner Loop Header: Depth=1
	udiv	x11, x9, x10
	msub	w12, w11, w10, w9
	orr	w12, w12, #0x30
	strb	w12, [x19], #-1
	cmp	x9, #9
	mov	x9, x11
	b.hi	LBB63_1
; %bb.2:
	tbnz	x0, #63, LBB63_4
; %bb.3:
	add	x19, x19, #1
	b	LBB63_5
LBB63_4:
	mov	w9, #45                         ; =0x2d
	strb	w9, [x19]
LBB63_5:
	sub	x20, x8, x19
	add	x0, x20, #1
	bl	_rc_allocate_data
	mov	x21, x0
	mov	x1, x19
	mov	x2, x20
	bl	_memcpy
	strb	wzr, [x21, x20]
	bl	_OUTLINED_FUNCTION_3
	stp	x21, x20, [x0]
	stp	xzr, xzr, [x0, #24]
	str	x20, [x0, #16]
	ldr	x8, [sp, #40]
Lloh125:
	adrp	x9, ___stack_chk_guard@GOTPAGE
Lloh126:
	ldr	x9, [x9, ___stack_chk_guard@GOTPAGEOFF]
Lloh127:
	ldr	x9, [x9]
	cmp	x9, x8
	b.ne	LBB63_7
; %bb.6:
	ldp	x29, x30, [sp, #80]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp, #64]             ; 16-byte Folded Reload
	ldp	x22, x21, [sp, #48]             ; 16-byte Folded Reload
	add	sp, sp, #96
	ret
LBB63_7:
	bl	___stack_chk_fail
	.loh AdrpLdrGotLdr	Lloh122, Lloh123, Lloh124
	.loh AdrpLdrGotLdr	Lloh125, Lloh126, Lloh127
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_character_text          ; -- Begin function minyar_character_text
	.p2align	2
_minyar_character_text:                 ; @minyar_character_text
	.cfi_startproc
; %bb.0:
	cmp	w0, #127
	b.hi	LBB64_4
; %bb.1:
Lloh128:
	adrp	x8, _minyar_character_text.ascii_texts@PAGE
Lloh129:
	add	x8, x8, _minyar_character_text.ascii_texts@PAGEOFF
	mov	w9, #48                         ; =0x30
	umaddl	x8, w0, w9, x8
	ldr	x9, [x8, #16]
	cbz	x9, LBB64_3
; %bb.2:
	add	x0, x8, #8
	ret
LBB64_3:
	mov	w9, w0
Lloh130:
	adrp	x10, _minyar_character_text.ascii_bytes@PAGE
Lloh131:
	add	x10, x10, _minyar_character_text.ascii_bytes@PAGEOFF
	add	x9, x10, x9, lsl #1
	strb	w0, [x9]
	stur	x9, [x8, #8]
	mov	w9, #1                          ; =0x1
	dup.2d	v0, x9
	stur	q0, [x8, #16]
	stp	xzr, xzr, [x8, #32]
	add	x0, x8, #8
	ret
LBB64_4:
	b	_encode_character_text
	.loh AdrpAdd	Lloh128, Lloh129
	.loh AdrpAdd	Lloh130, Lloh131
	.cfi_endproc
                                        ; -- End function
	.p2align	2                               ; -- Begin function encode_character_text
_encode_character_text:                 ; @encode_character_text
	.cfi_startproc
; %bb.0:
	sub	sp, sp, #48
	stp	x20, x19, [sp, #16]             ; 16-byte Folded Spill
	stp	x29, x30, [sp, #32]             ; 16-byte Folded Spill
	add	x29, sp, #32
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
	.cfi_offset w19, -24
	.cfi_offset w20, -32
	and	w9, w0, #0x1ff800
	lsr	w8, w0, #16
	cmp	w8, #16
	mov	w10, #55296                     ; =0xd800
	ccmp	w9, w10, #4, ls
	b.eq	LBB65_9
; %bb.1:
	cmp	w0, #127
	b.hi	LBB65_3
; %bb.2:
	strb	w0, [sp, #12]
	mov	w19, #1                         ; =0x1
	b	LBB65_8
LBB65_3:
	cmp	w0, #2047
	b.hi	LBB65_5
; %bb.4:
	lsr	w8, w0, #6
	orr	w8, w8, #0xc0
	strb	w8, [sp, #12]
	mov	w8, #128                        ; =0x80
	bfxil	w8, w0, #0, #6
	strb	w8, [sp, #13]
	mov	w19, #2                         ; =0x2
	b	LBB65_8
LBB65_5:
	cbnz	w8, LBB65_7
; %bb.6:
	lsr	w8, w0, #12
	orr	w8, w8, #0xe0
	strb	w8, [sp, #12]
	mov	w8, #128                        ; =0x80
	mov	w9, #128                        ; =0x80
	bfxil	w9, w0, #6, #6
	strb	w9, [sp, #13]
	bfxil	w8, w0, #0, #6
	strb	w8, [sp, #14]
	mov	w19, #3                         ; =0x3
	b	LBB65_8
LBB65_7:
	lsr	w8, w0, #18
	orr	w8, w8, #0xf0
	strb	w8, [sp, #12]
	mov	w8, #128                        ; =0x80
	mov	w9, #128                        ; =0x80
	bfxil	w9, w0, #12, #6
	strb	w9, [sp, #13]
	mov	w9, #128                        ; =0x80
	bfxil	w9, w0, #6, #6
	strb	w9, [sp, #14]
	bfxil	w8, w0, #0, #6
	strb	w8, [sp, #15]
	mov	w19, #4                         ; =0x4
LBB65_8:
	add	x0, x19, #1
	bl	_rc_allocate_data
	mov	x20, x0
	add	x1, sp, #12
	mov	x2, x19
	bl	_memcpy
	strb	wzr, [x20, x19]
	bl	_OUTLINED_FUNCTION_3
	stp	x20, x19, [x0]
	mov	x8, #-1                         ; =0xffffffffffffffff
	stp	xzr, xzr, [x0, #24]
	str	x8, [x0, #16]
	ldp	x29, x30, [sp, #32]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp, #16]             ; 16-byte Folded Reload
	add	sp, sp, #48
	ret
LBB65_9:
Lloh132:
	adrp	x0, l_.str.58@PAGE
Lloh133:
	add	x0, x0, l_.str.58@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh132, Lloh133
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_boolean_text            ; -- Begin function minyar_boolean_text
	.p2align	2
_minyar_boolean_text:                   ; @minyar_boolean_text
	.cfi_startproc
; %bb.0:
Lloh134:
	adrp	x8, l_.str.7@PAGE
Lloh135:
	add	x8, x8, l_.str.7@PAGEOFF
Lloh136:
	adrp	x9, l_.str.6@PAGE
Lloh137:
	add	x9, x9, l_.str.6@PAGEOFF
	cmp	w0, #0
	csel	x0, x9, x8, ne
	b	_copy_c_text
	.loh AdrpAdd	Lloh136, Lloh137
	.loh AdrpAdd	Lloh134, Lloh135
	.cfi_endproc
                                        ; -- End function
	.p2align	2                               ; -- Begin function copy_c_text
_copy_c_text:                           ; @copy_c_text
	.cfi_startproc
; %bb.0:
	stp	x26, x25, [sp, #-80]!           ; 16-byte Folded Spill
	stp	x24, x23, [sp, #16]             ; 16-byte Folded Spill
	stp	x22, x21, [sp, #32]             ; 16-byte Folded Spill
	stp	x20, x19, [sp, #48]             ; 16-byte Folded Spill
	stp	x29, x30, [sp, #64]             ; 16-byte Folded Spill
	add	x29, sp, #64
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
	.cfi_offset w19, -24
	.cfi_offset w20, -32
	.cfi_offset w21, -40
	.cfi_offset w22, -48
	.cfi_offset w23, -56
	.cfi_offset w24, -64
	.cfi_offset w25, -72
	.cfi_offset w26, -80
	mov	x21, x0
	bl	_strlen
	mov	x19, x0
	add	x22, x0, #1
	adrp	x25, _rc_pending_count@PAGE
	ldr	x8, [x25, _rc_pending_count@PAGEOFF]
	cbz	x8, LBB67_2
; %bb.1:
	mov	w0, #32                         ; =0x20
	bl	_minyar_rc_poll
	cmn	x22, #8
	b.lo	LBB67_3
	b	LBB67_9
LBB67_2:
	adrp	x8, _rc_bounded_last_work@PAGE
	str	xzr, [x8, _rc_bounded_last_work@PAGEOFF]
	cmn	x22, #8
	b.hs	LBB67_9
LBB67_3:
	add	x23, x19, #9
	mov	x0, x23
	bl	_malloc
	cbz	x0, LBB67_9
; %bb.4:
	mov	x20, x0
	adrp	x26, _rc_heap_allocation_count@PAGE
	ldr	x8, [x26, _rc_heap_allocation_count@PAGEOFF]
	add	x8, x8, #1
	str	x8, [x26, _rc_heap_allocation_count@PAGEOFF]
	str	x22, [x20], #8
	adrp	x24, _rc_bytes@PAGE
	ldr	x8, [x24, _rc_bytes@PAGEOFF]
	add	x8, x8, x23
	str	x8, [x24, _rc_bytes@PAGEOFF]
	mov	x0, x20
	mov	x1, x21
	mov	x2, x22
	bl	_memcpy
	ldr	x8, [x25, _rc_pending_count@PAGEOFF]
	cbz	x8, LBB67_6
; %bb.5:
	mov	w0, #32                         ; =0x20
	bl	_minyar_rc_poll
	b	LBB67_7
LBB67_6:
	adrp	x8, _rc_bounded_last_work@PAGE
	str	xzr, [x8, _rc_bounded_last_work@PAGEOFF]
LBB67_7:
	mov	w0, #48                         ; =0x30
	bl	_malloc
	cbz	x0, LBB67_9
; %bb.8:
	ldr	x8, [x26, _rc_heap_allocation_count@PAGEOFF]
	add	x8, x8, #1
	str	x8, [x26, _rc_heap_allocation_count@PAGEOFF]
	mov	w8, #9                          ; =0x9
	str	x8, [x0]
	adrp	x8, _rc_object_count@PAGE
	ldr	x9, [x8, _rc_object_count@PAGEOFF]
	add	x9, x9, #1
	str	x9, [x8, _rc_object_count@PAGEOFF]
	ldr	x8, [x24, _rc_bytes@PAGEOFF]
	add	x8, x8, #48
	str	x8, [x24, _rc_bytes@PAGEOFF]
	mov	x8, x0
	str	x20, [x8, #8]!
	mov	x9, #-1                         ; =0xffffffffffffffff
	stp	x19, x9, [x0, #16]
	stp	xzr, xzr, [x0, #32]
	mov	x0, x8
	ldp	x29, x30, [sp, #64]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp, #48]             ; 16-byte Folded Reload
	ldp	x22, x21, [sp, #32]             ; 16-byte Folded Reload
	ldp	x24, x23, [sp, #16]             ; 16-byte Folded Reload
	ldp	x26, x25, [sp], #80             ; 16-byte Folded Reload
	ret
LBB67_9:
	bl	_out_of_memory
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_initialize_arguments    ; -- Begin function minyar_initialize_arguments
	.p2align	2
_minyar_initialize_arguments:           ; @minyar_initialize_arguments
	.cfi_startproc
; %bb.0:
Lloh138:
	adrp	x8, _saved_argument_count@PAGE
	str	w0, [x8, _saved_argument_count@PAGEOFF]
Lloh139:
	adrp	x8, _saved_argument_values@PAGE
	str	x1, [x8, _saved_argument_values@PAGEOFF]
	mov	w0, #13                         ; =0xd
	mov	w1, #1                          ; =0x1
	b	_signal
	.loh AdrpAdrp	Lloh138, Lloh139
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_argument_count          ; -- Begin function minyar_argument_count
	.p2align	2
_minyar_argument_count:                 ; @minyar_argument_count
	.cfi_startproc
; %bb.0:
Lloh140:
	adrp	x8, _saved_argument_count@PAGE
Lloh141:
	ldr	w8, [x8, _saved_argument_count@PAGEOFF]
	sub	w9, w8, #1
	cmp	w8, #0
	csel	w8, w9, wzr, gt
	sxtw	x0, w8
	ret
	.loh AdrpLdr	Lloh140, Lloh141
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_argument                ; -- Begin function minyar_argument
	.p2align	2
_minyar_argument:                       ; @minyar_argument
	.cfi_startproc
; %bb.0:
	tbnz	x0, #63, LBB70_3
; %bb.1:
Lloh142:
	adrp	x8, _saved_argument_count@PAGE
Lloh143:
	ldr	w8, [x8, _saved_argument_count@PAGEOFF]
	sub	w9, w8, #1
	cmp	w8, #0
	csel	w8, w9, wzr, gt
	sxtw	x8, w8
	cmp	x8, x0
	b.le	LBB70_3
; %bb.2:
Lloh144:
	adrp	x8, _saved_argument_values@PAGE
Lloh145:
	ldr	x8, [x8, _saved_argument_values@PAGEOFF]
	add	x8, x8, x0, lsl #3
	ldr	x0, [x8, #8]
	b	_copy_c_text
LBB70_3:
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
	bl	_minyar_argument.cold.1
	.loh AdrpLdr	Lloh142, Lloh143
	.loh AdrpLdr	Lloh144, Lloh145
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_read_text_file          ; -- Begin function minyar_read_text_file
	.p2align	2
_minyar_read_text_file:                 ; @minyar_read_text_file
	.cfi_startproc
; %bb.0:
	sub	sp, sp, #96
	stp	x26, x25, [sp, #16]             ; 16-byte Folded Spill
	stp	x24, x23, [sp, #32]             ; 16-byte Folded Spill
	stp	x22, x21, [sp, #48]             ; 16-byte Folded Spill
	stp	x20, x19, [sp, #64]             ; 16-byte Folded Spill
	stp	x29, x30, [sp, #80]             ; 16-byte Folded Spill
	add	x29, sp, #80
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
	.cfi_offset w19, -24
	.cfi_offset w20, -32
	.cfi_offset w21, -40
	.cfi_offset w22, -48
	.cfi_offset w23, -56
	.cfi_offset w24, -64
	.cfi_offset w25, -72
	.cfi_offset w26, -80
	ldp	x21, x19, [x0]
	mov	x0, x21
	mov	w1, #0                          ; =0x0
	mov	x2, x19
	bl	_memchr
	cbnz	x0, LBB71_14
; %bb.1:
	add	x0, x19, #1
	bl	_malloc
	cbz	x0, LBB71_13
; %bb.2:
	mov	x20, x0
	adrp	x24, _rc_heap_allocation_count@PAGE
	ldr	x8, [x24, _rc_heap_allocation_count@PAGEOFF]
	add	x8, x8, #1
	str	x8, [x24, _rc_heap_allocation_count@PAGEOFF]
	mov	x1, x21
	mov	x2, x19
	bl	_memcpy
	strb	wzr, [x20, x19]
Lloh146:
	adrp	x1, l_.str.9@PAGE
Lloh147:
	add	x1, x1, l_.str.9@PAGEOFF
	mov	x0, x20
	bl	_fopen
	cbz	x0, LBB71_15
; %bb.3:
	mov	x22, x0
	bl	_text_file_length
	mov	x19, x0
	adrp	x26, _rc_pending_count@PAGE
	ldr	x8, [x26, _rc_pending_count@PAGEOFF]
	cbz	x8, LBB71_5
; %bb.4:
	mov	w0, #32                         ; =0x20
	bl	_minyar_rc_poll
	b	LBB71_6
LBB71_5:
	adrp	x8, _rc_bounded_last_work@PAGE
	str	xzr, [x8, _rc_bounded_last_work@PAGEOFF]
LBB71_6:
	add	x23, x19, #9
	mov	x0, x23
	bl	_malloc
	cbz	x0, LBB71_13
; %bb.7:
	mov	x21, x0
	add	x8, x19, #1
	ldr	x9, [x24, _rc_heap_allocation_count@PAGEOFF]
	add	x9, x9, #1
	str	x9, [x24, _rc_heap_allocation_count@PAGEOFF]
	str	x8, [x21], #8
	adrp	x25, _rc_bytes@PAGE
	ldr	x8, [x25, _rc_bytes@PAGEOFF]
	add	x8, x8, x23
	str	x8, [x25, _rc_bytes@PAGEOFF]
	mov	x0, x21
	mov	w1, #1                          ; =0x1
	mov	x2, x19
	mov	x3, x22
	bl	_fread
	cmp	x0, x19
	b.ne	LBB71_16
; %bb.8:
	mov	x0, x22
	bl	_fclose
	ldr	x8, [x24, _rc_heap_allocation_count@PAGEOFF]
	sub	x8, x8, #1
	str	x8, [x24, _rc_heap_allocation_count@PAGEOFF]
	mov	x0, x20
	bl	_free
	strb	wzr, [x21, x19]
	ldr	x8, [x26, _rc_pending_count@PAGEOFF]
	cbz	x8, LBB71_10
; %bb.9:
	mov	w0, #32                         ; =0x20
	bl	_minyar_rc_poll
	b	LBB71_11
LBB71_10:
	adrp	x8, _rc_bounded_last_work@PAGE
	str	xzr, [x8, _rc_bounded_last_work@PAGEOFF]
LBB71_11:
	mov	w0, #48                         ; =0x30
	bl	_malloc
	cbz	x0, LBB71_13
; %bb.12:
	ldr	x8, [x24, _rc_heap_allocation_count@PAGEOFF]
	add	x8, x8, #1
	str	x8, [x24, _rc_heap_allocation_count@PAGEOFF]
	mov	w8, #9                          ; =0x9
	str	x8, [x0]
	adrp	x8, _rc_object_count@PAGE
	ldr	x9, [x8, _rc_object_count@PAGEOFF]
	add	x9, x9, #1
	str	x9, [x8, _rc_object_count@PAGEOFF]
	ldr	x8, [x25, _rc_bytes@PAGEOFF]
	add	x8, x8, #48
	str	x8, [x25, _rc_bytes@PAGEOFF]
	mov	x8, x0
	str	x21, [x8, #8]!
	mov	x9, #-1                         ; =0xffffffffffffffff
	stp	x19, x9, [x0, #16]
	stp	xzr, xzr, [x0, #32]
	mov	x0, x8
	ldp	x29, x30, [sp, #80]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp, #64]             ; 16-byte Folded Reload
	ldp	x22, x21, [sp, #48]             ; 16-byte Folded Reload
	ldp	x24, x23, [sp, #32]             ; 16-byte Folded Reload
	ldp	x26, x25, [sp, #16]             ; 16-byte Folded Reload
	add	sp, sp, #96
	ret
LBB71_13:
	bl	_out_of_memory
LBB71_14:
	bl	_minyar_read_text_file.cold.1
LBB71_15:
Lloh148:
	adrp	x8, ___stderrp@GOTPAGE
Lloh149:
	ldr	x8, [x8, ___stderrp@GOTPAGEOFF]
Lloh150:
	ldr	x0, [x8]
	str	x20, [sp]
Lloh151:
	adrp	x1, l_.str.10@PAGE
Lloh152:
	add	x1, x1, l_.str.10@PAGEOFF
	bl	_fprintf
	mov	x0, x20
	bl	_rc_heap_deallocate
	mov	w0, #1                          ; =0x1
	bl	_exit
LBB71_16:
	bl	_minyar_read_text_file.cold.2
	.loh AdrpAdd	Lloh146, Lloh147
	.loh AdrpAdd	Lloh151, Lloh152
	.loh AdrpLdrGotLdr	Lloh148, Lloh149, Lloh150
	.cfi_endproc
                                        ; -- End function
	.p2align	2                               ; -- Begin function rc_heap_deallocate
_rc_heap_deallocate:                    ; @rc_heap_deallocate
	.cfi_startproc
; %bb.0:
	cbz	x0, LBB72_2
; %bb.1:
	adrp	x8, _rc_heap_allocation_count@PAGE
	ldr	x9, [x8, _rc_heap_allocation_count@PAGEOFF]
	sub	x9, x9, #1
	str	x9, [x8, _rc_heap_allocation_count@PAGEOFF]
	b	_free
LBB72_2:
	ret
	.cfi_endproc
                                        ; -- End function
	.p2align	2                               ; -- Begin function text_file_length
_text_file_length:                      ; @text_file_length
	.cfi_startproc
; %bb.0:
	stp	x20, x19, [sp, #-32]!           ; 16-byte Folded Spill
	stp	x29, x30, [sp, #16]             ; 16-byte Folded Spill
	add	x29, sp, #16
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
	.cfi_offset w19, -24
	.cfi_offset w20, -32
	mov	x19, x0
	bl	_fgetc
	cmn	w0, #1
	b.ne	LBB73_2
; %bb.1:
	mov	x0, x19
	bl	_ferror
	cbnz	w0, LBB73_7
LBB73_2:
	mov	x0, x19
	mov	x1, #0                          ; =0x0
	mov	w2, #2                          ; =0x2
	bl	_fseek
	cbnz	w0, LBB73_6
; %bb.3:
	mov	x0, x19
	bl	_ftell
	tbnz	x0, #63, LBB73_6
; %bb.4:
	mov	x20, x0
	mov	x0, x19
	mov	x1, #0                          ; =0x0
	mov	w2, #0                          ; =0x0
	bl	_fseek
	cbnz	w0, LBB73_6
; %bb.5:
	mov	x0, x20
	ldp	x29, x30, [sp, #16]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp], #32             ; 16-byte Folded Reload
	ret
LBB73_6:
	bl	_text_file_length.cold.2
LBB73_7:
	bl	_text_file_length.cold.1
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_write_text_file         ; -- Begin function minyar_write_text_file
	.p2align	2
_minyar_write_text_file:                ; @minyar_write_text_file
	.cfi_startproc
; %bb.0:
	stp	x24, x23, [sp, #-64]!           ; 16-byte Folded Spill
	stp	x22, x21, [sp, #16]             ; 16-byte Folded Spill
	stp	x20, x19, [sp, #32]             ; 16-byte Folded Spill
	stp	x29, x30, [sp, #48]             ; 16-byte Folded Spill
	add	x29, sp, #48
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
	.cfi_offset w19, -24
	.cfi_offset w20, -32
	.cfi_offset w21, -40
	.cfi_offset w22, -48
	.cfi_offset w23, -56
	.cfi_offset w24, -64
	mov	x19, x1
	ldp	x21, x20, [x0]
	mov	x0, x21
	mov	w1, #0                          ; =0x0
	mov	x2, x20
	bl	_memchr
	cbnz	x0, LBB74_7
; %bb.1:
	add	x0, x20, #1
	bl	_malloc
	cbz	x0, LBB74_8
; %bb.2:
	adrp	x23, _rc_heap_allocation_count@PAGE
	ldr	x8, [x23, _rc_heap_allocation_count@PAGEOFF]
	add	x8, x8, #1
	str	x8, [x23, _rc_heap_allocation_count@PAGEOFF]
	mov	x22, x0
	mov	x1, x21
	mov	x2, x20
	bl	_memcpy
	strb	wzr, [x22, x20]
Lloh153:
	adrp	x1, l_.str.12@PAGE
Lloh154:
	add	x1, x1, l_.str.12@PAGEOFF
	mov	x0, x22
	bl	_fopen
	mov	x20, x0
	ldr	x8, [x23, _rc_heap_allocation_count@PAGEOFF]
	sub	x8, x8, #1
	str	x8, [x23, _rc_heap_allocation_count@PAGEOFF]
	mov	x0, x22
	bl	_free
	cbz	x20, LBB74_9
; %bb.3:
	ldp	x0, x2, [x19]
	mov	w1, #1                          ; =0x1
	mov	x3, x20
	bl	_fwrite
	ldr	x8, [x19, #8]
	cmp	x0, x8
	b.ne	LBB74_6
; %bb.4:
	mov	x0, x20
	bl	_fclose
	cbnz	w0, LBB74_6
; %bb.5:
	ldp	x29, x30, [sp, #48]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp, #32]             ; 16-byte Folded Reload
	ldp	x22, x21, [sp, #16]             ; 16-byte Folded Reload
	ldp	x24, x23, [sp], #64             ; 16-byte Folded Reload
	ret
LBB74_6:
	bl	_minyar_write_text_file.cold.2
LBB74_7:
	bl	_minyar_write_text_file.cold.1
LBB74_8:
	bl	_out_of_memory
LBB74_9:
	bl	_minyar_write_text_file.cold.3
	.loh AdrpAdd	Lloh153, Lloh154
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_fail_integer_overflow   ; -- Begin function minyar_fail_integer_overflow
	.p2align	2
_minyar_fail_integer_overflow:          ; @minyar_fail_integer_overflow
	.cfi_startproc
; %bb.0:
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
Lloh155:
	adrp	x8, ___stderrp@GOTPAGE
Lloh156:
	ldr	x8, [x8, ___stderrp@GOTPAGEOFF]
Lloh157:
	ldr	x1, [x8]
Lloh158:
	adrp	x0, l_.str.15@PAGE
Lloh159:
	add	x0, x0, l_.str.15@PAGEOFF
	bl	_fputs
	bl	_OUTLINED_FUNCTION_0
	.loh AdrpAdd	Lloh158, Lloh159
	.loh AdrpLdrGotLdr	Lloh155, Lloh156, Lloh157
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_check_integer_overflow  ; -- Begin function minyar_check_integer_overflow
	.p2align	2
_minyar_check_integer_overflow:         ; @minyar_check_integer_overflow
	.cfi_startproc
; %bb.0:
	cbnz	w0, LBB76_2
; %bb.1:
	ret
LBB76_2:
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
	bl	_minyar_fail_integer_overflow
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_fail_integer_division   ; -- Begin function minyar_fail_integer_division
	.p2align	2
_minyar_fail_integer_division:          ; @minyar_fail_integer_division
	.cfi_startproc
; %bb.0:
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
Lloh160:
	adrp	x8, l_.str.17@PAGE
Lloh161:
	add	x8, x8, l_.str.17@PAGEOFF
Lloh162:
	adrp	x9, l_.str.16@PAGE
Lloh163:
	add	x9, x9, l_.str.16@PAGEOFF
	cmp	x0, #0
	csel	x0, x9, x8, eq
	bl	_integer_division_stop
	.loh AdrpAdd	Lloh162, Lloh163
	.loh AdrpAdd	Lloh160, Lloh161
	.cfi_endproc
                                        ; -- End function
	.p2align	2                               ; -- Begin function integer_division_stop
_integer_division_stop:                 ; @integer_division_stop
	.cfi_startproc
; %bb.0:
	stp	x20, x19, [sp, #-32]!           ; 16-byte Folded Spill
	stp	x29, x30, [sp, #16]             ; 16-byte Folded Spill
	add	x29, sp, #16
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
	.cfi_offset w19, -24
	.cfi_offset w20, -32
	mov	x19, x0
Lloh164:
	adrp	x20, ___stderrp@GOTPAGE
Lloh165:
	ldr	x20, [x20, ___stderrp@GOTPAGEOFF]
	ldr	x1, [x20]
Lloh166:
	adrp	x0, l_.str.4@PAGE
Lloh167:
	add	x0, x0, l_.str.4@PAGEOFF
	bl	_fputs
	ldr	x1, [x20]
	mov	x0, x19
	bl	_fputs
	ldr	x1, [x20]
	mov	w0, #10                         ; =0xa
	bl	_fputc
	bl	_OUTLINED_FUNCTION_0
	.loh AdrpAdd	Lloh166, Lloh167
	.loh AdrpLdrGot	Lloh164, Lloh165
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_check_integer_division  ; -- Begin function minyar_check_integer_division
	.p2align	2
_minyar_check_integer_division:         ; @minyar_check_integer_division
	.cfi_startproc
; %bb.0:
	cbz	x1, LBB79_4
; %bb.1:
	mov	x8, #-9223372036854775808       ; =0x8000000000000000
	cmp	x0, x8
	b.ne	LBB79_3
; %bb.2:
	cmn	x1, #1
	b.eq	LBB79_4
LBB79_3:
	ret
LBB79_4:
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
	mov	x0, x1
	bl	_minyar_fail_integer_division
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_print_float             ; -- Begin function minyar_print_float
	.p2align	2
_minyar_print_float:                    ; @minyar_print_float
	.cfi_startproc
; %bb.0:
	sub	sp, sp, #80
	stp	x29, x30, [sp, #64]             ; 16-byte Folded Spill
	add	x29, sp, #64
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
Lloh168:
	adrp	x8, ___stack_chk_guard@GOTPAGE
Lloh169:
	ldr	x8, [x8, ___stack_chk_guard@GOTPAGEOFF]
Lloh170:
	ldr	x8, [x8]
	stur	x8, [x29, #-8]
	add	x0, sp, #8
	bl	_format_float
	add	x0, sp, #8
	bl	_puts
	cmn	w0, #1
	b.eq	LBB80_4
; %bb.1:
Lloh171:
	adrp	x8, ___stdoutp@GOTPAGE
Lloh172:
	ldr	x8, [x8, ___stdoutp@GOTPAGEOFF]
Lloh173:
	ldr	x0, [x8]
	bl	_fflush
	cmn	w0, #1
	b.eq	LBB80_4
; %bb.2:
	ldur	x8, [x29, #-8]
Lloh174:
	adrp	x9, ___stack_chk_guard@GOTPAGE
Lloh175:
	ldr	x9, [x9, ___stack_chk_guard@GOTPAGEOFF]
Lloh176:
	ldr	x9, [x9]
	cmp	x9, x8
	b.ne	LBB80_5
; %bb.3:
	ldp	x29, x30, [sp, #64]             ; 16-byte Folded Reload
	add	sp, sp, #80
	ret
LBB80_4:
	bl	_output_error
LBB80_5:
	bl	___stack_chk_fail
	.loh AdrpLdrGotLdr	Lloh168, Lloh169, Lloh170
	.loh AdrpLdrGotLdr	Lloh171, Lloh172, Lloh173
	.loh AdrpLdrGotLdr	Lloh174, Lloh175, Lloh176
	.cfi_endproc
                                        ; -- End function
	.p2align	2                               ; -- Begin function format_float
_format_float:                          ; @format_float
	.cfi_startproc
; %bb.0:
	sub	sp, sp, #176
	stp	d9, d8, [sp, #96]               ; 16-byte Folded Spill
	stp	x24, x23, [sp, #112]            ; 16-byte Folded Spill
	stp	x22, x21, [sp, #128]            ; 16-byte Folded Spill
	stp	x20, x19, [sp, #144]            ; 16-byte Folded Spill
	stp	x29, x30, [sp, #160]            ; 16-byte Folded Spill
	add	x29, sp, #160
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
	.cfi_offset w19, -24
	.cfi_offset w20, -32
	.cfi_offset w21, -40
	.cfi_offset w22, -48
	.cfi_offset w23, -56
	.cfi_offset w24, -64
	.cfi_offset b8, -72
	.cfi_offset b9, -80
Lloh177:
	adrp	x8, ___stack_chk_guard@GOTPAGE
Lloh178:
	ldr	x8, [x8, ___stack_chk_guard@GOTPAGEOFF]
Lloh179:
	ldr	x8, [x8]
	stur	x8, [x29, #-72]
	fcmp	d0, d0
	b.vs	LBB81_73
; %bb.1:
	fmov	d8, d0
	fabs	d0, d0
	mov	x8, #9218868437227405312        ; =0x7ff0000000000000
	fmov	d1, x8
	fcmp	d0, d1
	b.eq	LBB81_4
; %bb.2:
	fcmp	d8, #0.0
	b.ne	LBB81_8
; %bb.3:
	fmov	x8, d8
Lloh180:
	adrp	x9, l_.str.64@PAGE
Lloh181:
	add	x9, x9, l_.str.64@PAGEOFF
Lloh182:
	adrp	x10, l_.str.65@PAGE
Lloh183:
	add	x10, x10, l_.str.65@PAGEOFF
	cmp	x8, #0
	csel	x2, x10, x9, eq
	b	LBB81_5
LBB81_4:
Lloh184:
	adrp	x8, l_.str.63@PAGE
Lloh185:
	add	x8, x8, l_.str.63@PAGEOFF
Lloh186:
	adrp	x9, l_.str.62@PAGE
Lloh187:
	add	x9, x9, l_.str.62@PAGEOFF
	fcmp	d8, #0.0
	csel	x2, x9, x8, mi
LBB81_5:
	mov	w1, #48                         ; =0x30
	bl	_snprintf
                                        ; kill: def $w0 killed $w0 def $x0
	sxtw	x0, w0
LBB81_6:
	ldur	x8, [x29, #-72]
Lloh188:
	adrp	x9, ___stack_chk_guard@GOTPAGE
Lloh189:
	ldr	x9, [x9, ___stack_chk_guard@GOTPAGEOFF]
Lloh190:
	ldr	x9, [x9]
	cmp	x9, x8
	b.ne	LBB81_74
; %bb.7:
	ldp	x29, x30, [sp, #160]            ; 16-byte Folded Reload
	ldp	x20, x19, [sp, #144]            ; 16-byte Folded Reload
	ldp	x22, x21, [sp, #128]            ; 16-byte Folded Reload
	ldp	x24, x23, [sp, #112]            ; 16-byte Folded Reload
	ldp	d9, d8, [sp, #96]               ; 16-byte Folded Reload
	add	sp, sp, #176
	ret
LBB81_8:
	mov	x8, #4845873199050653696        ; =0x4340000000000000
	fmov	d1, x8
	fcmp	d0, d1
	fcvtzs	d0, d8
	scvtf	d0, d0
	fccmp	d0, d8, #0, mi
	b.eq	LBB81_42
; %bb.9:
	mov	x20, x0
	fmov	x8, d8
	tst	x8, #0xfffffffffffff
	cset	w9, eq
	tst	x8, #0x7fe0000000000000
	csel	w21, wzr, w9, eq
	str	d8, [sp, #8]
	str	xzr, [sp]
Lloh191:
	adrp	x19, l_.str.67@PAGE
Lloh192:
	add	x19, x19, l_.str.67@PAGEOFF
	add	x0, sp, #48
	mov	w1, #40                         ; =0x28
	mov	x2, x19
	bl	_snprintf
	mov	w22, #1                         ; =0x1
	b	LBB81_11
LBB81_10:                               ;   in Loop: Header=BB81_11 Depth=1
	add	w23, w22, #1
	str	d8, [sp, #8]
	str	x22, [sp]
	add	x0, sp, #48
	mov	w1, #40                         ; =0x28
	mov	x2, x19
	bl	_snprintf
	mov	x22, x23
	cmp	w23, #17
	b.eq	LBB81_15
LBB81_11:                               ; =>This Inner Loop Header: Depth=1
	add	x0, sp, #48
	mov	x1, #0                          ; =0x0
	bl	_strtod
	fcmp	d0, d8
	b.eq	LBB81_15
; %bb.12:                               ;   in Loop: Header=BB81_11 Depth=1
	cbz	w21, LBB81_10
; %bb.13:                               ;   in Loop: Header=BB81_11 Depth=1
	add	x0, sp, #48
	fmov	d0, d8
	mov	w1, #1                          ; =0x1
	bl	_adjacent_float_decimal
	tbnz	w0, #0, LBB81_15
; %bb.14:                               ;   in Loop: Header=BB81_11 Depth=1
	add	x0, sp, #48
	fmov	d0, d8
	mov	w1, #-1                         ; =0xffffffff
	bl	_adjacent_float_decimal
	tbz	w0, #0, LBB81_10
LBB81_15:
	mov	x21, #0                         ; =0x0
	ldrb	w19, [sp, #48]
	cmp	w19, #45
	add	x8, sp, #48
	cinc	x8, x8, eq
	add	x0, x8, #1
	add	x8, sp, #24
	b	LBB81_17
LBB81_16:                               ;   in Loop: Header=BB81_17 Depth=1
	add	x0, x0, #1
LBB81_17:                               ; =>This Inner Loop Header: Depth=1
	ldurb	w9, [x0, #-1]
	cbz	w9, LBB81_21
; %bb.18:                               ;   in Loop: Header=BB81_17 Depth=1
	cmp	w9, #101
	b.eq	LBB81_21
; %bb.19:                               ;   in Loop: Header=BB81_17 Depth=1
	sub	w10, w9, #48
	cmp	w10, #9
	b.hi	LBB81_16
; %bb.20:                               ;   in Loop: Header=BB81_17 Depth=1
	strb	w9, [x8, x21]
	add	x21, x21, #1
	b	LBB81_16
LBB81_21:
	bl	_atoi
                                        ; kill: def $w0 killed $w0 def $x0
	cmp	x21, #0
	cset	w9, ne
	add	x10, sp, #24
	mov	x8, x20
LBB81_22:                               ; =>This Inner Loop Header: Depth=1
	mov	x11, x21
	cmp	x21, #2
	b.lo	LBB81_25
; %bb.23:                               ;   in Loop: Header=BB81_22 Depth=1
	sub	x21, x11, #1
	add	x12, x10, x11
	ldurb	w12, [x12, #-1]
	cmp	w12, #48
	b.eq	LBB81_22
; %bb.24:
	add	x9, x21, #1
LBB81_25:
	cmp	w19, #45
	b.ne	LBB81_27
; %bb.26:
	mov	w10, #45                        ; =0x2d
	strb	w10, [x8]
	mov	w10, #1                         ; =0x1
	b	LBB81_28
LBB81_27:
	mov	x10, #0                         ; =0x0
LBB81_28:
	add	w12, w0, #7
	cmp	w12, #27
	b.hi	LBB81_37
; %bb.29:
	tbnz	w0, #31, LBB81_56
; %bb.30:
	mov	x11, #0                         ; =0x0
	mov	w12, w0
	add	x12, x12, #1
	add	x13, x8, x10
	add	x14, sp, #24
	b	LBB81_34
LBB81_31:                               ;   in Loop: Header=BB81_34 Depth=1
	ldrb	w15, [x14, x11]
LBB81_32:                               ;   in Loop: Header=BB81_34 Depth=1
	strb	w15, [x13, x11]
LBB81_33:                               ;   in Loop: Header=BB81_34 Depth=1
	add	x11, x11, #1
	cmp	x12, x11
	b.eq	LBB81_43
LBB81_34:                               ; =>This Inner Loop Header: Depth=1
	add	x15, x10, x11
	cmp	x15, #46
	b.hi	LBB81_33
; %bb.35:                               ;   in Loop: Header=BB81_34 Depth=1
	cmp	x9, x11
	b.hi	LBB81_31
; %bb.36:                               ;   in Loop: Header=BB81_34 Depth=1
	mov	w15, #48                        ; =0x30
	b	LBB81_32
LBB81_37:
	ldrb	w12, [sp, #24]
	add	x13, x8, x10
	strb	w12, [x13]
	orr	x12, x10, #0x2
	mov	w14, #46                        ; =0x2e
	strb	w14, [x13, #1]
	cmp	x11, #2
	b.lo	LBB81_50
; %bb.38:
	mov	w10, #2                         ; =0x2
	cmp	x9, #2
	csel	x9, x9, x10, hi
	sub	x9, x9, #1
	add	x10, sp, #24
	add	x10, x10, #1
	b	LBB81_40
LBB81_39:                               ;   in Loop: Header=BB81_40 Depth=1
	add	x10, x10, #1
	mov	x12, x19
	subs	x9, x9, #1
	b.eq	LBB81_51
LBB81_40:                               ; =>This Inner Loop Header: Depth=1
	add	x19, x12, #1
	cmp	x19, #47
	b.hi	LBB81_39
; %bb.41:                               ;   in Loop: Header=BB81_40 Depth=1
	ldrb	w11, [x10]
	strb	w11, [x8, x12]
	b	LBB81_39
LBB81_42:
	fcvtzs	x8, d8
	str	x8, [sp]
Lloh193:
	adrp	x2, l_.str.66@PAGE
Lloh194:
	add	x2, x2, l_.str.66@PAGEOFF
	b	LBB81_5
LBB81_43:
	add	x13, x10, x11
	sub	x13, x13, #1
	cmp	x13, #46
	b.hs	LBB81_45
; %bb.44:
	add	x14, x8, x10
	mov	w15, #46                        ; =0x2e
	strb	w15, [x14, x11]
LBB81_45:
	subs	x9, x9, x12
	b.ls	LBB81_62
; %bb.46:
	mov	x13, #0                         ; =0x0
	add	x14, sp, #24
	add	x12, x14, x12
	add	x14, x8, x10
	add	x15, x10, x11
	b	LBB81_48
LBB81_47:                               ;   in Loop: Header=BB81_48 Depth=1
	add	x13, x13, #1
	cmp	x9, x13
	b.eq	LBB81_64
LBB81_48:                               ; =>This Inner Loop Header: Depth=1
	add	x16, x15, x13
	add	x16, x16, #2
	cmp	x16, #47
	b.hi	LBB81_47
; %bb.49:                               ;   in Loop: Header=BB81_48 Depth=1
	ldrb	w16, [x12, x13]
	add	x17, x14, x13
	add	x17, x17, x11
	strb	w16, [x17, #1]
	b	LBB81_47
LBB81_50:
	add	x19, x10, #3
	mov	w9, #48                         ; =0x30
	strb	w9, [x8, x12]
LBB81_51:
	str	x0, [sp]
Lloh195:
	adrp	x2, l_.str.68@PAGE
Lloh196:
	add	x2, x2, l_.str.68@PAGEOFF
	add	x21, sp, #16
	add	x0, sp, #16
	mov	w1, #8                          ; =0x8
	bl	_snprintf
	ldrb	w10, [sp, #16]
	cbz	w10, LBB81_61
; %bb.52:
	add	x9, x21, #1
	mov	x8, x20
	b	LBB81_54
LBB81_53:                               ;   in Loop: Header=BB81_54 Depth=1
	ldrb	w10, [x9], #1
	mov	x19, x0
	cbz	w10, LBB81_72
LBB81_54:                               ; =>This Inner Loop Header: Depth=1
	add	x0, x19, #1
	cmp	x0, #47
	b.hi	LBB81_53
; %bb.55:                               ;   in Loop: Header=BB81_54 Depth=1
	strb	w10, [x8, x19]
	b	LBB81_53
LBB81_56:
	mov	w11, #11824                     ; =0x2e30
	strh	w11, [x8, x10]
	orr	x11, x10, #0x2
	cmn	w0, #1
	b.eq	LBB81_66
; %bb.57:
	sub	w10, w10, w0
	add	w10, w10, #1
	mov	w12, #48                        ; =0x30
	b	LBB81_59
LBB81_58:                               ;   in Loop: Header=BB81_59 Depth=1
	add	x11, x11, #1
	cmp	x10, x11
	b.eq	LBB81_65
LBB81_59:                               ; =>This Inner Loop Header: Depth=1
	cmp	x11, #46
	b.hi	LBB81_58
; %bb.60:                               ;   in Loop: Header=BB81_59 Depth=1
	strb	w12, [x8, x11]
	b	LBB81_58
LBB81_61:
	mov	x0, x19
	mov	x8, x20
	b	LBB81_72
LBB81_62:
	add	x9, x10, x11
	add	x0, x9, #2
	cmp	x13, #44
	b.hi	LBB81_72
; %bb.63:
	add	x9, x8, x10
	add	x9, x9, x11
	mov	w10, #48                        ; =0x30
	strb	w10, [x9, #1]
	b	LBB81_72
LBB81_64:
	add	x9, x10, x11
	add	x9, x9, x13
	add	x0, x9, #1
	b	LBB81_72
LBB81_65:
	mov	x11, x10
LBB81_66:
	cbz	x9, LBB81_71
; %bb.67:
	add	x10, sp, #24
	b	LBB81_69
LBB81_68:                               ;   in Loop: Header=BB81_69 Depth=1
	add	x10, x10, #1
	mov	x11, x0
	subs	x9, x9, #1
	b.eq	LBB81_72
LBB81_69:                               ; =>This Inner Loop Header: Depth=1
	add	x0, x11, #1
	cmp	x0, #47
	b.hi	LBB81_68
; %bb.70:                               ;   in Loop: Header=BB81_69 Depth=1
	ldrb	w12, [x10]
	strb	w12, [x8, x11]
	b	LBB81_68
LBB81_71:
	mov	x0, x11
LBB81_72:
	mov	w9, #47                         ; =0x2f
	cmp	x0, #47
	csel	x9, x0, x9, lo
	strb	wzr, [x8, x9]
	b	LBB81_6
LBB81_73:
	mov	w8, #24910                      ; =0x614e
	movk	w8, #78, lsl #16
	str	w8, [x0]
	mov	w0, #3                          ; =0x3
	b	LBB81_6
LBB81_74:
	bl	___stack_chk_fail
	.loh AdrpLdrGotLdr	Lloh177, Lloh178, Lloh179
	.loh AdrpAdd	Lloh182, Lloh183
	.loh AdrpAdd	Lloh180, Lloh181
	.loh AdrpAdd	Lloh186, Lloh187
	.loh AdrpAdd	Lloh184, Lloh185
	.loh AdrpLdrGotLdr	Lloh188, Lloh189, Lloh190
	.loh AdrpAdd	Lloh191, Lloh192
	.loh AdrpAdd	Lloh193, Lloh194
	.loh AdrpAdd	Lloh195, Lloh196
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_float_text              ; -- Begin function minyar_float_text
	.p2align	2
_minyar_float_text:                     ; @minyar_float_text
	.cfi_startproc
; %bb.0:
	sub	sp, sp, #144
	stp	x26, x25, [sp, #64]             ; 16-byte Folded Spill
	stp	x24, x23, [sp, #80]             ; 16-byte Folded Spill
	stp	x22, x21, [sp, #96]             ; 16-byte Folded Spill
	stp	x20, x19, [sp, #112]            ; 16-byte Folded Spill
	stp	x29, x30, [sp, #128]            ; 16-byte Folded Spill
	add	x29, sp, #128
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
	.cfi_offset w19, -24
	.cfi_offset w20, -32
	.cfi_offset w21, -40
	.cfi_offset w22, -48
	.cfi_offset w23, -56
	.cfi_offset w24, -64
	.cfi_offset w25, -72
	.cfi_offset w26, -80
Lloh197:
	adrp	x8, ___stack_chk_guard@GOTPAGE
Lloh198:
	ldr	x8, [x8, ___stack_chk_guard@GOTPAGEOFF]
Lloh199:
	ldr	x8, [x8]
	str	x8, [sp, #56]
	add	x0, sp, #8
	bl	_format_float
	mov	x19, x0
	add	x21, x0, #1
	adrp	x24, _rc_pending_count@PAGE
	ldr	x8, [x24, _rc_pending_count@PAGEOFF]
	cbz	x8, LBB82_2
; %bb.1:
	mov	w0, #32                         ; =0x20
	bl	_minyar_rc_poll
	cmn	x21, #8
	b.lo	LBB82_3
	b	LBB82_10
LBB82_2:
	adrp	x8, _rc_bounded_last_work@PAGE
	str	xzr, [x8, _rc_bounded_last_work@PAGEOFF]
	cmn	x21, #8
	b.hs	LBB82_10
LBB82_3:
	add	x22, x19, #9
	mov	x0, x22
	bl	_malloc
	cbz	x0, LBB82_10
; %bb.4:
	mov	x20, x0
	adrp	x25, _rc_heap_allocation_count@PAGE
	ldr	x8, [x25, _rc_heap_allocation_count@PAGEOFF]
	add	x8, x8, #1
	str	x8, [x25, _rc_heap_allocation_count@PAGEOFF]
	str	x21, [x20], #8
	adrp	x23, _rc_bytes@PAGE
	ldr	x8, [x23, _rc_bytes@PAGEOFF]
	add	x8, x8, x22
	str	x8, [x23, _rc_bytes@PAGEOFF]
	add	x1, sp, #8
	mov	x0, x20
	mov	x2, x21
	bl	_memcpy
	ldr	x8, [x24, _rc_pending_count@PAGEOFF]
	cbz	x8, LBB82_6
; %bb.5:
	mov	w0, #32                         ; =0x20
	bl	_minyar_rc_poll
	b	LBB82_7
LBB82_6:
	adrp	x8, _rc_bounded_last_work@PAGE
	str	xzr, [x8, _rc_bounded_last_work@PAGEOFF]
LBB82_7:
	mov	w0, #48                         ; =0x30
	bl	_malloc
	cbz	x0, LBB82_10
; %bb.8:
	ldr	x8, [x25, _rc_heap_allocation_count@PAGEOFF]
	add	x8, x8, #1
	str	x8, [x25, _rc_heap_allocation_count@PAGEOFF]
	mov	w8, #9                          ; =0x9
	str	x8, [x0]
	adrp	x8, _rc_object_count@PAGE
	ldr	x9, [x8, _rc_object_count@PAGEOFF]
	add	x9, x9, #1
	str	x9, [x8, _rc_object_count@PAGEOFF]
	ldr	x8, [x23, _rc_bytes@PAGEOFF]
	add	x8, x8, #48
	str	x8, [x23, _rc_bytes@PAGEOFF]
	mov	x8, x0
	str	x20, [x8, #8]!
	stp	x19, x19, [x0, #16]
	stp	xzr, xzr, [x0, #32]
	ldr	x9, [sp, #56]
Lloh200:
	adrp	x10, ___stack_chk_guard@GOTPAGE
Lloh201:
	ldr	x10, [x10, ___stack_chk_guard@GOTPAGEOFF]
Lloh202:
	ldr	x10, [x10]
	cmp	x10, x9
	b.ne	LBB82_11
; %bb.9:
	mov	x0, x8
	ldp	x29, x30, [sp, #128]            ; 16-byte Folded Reload
	ldp	x20, x19, [sp, #112]            ; 16-byte Folded Reload
	ldp	x22, x21, [sp, #96]             ; 16-byte Folded Reload
	ldp	x24, x23, [sp, #80]             ; 16-byte Folded Reload
	ldp	x26, x25, [sp, #64]             ; 16-byte Folded Reload
	add	sp, sp, #144
	ret
LBB82_10:
	bl	_out_of_memory
LBB82_11:
	bl	___stack_chk_fail
	.loh AdrpLdrGotLdr	Lloh197, Lloh198, Lloh199
	.loh AdrpLdrGotLdr	Lloh200, Lloh201, Lloh202
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_float_integer           ; -- Begin function minyar_float_integer
	.p2align	2
_minyar_float_integer:                  ; @minyar_float_integer
	.cfi_startproc
; %bb.0:
	mov	x8, #-4332462841530417152       ; =0xc3e0000000000000
	fmov	d1, x8
	fcmp	d0, d1
	mov	x8, #4890909195324358656        ; =0x43e0000000000000
	fmov	d1, x8
	fccmp	d0, d1, #0, ge
	b.pl	LBB83_2
; %bb.1:
	fcvtzs	x0, d0
	ret
LBB83_2:
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
	bl	_minyar_float_integer.cold.1
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_integer_character       ; -- Begin function minyar_integer_character
	.p2align	2
_minyar_integer_character:              ; @minyar_integer_character
	.cfi_startproc
; %bb.0:
	lsr	x8, x0, #16
	cmp	x8, #16
	b.hi	LBB84_3
; %bb.1:
	and	x8, x0, #0x1ff800
	mov	w9, #55296                      ; =0xd800
	cmp	x8, x9
	b.eq	LBB84_3
; %bb.2:
                                        ; kill: def $w0 killed $w0 killed $x0
	ret
LBB84_3:
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
	bl	_minyar_integer_character.cold.1
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_integer_absolute        ; -- Begin function minyar_integer_absolute
	.p2align	2
_minyar_integer_absolute:               ; @minyar_integer_absolute
	.cfi_startproc
; %bb.0:
	mov	x8, #-9223372036854775808       ; =0x8000000000000000
	cmp	x0, x8
	b.eq	LBB85_2
; %bb.1:
	cmp	x0, #0
	cneg	x0, x0, mi
	ret
LBB85_2:
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
	bl	_minyar_integer_absolute.cold.1
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_check_clamp_integer     ; -- Begin function minyar_check_clamp_integer
	.p2align	2
_minyar_check_clamp_integer:            ; @minyar_check_clamp_integer
	.cfi_startproc
; %bb.0:
	cmp	x0, x1
	b.gt	LBB86_2
; %bb.1:
	ret
LBB86_2:
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
	bl	_minyar_check_clamp_integer.cold.1
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_check_clamp_float       ; -- Begin function minyar_check_clamp_float
	.p2align	2
_minyar_check_clamp_float:              ; @minyar_check_clamp_float
	.cfi_startproc
; %bb.0:
	fcmp	d0, d1
	b.hi	LBB87_2
; %bb.1:
	ret
LBB87_2:
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
	bl	_minyar_check_clamp_float.cold.1
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_check_shift             ; -- Begin function minyar_check_shift
	.p2align	2
_minyar_check_shift:                    ; @minyar_check_shift
	.cfi_startproc
; %bb.0:
	cmp	x0, #64
	b.hs	LBB88_2
; %bb.1:
	ret
LBB88_2:
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
	bl	_minyar_check_shift.cold.1
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_tan                     ; -- Begin function minyar_tan
	.p2align	2
_minyar_tan:                            ; @minyar_tan
	.cfi_startproc
; %bb.0:
	b	_tan
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_asin                    ; -- Begin function minyar_asin
	.p2align	2
_minyar_asin:                           ; @minyar_asin
	.cfi_startproc
; %bb.0:
	b	_asin
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_acos                    ; -- Begin function minyar_acos
	.p2align	2
_minyar_acos:                           ; @minyar_acos
	.cfi_startproc
; %bb.0:
	b	_acos
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_atan                    ; -- Begin function minyar_atan
	.p2align	2
_minyar_atan:                           ; @minyar_atan
	.cfi_startproc
; %bb.0:
	b	_atan
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_atan2                   ; -- Begin function minyar_atan2
	.p2align	2
_minyar_atan2:                          ; @minyar_atan2
	.cfi_startproc
; %bb.0:
	b	_atan2
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_bytes_new               ; -- Begin function minyar_bytes_new
	.p2align	2
_minyar_bytes_new:                      ; @minyar_bytes_new
	.cfi_startproc
; %bb.0:
	stp	x24, x23, [sp, #-64]!           ; 16-byte Folded Spill
	stp	x22, x21, [sp, #16]             ; 16-byte Folded Spill
	stp	x20, x19, [sp, #32]             ; 16-byte Folded Spill
	stp	x29, x30, [sp, #48]             ; 16-byte Folded Spill
	add	x29, sp, #48
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
	.cfi_offset w19, -24
	.cfi_offset w20, -32
	.cfi_offset w21, -40
	.cfi_offset w22, -48
	.cfi_offset w23, -56
	.cfi_offset w24, -64
	tbnz	x0, #63, LBB94_12
; %bb.1:
	mov	x19, x0
	mov	x8, #9223372036854775807        ; =0x7fffffffffffffff
	cmp	x0, x8
	b.eq	LBB94_13
; %bb.2:
	adrp	x24, _rc_pending_count@PAGE
	ldr	x8, [x24, _rc_pending_count@PAGEOFF]
	cbz	x8, LBB94_4
; %bb.3:
	mov	w0, #32                         ; =0x20
	bl	_minyar_rc_poll
	b	LBB94_5
LBB94_4:
	adrp	x8, _rc_bounded_last_work@PAGE
	str	xzr, [x8, _rc_bounded_last_work@PAGEOFF]
LBB94_5:
	add	x21, x19, #9
	mov	x0, x21
	bl	_malloc
	cbz	x0, LBB94_11
; %bb.6:
	mov	x20, x0
	add	x1, x19, #1
	adrp	x23, _rc_heap_allocation_count@PAGE
	ldr	x8, [x23, _rc_heap_allocation_count@PAGEOFF]
	add	x8, x8, #1
	str	x8, [x23, _rc_heap_allocation_count@PAGEOFF]
	str	x1, [x20], #8
	adrp	x22, _rc_bytes@PAGE
	ldr	x8, [x22, _rc_bytes@PAGEOFF]
	add	x8, x8, x21
	str	x8, [x22, _rc_bytes@PAGEOFF]
	mov	x0, x20
	bl	_bzero
	ldr	x8, [x24, _rc_pending_count@PAGEOFF]
	cbz	x8, LBB94_8
; %bb.7:
	mov	w0, #32                         ; =0x20
	bl	_minyar_rc_poll
	b	LBB94_9
LBB94_8:
	adrp	x8, _rc_bounded_last_work@PAGE
	str	xzr, [x8, _rc_bounded_last_work@PAGEOFF]
LBB94_9:
	mov	w0, #48                         ; =0x30
	bl	_malloc
	cbz	x0, LBB94_11
; %bb.10:
	ldr	x8, [x23, _rc_heap_allocation_count@PAGEOFF]
	add	x8, x8, #1
	str	x8, [x23, _rc_heap_allocation_count@PAGEOFF]
	mov	w8, #9                          ; =0x9
	str	x8, [x0]
	adrp	x8, _rc_object_count@PAGE
	ldr	x9, [x8, _rc_object_count@PAGEOFF]
	add	x9, x9, #1
	str	x9, [x8, _rc_object_count@PAGEOFF]
	ldr	x8, [x22, _rc_bytes@PAGEOFF]
	add	x9, x8, #48
	mov	x8, x0
	str	x20, [x8, #8]!
	str	x9, [x22, _rc_bytes@PAGEOFF]
	stp	x19, x19, [x0, #16]
	stp	xzr, xzr, [x0, #32]
	mov	x0, x8
	ldp	x29, x30, [sp, #48]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp, #32]             ; 16-byte Folded Reload
	ldp	x22, x21, [sp, #16]             ; 16-byte Folded Reload
	ldp	x24, x23, [sp], #64             ; 16-byte Folded Reload
	ret
LBB94_11:
	bl	_out_of_memory
LBB94_12:
	bl	_minyar_bytes_new.cold.2
LBB94_13:
	bl	_minyar_bytes_new.cold.1
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_bytes_length            ; -- Begin function minyar_bytes_length
	.p2align	2
_minyar_bytes_length:                   ; @minyar_bytes_length
	.cfi_startproc
; %bb.0:
	ldr	x0, [x0, #8]
	ret
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_bytes_resize            ; -- Begin function minyar_bytes_resize
	.p2align	2
_minyar_bytes_resize:                   ; @minyar_bytes_resize
	.cfi_startproc
; %bb.0:
	stp	x22, x21, [sp, #-48]!           ; 16-byte Folded Spill
	stp	x20, x19, [sp, #16]             ; 16-byte Folded Spill
	stp	x29, x30, [sp, #32]             ; 16-byte Folded Spill
	add	x29, sp, #32
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
	.cfi_offset w19, -24
	.cfi_offset w20, -32
	.cfi_offset w21, -40
	.cfi_offset w22, -48
	tbnz	x1, #63, LBB96_9
; %bb.1:
	mov	x19, x1
	mov	x20, x0
	ldr	x8, [x0, #8]
	cmp	x8, x1
	b.ge	LBB96_8
; %bb.2:
	lsr	x9, x19, #61
	cbnz	x9, LBB96_10
; %bb.3:
	ldr	x9, [x20, #16]
	cmp	x9, x19
	b.ge	LBB96_6
; %bb.4:
	lsl	x8, x9, #1
	mov	w10, #16                        ; =0x10
	cmp	x9, #16
	csel	x8, x10, x8, lt
	cmp	x8, x19
	csel	x21, x8, x19, gt
	mov	x8, #9223372036854775807        ; =0x7fffffffffffffff
	cmp	x21, x8
	b.hs	LBB96_11
; %bb.5:
	ldr	x0, [x20]
	add	x1, x21, #1
	bl	_rc_reallocate_data
	strb	wzr, [x0, x21]
	str	x0, [x20]
	str	x21, [x20, #16]
	ldr	x8, [x20, #8]
	b	LBB96_7
LBB96_6:
	ldr	x0, [x20]
LBB96_7:
	sub	x1, x19, x8
	add	x0, x0, x8
	bl	_bzero
LBB96_8:
	str	x19, [x20, #8]
	ldp	x29, x30, [sp, #32]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp, #16]             ; 16-byte Folded Reload
	ldp	x22, x21, [sp], #48             ; 16-byte Folded Reload
	ret
LBB96_9:
	bl	_minyar_bytes_resize.cold.3
LBB96_10:
	bl	_minyar_bytes_resize.cold.2
LBB96_11:
	bl	_minyar_bytes_resize.cold.1
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_bytes_clear             ; -- Begin function minyar_bytes_clear
	.p2align	2
_minyar_bytes_clear:                    ; @minyar_bytes_clear
	.cfi_startproc
; %bb.0:
	stp	x20, x19, [sp, #-32]!           ; 16-byte Folded Spill
	stp	x29, x30, [sp, #16]             ; 16-byte Folded Spill
	add	x29, sp, #16
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
	.cfi_offset w19, -24
	.cfi_offset w20, -32
	mov	x19, x0
	ldr	x8, [x0, #8]
	tbz	x8, #63, LBB97_4
; %bb.1:
	ldr	x9, [x19, #16]
	ldr	x0, [x19]
	tbz	x9, #63, LBB97_3
; %bb.2:
	mov	w1, #17                         ; =0x11
	bl	_rc_reallocate_data
	strb	wzr, [x0, #16]
	str	x0, [x19]
	mov	w8, #16                         ; =0x10
	str	x8, [x19, #16]
	ldr	x8, [x19, #8]
LBB97_3:
	neg	x1, x8
	add	x0, x0, x8
	bl	_bzero
LBB97_4:
	str	xzr, [x19, #8]
	ldp	x29, x30, [sp, #16]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp], #32             ; 16-byte Folded Reload
	ret
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_bytes_get               ; -- Begin function minyar_bytes_get
	.p2align	2
_minyar_bytes_get:                      ; @minyar_bytes_get
	.cfi_startproc
; %bb.0:
	ldr	x2, [x0, #8]
	cmp	x2, x1
	b.ls	LBB98_2
; %bb.1:
	ldr	x8, [x0]
	ldrb	w0, [x8, x1]
	ret
LBB98_2:
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
	mov	x0, x1
	mov	w1, #1                          ; =0x1
	bl	_bytes_position_stop
	.cfi_endproc
                                        ; -- End function
	.p2align	2                               ; -- Begin function bytes_position_stop
_bytes_position_stop:                   ; @bytes_position_stop
	.cfi_startproc
; %bb.0:
	sub	sp, sp, #208
	stp	x29, x30, [sp, #192]            ; 16-byte Folded Spill
	add	x29, sp, #192
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
	cmp	x1, #1
	b.ne	LBB99_2
; %bb.1:
	stp	x0, x2, [sp]
Lloh203:
	adrp	x2, l_.str.69@PAGE
Lloh204:
	add	x2, x2, l_.str.69@PAGEOFF
	b	LBB99_3
LBB99_2:
	stp	x0, x2, [sp, #8]
	str	x1, [sp]
Lloh205:
	adrp	x2, l_.str.70@PAGE
Lloh206:
	add	x2, x2, l_.str.70@PAGEOFF
LBB99_3:
	add	x0, sp, #32
	mov	w1, #160                        ; =0xa0
	bl	_snprintf
	add	x0, sp, #32
	bl	_minyar_stop
	.loh AdrpAdd	Lloh203, Lloh204
	.loh AdrpAdd	Lloh205, Lloh206
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_bytes_set               ; -- Begin function minyar_bytes_set
	.p2align	2
_minyar_bytes_set:                      ; @minyar_bytes_set
	.cfi_startproc
; %bb.0:
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
	ldr	x8, [x0, #8]
	cmp	x8, x1
	b.ls	LBB100_3
; %bb.1:
	cmp	x2, #256
	b.hs	LBB100_4
; %bb.2:
	ldr	x8, [x0]
	strb	w2, [x8, x1]
	ldp	x29, x30, [sp], #16             ; 16-byte Folded Reload
	ret
LBB100_3:
	mov	x0, x1
	mov	w1, #1                          ; =0x1
	mov	x2, x8
	bl	_bytes_position_stop
LBB100_4:
Lloh207:
	adrp	x1, l_.str.26@PAGE
Lloh208:
	add	x1, x1, l_.str.26@PAGEOFF
	mov	x0, x2
	bl	_bytes_value_stop
	.loh AdrpAdd	Lloh207, Lloh208
	.cfi_endproc
                                        ; -- End function
	.p2align	2                               ; -- Begin function bytes_value_stop
_bytes_value_stop:                      ; @bytes_value_stop
	.cfi_startproc
; %bb.0:
	sub	sp, sp, #192
	stp	x29, x30, [sp, #176]            ; 16-byte Folded Spill
	add	x29, sp, #176
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
	stp	x0, x1, [sp]
Lloh209:
	adrp	x2, l_.str.71@PAGE
Lloh210:
	add	x2, x2, l_.str.71@PAGEOFF
	add	x0, sp, #16
	mov	w1, #160                        ; =0xa0
	bl	_snprintf
	add	x0, sp, #16
	bl	_minyar_stop
	.loh AdrpAdd	Lloh209, Lloh210
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_bytes_add_int16         ; -- Begin function minyar_bytes_add_int16
	.p2align	2
_minyar_bytes_add_int16:                ; @minyar_bytes_add_int16
	.cfi_startproc
; %bb.0:
	stp	x22, x21, [sp, #-48]!           ; 16-byte Folded Spill
	stp	x20, x19, [sp, #16]             ; 16-byte Folded Spill
	stp	x29, x30, [sp, #32]             ; 16-byte Folded Spill
	add	x29, sp, #32
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
	.cfi_offset w19, -24
	.cfi_offset w20, -32
	.cfi_offset w21, -40
	.cfi_offset w22, -48
	mov	x19, x1
	cmp	x1, w19, sxth
	b.ne	LBB102_7
; %bb.1:
	mov	x20, x0
	ldr	x8, [x0, #8]
	mov	x9, #2305843009213693950        ; =0x1ffffffffffffffe
	cmp	x8, x9
	b.ge	LBB102_8
; %bb.2:
	ldr	x10, [x20, #16]
	add	x9, x8, #2
	cmp	x9, x10
	b.le	LBB102_5
; %bb.3:
	lsl	x8, x10, #1
	mov	w11, #16                        ; =0x10
	cmp	x10, #16
	csel	x8, x11, x8, lt
	cmp	x8, x9
	csel	x21, x8, x9, gt
	mov	x8, #9223372036854775807        ; =0x7fffffffffffffff
	cmp	x21, x8
	b.hs	LBB102_9
; %bb.4:
	ldr	x0, [x20]
	add	x1, x21, #1
	bl	_rc_reallocate_data
	strb	wzr, [x0, x21]
	str	x0, [x20]
	str	x21, [x20, #16]
	ldr	x8, [x20, #8]
	b	LBB102_6
LBB102_5:
	ldr	x0, [x20]
LBB102_6:
	strh	w19, [x0, x8]
	ldr	x8, [x20, #8]
	add	x8, x8, #2
	str	x8, [x20, #8]
	ldp	x29, x30, [sp, #32]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp, #16]             ; 16-byte Folded Reload
	ldp	x22, x21, [sp], #48             ; 16-byte Folded Reload
	ret
LBB102_7:
Lloh211:
	adrp	x1, l_.str.75@PAGE
Lloh212:
	add	x1, x1, l_.str.75@PAGEOFF
	mov	x0, x19
	bl	_bytes_value_stop
LBB102_8:
	bl	_minyar_bytes_add_int16.cold.2
LBB102_9:
	bl	_minyar_bytes_add_int16.cold.1
	.loh AdrpAdd	Lloh211, Lloh212
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_bytes_set_int16         ; -- Begin function minyar_bytes_set_int16
	.p2align	2
_minyar_bytes_set_int16:                ; @minyar_bytes_set_int16
	.cfi_startproc
; %bb.0:
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
	ldr	x8, [x0, #8]
	tbnz	x1, #63, LBB103_4
; %bb.1:
	sub	x9, x8, #2
	cmp	x9, x1
	b.lt	LBB103_4
; %bb.2:
	cmp	x2, w2, sxth
	b.ne	LBB103_5
; %bb.3:
	ldr	x8, [x0]
	strh	w2, [x8, x1]
	ldp	x29, x30, [sp], #16             ; 16-byte Folded Reload
	ret
LBB103_4:
	mov	x0, x1
	mov	w1, #2                          ; =0x2
	mov	x2, x8
	bl	_bytes_position_stop
LBB103_5:
Lloh213:
	adrp	x1, l_.str.75@PAGE
Lloh214:
	add	x1, x1, l_.str.75@PAGEOFF
	mov	x0, x2
	bl	_bytes_value_stop
	.loh AdrpAdd	Lloh213, Lloh214
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_bytes_get_int16         ; -- Begin function minyar_bytes_get_int16
	.p2align	2
_minyar_bytes_get_int16:                ; @minyar_bytes_get_int16
	.cfi_startproc
; %bb.0:
	ldr	x2, [x0, #8]
	tbnz	x1, #63, LBB104_3
; %bb.1:
	sub	x8, x2, #2
	cmp	x8, x1
	b.lt	LBB104_3
; %bb.2:
	ldr	x8, [x0]
	add	x8, x8, x1
	ldrb	w9, [x8]
	ldrb	w8, [x8, #1]
	lsl	x9, x9, #48
	orr	x8, x9, x8, lsl #56
	asr	x0, x8, #48
	ret
LBB104_3:
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
	mov	x0, x1
	mov	w1, #2                          ; =0x2
	bl	_bytes_position_stop
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_bytes_add_uint16        ; -- Begin function minyar_bytes_add_uint16
	.p2align	2
_minyar_bytes_add_uint16:               ; @minyar_bytes_add_uint16
	.cfi_startproc
; %bb.0:
	stp	x22, x21, [sp, #-48]!           ; 16-byte Folded Spill
	stp	x20, x19, [sp, #16]             ; 16-byte Folded Spill
	stp	x29, x30, [sp, #32]             ; 16-byte Folded Spill
	add	x29, sp, #32
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
	.cfi_offset w19, -24
	.cfi_offset w20, -32
	.cfi_offset w21, -40
	.cfi_offset w22, -48
	mov	x19, x1
	cmp	x1, #16, lsl #12                ; =65536
	b.hs	LBB105_7
; %bb.1:
	mov	x20, x0
	ldr	x8, [x0, #8]
	mov	x9, #2305843009213693950        ; =0x1ffffffffffffffe
	cmp	x8, x9
	b.ge	LBB105_8
; %bb.2:
	ldr	x10, [x20, #16]
	add	x9, x8, #2
	cmp	x9, x10
	b.le	LBB105_5
; %bb.3:
	lsl	x8, x10, #1
	mov	w11, #16                        ; =0x10
	cmp	x10, #16
	csel	x8, x11, x8, lt
	cmp	x8, x9
	csel	x21, x8, x9, gt
	mov	x8, #9223372036854775807        ; =0x7fffffffffffffff
	cmp	x21, x8
	b.hs	LBB105_9
; %bb.4:
	ldr	x0, [x20]
	add	x1, x21, #1
	bl	_rc_reallocate_data
	strb	wzr, [x0, x21]
	str	x0, [x20]
	str	x21, [x20, #16]
	ldr	x8, [x20, #8]
	b	LBB105_6
LBB105_5:
	ldr	x0, [x20]
LBB105_6:
	strh	w19, [x0, x8]
	ldr	x8, [x20, #8]
	add	x8, x8, #2
	str	x8, [x20, #8]
	ldp	x29, x30, [sp, #32]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp, #16]             ; 16-byte Folded Reload
	ldp	x22, x21, [sp], #48             ; 16-byte Folded Reload
	ret
LBB105_7:
Lloh215:
	adrp	x1, l_.str.73@PAGE
Lloh216:
	add	x1, x1, l_.str.73@PAGEOFF
	mov	x0, x19
	bl	_bytes_value_stop
LBB105_8:
	bl	_minyar_bytes_add_uint16.cold.2
LBB105_9:
	bl	_minyar_bytes_add_uint16.cold.1
	.loh AdrpAdd	Lloh215, Lloh216
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_bytes_set_uint16        ; -- Begin function minyar_bytes_set_uint16
	.p2align	2
_minyar_bytes_set_uint16:               ; @minyar_bytes_set_uint16
	.cfi_startproc
; %bb.0:
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
	ldr	x8, [x0, #8]
	tbnz	x1, #63, LBB106_4
; %bb.1:
	sub	x9, x8, #2
	cmp	x9, x1
	b.lt	LBB106_4
; %bb.2:
	cmp	x2, #16, lsl #12                ; =65536
	b.hs	LBB106_5
; %bb.3:
	ldr	x8, [x0]
	strh	w2, [x8, x1]
	ldp	x29, x30, [sp], #16             ; 16-byte Folded Reload
	ret
LBB106_4:
	mov	x0, x1
	mov	w1, #2                          ; =0x2
	mov	x2, x8
	bl	_bytes_position_stop
LBB106_5:
Lloh217:
	adrp	x1, l_.str.73@PAGE
Lloh218:
	add	x1, x1, l_.str.73@PAGEOFF
	mov	x0, x2
	bl	_bytes_value_stop
	.loh AdrpAdd	Lloh217, Lloh218
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_bytes_get_uint16        ; -- Begin function minyar_bytes_get_uint16
	.p2align	2
_minyar_bytes_get_uint16:               ; @minyar_bytes_get_uint16
	.cfi_startproc
; %bb.0:
	ldr	x2, [x0, #8]
	tbnz	x1, #63, LBB107_3
; %bb.1:
	sub	x8, x2, #2
	cmp	x8, x1
	b.lt	LBB107_3
; %bb.2:
	ldr	x8, [x0]
	ldrh	w0, [x8, x1]
	ret
LBB107_3:
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
	mov	x0, x1
	mov	w1, #2                          ; =0x2
	bl	_bytes_position_stop
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_bytes_add_int32         ; -- Begin function minyar_bytes_add_int32
	.p2align	2
_minyar_bytes_add_int32:                ; @minyar_bytes_add_int32
	.cfi_startproc
; %bb.0:
	stp	x22, x21, [sp, #-48]!           ; 16-byte Folded Spill
	stp	x20, x19, [sp, #16]             ; 16-byte Folded Spill
	stp	x29, x30, [sp, #32]             ; 16-byte Folded Spill
	add	x29, sp, #32
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
	.cfi_offset w19, -24
	.cfi_offset w20, -32
	.cfi_offset w21, -40
	.cfi_offset w22, -48
	mov	x19, x1
	cmp	x1, w19, sxtw
	b.ne	LBB108_7
; %bb.1:
	mov	x20, x0
	ldr	x8, [x0, #8]
	mov	x9, #2305843009213693948        ; =0x1ffffffffffffffc
	cmp	x8, x9
	b.ge	LBB108_8
; %bb.2:
	ldr	x10, [x20, #16]
	add	x9, x8, #4
	cmp	x9, x10
	b.le	LBB108_5
; %bb.3:
	lsl	x8, x10, #1
	mov	w11, #16                        ; =0x10
	cmp	x10, #16
	csel	x8, x11, x8, lt
	cmp	x8, x9
	csel	x21, x8, x9, gt
	mov	x8, #9223372036854775807        ; =0x7fffffffffffffff
	cmp	x21, x8
	b.hs	LBB108_9
; %bb.4:
	ldr	x0, [x20]
	add	x1, x21, #1
	bl	_rc_reallocate_data
	strb	wzr, [x0, x21]
	str	x0, [x20]
	str	x21, [x20, #16]
	ldr	x8, [x20, #8]
	b	LBB108_6
LBB108_5:
	ldr	x0, [x20]
LBB108_6:
	str	w19, [x0, x8]
	ldr	x8, [x20, #8]
	add	x8, x8, #4
	str	x8, [x20, #8]
	ldp	x29, x30, [sp, #32]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp, #16]             ; 16-byte Folded Reload
	ldp	x22, x21, [sp], #48             ; 16-byte Folded Reload
	ret
LBB108_7:
Lloh219:
	adrp	x1, l_.str.76@PAGE
Lloh220:
	add	x1, x1, l_.str.76@PAGEOFF
	mov	x0, x19
	bl	_bytes_value_stop
LBB108_8:
	bl	_minyar_bytes_add_int32.cold.2
LBB108_9:
	bl	_minyar_bytes_add_int32.cold.1
	.loh AdrpAdd	Lloh219, Lloh220
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_bytes_set_int32         ; -- Begin function minyar_bytes_set_int32
	.p2align	2
_minyar_bytes_set_int32:                ; @minyar_bytes_set_int32
	.cfi_startproc
; %bb.0:
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
	ldr	x8, [x0, #8]
	tbnz	x1, #63, LBB109_4
; %bb.1:
	sub	x9, x8, #4
	cmp	x9, x1
	b.lt	LBB109_4
; %bb.2:
	cmp	x2, w2, sxtw
	b.ne	LBB109_5
; %bb.3:
	ldr	x8, [x0]
	str	w2, [x8, x1]
	ldp	x29, x30, [sp], #16             ; 16-byte Folded Reload
	ret
LBB109_4:
	mov	x0, x1
	mov	w1, #4                          ; =0x4
	mov	x2, x8
	bl	_bytes_position_stop
LBB109_5:
Lloh221:
	adrp	x1, l_.str.76@PAGE
Lloh222:
	add	x1, x1, l_.str.76@PAGEOFF
	mov	x0, x2
	bl	_bytes_value_stop
	.loh AdrpAdd	Lloh221, Lloh222
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_bytes_get_int32         ; -- Begin function minyar_bytes_get_int32
	.p2align	2
_minyar_bytes_get_int32:                ; @minyar_bytes_get_int32
	.cfi_startproc
; %bb.0:
	ldr	x2, [x0, #8]
	tbnz	x1, #63, LBB110_3
; %bb.1:
	sub	x8, x2, #4
	cmp	x8, x1
	b.lt	LBB110_3
; %bb.2:
	ldr	x8, [x0]
	add	x8, x8, x1
	ldrb	w9, [x8]
	ldrb	w10, [x8, #1]
	ldrb	w11, [x8, #2]
	ldrb	w8, [x8, #3]
	lsl	x9, x9, #32
	orr	x9, x9, x10, lsl #40
	orr	x9, x9, x11, lsl #48
	orr	x8, x9, x8, lsl #56
	asr	x0, x8, #32
	ret
LBB110_3:
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
	mov	x0, x1
	mov	w1, #4                          ; =0x4
	bl	_bytes_position_stop
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_bytes_add_uint32        ; -- Begin function minyar_bytes_add_uint32
	.p2align	2
_minyar_bytes_add_uint32:               ; @minyar_bytes_add_uint32
	.cfi_startproc
; %bb.0:
	stp	x22, x21, [sp, #-48]!           ; 16-byte Folded Spill
	stp	x20, x19, [sp, #16]             ; 16-byte Folded Spill
	stp	x29, x30, [sp, #32]             ; 16-byte Folded Spill
	add	x29, sp, #32
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
	.cfi_offset w19, -24
	.cfi_offset w20, -32
	.cfi_offset w21, -40
	.cfi_offset w22, -48
	mov	x19, x1
	lsr	x8, x1, #32
	cbnz	x8, LBB111_7
; %bb.1:
	mov	x20, x0
	ldr	x8, [x0, #8]
	mov	x9, #2305843009213693948        ; =0x1ffffffffffffffc
	cmp	x8, x9
	b.ge	LBB111_8
; %bb.2:
	ldr	x10, [x20, #16]
	add	x9, x8, #4
	cmp	x9, x10
	b.le	LBB111_5
; %bb.3:
	lsl	x8, x10, #1
	mov	w11, #16                        ; =0x10
	cmp	x10, #16
	csel	x8, x11, x8, lt
	cmp	x8, x9
	csel	x21, x8, x9, gt
	mov	x8, #9223372036854775807        ; =0x7fffffffffffffff
	cmp	x21, x8
	b.hs	LBB111_9
; %bb.4:
	ldr	x0, [x20]
	add	x1, x21, #1
	bl	_rc_reallocate_data
	strb	wzr, [x0, x21]
	str	x0, [x20]
	str	x21, [x20, #16]
	ldr	x8, [x20, #8]
	b	LBB111_6
LBB111_5:
	ldr	x0, [x20]
LBB111_6:
	str	w19, [x0, x8]
	ldr	x8, [x20, #8]
	add	x8, x8, #4
	str	x8, [x20, #8]
	ldp	x29, x30, [sp, #32]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp, #16]             ; 16-byte Folded Reload
	ldp	x22, x21, [sp], #48             ; 16-byte Folded Reload
	ret
LBB111_7:
Lloh223:
	adrp	x1, l_.str.74@PAGE
Lloh224:
	add	x1, x1, l_.str.74@PAGEOFF
	mov	x0, x19
	bl	_bytes_value_stop
LBB111_8:
	bl	_minyar_bytes_add_uint32.cold.2
LBB111_9:
	bl	_minyar_bytes_add_uint32.cold.1
	.loh AdrpAdd	Lloh223, Lloh224
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_bytes_set_uint32        ; -- Begin function minyar_bytes_set_uint32
	.p2align	2
_minyar_bytes_set_uint32:               ; @minyar_bytes_set_uint32
	.cfi_startproc
; %bb.0:
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
	ldr	x8, [x0, #8]
	tbnz	x1, #63, LBB112_4
; %bb.1:
	sub	x9, x8, #4
	cmp	x9, x1
	b.lt	LBB112_4
; %bb.2:
	lsr	x8, x2, #32
	cbnz	x8, LBB112_5
; %bb.3:
	ldr	x8, [x0]
	str	w2, [x8, x1]
	ldp	x29, x30, [sp], #16             ; 16-byte Folded Reload
	ret
LBB112_4:
	mov	x0, x1
	mov	w1, #4                          ; =0x4
	mov	x2, x8
	bl	_bytes_position_stop
LBB112_5:
Lloh225:
	adrp	x1, l_.str.74@PAGE
Lloh226:
	add	x1, x1, l_.str.74@PAGEOFF
	mov	x0, x2
	bl	_bytes_value_stop
	.loh AdrpAdd	Lloh225, Lloh226
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_bytes_get_uint32        ; -- Begin function minyar_bytes_get_uint32
	.p2align	2
_minyar_bytes_get_uint32:               ; @minyar_bytes_get_uint32
	.cfi_startproc
; %bb.0:
	ldr	x2, [x0, #8]
	tbnz	x1, #63, LBB113_3
; %bb.1:
	sub	x8, x2, #4
	cmp	x8, x1
	b.lt	LBB113_3
; %bb.2:
	ldr	x8, [x0]
	ldr	w0, [x8, x1]
	ret
LBB113_3:
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
	mov	x0, x1
	mov	w1, #4                          ; =0x4
	bl	_bytes_position_stop
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_bytes_add_int64         ; -- Begin function minyar_bytes_add_int64
	.p2align	2
_minyar_bytes_add_int64:                ; @minyar_bytes_add_int64
	.cfi_startproc
; %bb.0:
	stp	x22, x21, [sp, #-48]!           ; 16-byte Folded Spill
	stp	x20, x19, [sp, #16]             ; 16-byte Folded Spill
	stp	x29, x30, [sp, #32]             ; 16-byte Folded Spill
	add	x29, sp, #32
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
	.cfi_offset w19, -24
	.cfi_offset w20, -32
	.cfi_offset w21, -40
	.cfi_offset w22, -48
	ldr	x8, [x0, #8]
	mov	x9, #2305843009213693944        ; =0x1ffffffffffffff8
	cmp	x8, x9
	b.ge	LBB114_6
; %bb.1:
	mov	x20, x1
	mov	x19, x0
	ldr	x10, [x0, #16]
	add	x9, x8, #8
	cmp	x9, x10
	b.le	LBB114_4
; %bb.2:
	lsl	x8, x10, #1
	mov	w11, #16                        ; =0x10
	cmp	x10, #16
	csel	x8, x11, x8, lt
	cmp	x8, x9
	csel	x21, x8, x9, gt
	mov	x8, #9223372036854775807        ; =0x7fffffffffffffff
	cmp	x21, x8
	b.hs	LBB114_7
; %bb.3:
	ldr	x0, [x19]
	add	x1, x21, #1
	bl	_rc_reallocate_data
	strb	wzr, [x0, x21]
	str	x0, [x19]
	str	x21, [x19, #16]
	ldr	x8, [x19, #8]
	b	LBB114_5
LBB114_4:
	ldr	x0, [x19]
LBB114_5:
	str	x20, [x0, x8]
	ldr	x8, [x19, #8]
	add	x8, x8, #8
	str	x8, [x19, #8]
	ldp	x29, x30, [sp, #32]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp, #16]             ; 16-byte Folded Reload
	ldp	x22, x21, [sp], #48             ; 16-byte Folded Reload
	ret
LBB114_6:
	bl	_minyar_bytes_add_int64.cold.2
LBB114_7:
	bl	_minyar_bytes_add_int64.cold.1
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_bytes_set_int64         ; -- Begin function minyar_bytes_set_int64
	.p2align	2
_minyar_bytes_set_int64:                ; @minyar_bytes_set_int64
	.cfi_startproc
; %bb.0:
	mov	x8, x2
	ldr	x2, [x0, #8]
	tbnz	x1, #63, LBB115_3
; %bb.1:
	sub	x9, x2, #8
	cmp	x9, x1
	b.lt	LBB115_3
; %bb.2:
	ldr	x9, [x0]
	str	x8, [x9, x1]
	ret
LBB115_3:
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
	mov	x0, x1
	mov	w1, #8                          ; =0x8
	bl	_bytes_position_stop
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_bytes_get_int64         ; -- Begin function minyar_bytes_get_int64
	.p2align	2
_minyar_bytes_get_int64:                ; @minyar_bytes_get_int64
	.cfi_startproc
; %bb.0:
	ldr	x2, [x0, #8]
	tbnz	x1, #63, LBB116_3
; %bb.1:
	sub	x8, x2, #8
	cmp	x8, x1
	b.lt	LBB116_3
; %bb.2:
	ldr	x8, [x0]
	ldr	x0, [x8, x1]
	ret
LBB116_3:
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
	mov	x0, x1
	mov	w1, #8                          ; =0x8
	bl	_bytes_position_stop
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_bytes_add               ; -- Begin function minyar_bytes_add
	.p2align	2
_minyar_bytes_add:                      ; @minyar_bytes_add
	.cfi_startproc
; %bb.0:
	stp	x22, x21, [sp, #-48]!           ; 16-byte Folded Spill
	stp	x20, x19, [sp, #16]             ; 16-byte Folded Spill
	stp	x29, x30, [sp, #32]             ; 16-byte Folded Spill
	add	x29, sp, #32
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
	.cfi_offset w19, -24
	.cfi_offset w20, -32
	.cfi_offset w21, -40
	.cfi_offset w22, -48
	mov	x19, x1
	cmp	x1, #256
	b.hs	LBB117_7
; %bb.1:
	mov	x20, x0
	ldr	x8, [x0, #8]
	mov	x9, #2305843009213693951        ; =0x1fffffffffffffff
	cmp	x8, x9
	b.ge	LBB117_8
; %bb.2:
	ldr	x9, [x20, #16]
	cmp	x8, x9
	b.ge	LBB117_4
; %bb.3:
	ldr	x0, [x20]
	b	LBB117_6
LBB117_4:
	add	x10, x8, #1
	lsl	x11, x9, #1
	mov	w12, #16                        ; =0x10
	cmp	x9, #16
	csel	x9, x12, x11, lt
	cmp	x9, x10
	csinc	x21, x9, x8, gt
	mov	x8, #9223372036854775807        ; =0x7fffffffffffffff
	cmp	x21, x8
	b.hs	LBB117_9
; %bb.5:
	ldr	x0, [x20]
	add	x1, x21, #1
	bl	_rc_reallocate_data
	strb	wzr, [x0, x21]
	str	x0, [x20]
	str	x21, [x20, #16]
	ldr	x8, [x20, #8]
LBB117_6:
	add	x9, x8, #1
	str	x9, [x20, #8]
	strb	w19, [x0, x8]
	ldp	x29, x30, [sp, #32]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp, #16]             ; 16-byte Folded Reload
	ldp	x22, x21, [sp], #48             ; 16-byte Folded Reload
	ret
LBB117_7:
Lloh227:
	adrp	x1, l_.str.26@PAGE
Lloh228:
	add	x1, x1, l_.str.26@PAGEOFF
	mov	x0, x19
	bl	_bytes_value_stop
LBB117_8:
	bl	_minyar_bytes_add.cold.2
LBB117_9:
	bl	_minyar_bytes_add.cold.1
	.loh AdrpAdd	Lloh227, Lloh228
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_bytes_add_float32       ; -- Begin function minyar_bytes_add_float32
	.p2align	2
_minyar_bytes_add_float32:              ; @minyar_bytes_add_float32
	.cfi_startproc
; %bb.0:
	stp	d9, d8, [sp, #-48]!             ; 16-byte Folded Spill
	stp	x20, x19, [sp, #16]             ; 16-byte Folded Spill
	stp	x29, x30, [sp, #32]             ; 16-byte Folded Spill
	add	x29, sp, #32
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
	.cfi_offset w19, -24
	.cfi_offset w20, -32
	.cfi_offset b8, -40
	.cfi_offset b9, -48
	ldr	x8, [x0, #8]
	mov	x9, #2305843009213693948        ; =0x1ffffffffffffffc
	cmp	x8, x9
	b.ge	LBB118_6
; %bb.1:
	fmov	d8, d0
	mov	x19, x0
	ldr	x10, [x0, #16]
	add	x9, x8, #4
	cmp	x9, x10
	b.le	LBB118_4
; %bb.2:
	lsl	x8, x10, #1
	mov	w11, #16                        ; =0x10
	cmp	x10, #16
	csel	x8, x11, x8, lt
	cmp	x8, x9
	csel	x20, x8, x9, gt
	mov	x8, #9223372036854775807        ; =0x7fffffffffffffff
	cmp	x20, x8
	b.hs	LBB118_7
; %bb.3:
	ldr	x0, [x19]
	add	x1, x20, #1
	bl	_rc_reallocate_data
	strb	wzr, [x0, x20]
	str	x0, [x19]
	str	x20, [x19, #16]
	ldr	x8, [x19, #8]
	b	LBB118_5
LBB118_4:
	ldr	x0, [x19]
LBB118_5:
	fcvt	s0, d8
	str	s0, [x0, x8]
	ldr	x8, [x19, #8]
	add	x8, x8, #4
	str	x8, [x19, #8]
	ldp	x29, x30, [sp, #32]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp, #16]             ; 16-byte Folded Reload
	ldp	d9, d8, [sp], #48               ; 16-byte Folded Reload
	ret
LBB118_6:
	bl	_minyar_bytes_add_float32.cold.2
LBB118_7:
	bl	_minyar_bytes_add_float32.cold.1
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_bytes_set_float32       ; -- Begin function minyar_bytes_set_float32
	.p2align	2
_minyar_bytes_set_float32:              ; @minyar_bytes_set_float32
	.cfi_startproc
; %bb.0:
	ldr	x2, [x0, #8]
	tbnz	x1, #63, LBB119_3
; %bb.1:
	sub	x8, x2, #4
	cmp	x8, x1
	b.lt	LBB119_3
; %bb.2:
	ldr	x8, [x0]
	fcvt	s0, d0
	str	s0, [x8, x1]
	ret
LBB119_3:
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
	mov	x0, x1
	mov	w1, #4                          ; =0x4
	bl	_bytes_position_stop
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_bytes_get_float32       ; -- Begin function minyar_bytes_get_float32
	.p2align	2
_minyar_bytes_get_float32:              ; @minyar_bytes_get_float32
	.cfi_startproc
; %bb.0:
	ldr	x2, [x0, #8]
	tbnz	x1, #63, LBB120_3
; %bb.1:
	sub	x8, x2, #4
	cmp	x8, x1
	b.lt	LBB120_3
; %bb.2:
	ldr	x8, [x0]
	ldr	s0, [x8, x1]
	fcvt	d0, s0
	ret
LBB120_3:
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
	mov	x0, x1
	mov	w1, #4                          ; =0x4
	bl	_bytes_position_stop
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_bytes_add_float64       ; -- Begin function minyar_bytes_add_float64
	.p2align	2
_minyar_bytes_add_float64:              ; @minyar_bytes_add_float64
	.cfi_startproc
; %bb.0:
	stp	d9, d8, [sp, #-48]!             ; 16-byte Folded Spill
	stp	x20, x19, [sp, #16]             ; 16-byte Folded Spill
	stp	x29, x30, [sp, #32]             ; 16-byte Folded Spill
	add	x29, sp, #32
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
	.cfi_offset w19, -24
	.cfi_offset w20, -32
	.cfi_offset b8, -40
	.cfi_offset b9, -48
	ldr	x8, [x0, #8]
	mov	x9, #2305843009213693944        ; =0x1ffffffffffffff8
	cmp	x8, x9
	b.ge	LBB121_6
; %bb.1:
	fmov	d8, d0
	mov	x19, x0
	ldr	x10, [x0, #16]
	add	x9, x8, #8
	cmp	x9, x10
	b.le	LBB121_4
; %bb.2:
	lsl	x8, x10, #1
	mov	w11, #16                        ; =0x10
	cmp	x10, #16
	csel	x8, x11, x8, lt
	cmp	x8, x9
	csel	x20, x8, x9, gt
	mov	x8, #9223372036854775807        ; =0x7fffffffffffffff
	cmp	x20, x8
	b.hs	LBB121_7
; %bb.3:
	ldr	x0, [x19]
	add	x1, x20, #1
	bl	_rc_reallocate_data
	strb	wzr, [x0, x20]
	str	x0, [x19]
	str	x20, [x19, #16]
	ldr	x8, [x19, #8]
	b	LBB121_5
LBB121_4:
	ldr	x0, [x19]
LBB121_5:
	str	d8, [x0, x8]
	ldr	x8, [x19, #8]
	add	x8, x8, #8
	str	x8, [x19, #8]
	ldp	x29, x30, [sp, #32]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp, #16]             ; 16-byte Folded Reload
	ldp	d9, d8, [sp], #48               ; 16-byte Folded Reload
	ret
LBB121_6:
	bl	_minyar_bytes_add_float64.cold.2
LBB121_7:
	bl	_minyar_bytes_add_float64.cold.1
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_bytes_set_float64       ; -- Begin function minyar_bytes_set_float64
	.p2align	2
_minyar_bytes_set_float64:              ; @minyar_bytes_set_float64
	.cfi_startproc
; %bb.0:
	ldr	x2, [x0, #8]
	tbnz	x1, #63, LBB122_3
; %bb.1:
	sub	x8, x2, #8
	cmp	x8, x1
	b.lt	LBB122_3
; %bb.2:
	ldr	x8, [x0]
	str	d0, [x8, x1]
	ret
LBB122_3:
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
	mov	x0, x1
	mov	w1, #8                          ; =0x8
	bl	_bytes_position_stop
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_bytes_get_float64       ; -- Begin function minyar_bytes_get_float64
	.p2align	2
_minyar_bytes_get_float64:              ; @minyar_bytes_get_float64
	.cfi_startproc
; %bb.0:
	ldr	x2, [x0, #8]
	tbnz	x1, #63, LBB123_3
; %bb.1:
	sub	x8, x2, #8
	cmp	x8, x1
	b.lt	LBB123_3
; %bb.2:
	ldr	x8, [x0]
	ldr	d0, [x8, x1]
	ret
LBB123_3:
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
	mov	x0, x1
	mov	w1, #8                          ; =0x8
	bl	_bytes_position_stop
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_bytes_slice             ; -- Begin function minyar_bytes_slice
	.p2align	2
_minyar_bytes_slice:                    ; @minyar_bytes_slice
	.cfi_startproc
; %bb.0:
	sub	sp, sp, #240
	stp	x22, x21, [sp, #192]            ; 16-byte Folded Spill
	stp	x20, x19, [sp, #208]            ; 16-byte Folded Spill
	stp	x29, x30, [sp, #224]            ; 16-byte Folded Spill
	add	x29, sp, #224
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
	.cfi_offset w19, -24
	.cfi_offset w20, -32
	.cfi_offset w21, -40
	.cfi_offset w22, -48
	mov	x19, x1
Lloh229:
	adrp	x8, ___stack_chk_guard@GOTPAGE
Lloh230:
	ldr	x8, [x8, ___stack_chk_guard@GOTPAGEOFF]
Lloh231:
	ldr	x8, [x8]
	stur	x8, [x29, #-40]
	ldr	x8, [x0, #8]
	tbnz	x1, #63, LBB124_5
; %bb.1:
	subs	x21, x2, x19
	b.lt	LBB124_5
; %bb.2:
	cmp	x8, x2
	b.lt	LBB124_5
; %bb.3:
	mov	x20, x0
	mov	x0, x21
	bl	_minyar_bytes_new
	mov	x22, x0
	ldr	x0, [x0]
	ldr	x8, [x20]
	add	x1, x8, x19
	mov	x2, x21
	bl	_memcpy
	ldur	x8, [x29, #-40]
Lloh232:
	adrp	x9, ___stack_chk_guard@GOTPAGE
Lloh233:
	ldr	x9, [x9, ___stack_chk_guard@GOTPAGEOFF]
Lloh234:
	ldr	x9, [x9]
	cmp	x9, x8
	b.ne	LBB124_6
; %bb.4:
	mov	x0, x22
	ldp	x29, x30, [sp, #224]            ; 16-byte Folded Reload
	ldp	x20, x19, [sp, #208]            ; 16-byte Folded Reload
	ldp	x22, x21, [sp, #192]            ; 16-byte Folded Reload
	add	sp, sp, #240
	ret
LBB124_5:
	stp	x2, x8, [sp, #8]
	str	x19, [sp]
Lloh235:
	adrp	x2, l_.str.27@PAGE
Lloh236:
	add	x2, x2, l_.str.27@PAGEOFF
	add	x0, sp, #24
	mov	w1, #160                        ; =0xa0
	bl	_snprintf
	add	x0, sp, #24
	bl	_minyar_stop
LBB124_6:
	bl	___stack_chk_fail
	.loh AdrpLdrGotLdr	Lloh229, Lloh230, Lloh231
	.loh AdrpLdrGotLdr	Lloh232, Lloh233, Lloh234
	.loh AdrpAdd	Lloh235, Lloh236
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_bytes_append            ; -- Begin function minyar_bytes_append
	.p2align	2
_minyar_bytes_append:                   ; @minyar_bytes_append
	.cfi_startproc
; %bb.0:
	stp	x22, x21, [sp, #-48]!           ; 16-byte Folded Spill
	stp	x20, x19, [sp, #16]             ; 16-byte Folded Spill
	stp	x29, x30, [sp, #32]             ; 16-byte Folded Spill
	add	x29, sp, #32
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
	.cfi_offset w19, -24
	.cfi_offset w20, -32
	.cfi_offset w21, -40
	.cfi_offset w22, -48
	ldr	x20, [x1, #8]
	ldr	x8, [x0, #8]
	mov	x9, #2305843009213693951        ; =0x1fffffffffffffff
	sub	x9, x9, x8
	cmp	x9, x20
	b.lt	LBB125_6
; %bb.1:
	mov	x21, x1
	mov	x19, x0
	ldr	x10, [x0, #16]
	add	x9, x8, x20
	cmp	x9, x10
	b.le	LBB125_4
; %bb.2:
	lsl	x8, x10, #1
	mov	w11, #16                        ; =0x10
	cmp	x10, #16
	csel	x8, x11, x8, lt
	cmp	x8, x9
	csel	x22, x8, x9, gt
	mov	x8, #9223372036854775807        ; =0x7fffffffffffffff
	cmp	x22, x8
	b.hs	LBB125_7
; %bb.3:
	ldr	x0, [x19]
	add	x1, x22, #1
	bl	_rc_reallocate_data
	strb	wzr, [x0, x22]
	str	x0, [x19]
	str	x22, [x19, #16]
	ldr	x8, [x19, #8]
	b	LBB125_5
LBB125_4:
	ldr	x0, [x19]
LBB125_5:
	ldr	x1, [x21]
	add	x0, x0, x8
	mov	x2, x20
	bl	_memmove
	ldr	x8, [x19, #8]
	add	x8, x8, x20
	str	x8, [x19, #8]
	ldp	x29, x30, [sp, #32]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp, #16]             ; 16-byte Folded Reload
	ldp	x22, x21, [sp], #48             ; 16-byte Folded Reload
	ret
LBB125_6:
	bl	_minyar_bytes_append.cold.2
LBB125_7:
	bl	_minyar_bytes_append.cold.1
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_read_bytes_file         ; -- Begin function minyar_read_bytes_file
	.p2align	2
_minyar_read_bytes_file:                ; @minyar_read_bytes_file
	.cfi_startproc
; %bb.0:
	sub	sp, sp, #64
	stp	x22, x21, [sp, #16]             ; 16-byte Folded Spill
	stp	x20, x19, [sp, #32]             ; 16-byte Folded Spill
	stp	x29, x30, [sp, #48]             ; 16-byte Folded Spill
	add	x29, sp, #48
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
	.cfi_offset w19, -24
	.cfi_offset w20, -32
	.cfi_offset w21, -40
	.cfi_offset w22, -48
	ldp	x21, x20, [x0]
	mov	x0, x21
	mov	w1, #0                          ; =0x0
	mov	x2, x20
	bl	_memchr
	cbnz	x0, LBB126_5
; %bb.1:
	add	x0, x20, #1
	bl	_malloc
	cbz	x0, LBB126_6
; %bb.2:
	mov	x19, x0
	adrp	x22, _rc_heap_allocation_count@PAGE
	ldr	x8, [x22, _rc_heap_allocation_count@PAGEOFF]
	add	x8, x8, #1
	str	x8, [x22, _rc_heap_allocation_count@PAGEOFF]
	mov	x1, x21
	mov	x2, x20
	bl	_memcpy
	strb	wzr, [x19, x20]
Lloh237:
	adrp	x1, l_.str.9@PAGE
Lloh238:
	add	x1, x1, l_.str.9@PAGEOFF
	mov	x0, x19
	bl	_fopen
	cbz	x0, LBB126_7
; %bb.3:
	mov	x20, x0
	ldr	x8, [x22, _rc_heap_allocation_count@PAGEOFF]
	sub	x8, x8, #1
	str	x8, [x22, _rc_heap_allocation_count@PAGEOFF]
	mov	x0, x19
	bl	_free
	mov	x0, x20
	bl	_text_file_length
	mov	x21, x0
	bl	_minyar_bytes_new
	mov	x19, x0
	ldr	x0, [x0]
	mov	w1, #1                          ; =0x1
	mov	x2, x21
	mov	x3, x20
	bl	_fread
	cmp	x0, x21
	b.ne	LBB126_8
; %bb.4:
	mov	x0, x20
	bl	_fclose
	mov	x0, x19
	ldp	x29, x30, [sp, #48]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp, #32]             ; 16-byte Folded Reload
	ldp	x22, x21, [sp, #16]             ; 16-byte Folded Reload
	add	sp, sp, #64
	ret
LBB126_5:
	bl	_minyar_read_bytes_file.cold.1
LBB126_6:
	bl	_out_of_memory
LBB126_7:
Lloh239:
	adrp	x8, ___stderrp@GOTPAGE
Lloh240:
	ldr	x8, [x8, ___stderrp@GOTPAGEOFF]
Lloh241:
	ldr	x0, [x8]
	str	x19, [sp]
Lloh242:
	adrp	x1, l_.str.10@PAGE
Lloh243:
	add	x1, x1, l_.str.10@PAGEOFF
	bl	_fprintf
	mov	w0, #1                          ; =0x1
	bl	_exit
LBB126_8:
	bl	_minyar_read_bytes_file.cold.2
	.loh AdrpAdd	Lloh237, Lloh238
	.loh AdrpAdd	Lloh242, Lloh243
	.loh AdrpLdrGotLdr	Lloh239, Lloh240, Lloh241
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_write_bytes_file        ; -- Begin function minyar_write_bytes_file
	.p2align	2
_minyar_write_bytes_file:               ; @minyar_write_bytes_file
	.cfi_startproc
; %bb.0:
	stp	x24, x23, [sp, #-64]!           ; 16-byte Folded Spill
	stp	x22, x21, [sp, #16]             ; 16-byte Folded Spill
	stp	x20, x19, [sp, #32]             ; 16-byte Folded Spill
	stp	x29, x30, [sp, #48]             ; 16-byte Folded Spill
	add	x29, sp, #48
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
	.cfi_offset w19, -24
	.cfi_offset w20, -32
	.cfi_offset w21, -40
	.cfi_offset w22, -48
	.cfi_offset w23, -56
	.cfi_offset w24, -64
	mov	x19, x1
	ldp	x21, x20, [x0]
	mov	x0, x21
	mov	w1, #0                          ; =0x0
	mov	x2, x20
	bl	_memchr
	cbnz	x0, LBB127_7
; %bb.1:
	add	x0, x20, #1
	bl	_malloc
	cbz	x0, LBB127_8
; %bb.2:
	adrp	x23, _rc_heap_allocation_count@PAGE
	ldr	x8, [x23, _rc_heap_allocation_count@PAGEOFF]
	add	x8, x8, #1
	str	x8, [x23, _rc_heap_allocation_count@PAGEOFF]
	mov	x22, x0
	mov	x1, x21
	mov	x2, x20
	bl	_memcpy
	strb	wzr, [x22, x20]
Lloh244:
	adrp	x1, l_.str.12@PAGE
Lloh245:
	add	x1, x1, l_.str.12@PAGEOFF
	mov	x0, x22
	bl	_fopen
	mov	x20, x0
	ldr	x8, [x23, _rc_heap_allocation_count@PAGEOFF]
	sub	x8, x8, #1
	str	x8, [x23, _rc_heap_allocation_count@PAGEOFF]
	mov	x0, x22
	bl	_free
	cbz	x20, LBB127_9
; %bb.3:
	ldp	x0, x2, [x19]
	mov	w1, #1                          ; =0x1
	mov	x3, x20
	bl	_fwrite
	ldr	x8, [x19, #8]
	cmp	x0, x8
	b.ne	LBB127_6
; %bb.4:
	mov	x0, x20
	bl	_fclose
	cbnz	w0, LBB127_6
; %bb.5:
	ldp	x29, x30, [sp, #48]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp, #32]             ; 16-byte Folded Reload
	ldp	x22, x21, [sp, #16]             ; 16-byte Folded Reload
	ldp	x24, x23, [sp], #64             ; 16-byte Folded Reload
	ret
LBB127_6:
	bl	_minyar_write_bytes_file.cold.2
LBB127_7:
	bl	_minyar_write_bytes_file.cold.1
LBB127_8:
	bl	_out_of_memory
LBB127_9:
	bl	_minyar_write_bytes_file.cold.3
	.loh AdrpAdd	Lloh244, Lloh245
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_file_exists             ; -- Begin function minyar_file_exists
	.p2align	2
_minyar_file_exists:                    ; @minyar_file_exists
	.cfi_startproc
; %bb.0:
	stp	x22, x21, [sp, #-48]!           ; 16-byte Folded Spill
	stp	x20, x19, [sp, #16]             ; 16-byte Folded Spill
	stp	x29, x30, [sp, #32]             ; 16-byte Folded Spill
	add	x29, sp, #32
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
	.cfi_offset w19, -24
	.cfi_offset w20, -32
	.cfi_offset w21, -40
	.cfi_offset w22, -48
	ldp	x20, x19, [x0]
	mov	x0, x20
	mov	w1, #0                          ; =0x0
	mov	x2, x19
	bl	_memchr
	cbnz	x0, LBB128_5
; %bb.1:
	add	x0, x19, #1
	bl	_malloc
	cbz	x0, LBB128_6
; %bb.2:
	adrp	x22, _rc_heap_allocation_count@PAGE
	ldr	x8, [x22, _rc_heap_allocation_count@PAGEOFF]
	add	x8, x8, #1
	str	x8, [x22, _rc_heap_allocation_count@PAGEOFF]
	mov	x21, x0
	mov	x1, x20
	mov	x2, x19
	bl	_memcpy
	strb	wzr, [x21, x19]
Lloh246:
	adrp	x1, l_.str.9@PAGE
Lloh247:
	add	x1, x1, l_.str.9@PAGEOFF
	mov	x0, x21
	bl	_fopen
	mov	x19, x0
	ldr	x8, [x22, _rc_heap_allocation_count@PAGEOFF]
	sub	x8, x8, #1
	str	x8, [x22, _rc_heap_allocation_count@PAGEOFF]
	mov	x0, x21
	bl	_free
	cbz	x19, LBB128_4
; %bb.3:
	mov	x0, x19
	bl	_fclose
LBB128_4:
	cmp	x19, #0
	cset	w0, ne
	ldp	x29, x30, [sp, #32]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp, #16]             ; 16-byte Folded Reload
	ldp	x22, x21, [sp], #48             ; 16-byte Folded Reload
	ret
LBB128_5:
	bl	_minyar_file_exists.cold.1
LBB128_6:
	bl	_out_of_memory
	.loh AdrpAdd	Lloh246, Lloh247
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_bytes_extend            ; -- Begin function minyar_bytes_extend
	.p2align	2
_minyar_bytes_extend:                   ; @minyar_bytes_extend
	.cfi_startproc
; %bb.0:
	stp	x22, x21, [sp, #-48]!           ; 16-byte Folded Spill
	stp	x20, x19, [sp, #16]             ; 16-byte Folded Spill
	stp	x29, x30, [sp, #32]             ; 16-byte Folded Spill
	add	x29, sp, #32
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
	.cfi_offset w19, -24
	.cfi_offset w20, -32
	.cfi_offset w21, -40
	.cfi_offset w22, -48
	tbnz	x1, #63, LBB129_7
; %bb.1:
	mov	x20, x1
	mov	x19, x0
	ldr	x22, [x0, #8]
	mov	x8, #2305843009213693951        ; =0x1fffffffffffffff
	sub	x8, x8, x22
	cmp	x8, x1
	b.lt	LBB129_8
; %bb.2:
	ldr	x9, [x19, #16]
	add	x8, x22, x20
	cmp	x8, x9
	b.le	LBB129_5
; %bb.3:
	lsl	x10, x9, #1
	mov	w11, #16                        ; =0x10
	cmp	x9, #16
	csel	x9, x11, x10, lt
	cmp	x9, x8
	csel	x22, x9, x8, gt
	mov	x8, #9223372036854775807        ; =0x7fffffffffffffff
	cmp	x22, x8
	b.hs	LBB129_9
; %bb.4:
	ldr	x0, [x19]
	add	x1, x22, #1
	bl	_rc_reallocate_data
	mov	x21, x0
	strb	wzr, [x0, x22]
	str	x0, [x19]
	str	x22, [x19, #16]
	ldr	x22, [x19, #8]
	b	LBB129_6
LBB129_5:
	ldr	x21, [x19]
LBB129_6:
	add	x0, x21, x22
	mov	x1, x20
	bl	_bzero
	ldr	x8, [x19, #8]
	add	x8, x8, x20
	str	x8, [x19, #8]
	add	x0, x21, x22
	ldp	x29, x30, [sp, #32]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp, #16]             ; 16-byte Folded Reload
	ldp	x22, x21, [sp], #48             ; 16-byte Folded Reload
	ret
LBB129_7:
	bl	_minyar_bytes_extend.cold.3
LBB129_8:
	bl	_minyar_bytes_extend.cold.2
LBB129_9:
	bl	_minyar_bytes_extend.cold.1
	.cfi_endproc
                                        ; -- End function
	.section	__TEXT,__literal16,16byte_literals
	.p2align	4, 0x0                          ; -- Begin function main
lCPI130_0:
	.quad	12                              ; 0xc
	.quad	130                             ; 0x82
	.section	__TEXT,__text,regular,pure_instructions
	.globl	_main
	.p2align	2
_main:                                  ; @main
	.cfi_startproc
; %bb.0:
	sub	sp, sp, #224
	stp	x28, x27, [sp, #128]            ; 16-byte Folded Spill
	stp	x26, x25, [sp, #144]            ; 16-byte Folded Spill
	stp	x24, x23, [sp, #160]            ; 16-byte Folded Spill
	stp	x22, x21, [sp, #176]            ; 16-byte Folded Spill
	stp	x20, x19, [sp, #192]            ; 16-byte Folded Spill
	stp	x29, x30, [sp, #208]            ; 16-byte Folded Spill
	add	x29, sp, #208
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
	.cfi_offset w19, -24
	.cfi_offset w20, -32
	.cfi_offset w21, -40
	.cfi_offset w22, -48
	.cfi_offset w23, -56
	.cfi_offset w24, -64
	.cfi_offset w25, -72
	.cfi_offset w26, -80
	.cfi_offset w27, -88
	.cfi_offset w28, -96
	cmp	w0, #6
	b.ne	LBB130_74
; %bb.1:
	mov	x20, x1
	ldr	x0, [x1, #8]
	mov	x1, #0                          ; =0x0
	mov	w2, #10                         ; =0xa
	bl	_strtoull
	mov	x21, x0
	ldr	x0, [x20, #16]
	mov	x1, #0                          ; =0x0
	mov	w2, #10                         ; =0xa
	bl	_strtoull
	mov	x22, x0
	ldr	x0, [x20, #24]
	mov	x1, #0                          ; =0x0
	mov	w2, #10                         ; =0xa
	bl	_strtoul
	mov	x24, x0
	ldr	x0, [x20, #32]
	mov	x1, #0                          ; =0x0
	mov	w2, #16                         ; =0x10
	bl	_strtoull
	mov	x25, x0
	ldr	x0, [x20, #40]
	mov	x1, #0                          ; =0x0
	mov	w2, #16                         ; =0x10
	bl	_strtoull
	str	x0, [sp, #96]                   ; 8-byte Folded Spill
	mov	w8, #8193                       ; =0x2001
	cmp	x21, x8
	b.hi	LBB130_75
; %bb.2:
	sub	x8, x22, #256, lsl #12          ; =1048576
	sub	x8, x8, #1
	cmn	x8, #256, lsl #12               ; =1048576
	ccmp	w24, #3, #2, hs
	b.hs	LBB130_75
; %bb.3:
	cmp	w24, #2
	b.ne	LBB130_5
; %bb.4:
Lloh248:
	adrp	x0, l_.str.35@PAGE
Lloh249:
	add	x0, x0, l_.str.35@PAGEOFF
	bl	_copy_c_text
	mov	x26, x0
	b	LBB130_6
LBB130_5:
	mov	x26, #0                         ; =0x0
LBB130_6:
	adrp	x19, _rc_pending_count@PAGE
	ldr	x8, [x19, _rc_pending_count@PAGEOFF]
	adrp	x9, _rc_bounded_last_work@PAGE
	cbz	x8, LBB130_8
; %bb.7:
	mov	w0, #32                         ; =0x20
	bl	_minyar_rc_poll
	b	LBB130_9
LBB130_8:
	str	xzr, [x9, _rc_bounded_last_work@PAGEOFF]
LBB130_9:
	mov	w0, #32                         ; =0x20
	bl	_malloc
	cbz	x0, LBB130_84
; %bb.10:
	mov	x27, x0
	adrp	x9, _rc_heap_allocation_count@PAGE
	ldr	x8, [x9, _rc_heap_allocation_count@PAGEOFF]
	add	x8, x8, #1
	str	x8, [x9, _rc_heap_allocation_count@PAGEOFF]
	mov	w8, #10                         ; =0xa
	str	x8, [x0]
Lloh250:
	adrp	x10, _rc_object_count@PAGE
	ldr	x9, [x10, _rc_object_count@PAGEOFF]
	add	x9, x9, #1
	str	x9, [x10, _rc_object_count@PAGEOFF]
Lloh251:
	adrp	x10, _rc_bytes@PAGE
	ldr	x9, [x10, _rc_bytes@PAGEOFF]
	add	x9, x9, #32
	str	x9, [x10, _rc_bytes@PAGEOFF]
	mov	x23, x0
	str	xzr, [x23, #8]!
	stp	xzr, xzr, [x0, #16]
	cmp	w24, #2
	b.ne	LBB130_12
; %bb.11:
	mov	w8, #14                         ; =0xe
	str	x8, [x27]
LBB130_12:
	mov	x28, #31765                     ; =0x7c15
	movk	x28, #32586, lsl #16
	movk	x28, #31161, lsl #32
	movk	x28, #40503, lsl #48
	str	x21, [sp, #56]                  ; 8-byte Folded Spill
	cbz	x21, LBB130_17
; %bb.13:
	mov	x20, x25
LBB130_14:                              ; =>This Inner Loop Header: Depth=1
	cmp	w24, #2
	csel	x1, x26, x20, eq
	mov	x0, x23
	bl	_minyar_list_add
	add	x20, x20, x28
	subs	x21, x21, #1
	b.ne	LBB130_14
; %bb.15:
	ldr	x8, [x27]
	cmp	x8, #8
	b.lo	LBB130_18
; %bb.16:
	cmn	x8, #8
	b.hs	LBB130_86
LBB130_17:
	add	x8, x8, #8
	str	x8, [x27]
LBB130_18:
	cmp	w24, #2
	mov	x8, #12816                      ; =0x3210
	movk	x8, #30292, lsl #16
	movk	x8, #47768, lsl #32
	movk	x8, #65244, lsl #48
	csel	x8, x26, x8, eq
	str	x8, [sp, #88]                   ; 8-byte Folded Spill
	ldr	x8, [x19, _rc_pending_count@PAGEOFF]
	cbz	x8, LBB130_20
LBB130_19:                              ; =>This Inner Loop Header: Depth=1
	mov	w0, #32                         ; =0x20
	bl	_minyar_rc_poll
	ldr	x8, [x19, _rc_pending_count@PAGEOFF]
	cbnz	x8, LBB130_19
LBB130_20:
	sub	x1, x29, #96
	mov	w0, #12                         ; =0xc
	bl	_clock_gettime
	cbnz	w0, LBB130_76
; %bb.21:
	str	x26, [sp, #104]                 ; 8-byte Folded Spill
	ldp	x9, x8, [x29, #-96]
	str	x9, [sp, #32]                   ; 8-byte Folded Spill
	stp	x8, x27, [sp, #40]              ; 16-byte Folded Spill
	mov	x27, #0                         ; =0x0
	cbz	x22, LBB130_37
; %bb.22:
	mov	x21, #0                         ; =0x0
	cmp	w24, #2
	cset	w28, eq
	ldr	x8, [sp, #56]                   ; 8-byte Folded Reload
	add	x20, x8, #1
Lloh252:
	adrp	x8, lCPI130_0@PAGE
Lloh253:
	ldr	q0, [x8, lCPI130_0@PAGEOFF]
	str	q0, [sp, #64]                   ; 16-byte Folded Spill
	b	LBB130_25
LBB130_23:                              ;   in Loop: Header=BB130_25 Depth=1
	mov	w8, w0
	adrp	x9, _rc_bounded_last_work@PAGE
	str	x8, [x9, _rc_bounded_last_work@PAGEOFF]
LBB130_24:                              ;   in Loop: Header=BB130_25 Depth=1
	ldr	x8, [sp, #96]                   ; 8-byte Folded Reload
	add	x8, x8, x21
	eor	x27, x8, x27
	add	x21, x21, #1
	mov	x22, x26
	cmp	x21, x26
	b.eq	LBB130_37
LBB130_25:                              ; =>This Loop Header: Depth=1
                                        ;     Child Loop BB130_36 Depth 2
	mov	x26, x22
	cmp	w24, #1
	b.ne	LBB130_31
; %bb.26:                               ;   in Loop: Header=BB130_25 Depth=1
	ldr	x8, [x19, _rc_pending_count@PAGEOFF]
	cbz	x8, LBB130_28
; %bb.27:                               ;   in Loop: Header=BB130_25 Depth=1
	mov	w0, #32                         ; =0x20
	bl	_minyar_rc_poll
	b	LBB130_29
LBB130_28:                              ;   in Loop: Header=BB130_25 Depth=1
	adrp	x8, _rc_bounded_last_work@PAGE
	str	xzr, [x8, _rc_bounded_last_work@PAGEOFF]
LBB130_29:                              ;   in Loop: Header=BB130_25 Depth=1
	mov	w0, #1186                       ; =0x4a2
	bl	_malloc
	cbz	x0, LBB130_84
; %bb.30:                               ;   in Loop: Header=BB130_25 Depth=1
Lloh254:
	adrp	x9, _rc_heap_allocation_count@PAGE
	ldr	x8, [x9, _rc_heap_allocation_count@PAGEOFF]
	add	x8, x8, #1
	str	x8, [x9, _rc_heap_allocation_count@PAGEOFF]
Lloh255:
	adrp	x9, _rc_object_count@PAGE
	ldr	x8, [x9, _rc_object_count@PAGEOFF]
	add	x8, x8, #1
	str	x8, [x9, _rc_object_count@PAGEOFF]
Lloh256:
	adrp	x9, _rc_bytes@PAGE
	ldr	x8, [x9, _rc_bytes@PAGEOFF]
	add	x8, x8, #1186
	str	x8, [x9, _rc_bytes@PAGEOFF]
	mov	x22, x0
	add	x0, x0, #16
	mov	w1, #1170                       ; =0x492
	bl	_bzero
	ldr	q0, [sp, #64]                   ; 16-byte Folded Reload
	str	q0, [x22], #8
	mov	x0, x22
	bl	_rc_drop
LBB130_31:                              ;   in Loop: Header=BB130_25 Depth=1
	mov	x0, x23
	ldr	x1, [sp, #88]                   ; 8-byte Folded Reload
	mov	x2, x28
	mov	x3, #0                          ; =0x0
	bl	_minyar_list_appended
	cmp	x0, x23
	b.eq	LBB130_70
; %bb.32:                               ;   in Loop: Header=BB130_25 Depth=1
	mov	x22, x0
	ldr	x8, [x0, #8]
	cmp	x8, x20
	b.ne	LBB130_70
; %bb.33:                               ;   in Loop: Header=BB130_25 Depth=1
	ldr	x0, [x22]
	mov	x1, x20
	ldr	x2, [sp, #104]                  ; 8-byte Folded Reload
	bl	_research_checksum
	ldr	x8, [sp, #96]                   ; 8-byte Folded Reload
	cmp	x0, x8
	b.ne	LBB130_71
; %bb.34:                               ;   in Loop: Header=BB130_25 Depth=1
	mov	x0, x22
	bl	_rc_drop
	ldr	x8, [x19, _rc_pending_count@PAGEOFF]
	cbz	x8, LBB130_23
; %bb.35:                               ;   in Loop: Header=BB130_25 Depth=1
	mov	w8, #32                         ; =0x20
	sub	w8, w8, w0
	mov	x22, x0
	mov	x0, x8
	bl	_minyar_rc_poll
	adrp	x10, _rc_bounded_last_work@PAGE
	ldr	x8, [x10, _rc_bounded_last_work@PAGEOFF]
	ldr	x9, [x19, _rc_pending_count@PAGEOFF]
	add	x8, x8, w22, uxtw
	str	x8, [x10, _rc_bounded_last_work@PAGEOFF]
	cbz	x9, LBB130_24
LBB130_36:                              ;   Parent Loop BB130_25 Depth=1
                                        ; =>  This Inner Loop Header: Depth=2
	mov	w0, #32                         ; =0x20
	bl	_minyar_rc_poll
	ldr	x8, [x19, _rc_pending_count@PAGEOFF]
	cbnz	x8, LBB130_36
	b	LBB130_24
LBB130_37:
	sub	x1, x29, #96
	mov	w0, #12                         ; =0xc
	bl	_clock_gettime
	cbnz	w0, LBB130_77
; %bb.38:
	mov	x28, x22
	cmp	w24, #2
	cset	w2, eq
	ldp	x26, x22, [x29, #-96]
	mov	x0, x23
	ldr	x1, [sp, #88]                   ; 8-byte Folded Reload
	mov	x3, #0                          ; =0x0
	bl	_minyar_list_appended
	ldr	x9, [x0]
	ldr	x8, [x23]
	ldr	x21, [sp, #56]                  ; 8-byte Folded Reload
	cbz	x21, LBB130_40
; %bb.39:
	cmp	x9, x8
	b.eq	LBB130_78
LBB130_40:
	cbz	x21, LBB130_45
; %bb.41:
	mov	x10, x8
	mov	x11, x9
	mov	x12, x21
LBB130_42:                              ; =>This Inner Loop Header: Depth=1
	ldr	x13, [x10], #8
	cmp	w24, #2
	ldr	x14, [sp, #104]                 ; 8-byte Folded Reload
	csel	x14, x14, x25, eq
	cmp	x13, x14
	b.ne	LBB130_72
; %bb.43:                               ;   in Loop: Header=BB130_42 Depth=1
	ldr	x14, [x11]
	cmp	x14, x13
	b.ne	LBB130_73
; %bb.44:                               ;   in Loop: Header=BB130_42 Depth=1
	add	x11, x11, #8
	mov	x13, #31765                     ; =0x7c15
	movk	x13, #32586, lsl #16
	movk	x13, #31161, lsl #32
	movk	x13, #40503, lsl #48
	add	x25, x25, x13
	subs	x12, x12, #1
	b.ne	LBB130_42
LBB130_45:
	ldr	x10, [x9, x21, lsl #3]
	ldr	x11, [sp, #88]                  ; 8-byte Folded Reload
	cmp	x10, x11
	b.ne	LBB130_79
; %bb.46:
	adrp	x25, _rc_bounded_last_work@PAGE
	cbz	x21, LBB130_54
; %bb.47:
	ldr	x10, [x0, #8]
	cbz	x10, LBB130_85
; %bb.48:
	ldr	x21, [x8]
	ldur	x10, [x0, #-8]
	and	x10, x10, #0x7
	cmp	x10, #3
	b.ne	LBB130_52
; %bb.49:
	mov	x24, x0
	ldr	x0, [x9]
	str	xzr, [x9]
	bl	_rc_drop
	mov	x20, x0
	ldr	x8, [x19, _rc_pending_count@PAGEOFF]
	cbz	x8, LBB130_51
; %bb.50:
	mov	w8, #32                         ; =0x20
	sub	w0, w8, w20
	bl	_minyar_rc_poll
	ldr	x8, [x25, _rc_bounded_last_work@PAGEOFF]
LBB130_51:
	add	x8, x8, w20, uxtw
	str	x8, [x25, _rc_bounded_last_work@PAGEOFF]
	ldr	x8, [x23]
	mov	x0, x24
	b	LBB130_53
LBB130_52:
	str	xzr, [x9]
LBB130_53:
	ldr	x8, [x8]
	cmp	x8, x21
	ldr	x21, [sp, #56]                  ; 8-byte Folded Reload
	b.ne	LBB130_83
LBB130_54:
	bl	_rc_drop
	mov	x20, x0
	ldr	x8, [x19, _rc_pending_count@PAGEOFF]
	cbz	x8, LBB130_56
; %bb.55:
	mov	w8, #32                         ; =0x20
	sub	w0, w8, w20
	bl	_minyar_rc_poll
	ldr	x8, [x25, _rc_bounded_last_work@PAGEOFF]
LBB130_56:
	add	x8, x8, w20, uxtw
	str	x8, [x25, _rc_bounded_last_work@PAGEOFF]
	mov	x0, x23
	bl	_rc_drop
	mov	x20, x0
	ldr	x8, [x19, _rc_pending_count@PAGEOFF]
	cbz	x8, LBB130_58
; %bb.57:
	mov	w8, #32                         ; =0x20
	sub	w0, w8, w20
	bl	_minyar_rc_poll
	ldr	x8, [x25, _rc_bounded_last_work@PAGEOFF]
LBB130_58:
	add	x8, x8, w20, uxtw
	str	x8, [x25, _rc_bounded_last_work@PAGEOFF]
	ldr	x8, [sp, #48]                   ; 8-byte Folded Reload
	ldr	x8, [x8, #16]
	cmp	x8, x21
	b.ne	LBB130_80
; %bb.59:
	mov	x0, x23
	bl	_rc_drop
	mov	x20, x0
	ldr	x8, [x19, _rc_pending_count@PAGEOFF]
	cbz	x8, LBB130_61
; %bb.60:
	mov	w8, #32                         ; =0x20
	sub	w0, w8, w20
	bl	_minyar_rc_poll
	ldr	x8, [x25, _rc_bounded_last_work@PAGEOFF]
LBB130_61:
	add	x8, x8, w20, uxtw
	str	x8, [x25, _rc_bounded_last_work@PAGEOFF]
	ldr	x0, [sp, #104]                  ; 8-byte Folded Reload
	cbz	x0, LBB130_66
; %bb.62:
	bl	_rc_drop
	mov	x20, x0
	ldr	x8, [x19, _rc_pending_count@PAGEOFF]
	cbz	x8, LBB130_64
; %bb.63:
	mov	w8, #32                         ; =0x20
	sub	w0, w8, w20
	bl	_minyar_rc_poll
	ldr	x8, [x25, _rc_bounded_last_work@PAGEOFF]
LBB130_64:
	add	x8, x8, w20, uxtw
	str	x8, [x25, _rc_bounded_last_work@PAGEOFF]
	b	LBB130_66
LBB130_65:                              ;   in Loop: Header=BB130_66 Depth=1
	mov	w0, #32                         ; =0x20
	bl	_minyar_rc_poll
LBB130_66:                              ; =>This Inner Loop Header: Depth=1
	ldr	x8, [x19, _rc_pending_count@PAGEOFF]
	cbnz	x8, LBB130_65
; %bb.67:
Lloh257:
	adrp	x8, _rc_object_count@PAGE
Lloh258:
	ldr	x8, [x8, _rc_object_count@PAGEOFF]
Lloh259:
	adrp	x9, _rc_bytes@PAGE
Lloh260:
	ldr	x9, [x9, _rc_bytes@PAGEOFF]
	orr	x8, x8, x9
	cbnz	x8, LBB130_81
; %bb.68:
Lloh261:
	adrp	x8, _rc_heap_allocation_count@PAGE
Lloh262:
	ldr	x8, [x8, _rc_heap_allocation_count@PAGEOFF]
	cbnz	x8, LBB130_82
; %bb.69:
	ldp	x8, x10, [sp, #32]              ; 16-byte Folded Reload
	sub	x8, x26, x8
	mov	w9, #51712                      ; =0xca00
	movk	w9, #15258, lsl #16
	sub	x10, x22, x10
	madd	x8, x8, x9, x10
	stp	x27, x28, [sp, #8]
	str	x8, [sp]
Lloh263:
	adrp	x0, l_.str.46@PAGE
Lloh264:
	add	x0, x0, l_.str.46@PAGEOFF
	bl	_printf
	mov	w0, #0                          ; =0x0
	ldp	x29, x30, [sp, #208]            ; 16-byte Folded Reload
	ldp	x20, x19, [sp, #192]            ; 16-byte Folded Reload
	ldp	x22, x21, [sp, #176]            ; 16-byte Folded Reload
	ldp	x24, x23, [sp, #160]            ; 16-byte Folded Reload
	ldp	x26, x25, [sp, #144]            ; 16-byte Folded Reload
	ldp	x28, x27, [sp, #128]            ; 16-byte Folded Reload
	add	sp, sp, #224
	ret
LBB130_70:
	bl	_main.cold.5
LBB130_71:
	bl	_main.cold.4
LBB130_72:
	bl	_main.cold.7
LBB130_73:
	bl	_main.cold.8
LBB130_74:
	bl	_main.cold.1
LBB130_75:
	bl	_main.cold.16
LBB130_76:
	bl	_main.cold.3
LBB130_77:
	bl	_main.cold.6
LBB130_78:
	bl	_main.cold.15
LBB130_79:
	bl	_main.cold.9
LBB130_80:
	bl	_main.cold.11
LBB130_81:
	bl	_main.cold.13
LBB130_82:
	bl	_main.cold.12
LBB130_83:
	bl	_main.cold.10
LBB130_84:
	bl	_out_of_memory
LBB130_85:
	bl	_main.cold.14
LBB130_86:
	bl	_main.cold.2
	.loh AdrpAdd	Lloh248, Lloh249
	.loh AdrpAdrp	Lloh250, Lloh251
	.loh AdrpLdr	Lloh252, Lloh253
	.loh AdrpAdrp	Lloh255, Lloh256
	.loh AdrpAdrp	Lloh254, Lloh255
	.loh AdrpLdr	Lloh259, Lloh260
	.loh AdrpLdr	Lloh257, Lloh258
	.loh AdrpLdr	Lloh261, Lloh262
	.loh AdrpAdd	Lloh263, Lloh264
	.cfi_endproc
                                        ; -- End function
	.p2align	2                               ; -- Begin function rc_bounded_enqueue
_rc_bounded_enqueue:                    ; @rc_bounded_enqueue
	.cfi_startproc
; %bb.0:
	ldr	x8, [x0]
	and	x9, x8, #0x7
	cmp	x9, #1
	b.eq	LBB131_8
; %bb.1:
	cmp	x9, #3
	b.ne	LBB131_3
; %bb.2:
	str	xzr, [x0, #24]
	b	LBB131_8
LBB131_3:
	ldr	x9, [x0, #8]
	cbz	x9, LBB131_8
; %bb.4:
	mov	x8, #0                          ; =0x0
	add	x9, x0, x9, lsl #3
	add	x9, x9, #16
LBB131_5:                               ; =>This Inner Loop Header: Depth=1
	ldrb	w10, [x9, x8]
	and	w10, w10, #0x1
	strb	w10, [x9, x8]
	cmp	x8, #8
	b.hi	LBB131_7
; %bb.6:                                ;   in Loop: Header=BB131_5 Depth=1
	add	x8, x8, #1
	ldr	x10, [x0, #8]
	cmp	x8, x10
	b.lo	LBB131_5
LBB131_7:
	ldr	x8, [x0]
LBB131_8:
	adrp	x9, _rc_bounded_recent_head@PAGE
	ldr	x10, [x9, _rc_bounded_recent_head@PAGEOFF]
	orr	x8, x8, x10
	str	x8, [x0]
	str	x0, [x9, _rc_bounded_recent_head@PAGEOFF]
	adrp	x8, _rc_bounded_recent_tail@PAGE
	ldr	x9, [x8, _rc_bounded_recent_tail@PAGEOFF]
	cbnz	x9, LBB131_10
; %bb.9:
	str	x0, [x8, _rc_bounded_recent_tail@PAGEOFF]
LBB131_10:
	adrp	x8, _rc_pending_count@PAGE
	ldr	x9, [x8, _rc_pending_count@PAGEOFF]
	add	x9, x9, #1
	str	x9, [x8, _rc_pending_count@PAGEOFF]
	ret
	.cfi_endproc
                                        ; -- End function
	.p2align	2                               ; -- Begin function rc_bounded_old_object_unit
_rc_bounded_old_object_unit:            ; @rc_bounded_old_object_unit
	.cfi_startproc
; %bb.0:
	stp	x20, x19, [sp, #-32]!           ; 16-byte Folded Spill
	stp	x29, x30, [sp, #16]             ; 16-byte Folded Spill
	add	x29, sp, #16
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
	.cfi_offset w19, -24
	.cfi_offset w20, -32
	adrp	x19, _rc_bounded_active@PAGE
	ldr	x0, [x19, _rc_bounded_active@PAGEOFF]
	cbz	x0, LBB132_2
; %bb.1:
	ldr	x8, [x0]
	b	LBB132_10
LBB132_2:
	adrp	x8, _rc_bounded_head@PAGE
	ldr	x0, [x8, _rc_bounded_head@PAGEOFF]
	str	x0, [x19, _rc_bounded_active@PAGEOFF]
	ldr	x9, [x0]
	and	x10, x9, #0xfffffffffffffff8
	str	x10, [x8, _rc_bounded_head@PAGEOFF]
	and	x8, x9, #0x7
	str	x8, [x0]
	cmp	x8, #1
	b.eq	LBB132_8
; %bb.3:
	cmp	x8, #3
	b.ne	LBB132_5
; %bb.4:
	ldr	x9, [x0, #24]
	b	LBB132_9
LBB132_5:
	ldr	x12, [x0, #8]
	cbz	x12, LBB132_8
; %bb.6:
	mov	x10, #0                         ; =0x0
	mov	x9, #0                          ; =0x0
	add	x11, x0, x12, lsl #3
	add	x11, x11, #16
	sub	x12, x12, #1
	mov	w13, #9                         ; =0x9
	cmp	x12, #9
	csel	x12, x12, x13, lo
	lsl	x13, x12, #3
	sub	x12, x13, x12
	add	x12, x12, #7
LBB132_7:                               ; =>This Inner Loop Header: Depth=1
	ldrb	w13, [x11], #1
	lsr	x13, x13, #1
	lsl	x13, x13, x10
	orr	x9, x13, x9
	add	x10, x10, #7
	cmp	x12, x10
	b.ne	LBB132_7
	b	LBB132_9
LBB132_8:
	mov	x9, #0                          ; =0x0
LBB132_9:
	adrp	x10, _rc_bounded_cursor@PAGE
	str	x9, [x10, _rc_bounded_cursor@PAGEOFF]
LBB132_10:
	and	w1, w8, #0x7
	cmp	w1, #4
	b.eq	LBB132_14
; %bb.11:
	cmp	w1, #3
	b.ne	LBB132_17
; %bb.12:
	adrp	x9, _rc_bounded_cursor@PAGE
	ldr	x8, [x9, _rc_bounded_cursor@PAGEOFF]
	ldr	x10, [x0, #16]
	cmp	x8, x10
	b.hs	LBB132_17
; %bb.13:
	ldr	x10, [x0, #8]
	add	x11, x8, #1
	str	x11, [x9, _rc_bounded_cursor@PAGEOFF]
	b	LBB132_16
LBB132_14:
	adrp	x9, _rc_bounded_cursor@PAGE
	ldr	x8, [x9, _rc_bounded_cursor@PAGEOFF]
	ldr	x11, [x0, #8]
	cmp	x8, x11
	b.hs	LBB132_17
; %bb.15:
	add	x10, x0, #16
	add	x11, x10, x11, lsl #3
	add	x12, x8, #1
	str	x12, [x9, _rc_bounded_cursor@PAGEOFF]
	ldrb	w9, [x11, x8]
	tbz	w9, #0, LBB132_18
LBB132_16:
	ldr	x0, [x10, x8, lsl #3]
	ldp	x29, x30, [sp, #16]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp], #32             ; 16-byte Folded Reload
	b	_rc_drop
LBB132_17:
	bl	_rc_bounded_finish_object
	adrp	x8, _rc_pending_count@PAGE
	ldr	x9, [x8, _rc_pending_count@PAGEOFF]
	sub	x9, x9, #1
	str	x9, [x8, _rc_pending_count@PAGEOFF]
	str	xzr, [x19, _rc_bounded_active@PAGEOFF]
LBB132_18:
	ldp	x29, x30, [sp, #16]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp], #32             ; 16-byte Folded Reload
	ret
	.cfi_endproc
                                        ; -- End function
	.p2align	2                               ; -- Begin function rc_allocate_object
_rc_allocate_object:                    ; @rc_allocate_object
	.cfi_startproc
; %bb.0:
	stp	x20, x19, [sp, #-32]!           ; 16-byte Folded Spill
	stp	x29, x30, [sp, #16]             ; 16-byte Folded Spill
	add	x29, sp, #16
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
	.cfi_offset w19, -24
	.cfi_offset w20, -32
	mov	x19, x1
	mov	x20, x0
Lloh265:
	adrp	x8, _rc_pending_count@PAGE
Lloh266:
	ldr	x8, [x8, _rc_pending_count@PAGEOFF]
	cbz	x8, LBB133_2
; %bb.1:
	mov	w0, #32                         ; =0x20
	bl	_minyar_rc_poll
	cmn	x20, #8
	b.lo	LBB133_3
	b	LBB133_5
LBB133_2:
	adrp	x8, _rc_bounded_last_work@PAGE
	str	xzr, [x8, _rc_bounded_last_work@PAGEOFF]
	cmn	x20, #8
	b.hs	LBB133_5
LBB133_3:
	add	x20, x20, #8
	mov	x0, x20
	bl	_malloc
	cbz	x0, LBB133_5
; %bb.4:
	adrp	x8, _rc_heap_allocation_count@PAGE
	ldr	x9, [x8, _rc_heap_allocation_count@PAGEOFF]
	add	x9, x9, #1
	str	x9, [x8, _rc_heap_allocation_count@PAGEOFF]
	orr	w8, w19, #0x8
	str	x8, [x0], #8
Lloh267:
	adrp	x8, _rc_object_count@PAGE
	ldr	x9, [x8, _rc_object_count@PAGEOFF]
	add	x9, x9, #1
	str	x9, [x8, _rc_object_count@PAGEOFF]
Lloh268:
	adrp	x8, _rc_bytes@PAGE
	ldr	x9, [x8, _rc_bytes@PAGEOFF]
	add	x9, x9, x20
	str	x9, [x8, _rc_bytes@PAGEOFF]
	ldp	x29, x30, [sp, #16]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp], #32             ; 16-byte Folded Reload
	ret
LBB133_5:
	bl	_out_of_memory
	.loh AdrpLdr	Lloh265, Lloh266
	.loh AdrpAdrp	Lloh267, Lloh268
	.cfi_endproc
                                        ; -- End function
	.p2align	2                               ; -- Begin function rc_allocate_data
_rc_allocate_data:                      ; @rc_allocate_data
	.cfi_startproc
; %bb.0:
	stp	x20, x19, [sp, #-32]!           ; 16-byte Folded Spill
	stp	x29, x30, [sp, #16]             ; 16-byte Folded Spill
	add	x29, sp, #16
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
	.cfi_offset w19, -24
	.cfi_offset w20, -32
	mov	x19, x0
Lloh269:
	adrp	x8, _rc_pending_count@PAGE
Lloh270:
	ldr	x8, [x8, _rc_pending_count@PAGEOFF]
	cbz	x8, LBB134_2
; %bb.1:
	mov	w0, #32                         ; =0x20
	bl	_minyar_rc_poll
	cmn	x19, #8
	b.lo	LBB134_3
	b	LBB134_5
LBB134_2:
	adrp	x8, _rc_bounded_last_work@PAGE
	str	xzr, [x8, _rc_bounded_last_work@PAGEOFF]
	cmn	x19, #8
	b.hs	LBB134_5
LBB134_3:
	add	x20, x19, #8
	mov	x0, x20
	bl	_malloc
	cbz	x0, LBB134_5
; %bb.4:
Lloh271:
	adrp	x8, _rc_heap_allocation_count@PAGE
	ldr	x9, [x8, _rc_heap_allocation_count@PAGEOFF]
	add	x9, x9, #1
	str	x19, [x0], #8
	str	x9, [x8, _rc_heap_allocation_count@PAGEOFF]
Lloh272:
	adrp	x8, _rc_bytes@PAGE
	ldr	x9, [x8, _rc_bytes@PAGEOFF]
	add	x9, x9, x20
	str	x9, [x8, _rc_bytes@PAGEOFF]
	ldp	x29, x30, [sp, #16]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp], #32             ; 16-byte Folded Reload
	ret
LBB134_5:
	bl	_out_of_memory
	.loh AdrpLdr	Lloh269, Lloh270
	.loh AdrpAdrp	Lloh271, Lloh272
	.cfi_endproc
                                        ; -- End function
	.p2align	2                               ; -- Begin function build_text_index
_build_text_index:                      ; @build_text_index
	.cfi_startproc
; %bb.0:
	sub	sp, sp, #80
	stp	x24, x23, [sp, #16]             ; 16-byte Folded Spill
	stp	x22, x21, [sp, #32]             ; 16-byte Folded Spill
	stp	x20, x19, [sp, #48]             ; 16-byte Folded Spill
	stp	x29, x30, [sp, #64]             ; 16-byte Folded Spill
	add	x29, sp, #64
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
	.cfi_offset w19, -24
	.cfi_offset w20, -32
	.cfi_offset w21, -40
	.cfi_offset w22, -48
	.cfi_offset w23, -56
	.cfi_offset w24, -64
	mov	x19, x0
	mov	x9, #0                          ; =0x0
	ldr	x21, [x0, #8]
	mov	x8, x21
LBB135_1:                               ; =>This Inner Loop Header: Depth=1
	mov	x20, x9
	subs	x8, x8, #8
	b.lt	LBB135_3
; %bb.2:                                ;   in Loop: Header=BB135_1 Depth=1
	ldr	x9, [x19]
	ldr	x10, [x9, x20]
	add	x9, x20, #8
	and	x10, x10, #0x8080808080808080
	cbz	x10, LBB135_1
LBB135_3:
	cmp	x20, x21
	b.ge	LBB135_8
; %bb.4:
	ldr	x8, [x19]
LBB135_5:                               ; =>This Inner Loop Header: Depth=1
	ldrsb	w9, [x8, x20]
	tbnz	w9, #31, LBB135_8
; %bb.6:                                ;   in Loop: Header=BB135_5 Depth=1
	add	x20, x20, #1
	cmp	x21, x20
	b.ne	LBB135_5
; %bb.7:
	mov	x22, x21
	b	LBB135_13
LBB135_8:
	cmp	x20, x21
	b.ge	LBB135_11
; %bb.9:
	mov	x22, x20
LBB135_10:                              ; =>This Inner Loop Header: Depth=1
	ldr	x8, [x19]
	sub	x1, x21, x20
	add	x0, x8, x20
	bl	_OUTLINED_FUNCTION_1
	ldr	x8, [sp, #8]
	add	x22, x22, #1
	ldr	x21, [x19, #8]
	add	x20, x8, x20
	cmp	x20, x21
	b.lt	LBB135_10
	b	LBB135_12
LBB135_11:
	mov	x22, x20
LBB135_12:
	cmp	x22, x21
	b.ne	LBB135_14
LBB135_13:
	str	x22, [x19, #16]
	b	LBB135_34
LBB135_14:
	lsr	x8, x22, #6
	add	x8, x8, #3
	mov	x9, #4294967296                 ; =0x100000000
	cmp	x21, x9
	mov	w9, #2                          ; =0x2
	cinc	x9, x9, ge
	lsl	x0, x8, x9
	bl	_rc_allocate_data
	mov	x20, x0
	ldr	x8, [x19, #8]
	cmp	x8, #1
	b.lt	LBB135_23
; %bb.15:
	mov	x23, #0                         ; =0x0
	mov	x22, #0                         ; =0x0
	mov	w24, #-1                        ; =0xffffffff
LBB135_16:                              ; =>This Inner Loop Header: Depth=1
	tst	x22, #0x3f
	b.ne	LBB135_20
; %bb.17:                               ;   in Loop: Header=BB135_16 Depth=1
	lsr	x9, x22, #6
	cmp	x21, x24
	b.gt	LBB135_19
; %bb.18:                               ;   in Loop: Header=BB135_16 Depth=1
	str	w23, [x20, x9, lsl #2]
	b	LBB135_20
LBB135_19:                              ;   in Loop: Header=BB135_16 Depth=1
	str	x23, [x20, x9, lsl #3]
LBB135_20:                              ;   in Loop: Header=BB135_16 Depth=1
	add	x22, x22, #1
	ldr	x9, [x19]
	sub	x1, x8, x23
	add	x0, x9, x23
	bl	_OUTLINED_FUNCTION_1
	ldr	x9, [sp, #8]
	ldr	x8, [x19, #8]
	add	x23, x9, x23
	cmp	x23, x8
	b.lt	LBB135_16
; %bb.21:
	lsr	x9, x22, #6
	tst	x22, #0x3f
	b.eq	LBB135_25
; %bb.22:
	stp	x22, x20, [x19, #16]
	add	x10, x9, #1
	mov	x11, #4294967296                ; =0x100000000
	b	LBB135_31
LBB135_23:
	mov	w8, #-1                         ; =0xffffffff
	cmp	x21, x8
	b.gt	LBB135_27
; %bb.24:
	str	wzr, [x20]
	b	LBB135_28
LBB135_25:
	mov	x11, #4294967296                ; =0x100000000
	cmp	x21, x11
	b.ge	LBB135_29
; %bb.26:
	str	w23, [x20, x9, lsl #2]
	b	LBB135_30
LBB135_27:
	str	xzr, [x20]
LBB135_28:
	mov	x22, #0                         ; =0x0
	stp	xzr, x20, [x19, #16]
	mov	w10, #1                         ; =0x1
	b	LBB135_32
LBB135_29:
	str	x23, [x20, x9, lsl #3]
LBB135_30:
	add	x10, x9, #1
	stp	x22, x20, [x19, #16]
LBB135_31:
	cmp	x8, x11
	b.ge	LBB135_33
LBB135_32:
	str	wzr, [x20, x10, lsl #2]
	mov	w8, #64                         ; =0x40
	sdiv	x8, x22, x8
	add	x8, x20, x8, lsl #2
	str	wzr, [x8, #8]
	b	LBB135_34
LBB135_33:
	str	xzr, [x20, x10, lsl #3]
	add	x8, x20, x9, lsl #3
	str	xzr, [x8, #16]
LBB135_34:
	ldp	x29, x30, [sp, #64]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp, #48]             ; 16-byte Folded Reload
	ldp	x22, x21, [sp, #32]             ; 16-byte Folded Reload
	ldp	x24, x23, [sp, #16]             ; 16-byte Folded Reload
	add	sp, sp, #80
	ret
	.cfi_endproc
                                        ; -- End function
	.p2align	2                               ; -- Begin function decode_character
_decode_character:                      ; @decode_character
	.cfi_startproc
; %bb.0:
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
	cmp	x1, #0
	b.le	LBB136_28
; %bb.1:
	mov	x8, x0
	ldrsb	w9, [x0]
	and	w0, w9, #0xff
	tbnz	w9, #31, LBB136_3
; %bb.2:
	mov	w8, #1                          ; =0x1
	str	x8, [x2]
	ldp	x29, x30, [sp], #16             ; 16-byte Folded Reload
	ret
LBB136_3:
	cmp	x1, #1
	b.eq	LBB136_7
; %bb.4:
	sub	w9, w0, #194
	cmp	w9, #29
	b.hi	LBB136_7
; %bb.5:
	ldrb	w9, [x8, #1]
	and	w9, w9, #0xc0
	cmp	w9, #128
	b.ne	LBB136_7
; %bb.6:
	mov	w9, #2                          ; =0x2
	str	x9, [x2]
	ldrb	w8, [x8, #1]
	and	w8, w8, #0x3f
	bfi	w8, w0, #6, #5
	mov	x0, x8
	ldp	x29, x30, [sp], #16             ; 16-byte Folded Reload
	ret
LBB136_7:
	cmp	x1, #3
	b.lo	LBB136_16
; %bb.8:
	and	w9, w0, #0xf0
	cmp	w9, #224
	b.ne	LBB136_16
; %bb.9:
	ldrb	w9, [x8, #1]
	and	w10, w9, #0xc0
	cmp	w10, #128
	b.ne	LBB136_16
; %bb.10:
	ldrb	w10, [x8, #2]
	and	w10, w10, #0xc0
	cmp	w10, #128
	b.ne	LBB136_16
; %bb.11:
	cmp	w0, #224
	b.ne	LBB136_13
; %bb.12:
	cmp	w9, #160
	b.lo	LBB136_27
LBB136_13:
	cmp	w0, #237
	b.ne	LBB136_15
; %bb.14:
	cmp	w9, #159
	b.hi	LBB136_27
LBB136_15:
	mov	w9, #3                          ; =0x3
	str	x9, [x2]
	ubfiz	w0, w0, #12, #4
	ldrb	w9, [x8, #1]
	bfi	w0, w9, #6, #6
	ldrb	w8, [x8, #2]
	b	LBB136_26
LBB136_16:
	cmp	x1, #4
	b.lo	LBB136_27
; %bb.17:
	sub	w9, w0, #240
	cmp	w9, #4
	b.hi	LBB136_27
; %bb.18:
	ldrb	w9, [x8, #1]
	and	w10, w9, #0xc0
	cmp	w10, #128
	b.ne	LBB136_27
; %bb.19:
	ldrb	w10, [x8, #2]
	and	w10, w10, #0xc0
	cmp	w10, #128
	b.ne	LBB136_27
; %bb.20:
	ldrb	w10, [x8, #3]
	and	w10, w10, #0xc0
	cmp	w10, #128
	b.ne	LBB136_27
; %bb.21:
	cmp	w0, #240
	b.ne	LBB136_23
; %bb.22:
	cmp	w9, #144
	b.lo	LBB136_27
LBB136_23:
	cmp	w0, #244
	b.ne	LBB136_25
; %bb.24:
	cmp	w9, #143
	b.hi	LBB136_27
LBB136_25:
	mov	w9, #4                          ; =0x4
	str	x9, [x2]
	ubfiz	w0, w0, #18, #3
	ldrb	w9, [x8, #1]
	bfi	w0, w9, #12, #6
	ldrb	w9, [x8, #2]
	bfi	w0, w9, #6, #6
	ldrb	w8, [x8, #3]
LBB136_26:
	bfxil	w0, w8, #0, #6
	ldp	x29, x30, [sp], #16             ; 16-byte Folded Reload
	ret
LBB136_27:
	bl	_invalid_utf8
LBB136_28:
	bl	_position_outside_text
	.cfi_endproc
                                        ; -- End function
	.p2align	2                               ; -- Begin function position_outside_text
_position_outside_text:                 ; @position_outside_text
	.cfi_startproc
; %bb.0:
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
Lloh273:
	adrp	x0, l_.str.54@PAGE
Lloh274:
	add	x0, x0, l_.str.54@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh273, Lloh274
	.cfi_endproc
                                        ; -- End function
	.p2align	2                               ; -- Begin function invalid_utf8
_invalid_utf8:                          ; @invalid_utf8
	.cfi_startproc
; %bb.0:
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
Lloh275:
	adrp	x0, l_.str.55@PAGE
Lloh276:
	add	x0, x0, l_.str.55@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh275, Lloh276
	.cfi_endproc
                                        ; -- End function
	.p2align	2                               ; -- Begin function negative_text_position
_negative_text_position:                ; @negative_text_position
	.cfi_startproc
; %bb.0:
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
Lloh277:
	adrp	x0, l_.str.56@PAGE
Lloh278:
	add	x0, x0, l_.str.56@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh277, Lloh278
	.cfi_endproc
                                        ; -- End function
	.p2align	2                               ; -- Begin function adjacent_float_decimal
_adjacent_float_decimal:                ; @adjacent_float_decimal
	.cfi_startproc
; %bb.0:
	sub	sp, sp, #144
	stp	d9, d8, [sp, #64]               ; 16-byte Folded Spill
	stp	x24, x23, [sp, #80]             ; 16-byte Folded Spill
	stp	x22, x21, [sp, #96]             ; 16-byte Folded Spill
	stp	x20, x19, [sp, #112]            ; 16-byte Folded Spill
	stp	x29, x30, [sp, #128]            ; 16-byte Folded Spill
	add	x29, sp, #128
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
	.cfi_offset w19, -24
	.cfi_offset w20, -32
	.cfi_offset w21, -40
	.cfi_offset w22, -48
	.cfi_offset w23, -56
	.cfi_offset w24, -64
	.cfi_offset b8, -72
	.cfi_offset b9, -80
	mov	x20, x1
	fmov	d8, d0
	mov	x19, x0
Lloh279:
	adrp	x8, ___stack_chk_guard@GOTPAGE
Lloh280:
	ldr	x8, [x8, ___stack_chk_guard@GOTPAGEOFF]
Lloh281:
	ldr	x8, [x8]
	str	x8, [sp, #56]
	bl	_strlen
	mov	x8, x0
	add	x21, sp, #16
	add	x0, sp, #16
	add	x2, x8, #1
	mov	x1, x19
	mov	w3, #40                         ; =0x28
	bl	___memcpy_chk
	ldrb	w8, [sp, #16]
	cmp	w8, #45
	cset	w22, eq
	cinc	x23, x21, eq
	add	x0, sp, #16
	mov	w1, #101                        ; =0x65
	bl	_strchr
	mov	x21, x0
	add	x0, x0, #1
	bl	_atoi
	mov	x8, x0
	cmp	x21, x23
	b.ls	LBB140_10
; %bb.1:
	mov	x10, x21
	mov	x9, x21
	b	LBB140_4
LBB140_2:                               ;   in Loop: Header=BB140_4 Depth=1
	strb	w10, [x9]
LBB140_3:                               ;   in Loop: Header=BB140_4 Depth=1
	mov	x10, x9
	cmp	x9, x23
	b.ls	LBB140_10
LBB140_4:                               ; =>This Inner Loop Header: Depth=1
	ldrsb	w11, [x9, #-1]!
	cmp	w11, #46
	b.eq	LBB140_3
; %bb.5:                                ;   in Loop: Header=BB140_4 Depth=1
	cmp	w20, #1
	b.lt	LBB140_8
; %bb.6:                                ;   in Loop: Header=BB140_4 Depth=1
	cmp	w11, #57
	b.lt	LBB140_15
; %bb.7:                                ;   in Loop: Header=BB140_4 Depth=1
	mov	w10, #48                        ; =0x30
	b	LBB140_2
LBB140_8:                               ;   in Loop: Header=BB140_4 Depth=1
	cmp	w11, #48
	b.gt	LBB140_16
; %bb.9:                                ;   in Loop: Header=BB140_4 Depth=1
	mov	w10, #57                        ; =0x39
	b	LBB140_2
LBB140_10:
	mov	w9, #49                         ; =0x31
	strb	w9, [x23]
	add	w8, w8, #1
LBB140_11:
	add	x9, sp, #16
	sub	x9, x9, x21
	str	x8, [sp]
Lloh282:
	adrp	x2, l_.str.68@PAGE
Lloh283:
	add	x2, x2, l_.str.68@PAGEOFF
	add	x1, x9, #40
	mov	x0, x21
	bl	_snprintf
	add	x0, sp, #16
	mov	x1, #0                          ; =0x0
	bl	_strtod
	fmov	d9, d0
	fcmp	d0, d8
	b.ne	LBB140_13
; %bb.12:
	add	x0, sp, #16
	bl	_strlen
	add	x1, sp, #16
	add	x2, x0, #1
	mov	x0, x19
	bl	_memcpy
LBB140_13:
	fcmp	d9, d8
	cset	w0, eq
	ldr	x8, [sp, #56]
Lloh284:
	adrp	x9, ___stack_chk_guard@GOTPAGE
Lloh285:
	ldr	x9, [x9, ___stack_chk_guard@GOTPAGEOFF]
Lloh286:
	ldr	x9, [x9]
	cmp	x9, x8
	b.ne	LBB140_23
; %bb.14:
	ldp	x29, x30, [sp, #128]            ; 16-byte Folded Reload
	ldp	x20, x19, [sp, #112]            ; 16-byte Folded Reload
	ldp	x22, x21, [sp, #96]             ; 16-byte Folded Reload
	ldp	x24, x23, [sp, #80]             ; 16-byte Folded Reload
	ldp	d9, d8, [sp, #64]               ; 16-byte Folded Reload
	add	sp, sp, #144
	ret
LBB140_15:
	mov	w9, #1                          ; =0x1
	b	LBB140_17
LBB140_16:
	mov	w9, #255                        ; =0xff
LBB140_17:
	add	w9, w11, w9
	sturb	w9, [x10, #-1]
	ldrb	w9, [x23]
	cmp	w9, #48
	b.ne	LBB140_11
; %bb.18:
	add	x9, sp, #16
	add	x9, x22, x9
	add	x9, x9, #1
	mov	w11, #48                        ; =0x30
	mov	w10, #57                        ; =0x39
	cmp	w11, #46
	b.eq	LBB140_20
LBB140_19:
	sturb	w10, [x9, #-1]
LBB140_20:                              ; =>This Inner Loop Header: Depth=1
	cmp	x9, x21
	b.hs	LBB140_22
; %bb.21:                               ;   in Loop: Header=BB140_20 Depth=1
	ldrb	w11, [x9], #1
	cmp	w11, #46
	b.ne	LBB140_19
	b	LBB140_20
LBB140_22:
	sub	w8, w8, #1
	b	LBB140_11
LBB140_23:
	bl	___stack_chk_fail
	.loh AdrpLdrGotLdr	Lloh279, Lloh280, Lloh281
	.loh AdrpAdd	Lloh282, Lloh283
	.loh AdrpLdrGotLdr	Lloh284, Lloh285, Lloh286
	.cfi_endproc
                                        ; -- End function
	.p2align	2                               ; -- Begin function minyar_stack_enter.cold.1
_minyar_stack_enter.cold.1:             ; @minyar_stack_enter.cold.1
	.cfi_startproc
; %bb.0:
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
Lloh287:
	adrp	x0, l_.str@PAGE
Lloh288:
	add	x0, x0, l_.str@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh287, Lloh288
	.cfi_endproc
                                        ; -- End function
	.p2align	2                               ; -- Begin function minyar_stack_leave.cold.1
_minyar_stack_leave.cold.1:             ; @minyar_stack_leave.cold.1
	.cfi_startproc
; %bb.0:
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
Lloh289:
	adrp	x0, l_.str.1@PAGE
Lloh290:
	add	x0, x0, l_.str.1@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh289, Lloh290
	.cfi_endproc
                                        ; -- End function
	.p2align	2                               ; -- Begin function minyar_rc_retain.cold.1
_minyar_rc_retain.cold.1:               ; @minyar_rc_retain.cold.1
	.cfi_startproc
; %bb.0:
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
Lloh291:
	adrp	x0, l_.str.2@PAGE
Lloh292:
	add	x0, x0, l_.str.2@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh291, Lloh292
	.cfi_endproc
                                        ; -- End function
	.p2align	2                               ; -- Begin function minyar_rc_local.cold.1
_minyar_rc_local.cold.1:                ; @minyar_rc_local.cold.1
	.cfi_startproc
; %bb.0:
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
Lloh293:
	adrp	x0, l_.str.2@PAGE
Lloh294:
	add	x0, x0, l_.str.2@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh293, Lloh294
	.cfi_endproc
                                        ; -- End function
	.p2align	2                               ; -- Begin function minyar_rc_borrow.cold.1
_minyar_rc_borrow.cold.1:               ; @minyar_rc_borrow.cold.1
	.cfi_startproc
; %bb.0:
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
Lloh295:
	adrp	x0, l_.str.2@PAGE
Lloh296:
	add	x0, x0, l_.str.2@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh295, Lloh296
	.cfi_endproc
                                        ; -- End function
	.p2align	2                               ; -- Begin function minyar_list_add.cold.1
_minyar_list_add.cold.1:                ; @minyar_list_add.cold.1
	.cfi_startproc
; %bb.0:
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
Lloh297:
	adrp	x0, l_.str.2@PAGE
Lloh298:
	add	x0, x0, l_.str.2@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh297, Lloh298
	.cfi_endproc
                                        ; -- End function
	.p2align	2                               ; -- Begin function minyar_list_set_owned.cold.1
_minyar_list_set_owned.cold.1:          ; @minyar_list_set_owned.cold.1
	.cfi_startproc
; %bb.0:
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
Lloh299:
	adrp	x0, l_.str.2@PAGE
Lloh300:
	add	x0, x0, l_.str.2@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh299, Lloh300
	.cfi_endproc
                                        ; -- End function
	.p2align	2                               ; -- Begin function minyar_list_appended.cold.1
_minyar_list_appended.cold.1:           ; @minyar_list_appended.cold.1
	.cfi_startproc
; %bb.0:
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
Lloh301:
	adrp	x0, l_.str.3@PAGE
Lloh302:
	add	x0, x0, l_.str.3@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh301, Lloh302
	.cfi_endproc
                                        ; -- End function
	.p2align	2                               ; -- Begin function minyar_record_new.cold.1
_minyar_record_new.cold.1:              ; @minyar_record_new.cold.1
	.cfi_startproc
; %bb.0:
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
Lloh303:
	adrp	x0, l_.str.50@PAGE
Lloh304:
	add	x0, x0, l_.str.50@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh303, Lloh304
	.cfi_endproc
                                        ; -- End function
	.p2align	2                               ; -- Begin function minyar_record_new_scalar.cold.1
_minyar_record_new_scalar.cold.1:       ; @minyar_record_new_scalar.cold.1
	.cfi_startproc
; %bb.0:
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
Lloh305:
	adrp	x0, l_.str.50@PAGE
Lloh306:
	add	x0, x0, l_.str.50@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh305, Lloh306
	.cfi_endproc
                                        ; -- End function
	.p2align	2                               ; -- Begin function minyar_record_set_reference.cold.1
_minyar_record_set_reference.cold.1:    ; @minyar_record_set_reference.cold.1
	.cfi_startproc
; %bb.0:
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
Lloh307:
	adrp	x0, l_.str.2@PAGE
Lloh308:
	add	x0, x0, l_.str.2@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh307, Lloh308
	.cfi_endproc
                                        ; -- End function
	.p2align	2                               ; -- Begin function minyar_record_replace.cold.1
_minyar_record_replace.cold.1:          ; @minyar_record_replace.cold.1
	.cfi_startproc
; %bb.0:
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
Lloh309:
	adrp	x0, l_.str.2@PAGE
Lloh310:
	add	x0, x0, l_.str.2@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh309, Lloh310
	.cfi_endproc
                                        ; -- End function
	.p2align	2                               ; -- Begin function minyar_print_character.cold.1
_minyar_print_character.cold.1:         ; @minyar_print_character.cold.1
	.cfi_startproc
; %bb.0:
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
Lloh311:
	adrp	x0, l_.str.58@PAGE
Lloh312:
	add	x0, x0, l_.str.58@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh311, Lloh312
	.cfi_endproc
                                        ; -- End function
	.p2align	2                               ; -- Begin function minyar_text_slice.cold.1
_minyar_text_slice.cold.1:              ; @minyar_text_slice.cold.1
	.cfi_startproc
; %bb.0:
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
Lloh313:
	adrp	x0, l_.str.2@PAGE
Lloh314:
	add	x0, x0, l_.str.2@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh313, Lloh314
	.cfi_endproc
                                        ; -- End function
	.p2align	2                               ; -- Begin function minyar_text_slice.cold.2
_minyar_text_slice.cold.2:              ; @minyar_text_slice.cold.2
	.cfi_startproc
; %bb.0:
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
Lloh315:
	adrp	x0, l_.str.2@PAGE
Lloh316:
	add	x0, x0, l_.str.2@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh315, Lloh316
	.cfi_endproc
                                        ; -- End function
	.p2align	2                               ; -- Begin function minyar_argument.cold.1
_minyar_argument.cold.1:                ; @minyar_argument.cold.1
	.cfi_startproc
; %bb.0:
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
Lloh317:
	adrp	x0, l_.str.8@PAGE
Lloh318:
	add	x0, x0, l_.str.8@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh317, Lloh318
	.cfi_endproc
                                        ; -- End function
	.p2align	2                               ; -- Begin function minyar_read_text_file.cold.1
_minyar_read_text_file.cold.1:          ; @minyar_read_text_file.cold.1
	.cfi_startproc
; %bb.0:
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
Lloh319:
	adrp	x0, l_.str.59@PAGE
Lloh320:
	add	x0, x0, l_.str.59@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh319, Lloh320
	.cfi_endproc
                                        ; -- End function
	.p2align	2                               ; -- Begin function minyar_read_text_file.cold.2
_minyar_read_text_file.cold.2:          ; @minyar_read_text_file.cold.2
	.cfi_startproc
; %bb.0:
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
Lloh321:
	adrp	x0, l_.str.11@PAGE
Lloh322:
	add	x0, x0, l_.str.11@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh321, Lloh322
	.cfi_endproc
                                        ; -- End function
	.p2align	2                               ; -- Begin function text_file_length.cold.1
_text_file_length.cold.1:               ; @text_file_length.cold.1
	.cfi_startproc
; %bb.0:
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
Lloh323:
	adrp	x0, l_.str.11@PAGE
Lloh324:
	add	x0, x0, l_.str.11@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh323, Lloh324
	.cfi_endproc
                                        ; -- End function
	.p2align	2                               ; -- Begin function text_file_length.cold.2
_text_file_length.cold.2:               ; @text_file_length.cold.2
	.cfi_startproc
; %bb.0:
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
Lloh325:
	adrp	x0, l_.str.11@PAGE
Lloh326:
	add	x0, x0, l_.str.11@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh325, Lloh326
	.cfi_endproc
                                        ; -- End function
	.p2align	2                               ; -- Begin function minyar_write_text_file.cold.1
_minyar_write_text_file.cold.1:         ; @minyar_write_text_file.cold.1
	.cfi_startproc
; %bb.0:
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
Lloh327:
	adrp	x0, l_.str.59@PAGE
Lloh328:
	add	x0, x0, l_.str.59@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh327, Lloh328
	.cfi_endproc
                                        ; -- End function
	.p2align	2                               ; -- Begin function minyar_write_text_file.cold.2
_minyar_write_text_file.cold.2:         ; @minyar_write_text_file.cold.2
	.cfi_startproc
; %bb.0:
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
Lloh329:
	adrp	x0, l_.str.14@PAGE
Lloh330:
	add	x0, x0, l_.str.14@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh329, Lloh330
	.cfi_endproc
                                        ; -- End function
	.p2align	2                               ; -- Begin function minyar_write_text_file.cold.3
_minyar_write_text_file.cold.3:         ; @minyar_write_text_file.cold.3
	.cfi_startproc
; %bb.0:
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
Lloh331:
	adrp	x0, l_.str.13@PAGE
Lloh332:
	add	x0, x0, l_.str.13@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh331, Lloh332
	.cfi_endproc
                                        ; -- End function
	.p2align	2                               ; -- Begin function minyar_float_integer.cold.1
_minyar_float_integer.cold.1:           ; @minyar_float_integer.cold.1
	.cfi_startproc
; %bb.0:
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
Lloh333:
	adrp	x8, l_.str.18@PAGE
Lloh334:
	add	x8, x8, l_.str.18@PAGEOFF
Lloh335:
	adrp	x9, l_.str.19@PAGE
Lloh336:
	add	x9, x9, l_.str.19@PAGEOFF
	fcmp	d0, d0
	csel	x0, x9, x8, vc
	bl	_minyar_stop
	.loh AdrpAdd	Lloh335, Lloh336
	.loh AdrpAdd	Lloh333, Lloh334
	.cfi_endproc
                                        ; -- End function
	.p2align	2                               ; -- Begin function minyar_integer_character.cold.1
_minyar_integer_character.cold.1:       ; @minyar_integer_character.cold.1
	.cfi_startproc
; %bb.0:
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
Lloh337:
	adrp	x0, l_.str.20@PAGE
Lloh338:
	add	x0, x0, l_.str.20@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh337, Lloh338
	.cfi_endproc
                                        ; -- End function
	.p2align	2                               ; -- Begin function minyar_integer_absolute.cold.1
_minyar_integer_absolute.cold.1:        ; @minyar_integer_absolute.cold.1
	.cfi_startproc
; %bb.0:
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
Lloh339:
	adrp	x0, l_.str.21@PAGE
Lloh340:
	add	x0, x0, l_.str.21@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh339, Lloh340
	.cfi_endproc
                                        ; -- End function
	.p2align	2                               ; -- Begin function minyar_check_clamp_integer.cold.1
_minyar_check_clamp_integer.cold.1:     ; @minyar_check_clamp_integer.cold.1
	.cfi_startproc
; %bb.0:
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
Lloh341:
	adrp	x0, l_.str.22@PAGE
Lloh342:
	add	x0, x0, l_.str.22@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh341, Lloh342
	.cfi_endproc
                                        ; -- End function
	.p2align	2                               ; -- Begin function minyar_check_clamp_float.cold.1
_minyar_check_clamp_float.cold.1:       ; @minyar_check_clamp_float.cold.1
	.cfi_startproc
; %bb.0:
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
Lloh343:
	adrp	x0, l_.str.22@PAGE
Lloh344:
	add	x0, x0, l_.str.22@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh343, Lloh344
	.cfi_endproc
                                        ; -- End function
	.p2align	2                               ; -- Begin function minyar_check_shift.cold.1
_minyar_check_shift.cold.1:             ; @minyar_check_shift.cold.1
	.cfi_startproc
; %bb.0:
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
Lloh345:
	adrp	x0, l_.str.23@PAGE
Lloh346:
	add	x0, x0, l_.str.23@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh345, Lloh346
	.cfi_endproc
                                        ; -- End function
	.p2align	2                               ; -- Begin function minyar_bytes_new.cold.1
_minyar_bytes_new.cold.1:               ; @minyar_bytes_new.cold.1
	.cfi_startproc
; %bb.0:
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
Lloh347:
	adrp	x0, l_.str.25@PAGE
Lloh348:
	add	x0, x0, l_.str.25@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh347, Lloh348
	.cfi_endproc
                                        ; -- End function
	.p2align	2                               ; -- Begin function minyar_bytes_new.cold.2
_minyar_bytes_new.cold.2:               ; @minyar_bytes_new.cold.2
	.cfi_startproc
; %bb.0:
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
Lloh349:
	adrp	x0, l_.str.24@PAGE
Lloh350:
	add	x0, x0, l_.str.24@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh349, Lloh350
	.cfi_endproc
                                        ; -- End function
	.p2align	2                               ; -- Begin function minyar_bytes_resize.cold.1
_minyar_bytes_resize.cold.1:            ; @minyar_bytes_resize.cold.1
	.cfi_startproc
; %bb.0:
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
Lloh351:
	adrp	x0, l_.str.25@PAGE
Lloh352:
	add	x0, x0, l_.str.25@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh351, Lloh352
	.cfi_endproc
                                        ; -- End function
	.p2align	2                               ; -- Begin function minyar_bytes_resize.cold.2
_minyar_bytes_resize.cold.2:            ; @minyar_bytes_resize.cold.2
	.cfi_startproc
; %bb.0:
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
Lloh353:
	adrp	x0, l_.str.25@PAGE
Lloh354:
	add	x0, x0, l_.str.25@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh353, Lloh354
	.cfi_endproc
                                        ; -- End function
	.p2align	2                               ; -- Begin function minyar_bytes_resize.cold.3
_minyar_bytes_resize.cold.3:            ; @minyar_bytes_resize.cold.3
	.cfi_startproc
; %bb.0:
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
Lloh355:
	adrp	x0, l_.str.24@PAGE
Lloh356:
	add	x0, x0, l_.str.24@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh355, Lloh356
	.cfi_endproc
                                        ; -- End function
	.p2align	2                               ; -- Begin function minyar_bytes_add_int16.cold.1
_minyar_bytes_add_int16.cold.1:         ; @minyar_bytes_add_int16.cold.1
	.cfi_startproc
; %bb.0:
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
Lloh357:
	adrp	x0, l_.str.25@PAGE
Lloh358:
	add	x0, x0, l_.str.25@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh357, Lloh358
	.cfi_endproc
                                        ; -- End function
	.p2align	2                               ; -- Begin function minyar_bytes_add_int16.cold.2
_minyar_bytes_add_int16.cold.2:         ; @minyar_bytes_add_int16.cold.2
	.cfi_startproc
; %bb.0:
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
Lloh359:
	adrp	x0, l_.str.25@PAGE
Lloh360:
	add	x0, x0, l_.str.25@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh359, Lloh360
	.cfi_endproc
                                        ; -- End function
	.p2align	2                               ; -- Begin function minyar_bytes_add_uint16.cold.1
_minyar_bytes_add_uint16.cold.1:        ; @minyar_bytes_add_uint16.cold.1
	.cfi_startproc
; %bb.0:
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
Lloh361:
	adrp	x0, l_.str.25@PAGE
Lloh362:
	add	x0, x0, l_.str.25@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh361, Lloh362
	.cfi_endproc
                                        ; -- End function
	.p2align	2                               ; -- Begin function minyar_bytes_add_uint16.cold.2
_minyar_bytes_add_uint16.cold.2:        ; @minyar_bytes_add_uint16.cold.2
	.cfi_startproc
; %bb.0:
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
Lloh363:
	adrp	x0, l_.str.25@PAGE
Lloh364:
	add	x0, x0, l_.str.25@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh363, Lloh364
	.cfi_endproc
                                        ; -- End function
	.p2align	2                               ; -- Begin function minyar_bytes_add_int32.cold.1
_minyar_bytes_add_int32.cold.1:         ; @minyar_bytes_add_int32.cold.1
	.cfi_startproc
; %bb.0:
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
Lloh365:
	adrp	x0, l_.str.25@PAGE
Lloh366:
	add	x0, x0, l_.str.25@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh365, Lloh366
	.cfi_endproc
                                        ; -- End function
	.p2align	2                               ; -- Begin function minyar_bytes_add_int32.cold.2
_minyar_bytes_add_int32.cold.2:         ; @minyar_bytes_add_int32.cold.2
	.cfi_startproc
; %bb.0:
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
Lloh367:
	adrp	x0, l_.str.25@PAGE
Lloh368:
	add	x0, x0, l_.str.25@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh367, Lloh368
	.cfi_endproc
                                        ; -- End function
	.p2align	2                               ; -- Begin function minyar_bytes_add_uint32.cold.1
_minyar_bytes_add_uint32.cold.1:        ; @minyar_bytes_add_uint32.cold.1
	.cfi_startproc
; %bb.0:
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
Lloh369:
	adrp	x0, l_.str.25@PAGE
Lloh370:
	add	x0, x0, l_.str.25@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh369, Lloh370
	.cfi_endproc
                                        ; -- End function
	.p2align	2                               ; -- Begin function minyar_bytes_add_uint32.cold.2
_minyar_bytes_add_uint32.cold.2:        ; @minyar_bytes_add_uint32.cold.2
	.cfi_startproc
; %bb.0:
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
Lloh371:
	adrp	x0, l_.str.25@PAGE
Lloh372:
	add	x0, x0, l_.str.25@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh371, Lloh372
	.cfi_endproc
                                        ; -- End function
	.p2align	2                               ; -- Begin function minyar_bytes_add_int64.cold.1
_minyar_bytes_add_int64.cold.1:         ; @minyar_bytes_add_int64.cold.1
	.cfi_startproc
; %bb.0:
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
Lloh373:
	adrp	x0, l_.str.25@PAGE
Lloh374:
	add	x0, x0, l_.str.25@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh373, Lloh374
	.cfi_endproc
                                        ; -- End function
	.p2align	2                               ; -- Begin function minyar_bytes_add_int64.cold.2
_minyar_bytes_add_int64.cold.2:         ; @minyar_bytes_add_int64.cold.2
	.cfi_startproc
; %bb.0:
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
Lloh375:
	adrp	x0, l_.str.25@PAGE
Lloh376:
	add	x0, x0, l_.str.25@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh375, Lloh376
	.cfi_endproc
                                        ; -- End function
	.p2align	2                               ; -- Begin function minyar_bytes_add.cold.1
_minyar_bytes_add.cold.1:               ; @minyar_bytes_add.cold.1
	.cfi_startproc
; %bb.0:
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
Lloh377:
	adrp	x0, l_.str.25@PAGE
Lloh378:
	add	x0, x0, l_.str.25@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh377, Lloh378
	.cfi_endproc
                                        ; -- End function
	.p2align	2                               ; -- Begin function minyar_bytes_add.cold.2
_minyar_bytes_add.cold.2:               ; @minyar_bytes_add.cold.2
	.cfi_startproc
; %bb.0:
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
Lloh379:
	adrp	x0, l_.str.25@PAGE
Lloh380:
	add	x0, x0, l_.str.25@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh379, Lloh380
	.cfi_endproc
                                        ; -- End function
	.p2align	2                               ; -- Begin function minyar_bytes_add_float32.cold.1
_minyar_bytes_add_float32.cold.1:       ; @minyar_bytes_add_float32.cold.1
	.cfi_startproc
; %bb.0:
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
Lloh381:
	adrp	x0, l_.str.25@PAGE
Lloh382:
	add	x0, x0, l_.str.25@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh381, Lloh382
	.cfi_endproc
                                        ; -- End function
	.p2align	2                               ; -- Begin function minyar_bytes_add_float32.cold.2
_minyar_bytes_add_float32.cold.2:       ; @minyar_bytes_add_float32.cold.2
	.cfi_startproc
; %bb.0:
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
Lloh383:
	adrp	x0, l_.str.25@PAGE
Lloh384:
	add	x0, x0, l_.str.25@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh383, Lloh384
	.cfi_endproc
                                        ; -- End function
	.p2align	2                               ; -- Begin function minyar_bytes_add_float64.cold.1
_minyar_bytes_add_float64.cold.1:       ; @minyar_bytes_add_float64.cold.1
	.cfi_startproc
; %bb.0:
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
Lloh385:
	adrp	x0, l_.str.25@PAGE
Lloh386:
	add	x0, x0, l_.str.25@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh385, Lloh386
	.cfi_endproc
                                        ; -- End function
	.p2align	2                               ; -- Begin function minyar_bytes_add_float64.cold.2
_minyar_bytes_add_float64.cold.2:       ; @minyar_bytes_add_float64.cold.2
	.cfi_startproc
; %bb.0:
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
Lloh387:
	adrp	x0, l_.str.25@PAGE
Lloh388:
	add	x0, x0, l_.str.25@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh387, Lloh388
	.cfi_endproc
                                        ; -- End function
	.p2align	2                               ; -- Begin function minyar_bytes_append.cold.1
_minyar_bytes_append.cold.1:            ; @minyar_bytes_append.cold.1
	.cfi_startproc
; %bb.0:
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
Lloh389:
	adrp	x0, l_.str.25@PAGE
Lloh390:
	add	x0, x0, l_.str.25@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh389, Lloh390
	.cfi_endproc
                                        ; -- End function
	.p2align	2                               ; -- Begin function minyar_bytes_append.cold.2
_minyar_bytes_append.cold.2:            ; @minyar_bytes_append.cold.2
	.cfi_startproc
; %bb.0:
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
Lloh391:
	adrp	x0, l_.str.25@PAGE
Lloh392:
	add	x0, x0, l_.str.25@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh391, Lloh392
	.cfi_endproc
                                        ; -- End function
	.p2align	2                               ; -- Begin function minyar_read_bytes_file.cold.1
_minyar_read_bytes_file.cold.1:         ; @minyar_read_bytes_file.cold.1
	.cfi_startproc
; %bb.0:
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
Lloh393:
	adrp	x0, l_.str.59@PAGE
Lloh394:
	add	x0, x0, l_.str.59@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh393, Lloh394
	.cfi_endproc
                                        ; -- End function
	.p2align	2                               ; -- Begin function minyar_read_bytes_file.cold.2
_minyar_read_bytes_file.cold.2:         ; @minyar_read_bytes_file.cold.2
	.cfi_startproc
; %bb.0:
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
Lloh395:
	adrp	x0, l_.str.28@PAGE
Lloh396:
	add	x0, x0, l_.str.28@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh395, Lloh396
	.cfi_endproc
                                        ; -- End function
	.p2align	2                               ; -- Begin function minyar_write_bytes_file.cold.1
_minyar_write_bytes_file.cold.1:        ; @minyar_write_bytes_file.cold.1
	.cfi_startproc
; %bb.0:
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
Lloh397:
	adrp	x0, l_.str.59@PAGE
Lloh398:
	add	x0, x0, l_.str.59@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh397, Lloh398
	.cfi_endproc
                                        ; -- End function
	.p2align	2                               ; -- Begin function minyar_write_bytes_file.cold.2
_minyar_write_bytes_file.cold.2:        ; @minyar_write_bytes_file.cold.2
	.cfi_startproc
; %bb.0:
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
Lloh399:
	adrp	x0, l_.str.30@PAGE
Lloh400:
	add	x0, x0, l_.str.30@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh399, Lloh400
	.cfi_endproc
                                        ; -- End function
	.p2align	2                               ; -- Begin function minyar_write_bytes_file.cold.3
_minyar_write_bytes_file.cold.3:        ; @minyar_write_bytes_file.cold.3
	.cfi_startproc
; %bb.0:
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
Lloh401:
	adrp	x0, l_.str.29@PAGE
Lloh402:
	add	x0, x0, l_.str.29@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh401, Lloh402
	.cfi_endproc
                                        ; -- End function
	.p2align	2                               ; -- Begin function minyar_file_exists.cold.1
_minyar_file_exists.cold.1:             ; @minyar_file_exists.cold.1
	.cfi_startproc
; %bb.0:
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
Lloh403:
	adrp	x0, l_.str.59@PAGE
Lloh404:
	add	x0, x0, l_.str.59@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh403, Lloh404
	.cfi_endproc
                                        ; -- End function
	.p2align	2                               ; -- Begin function minyar_bytes_extend.cold.1
_minyar_bytes_extend.cold.1:            ; @minyar_bytes_extend.cold.1
	.cfi_startproc
; %bb.0:
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
Lloh405:
	adrp	x0, l_.str.25@PAGE
Lloh406:
	add	x0, x0, l_.str.25@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh405, Lloh406
	.cfi_endproc
                                        ; -- End function
	.p2align	2                               ; -- Begin function minyar_bytes_extend.cold.2
_minyar_bytes_extend.cold.2:            ; @minyar_bytes_extend.cold.2
	.cfi_startproc
; %bb.0:
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
Lloh407:
	adrp	x0, l_.str.25@PAGE
Lloh408:
	add	x0, x0, l_.str.25@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh407, Lloh408
	.cfi_endproc
                                        ; -- End function
	.p2align	2                               ; -- Begin function minyar_bytes_extend.cold.3
_minyar_bytes_extend.cold.3:            ; @minyar_bytes_extend.cold.3
	.cfi_startproc
; %bb.0:
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
Lloh409:
	adrp	x0, l_.str.31@PAGE
Lloh410:
	add	x0, x0, l_.str.31@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh409, Lloh410
	.cfi_endproc
                                        ; -- End function
	.p2align	2                               ; -- Begin function main.cold.1
_main.cold.1:                           ; @main.cold.1
	.cfi_startproc
; %bb.0:
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
Lloh411:
	adrp	x0, l___func__.main@PAGE
Lloh412:
	add	x0, x0, l___func__.main@PAGEOFF
Lloh413:
	adrp	x1, l_.str.32@PAGE
Lloh414:
	add	x1, x1, l_.str.32@PAGEOFF
Lloh415:
	adrp	x3, l_.str.33@PAGE
Lloh416:
	add	x3, x3, l_.str.33@PAGEOFF
	mov	w2, #29                         ; =0x1d
	bl	___assert_rtn
	.loh AdrpAdd	Lloh415, Lloh416
	.loh AdrpAdd	Lloh413, Lloh414
	.loh AdrpAdd	Lloh411, Lloh412
	.cfi_endproc
                                        ; -- End function
	.p2align	2                               ; -- Begin function main.cold.2
_main.cold.2:                           ; @main.cold.2
	.cfi_startproc
; %bb.0:
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
Lloh417:
	adrp	x0, l_.str.2@PAGE
Lloh418:
	add	x0, x0, l_.str.2@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh417, Lloh418
	.cfi_endproc
                                        ; -- End function
	.p2align	2                               ; -- Begin function main.cold.3
_main.cold.3:                           ; @main.cold.3
	.cfi_startproc
; %bb.0:
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
Lloh419:
	adrp	x0, l___func__.cpu_nanoseconds@PAGE
Lloh420:
	add	x0, x0, l___func__.cpu_nanoseconds@PAGEOFF
Lloh421:
	adrp	x1, l_.str.32@PAGE
Lloh422:
	add	x1, x1, l_.str.32@PAGEOFF
Lloh423:
	adrp	x3, l_.str.77@PAGE
Lloh424:
	add	x3, x3, l_.str.77@PAGEOFF
	mov	w2, #24                         ; =0x18
	bl	___assert_rtn
	.loh AdrpAdd	Lloh423, Lloh424
	.loh AdrpAdd	Lloh421, Lloh422
	.loh AdrpAdd	Lloh419, Lloh420
	.cfi_endproc
                                        ; -- End function
	.p2align	2                               ; -- Begin function main.cold.4
_main.cold.4:                           ; @main.cold.4
	.cfi_startproc
; %bb.0:
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
Lloh425:
	adrp	x0, l___func__.main@PAGE
Lloh426:
	add	x0, x0, l___func__.main@PAGEOFF
Lloh427:
	adrp	x1, l_.str.32@PAGE
Lloh428:
	add	x1, x1, l_.str.32@PAGEOFF
Lloh429:
	adrp	x3, l_.str.37@PAGE
Lloh430:
	add	x3, x3, l_.str.37@PAGEOFF
	mov	w2, #71                         ; =0x47
	bl	___assert_rtn
	.loh AdrpAdd	Lloh429, Lloh430
	.loh AdrpAdd	Lloh427, Lloh428
	.loh AdrpAdd	Lloh425, Lloh426
	.cfi_endproc
                                        ; -- End function
	.p2align	2                               ; -- Begin function main.cold.5
_main.cold.5:                           ; @main.cold.5
	.cfi_startproc
; %bb.0:
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
Lloh431:
	adrp	x0, l___func__.main@PAGE
Lloh432:
	add	x0, x0, l___func__.main@PAGEOFF
Lloh433:
	adrp	x1, l_.str.32@PAGE
Lloh434:
	add	x1, x1, l_.str.32@PAGEOFF
Lloh435:
	adrp	x3, l_.str.36@PAGE
Lloh436:
	add	x3, x3, l_.str.36@PAGEOFF
	mov	w2, #69                         ; =0x45
	bl	___assert_rtn
	.loh AdrpAdd	Lloh435, Lloh436
	.loh AdrpAdd	Lloh433, Lloh434
	.loh AdrpAdd	Lloh431, Lloh432
	.cfi_endproc
                                        ; -- End function
	.p2align	2                               ; -- Begin function main.cold.6
_main.cold.6:                           ; @main.cold.6
	.cfi_startproc
; %bb.0:
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
Lloh437:
	adrp	x0, l___func__.cpu_nanoseconds@PAGE
Lloh438:
	add	x0, x0, l___func__.cpu_nanoseconds@PAGEOFF
Lloh439:
	adrp	x1, l_.str.32@PAGE
Lloh440:
	add	x1, x1, l_.str.32@PAGEOFF
Lloh441:
	adrp	x3, l_.str.77@PAGE
Lloh442:
	add	x3, x3, l_.str.77@PAGEOFF
	mov	w2, #24                         ; =0x18
	bl	___assert_rtn
	.loh AdrpAdd	Lloh441, Lloh442
	.loh AdrpAdd	Lloh439, Lloh440
	.loh AdrpAdd	Lloh437, Lloh438
	.cfi_endproc
                                        ; -- End function
	.p2align	2                               ; -- Begin function main.cold.7
_main.cold.7:                           ; @main.cold.7
	.cfi_startproc
; %bb.0:
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
Lloh443:
	adrp	x0, l___func__.main@PAGE
Lloh444:
	add	x0, x0, l___func__.main@PAGEOFF
Lloh445:
	adrp	x1, l_.str.32@PAGE
Lloh446:
	add	x1, x1, l_.str.32@PAGEOFF
Lloh447:
	adrp	x3, l_.str.39@PAGE
Lloh448:
	add	x3, x3, l_.str.39@PAGEOFF
	mov	w2, #83                         ; =0x53
	bl	___assert_rtn
	.loh AdrpAdd	Lloh447, Lloh448
	.loh AdrpAdd	Lloh445, Lloh446
	.loh AdrpAdd	Lloh443, Lloh444
	.cfi_endproc
                                        ; -- End function
	.p2align	2                               ; -- Begin function main.cold.8
_main.cold.8:                           ; @main.cold.8
	.cfi_startproc
; %bb.0:
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
Lloh449:
	adrp	x0, l___func__.main@PAGE
Lloh450:
	add	x0, x0, l___func__.main@PAGEOFF
Lloh451:
	adrp	x1, l_.str.32@PAGE
Lloh452:
	add	x1, x1, l_.str.32@PAGEOFF
Lloh453:
	adrp	x3, l_.str.40@PAGE
Lloh454:
	add	x3, x3, l_.str.40@PAGEOFF
	mov	w2, #84                         ; =0x54
	bl	___assert_rtn
	.loh AdrpAdd	Lloh453, Lloh454
	.loh AdrpAdd	Lloh451, Lloh452
	.loh AdrpAdd	Lloh449, Lloh450
	.cfi_endproc
                                        ; -- End function
	.p2align	2                               ; -- Begin function main.cold.9
_main.cold.9:                           ; @main.cold.9
	.cfi_startproc
; %bb.0:
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
Lloh455:
	adrp	x0, l___func__.main@PAGE
Lloh456:
	add	x0, x0, l___func__.main@PAGEOFF
Lloh457:
	adrp	x1, l_.str.32@PAGE
Lloh458:
	add	x1, x1, l_.str.32@PAGEOFF
Lloh459:
	adrp	x3, l_.str.41@PAGE
Lloh460:
	add	x3, x3, l_.str.41@PAGEOFF
	mov	w2, #86                         ; =0x56
	bl	___assert_rtn
	.loh AdrpAdd	Lloh459, Lloh460
	.loh AdrpAdd	Lloh457, Lloh458
	.loh AdrpAdd	Lloh455, Lloh456
	.cfi_endproc
                                        ; -- End function
	.p2align	2                               ; -- Begin function main.cold.10
_main.cold.10:                          ; @main.cold.10
	.cfi_startproc
; %bb.0:
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
Lloh461:
	adrp	x0, l___func__.main@PAGE
Lloh462:
	add	x0, x0, l___func__.main@PAGEOFF
Lloh463:
	adrp	x1, l_.str.32@PAGE
Lloh464:
	add	x1, x1, l_.str.32@PAGEOFF
Lloh465:
	adrp	x3, l_.str.42@PAGE
Lloh466:
	add	x3, x3, l_.str.42@PAGEOFF
	mov	w2, #90                         ; =0x5a
	bl	___assert_rtn
	.loh AdrpAdd	Lloh465, Lloh466
	.loh AdrpAdd	Lloh463, Lloh464
	.loh AdrpAdd	Lloh461, Lloh462
	.cfi_endproc
                                        ; -- End function
	.p2align	2                               ; -- Begin function main.cold.11
_main.cold.11:                          ; @main.cold.11
	.cfi_startproc
; %bb.0:
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
Lloh467:
	adrp	x0, l___func__.main@PAGE
Lloh468:
	add	x0, x0, l___func__.main@PAGEOFF
Lloh469:
	adrp	x1, l_.str.32@PAGE
Lloh470:
	add	x1, x1, l_.str.32@PAGEOFF
Lloh471:
	adrp	x3, l_.str.43@PAGE
Lloh472:
	add	x3, x3, l_.str.43@PAGEOFF
	mov	w2, #94                         ; =0x5e
	bl	___assert_rtn
	.loh AdrpAdd	Lloh471, Lloh472
	.loh AdrpAdd	Lloh469, Lloh470
	.loh AdrpAdd	Lloh467, Lloh468
	.cfi_endproc
                                        ; -- End function
	.p2align	2                               ; -- Begin function main.cold.12
_main.cold.12:                          ; @main.cold.12
	.cfi_startproc
; %bb.0:
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
Lloh473:
	adrp	x0, l___func__.main@PAGE
Lloh474:
	add	x0, x0, l___func__.main@PAGEOFF
Lloh475:
	adrp	x1, l_.str.32@PAGE
Lloh476:
	add	x1, x1, l_.str.32@PAGEOFF
Lloh477:
	adrp	x3, l_.str.45@PAGE
Lloh478:
	add	x3, x3, l_.str.45@PAGEOFF
	mov	w2, #103                        ; =0x67
	bl	___assert_rtn
	.loh AdrpAdd	Lloh477, Lloh478
	.loh AdrpAdd	Lloh475, Lloh476
	.loh AdrpAdd	Lloh473, Lloh474
	.cfi_endproc
                                        ; -- End function
	.p2align	2                               ; -- Begin function main.cold.13
_main.cold.13:                          ; @main.cold.13
	.cfi_startproc
; %bb.0:
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
Lloh479:
	adrp	x0, l___func__.main@PAGE
Lloh480:
	add	x0, x0, l___func__.main@PAGEOFF
Lloh481:
	adrp	x1, l_.str.32@PAGE
Lloh482:
	add	x1, x1, l_.str.32@PAGEOFF
Lloh483:
	adrp	x3, l_.str.44@PAGE
Lloh484:
	add	x3, x3, l_.str.44@PAGEOFF
	mov	w2, #99                         ; =0x63
	bl	___assert_rtn
	.loh AdrpAdd	Lloh483, Lloh484
	.loh AdrpAdd	Lloh481, Lloh482
	.loh AdrpAdd	Lloh479, Lloh480
	.cfi_endproc
                                        ; -- End function
	.p2align	2                               ; -- Begin function main.cold.14
_main.cold.14:                          ; @main.cold.14
	.cfi_startproc
; %bb.0:
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
	mov	x0, #0                          ; =0x0
	mov	x1, #0                          ; =0x0
	bl	_list_position_stop
	.cfi_endproc
                                        ; -- End function
	.p2align	2                               ; -- Begin function main.cold.15
_main.cold.15:                          ; @main.cold.15
	.cfi_startproc
; %bb.0:
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
Lloh485:
	adrp	x0, l___func__.main@PAGE
Lloh486:
	add	x0, x0, l___func__.main@PAGEOFF
Lloh487:
	adrp	x1, l_.str.32@PAGE
Lloh488:
	add	x1, x1, l_.str.32@PAGEOFF
Lloh489:
	adrp	x3, l_.str.38@PAGE
Lloh490:
	add	x3, x3, l_.str.38@PAGEOFF
	mov	w2, #79                         ; =0x4f
	bl	___assert_rtn
	.loh AdrpAdd	Lloh489, Lloh490
	.loh AdrpAdd	Lloh487, Lloh488
	.loh AdrpAdd	Lloh485, Lloh486
	.cfi_endproc
                                        ; -- End function
	.p2align	2                               ; -- Begin function main.cold.16
_main.cold.16:                          ; @main.cold.16
	.cfi_startproc
; %bb.0:
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
Lloh491:
	adrp	x0, l___func__.main@PAGE
Lloh492:
	add	x0, x0, l___func__.main@PAGEOFF
Lloh493:
	adrp	x1, l_.str.32@PAGE
Lloh494:
	add	x1, x1, l_.str.32@PAGEOFF
Lloh495:
	adrp	x3, l_.str.34@PAGE
Lloh496:
	add	x3, x3, l_.str.34@PAGEOFF
	mov	w2, #35                         ; =0x23
	bl	___assert_rtn
	.loh AdrpAdd	Lloh495, Lloh496
	.loh AdrpAdd	Lloh493, Lloh494
	.loh AdrpAdd	Lloh491, Lloh492
	.cfi_endproc
                                        ; -- End function
	.p2align	2                               ; -- Begin function OUTLINED_FUNCTION_0
_OUTLINED_FUNCTION_0:                   ; @OUTLINED_FUNCTION_0 Thunk
	.cfi_startproc
; %bb.0:
	mov	w0, #1                          ; =0x1
	b	_exit
	.cfi_endproc
                                        ; -- End function
	.p2align	2                               ; -- Begin function OUTLINED_FUNCTION_1
_OUTLINED_FUNCTION_1:                   ; @OUTLINED_FUNCTION_1 Thunk
	.cfi_startproc
; %bb.0:
	add	x2, sp, #8
	b	_decode_character
	.cfi_endproc
                                        ; -- End function
	.p2align	2                               ; -- Begin function OUTLINED_FUNCTION_2
_OUTLINED_FUNCTION_2:                   ; @OUTLINED_FUNCTION_2 Tail Call
	.cfi_startproc
; %bb.0:
	ldp	x20, x19, [sp], #32
	ret
	.cfi_endproc
                                        ; -- End function
	.p2align	2                               ; -- Begin function OUTLINED_FUNCTION_3
_OUTLINED_FUNCTION_3:                   ; @OUTLINED_FUNCTION_3 Thunk
	.cfi_startproc
; %bb.0:
	mov	w0, #40                         ; =0x28
	mov	w1, #1                          ; =0x1
	b	_rc_allocate_object
	.cfi_endproc
                                        ; -- End function
.zerofill __DATA,__bss,_minyar_call_depth,8,3 ; @minyar_call_depth
	.section	__TEXT,__cstring,cstring_literals
l_.str:                                 ; @.str
	.asciz	"the program exceeded the maximum call depth."

l_.str.1:                               ; @.str.1
	.asciz	"the runtime detected an unbalanced function return."

l_.str.2:                               ; @.str.2
	.asciz	"this value has too many references."

.zerofill __DATA,__bss,_rc_bounded_frame_head,8,3 ; @rc_bounded_frame_head
.zerofill __DATA,__bss,_rc_bounded_chunk_head,8,3 ; @rc_bounded_chunk_head
.zerofill __DATA,__bss,_rc_pending_count,8,3 ; @rc_pending_count
.zerofill __DATA,__bss,_rc_bounded_active,8,3 ; @rc_bounded_active
.zerofill __DATA,__bss,_rc_bounded_head,8,3 ; @rc_bounded_head
.zerofill __DATA,__bss,_rc_bounded_recent_head,8,3 ; @rc_bounded_recent_head
.zerofill __DATA,__bss,_rc_bounded_tail,8,3 ; @rc_bounded_tail
.zerofill __DATA,__bss,_rc_bounded_recent_tail,8,3 ; @rc_bounded_recent_tail
.zerofill __DATA,__bss,_rc_bounded_cursor,8,3 ; @rc_bounded_cursor
.zerofill __DATA,__bss,_rc_bounded_recent_turn,4,2 ; @rc_bounded_recent_turn
.zerofill __DATA,__bss,_rc_bounded_next_queue,4,2 ; @rc_bounded_next_queue
.zerofill __DATA,__bss,_rc_bounded_last_work,8,3 ; @rc_bounded_last_work
.zerofill __DATA,__bss,_rc_free_frames,8,3 ; @rc_free_frames
.zerofill __DATA,__bss,_rc_bounded_cached_frame_bytes,8,3 ; @rc_bounded_cached_frame_bytes
.zerofill __DATA,__bss,_rc_frames,8,3   ; @rc_frames
.zerofill __DATA,__bss,_rc_bounded_frame_tail,8,3 ; @rc_bounded_frame_tail
l_.str.3:                               ; @.str.3
	.asciz	"this List became too large."

l_.str.4:                               ; @.str.4
	.asciz	"Minyar stopped: "

l_.str.5:                               ; @.str.5
	.asciz	"%lld\n"

l_.str.6:                               ; @.str.6
	.asciz	"true"

l_.str.7:                               ; @.str.7
	.asciz	"false"

.zerofill __DATA,__bss,_minyar_integer_text.integer_cache,262144,3 ; @minyar_integer_text.integer_cache
.zerofill __DATA,__bss,_rc_immortal_object_count,8,3 ; @rc_immortal_object_count
.zerofill __DATA,__bss,_minyar_character_text.ascii_texts,6144,3 ; @minyar_character_text.ascii_texts
.zerofill __DATA,__bss,_minyar_character_text.ascii_bytes,256,0 ; @minyar_character_text.ascii_bytes
.zerofill __DATA,__bss,_saved_argument_count,4,2 ; @saved_argument_count
.zerofill __DATA,__bss,_saved_argument_values,8,3 ; @saved_argument_values
l_.str.8:                               ; @.str.8
	.asciz	"a program argument position was outside the argument list."

l_.str.9:                               ; @.str.9
	.asciz	"rb"

l_.str.10:                              ; @.str.10
	.asciz	"Minyar stopped: the file '%s' could not be opened.\n"

l_.str.11:                              ; @.str.11
	.asciz	"a requested text file could not be read."

l_.str.12:                              ; @.str.12
	.asciz	"wb"

l_.str.13:                              ; @.str.13
	.asciz	"a requested text file could not be created."

l_.str.14:                              ; @.str.14
	.asciz	"a requested text file could not be written."

l_.str.15:                              ; @.str.15
	.asciz	"Minyar stopped: this Integer calculation is outside the supported range.\n"

l_.str.16:                              ; @.str.16
	.asciz	"an Integer cannot be divided by zero."

l_.str.17:                              ; @.str.17
	.asciz	"this Integer division is outside the supported range."

l_.str.18:                              ; @.str.18
	.asciz	"NaN cannot be converted to an Integer."

l_.str.19:                              ; @.str.19
	.asciz	"this Float is outside the Integer range."

l_.str.20:                              ; @.str.20
	.asciz	"this Integer is not a Unicode scalar value."

l_.str.21:                              ; @.str.21
	.asciz	"the absolute value of this Integer is outside the supported range."

l_.str.22:                              ; @.str.22
	.asciz	"clamp needs a lower bound that is not above its upper bound."

l_.str.23:                              ; @.str.23
	.asciz	"a shift count must be between 0 and 63."

l_.str.24:                              ; @.str.24
	.asciz	"Bytes cannot have a negative length."

l_.str.25:                              ; @.str.25
	.asciz	"these Bytes are too large."

l_.str.26:                              ; @.str.26
	.asciz	"a byte (0 to 255)"

l_.str.27:                              ; @.str.27
	.asciz	"Bytes range %lld to %lld is outside its length of %lld."

l_.str.28:                              ; @.str.28
	.asciz	"a requested file could not be read."

l_.str.29:                              ; @.str.29
	.asciz	"a requested file could not be created."

l_.str.30:                              ; @.str.30
	.asciz	"a requested file could not be written."

l_.str.31:                              ; @.str.31
	.asciz	"Bytes cannot shrink by a negative amount."

l___func__.main:                        ; @__func__.main
	.asciz	"main"

l_.str.32:                              ; @.str.32
	.asciz	"memory-research-list-bulk-cpu.c"

l_.str.33:                              ; @.str.33
	.asciz	"argc == 6"

l_.str.34:                              ; @.str.34
	.asciz	"length <= 8193 && repetitions && repetitions <= 1048576 && mode <= 2"

l_.str.35:                              ; @.str.35
	.asciz	"shared reference"

l_.str.36:                              ; @.str.36
	.asciz	"result != source && result->length == (long long)length + 1"

l_.str.37:                              ; @.str.37
	.asciz	"checksum == expected"

l_.str.38:                              ; @.str.38
	.asciz	"control->values != source->values || !length"

l_.str.39:                              ; @.str.39
	.asciz	"value == (mode == 2 ? (uint64_t)(uintptr_t)shared : slot(i, seed))"

l_.str.40:                              ; @.str.40
	.asciz	"control->values[i] == source->values[i]"

l_.str.41:                              ; @.str.41
	.asciz	"control->values[length] == tail"

l_.str.42:                              ; @.str.42
	.asciz	"source->values[0] == old"

l_.str.43:                              ; @.str.43
	.asciz	"source->length == (long long)length"

.zerofill __DATA,__bss,_rc_object_count,8,3 ; @rc_object_count
.zerofill __DATA,__bss,_rc_bytes,8,3    ; @rc_bytes
l_.str.44:                              ; @.str.44
	.asciz	"!rc_object_count && !rc_bytes"

.zerofill __DATA,__bss,_rc_heap_allocation_count,8,3 ; @rc_heap_allocation_count
l_.str.45:                              ; @.str.45
	.asciz	"!rc_heap_allocation_count"

l_.str.46:                              ; @.str.46
	.asciz	"{\"kind\":\"result\",\"cpu_nanoseconds\":%llu,\"checksum\":\"%016llx\",\"repetitions\":%zu,\"recovered\":true}\n"

l_.str.47:                              ; @.str.47
	.asciz	"Minyar stopped: %s\n"

.zerofill __DATA,__bss,_rc_bounded_chunk_tail,8,3 ; @rc_bounded_chunk_tail
l_.str.48:                              ; @.str.48
	.asciz	"the computer ran out of memory."

l_.str.49:                              ; @.str.49
	.asciz	"List position %lld is outside its length of %lld."

l_.str.50:                              ; @.str.50
	.asciz	"this record has too many fields."

l_.str.51:                              ; @.str.51
	.asciz	"standard output could not be written."

l_.str.52:                              ; @.str.52
	.asciz	"the joined Text would be too large."

l_.str.54:                              ; @.str.54
	.asciz	"a Text position was outside the Text."

l_.str.55:                              ; @.str.55
	.asciz	"Text contained invalid UTF-8."

l_.str.56:                              ; @.str.56
	.asciz	"a Text position cannot be negative."

.zerofill __DATA,__bss,_text_decode_count,8,3 ; @text_decode_count
l_.str.57:                              ; @.str.57
	.asciz	"a Text slice must stay within the Text and end after it starts."

l_.str.58:                              ; @.str.58
	.asciz	"this Character is not valid Unicode."

l_.str.59:                              ; @.str.59
	.asciz	"a file path cannot contain a zero byte."

l_.str.62:                              ; @.str.62
	.asciz	"-Infinity"

l_.str.63:                              ; @.str.63
	.asciz	"Infinity"

l_.str.64:                              ; @.str.64
	.asciz	"-0.0"

l_.str.65:                              ; @.str.65
	.asciz	"0.0"

l_.str.66:                              ; @.str.66
	.asciz	"%lld.0"

l_.str.67:                              ; @.str.67
	.asciz	"%.*e"

l_.str.68:                              ; @.str.68
	.asciz	"e%+d"

l_.str.69:                              ; @.str.69
	.asciz	"Bytes position %lld is outside its length of %lld."

l_.str.70:                              ; @.str.70
	.asciz	"a %lld-byte value at position %lld does not fit in Bytes of length %lld."

l_.str.71:                              ; @.str.71
	.asciz	"%lld does not fit in %s."

l_.str.73:                              ; @.str.73
	.asciz	"an unsigned 16-bit Integer"

l_.str.74:                              ; @.str.74
	.asciz	"an unsigned 32-bit Integer"

l_.str.75:                              ; @.str.75
	.asciz	"a signed 16-bit Integer"

l_.str.76:                              ; @.str.76
	.asciz	"a signed 32-bit Integer"

l___func__.cpu_nanoseconds:             ; @__func__.cpu_nanoseconds
	.asciz	"cpu_nanoseconds"

l_.str.77:                              ; @.str.77
	.asciz	"clock_gettime(CLOCK_PROCESS_CPUTIME_ID, &value) == 0"

.zerofill __DATA,__bss,__MergedGlobals,24,3 ; @_MergedGlobals
.subsections_via_symbols
