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
	adrp	x1, l_.str.46@PAGE
Lloh8:
	add	x1, x1, l_.str.46@PAGEOFF
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
	adrp	x22, _rc_pending_count@PAGE
	ldr	x28, [x22, _rc_pending_count@PAGEOFF]
	ccmp	x28, #0, #4, ne
	cset	w8, ne
	mov	x19, #0                         ; =0x0
	orr	x9, x9, x10
	cbz	x9, LBB5_46
; %bb.1:
	cbz	w8, LBB5_78
; %bb.2:
	adrp	x25, _rc_bounded_next_queue@PAGE
	adrp	x27, _rc_bounded_head@PAGE
	adrp	x26, _rc_bounded_recent_head@PAGE
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
	ldr	x11, [x26, _rc_bounded_recent_head@PAGEOFF]
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
	b	LBB5_37
LBB5_9:                                 ;   in Loop: Header=BB5_3 Depth=1
	cbz	w9, LBB5_11
LBB5_10:                                ;   in Loop: Header=BB5_3 Depth=1
	mov	w8, #1                          ; =0x1
	str	w8, [x25, _rc_bounded_next_queue@PAGEOFF]
	bl	_rc_bounded_object_unit
	b	LBB5_44
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
	b	LBB5_44
LBB5_17:                                ;   in Loop: Header=BB5_3 Depth=1
	ldr	x8, [x20]
	str	x8, [x23, _rc_bounded_frame_head@PAGEOFF]
	cbz	x8, LBB5_32
; %bb.18:                               ;   in Loop: Header=BB5_3 Depth=1
	ldr	x0, [x20, #8]
	cbz	x0, LBB5_33
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
	b.ls	LBB5_42
LBB5_21:                                ;   in Loop: Header=BB5_3 Depth=1
	bl	_free
	b	LBB5_34
LBB5_22:                                ;   in Loop: Header=BB5_3 Depth=1
	cmp	w10, #2
	b.ne	LBB5_29
; %bb.23:                               ;   in Loop: Header=BB5_3 Depth=1
	cbz	x0, LBB5_29
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
	b	LBB5_44
LBB5_27:                                ;   in Loop: Header=BB5_3 Depth=1
	ldr	x8, [x0]
	str	x8, [x24, _rc_bounded_chunk_head@PAGEOFF]
	cbnz	x8, LBB5_35
; %bb.28:                               ;   in Loop: Header=BB5_3 Depth=1
	adrp	x8, _rc_bounded_chunk_tail@PAGE
	str	xzr, [x8, _rc_bounded_chunk_tail@PAGEOFF]
	b	LBB5_35
LBB5_29:                                ;   in Loop: Header=BB5_3 Depth=1
	cmp	w10, #2
	b.ne	LBB5_36
; %bb.30:                               ;   in Loop: Header=BB5_3 Depth=1
	tbnz	w9, #0, LBB5_10
; %bb.31:                               ;   in Loop: Header=BB5_3 Depth=1
	mov	w9, #0                          ; =0x0
	b	LBB5_38
LBB5_32:                                ;   in Loop: Header=BB5_3 Depth=1
	adrp	x8, _rc_bounded_frame_tail@PAGE
	str	xzr, [x8, _rc_bounded_frame_tail@PAGEOFF]
	ldr	x0, [x20, #8]
	cbnz	x0, LBB5_19
LBB5_33:                                ;   in Loop: Header=BB5_3 Depth=1
Lloh13:
	adrp	x8, _rc_bounded_cached_frame_bytes@PAGE
Lloh14:
	ldr	x8, [x8, _rc_bounded_cached_frame_bytes@PAGEOFF]
	mov	w9, #262080                     ; =0x3ffc0
	cmp	x8, x9
	b.ls	LBB5_41
LBB5_34:                                ;   in Loop: Header=BB5_3 Depth=1
	mov	x0, x20
LBB5_35:                                ;   in Loop: Header=BB5_3 Depth=1
	bl	_free
	b	LBB5_43
LBB5_36:                                ;   in Loop: Header=BB5_3 Depth=1
	mov	w8, #0                          ; =0x0
	mov	w9, #2                          ; =0x2
	mov	w10, #1                         ; =0x1
	tbnz	w8, #0, LBB5_14
LBB5_37:                                ;   in Loop: Header=BB5_3 Depth=1
	cmp	x0, #0
	csel	w8, wzr, w10, eq
	tbnz	w8, #0, LBB5_24
LBB5_38:                                ;   in Loop: Header=BB5_3 Depth=1
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
; %bb.39:                               ;   in Loop: Header=BB5_3 Depth=1
	cbnz	w8, LBB5_25
; %bb.40:                               ;   in Loop: Header=BB5_3 Depth=1
	bl	_rc_bounded_object_unit
	b	LBB5_44
LBB5_41:                                ;   in Loop: Header=BB5_3 Depth=1
	mov	w9, #64                         ; =0x40
LBB5_42:                                ;   in Loop: Header=BB5_3 Depth=1
	adrp	x11, _rc_free_frames@PAGE
	ldr	x10, [x11, _rc_free_frames@PAGEOFF]
	str	x10, [x20]
	str	x20, [x11, _rc_free_frames@PAGEOFF]
	add	x8, x9, x8
	adrp	x9, _rc_bounded_cached_frame_bytes@PAGE
	str	x8, [x9, _rc_bounded_cached_frame_bytes@PAGEOFF]
LBB5_43:                                ;   in Loop: Header=BB5_3 Depth=1
	sub	x8, x28, #1
	str	x8, [x22, _rc_pending_count@PAGEOFF]
LBB5_44:                                ;   in Loop: Header=BB5_3 Depth=1
	add	x19, x19, #1
	cmp	x19, x21
	b.hs	LBB5_78
; %bb.45:                               ;   in Loop: Header=BB5_3 Depth=1
	ldr	x28, [x22, _rc_pending_count@PAGEOFF]
	cbnz	x28, LBB5_3
	b	LBB5_78
LBB5_46:
	cbz	w8, LBB5_78
; %bb.47:
	adrp	x23, _rc_bounded_active@PAGE
	adrp	x24, _rc_bounded_recent_head@PAGE
	adrp	x25, _rc_bounded_cursor@PAGE
	adrp	x26, _rc_bounded_recent_turn@PAGE
LBB5_48:                                ; =>This Loop Header: Depth=1
                                        ;     Child Loop BB5_56 Depth 2
                                        ;     Child Loop BB5_69 Depth 2
	sub	x27, x21, x19
	ldr	x20, [x23, _rc_bounded_active@PAGEOFF]
	ldr	x8, [x24, _rc_bounded_recent_head@PAGEOFF]
	cmp	x27, #2
	b.lo	LBB5_61
; %bb.49:                               ;   in Loop: Header=BB5_48 Depth=1
	cmp	x28, #1
	b.ne	LBB5_61
; %bb.50:                               ;   in Loop: Header=BB5_48 Depth=1
	cbnz	x20, LBB5_61
; %bb.51:                               ;   in Loop: Header=BB5_48 Depth=1
Lloh15:
	adrp	x9, _rc_bounded_head@PAGE
Lloh16:
	ldr	x9, [x9, _rc_bounded_head@PAGEOFF]
	cmp	x9, #0
	csel	x0, x8, x9, eq
	cbz	x0, LBB5_73
; %bb.52:                               ;   in Loop: Header=BB5_48 Depth=1
	ldr	x8, [x0]
	and	x8, x8, #0x7
	cmp	x8, #4
	b.ne	LBB5_73
; %bb.53:                               ;   in Loop: Header=BB5_48 Depth=1
	mov	x9, x0
	ldr	x8, [x9, #8]!
	cmp	x8, #1
	b.ne	LBB5_73
; %bb.54:                               ;   in Loop: Header=BB5_48 Depth=1
	mov	x8, x0
	ldrb	w10, [x8, #24]!
	cmp	w10, #1
	b.hi	LBB5_73
; %bb.55:                               ;   in Loop: Header=BB5_48 Depth=1
Lloh17:
	adrp	x10, _rc_bounded_head@PAGE
	str	xzr, [x10, _rc_bounded_head@PAGEOFF]
Lloh18:
	adrp	x10, _rc_bounded_recent_tail@PAGE
	str	xzr, [x10, _rc_bounded_recent_tail@PAGEOFF]
	str	xzr, [x24, _rc_bounded_recent_head@PAGEOFF]
	mov	w10, #4                         ; =0x4
	str	x10, [x0]
	str	x0, [x23, _rc_bounded_active@PAGEOFF]
	mov	w10, #1                         ; =0x1
	str	x10, [x25, _rc_bounded_cursor@PAGEOFF]
	cmp	x27, #4
	b.lo	LBB5_64
LBB5_56:                                ;   Parent Loop BB5_48 Depth=1
                                        ; =>  This Inner Loop Header: Depth=2
	ldrb	w10, [x8]
	tbz	w10, #0, LBB5_64
; %bb.57:                               ;   in Loop: Header=BB5_56 Depth=2
	ldr	x28, [x9, #8]
	cbz	x28, LBB5_64
; %bb.58:                               ;   in Loop: Header=BB5_56 Depth=2
	mov	x20, x28
	ldr	x10, [x20, #-8]!
	cmp	x10, #12
	b.ne	LBB5_64
; %bb.59:                               ;   in Loop: Header=BB5_56 Depth=2
	ldr	x10, [x28]
	cmp	x10, #1
	b.ne	LBB5_64
; %bb.60:                               ;   in Loop: Header=BB5_56 Depth=2
	mov	w8, #4                          ; =0x4
	stur	x8, [x28, #-8]
	bl	_free
	add	x8, x28, #16
	str	x20, [x23, _rc_bounded_active@PAGEOFF]
	add	x19, x19, #2
	sub	x27, x27, #2
	mov	x0, x20
	mov	x9, x28
	cmp	x27, #3
	b.hi	LBB5_56
	b	LBB5_65
LBB5_61:                                ;   in Loop: Header=BB5_48 Depth=1
	cmp	x8, #0
	ccmp	x20, #0, #4, eq
	b.eq	LBB5_73
; %bb.62:                               ;   in Loop: Header=BB5_48 Depth=1
	ldr	x8, [x20]
	and	x8, x8, #0x7
	cmp	x8, #3
	b.ne	LBB5_73
; %bb.63:                               ;   in Loop: Header=BB5_48 Depth=1
	ldr	x9, [x20, #16]
	ldr	x8, [x25, _rc_bounded_cursor@PAGEOFF]
	sub	x9, x9, x8
	cmp	x27, x9
	csel	x27, x27, x9, lo
	add	x28, x27, x8
	cmp	x8, x28
	b.lo	LBB5_69
	b	LBB5_72
LBB5_64:                                ;   in Loop: Header=BB5_48 Depth=1
	mov	x28, x9
	mov	x20, x0
LBB5_65:                                ;   in Loop: Header=BB5_48 Depth=1
	ldr	w9, [x26, _rc_bounded_recent_turn@PAGEOFF]
	eor	w10, w9, #0x1
	str	w10, [x26, _rc_bounded_recent_turn@PAGEOFF]
	ldrb	w8, [x8]
	tbz	w8, #0, LBB5_67
; %bb.66:                               ;   in Loop: Header=BB5_48 Depth=1
	ldr	x0, [x28, #8]
	bl	_rc_drop
	ldr	w8, [x26, _rc_bounded_recent_turn@PAGEOFF]
	eor	w9, w8, #0x1
LBB5_67:                                ;   in Loop: Header=BB5_48 Depth=1
	str	w9, [x26, _rc_bounded_recent_turn@PAGEOFF]
	mov	x0, x20
	bl	_free
	ldr	x8, [x22, _rc_pending_count@PAGEOFF]
	sub	x8, x8, #1
	str	x8, [x22, _rc_pending_count@PAGEOFF]
	str	xzr, [x23, _rc_bounded_active@PAGEOFF]
	add	x19, x19, #2
	b	LBB5_74
LBB5_68:                                ;   in Loop: Header=BB5_69 Depth=2
	bl	_rc_drop
	ldr	x9, [x24, _rc_bounded_recent_head@PAGEOFF]
	ldr	x8, [x25, _rc_bounded_cursor@PAGEOFF]
	cmp	x9, #0
	ccmp	x8, x28, #2, eq
	b.hs	LBB5_72
LBB5_69:                                ;   Parent Loop BB5_48 Depth=1
                                        ; =>  This Inner Loop Header: Depth=2
	add	x19, x19, #1
	ldr	w9, [x26, _rc_bounded_recent_turn@PAGEOFF]
	eor	w9, w9, #0x1
	str	w9, [x26, _rc_bounded_recent_turn@PAGEOFF]
	ldr	x9, [x20, #8]
	add	x10, x8, #1
	str	x10, [x25, _rc_bounded_cursor@PAGEOFF]
	ldr	x0, [x9, x8, lsl #3]
	cbz	x0, LBB5_68
; %bb.70:                               ;   in Loop: Header=BB5_69 Depth=2
	sub	x8, x0, #8
	ldr	x9, [x8]
	cmp	x9, #13
	b.ne	LBB5_68
; %bb.71:                               ;   in Loop: Header=BB5_69 Depth=2
	mov	x0, x8
	bl	_free
	ldr	x8, [x25, _rc_bounded_cursor@PAGEOFF]
	cmp	x8, x28
	b.lo	LBB5_69
LBB5_72:                                ;   in Loop: Header=BB5_48 Depth=1
	cbnz	x27, LBB5_74
LBB5_73:                                ;   in Loop: Header=BB5_48 Depth=1
	bl	_rc_bounded_object_unit
	add	x19, x19, #1
LBB5_74:                                ;   in Loop: Header=BB5_48 Depth=1
	cmp	x19, x21
	b.hs	LBB5_76
; %bb.75:                               ;   in Loop: Header=BB5_48 Depth=1
	ldr	x28, [x22, _rc_pending_count@PAGEOFF]
	cbnz	x28, LBB5_48
LBB5_76:
	cbz	x19, LBB5_78
; %bb.77:
	mov	w8, #1                          ; =0x1
	adrp	x9, _rc_bounded_next_queue@PAGE
	str	w8, [x9, _rc_bounded_next_queue@PAGEOFF]
LBB5_78:
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
	.loh AdrpAdrp	Lloh17, Lloh18
	.cfi_endproc
                                        ; -- End function
	.p2align	2                               ; -- Begin function rc_drop
_rc_drop:                               ; @rc_drop
	.cfi_startproc
; %bb.0:
	cbz	x0, LBB6_33
; %bb.1:
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
	mov	x19, x0
	ldr	x9, [x0, #-8]!
	cmp	x9, #13
	b.ne	LBB6_3
LBB6_2:
	bl	_free
	mov	w0, #1                          ; =0x1
	b	LBB6_32
LBB6_3:
	subs	x8, x9, #8
	b.lo	LBB6_31
; %bb.4:
	str	x8, [x0]
	cmp	x8, #7
	b.hi	LBB6_31
; %bb.5:
	and	w8, w9, #0x7
	cmp	w8, #1
	b.ne	LBB6_16
; %bb.6:
	ldr	x20, [x19, #32]
	cbnz	x20, LBB6_9
; %bb.7:
	ldr	x8, [x19]
	cbz	x8, LBB6_9
; %bb.8:
	sub	x8, x8, #8
	mov	x21, x0
	mov	x0, x8
	bl	_free
	mov	x0, x21
LBB6_9:
	ldr	x8, [x19, #24]
	cbz	x8, LBB6_11
; %bb.10:
	sub	x8, x8, #8
	mov	x19, x0
	mov	x0, x8
	bl	_free
	mov	x0, x19
LBB6_11:
	bl	_free
	cbz	x20, LBB6_15
; %bb.12:
	ldr	x8, [x20, #-8]!
	subs	x8, x8, #8
	b.lo	LBB6_15
; %bb.13:
	str	x8, [x20]
	cmp	x8, #7
	b.hi	LBB6_15
; %bb.14:
	mov	x0, x20
	bl	_rc_bounded_enqueue
LBB6_15:
	mov	w0, #1                          ; =0x1
	b	LBB6_32
LBB6_16:
	and	w9, w9, #0x3
	cmp	w9, #2
	b.ne	LBB6_24
; %bb.17:
	sub	w9, w8, #2
	cmp	w9, #2
	b.lo	LBB6_27
; %bb.18:
	cmp	w8, #6
	b.eq	LBB6_27
; %bb.19:
	cmp	w8, #1
	b.ne	LBB6_2
; %bb.20:
	ldr	x8, [x19, #32]
	cbnz	x8, LBB6_23
; %bb.21:
	ldr	x8, [x19]
	cbz	x8, LBB6_23
; %bb.22:
	sub	x8, x8, #8
	mov	x20, x0
	mov	x0, x8
	bl	_free
	mov	x0, x20
LBB6_23:
	ldr	x8, [x19, #24]
	cbnz	x8, LBB6_28
	b	LBB6_2
LBB6_24:
	cmp	w8, #4
	b.eq	LBB6_29
; %bb.25:
	cmp	w8, #3
	b.ne	LBB6_30
; %bb.26:
	ldr	x8, [x19, #8]
	cbnz	x8, LBB6_30
LBB6_27:
	ldr	x8, [x19]
	cbz	x8, LBB6_2
LBB6_28:
	sub	x8, x8, #8
	mov	x19, x0
	mov	x0, x8
	bl	_free
	mov	x0, x19
	b	LBB6_2
LBB6_29:
	ldr	x8, [x19]
	cbz	x8, LBB6_2
LBB6_30:
	bl	_rc_bounded_enqueue
LBB6_31:
	mov	w0, #0                          ; =0x0
LBB6_32:
	ldp	x29, x30, [sp, #32]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp, #16]             ; 16-byte Folded Reload
	ldp	x22, x21, [sp], #48             ; 16-byte Folded Reload
LBB6_33:
	ret
	.cfi_endproc
                                        ; -- End function
	.p2align	2                               ; -- Begin function rc_bounded_object_unit
_rc_bounded_object_unit:                ; @rc_bounded_object_unit
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
Lloh19:
	adrp	x8, _rc_bounded_active@PAGE
Lloh20:
	ldr	x9, [x8, _rc_bounded_active@PAGEOFF]
	adrp	x12, _rc_bounded_head@PAGE
	ldr	x10, [x12, _rc_bounded_head@PAGEOFF]
Lloh21:
	adrp	x8, _rc_bounded_recent_head@PAGE
	ldr	x19, [x8, _rc_bounded_recent_head@PAGEOFF]
	adrp	x11, _rc_bounded_recent_turn@PAGE
	orr	x13, x9, x10
	cbz	x13, LBB7_8
; %bb.1:
	ldr	w12, [x11, _rc_bounded_recent_turn@PAGEOFF]
	eor	w13, w12, #0x1
	str	w13, [x11, _rc_bounded_recent_turn@PAGEOFF]
	cmp	w12, #0
	ccmp	x19, #0, #4, ne
	b.eq	LBB7_9
; %bb.2:
	cmp	x9, #0
	ccmp	x10, #0, #0, ne
	b.ne	LBB7_5
; %bb.3:
	ldr	x10, [x9]
	and	x10, x10, #0x7
	cmp	x10, #4
	b.ne	LBB7_5
; %bb.4:
	ldr	x9, [x9, #8]
Lloh22:
	adrp	x10, _rc_bounded_cursor@PAGE
Lloh23:
	ldr	x10, [x10, _rc_bounded_cursor@PAGEOFF]
	cmp	x9, #1
	ccmp	x10, #1, #0, eq
	b.eq	LBB7_9
LBB7_5:
	ldr	x12, [x19]
	and	w10, w12, #0x7
	and	x9, x12, #0x7
	cmp	x9, #1
	b.eq	LBB7_19
; %bb.6:
	cmp	x9, #3
	b.ne	LBB7_10
; %bb.7:
	ldr	x11, [x19, #24]
	cmp	w10, #4
	b.ne	LBB7_14
	b	LBB7_20
LBB7_8:
	str	x19, [x12, _rc_bounded_head@PAGEOFF]
	adrp	x9, _rc_bounded_recent_tail@PAGE
	ldr	x10, [x9, _rc_bounded_recent_tail@PAGEOFF]
	adrp	x12, _rc_bounded_tail@PAGE
	str	x10, [x12, _rc_bounded_tail@PAGEOFF]
	str	xzr, [x9, _rc_bounded_recent_tail@PAGEOFF]
	str	xzr, [x8, _rc_bounded_recent_head@PAGEOFF]
	ldr	w8, [x11, _rc_bounded_recent_turn@PAGEOFF]
	eor	w8, w8, #0x1
	str	w8, [x11, _rc_bounded_recent_turn@PAGEOFF]
LBB7_9:
	ldp	x29, x30, [sp, #16]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp], #32             ; 16-byte Folded Reload
	b	_rc_bounded_old_object_unit
LBB7_10:
	ldr	x15, [x19, #8]
	cbz	x15, LBB7_19
; %bb.11:
	mov	x13, #0                         ; =0x0
	mov	x11, #0                         ; =0x0
	add	x14, x19, x15, lsl #3
	add	x14, x14, #16
	sub	x15, x15, #1
	mov	w16, #9                         ; =0x9
	cmp	x15, #9
	csel	x15, x15, x16, lo
	lsl	x16, x15, #3
	sub	x15, x16, x15
	add	x15, x15, #7
LBB7_12:                                ; =>This Inner Loop Header: Depth=1
	ldrb	w16, [x14], #1
	lsr	x16, x16, #1
	lsl	x16, x16, x13
	orr	x11, x16, x11
	add	x13, x13, #7
	cmp	x15, x13
	b.ne	LBB7_12
; %bb.13:
	cmp	w10, #4
	b.eq	LBB7_20
LBB7_14:
	cmp	w10, #3
	b.ne	LBB7_23
; %bb.15:
	mov	x13, x19
	ldr	x14, [x13, #16]!
	cmp	x11, x14
	b.hs	LBB7_23
; %bb.16:
	ldr	x10, [x19, #8]
	ldr	x0, [x10, x11, lsl #3]
	cmp	x9, #1
	b.eq	LBB7_45
; %bb.17:
	add	x8, x11, #1
	cmp	x9, #3
	b.ne	LBB7_39
; %bb.18:
	str	x8, [x19, #24]
	b	LBB7_45
LBB7_19:
	mov	x11, #0                         ; =0x0
	cmp	w10, #4
	b.ne	LBB7_14
LBB7_20:
	ldr	x13, [x19, #8]
	cmp	x11, x13
	b.hs	LBB7_23
; %bb.21:
	add	x10, x19, #16
	add	x8, x10, x13, lsl #3
	ldrb	w12, [x8, x11]
	tbnz	w12, #0, LBB7_35
; %bb.22:
	mov	x0, #0                          ; =0x0
	b	LBB7_36
LBB7_23:
	ands	x9, x12, #0xfffffffffffffff8
	str	x9, [x8, _rc_bounded_recent_head@PAGEOFF]
	b.ne	LBB7_25
; %bb.24:
	adrp	x8, _rc_bounded_recent_tail@PAGE
	str	xzr, [x8, _rc_bounded_recent_tail@PAGEOFF]
LBB7_25:
	sub	w8, w10, #2
	cmp	w8, #2
	b.lo	LBB7_32
; %bb.26:
	cmp	w10, #6
	b.eq	LBB7_32
; %bb.27:
	cmp	w10, #1
	b.ne	LBB7_34
; %bb.28:
	ldr	x8, [x19, #40]
	cbnz	x8, LBB7_31
; %bb.29:
	ldr	x8, [x19, #8]
	cbz	x8, LBB7_31
; %bb.30:
	sub	x0, x8, #8
	bl	_free
LBB7_31:
	ldr	x8, [x19, #32]
	cbnz	x8, LBB7_33
	b	LBB7_34
LBB7_32:
	ldr	x8, [x19, #8]
	cbz	x8, LBB7_34
LBB7_33:
	sub	x0, x8, #8
	bl	_free
LBB7_34:
	mov	x0, x19
	bl	_free
	adrp	x8, _rc_pending_count@PAGE
	ldr	x9, [x8, _rc_pending_count@PAGEOFF]
	sub	x9, x9, #1
	str	x9, [x8, _rc_pending_count@PAGEOFF]
	ldp	x29, x30, [sp, #16]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp], #32             ; 16-byte Folded Reload
	ret
LBB7_35:
	ldr	x0, [x10, x11, lsl #3]
LBB7_36:
	cmp	x9, #1
	b.eq	LBB7_45
; %bb.37:
	add	x10, x11, #1
	cmp	x9, #3
	b.ne	LBB7_42
; %bb.38:
	str	x10, [x19, #24]
	b	LBB7_45
LBB7_39:
	mov	x9, #0                          ; =0x0
	add	x10, x13, x10, lsl #3
LBB7_40:                                ; =>This Inner Loop Header: Depth=1
	ldrb	w11, [x10, x9]
	bfi	w11, w8, #1, #31
	strb	w11, [x10, x9]
	cmp	x9, #8
	b.hi	LBB7_45
; %bb.41:                               ;   in Loop: Header=BB7_40 Depth=1
	lsr	x8, x8, #7
	add	x9, x9, #1
	ldr	x11, [x19, #8]
	cmp	x9, x11
	b.lo	LBB7_40
	b	LBB7_45
LBB7_42:
	mov	x9, #0                          ; =0x0
LBB7_43:                                ; =>This Inner Loop Header: Depth=1
	ldrb	w11, [x8, x9]
	bfi	w11, w10, #1, #31
	strb	w11, [x8, x9]
	cmp	x9, #8
	b.hi	LBB7_45
; %bb.44:                               ;   in Loop: Header=BB7_43 Depth=1
	lsr	x10, x10, #7
	add	x9, x9, #1
	ldr	x11, [x19, #8]
	cmp	x9, x11
	b.lo	LBB7_43
LBB7_45:
	ldp	x29, x30, [sp, #16]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp], #32             ; 16-byte Folded Reload
	b	_rc_drop
	.loh AdrpAdrp	Lloh19, Lloh21
	.loh AdrpLdr	Lloh19, Lloh20
	.loh AdrpLdr	Lloh22, Lloh23
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_rc_release              ; -- Begin function minyar_rc_release
	.p2align	2
_minyar_rc_release:                     ; @minyar_rc_release
	.cfi_startproc
; %bb.0:
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
	bl	_rc_drop
Lloh24:
	adrp	x8, _rc_pending_count@PAGE
Lloh25:
	ldr	x8, [x8, _rc_pending_count@PAGEOFF]
	cbz	x8, LBB8_2
; %bb.1:
	mov	w8, #32                         ; =0x20
	sub	w0, w8, w0
	ldp	x29, x30, [sp], #16             ; 16-byte Folded Reload
	b	_minyar_rc_poll
LBB8_2:
	ldp	x29, x30, [sp], #16             ; 16-byte Folded Reload
	ret
	.loh AdrpLdr	Lloh24, Lloh25
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
	cbz	x20, LBB9_3
; %bb.1:
	ldp	x9, x10, [x20]
	str	x9, [x8, _rc_free_frames@PAGEOFF]
	adrp	x8, _rc_bounded_cached_frame_bytes@PAGE
	ldr	x9, [x8, _rc_bounded_cached_frame_bytes@PAGEOFF]
	sub	x9, x9, #64
	str	x9, [x8, _rc_bounded_cached_frame_bytes@PAGEOFF]
	cbz	x10, LBB9_4
; %bb.2:
	ldr	x10, [x20, #24]
	sub	x9, x9, x10, lsl #4
	str	x9, [x8, _rc_bounded_cached_frame_bytes@PAGEOFF]
	b	LBB9_4
LBB9_3:
	mov	w0, #1                          ; =0x1
	mov	w1, #64                         ; =0x40
	bl	_calloc
	mov	x20, x0
	cbz	x0, LBB9_14
LBB9_4:
	lsr	x8, x19, #60
	cbnz	x8, LBB9_14
; %bb.5:
	ldr	x8, [x20, #24]
	cmp	x8, x19
	b.hs	LBB9_9
; %bb.6:
	ldr	x0, [x20, #8]
	lsl	x1, x19, #4
	cbz	x0, LBB9_13
; %bb.7:
	bl	_realloc
	cbz	x0, LBB9_14
LBB9_8:
	str	x0, [x20, #8]
	str	x19, [x20, #24]
	b	LBB9_11
LBB9_9:
	cbz	x19, LBB9_12
; %bb.10:
	ldr	x0, [x20, #8]
LBB9_11:
	lsl	x1, x19, #3
	bl	_bzero
LBB9_12:
	str	x19, [x20, #16]
	stp	xzr, xzr, [x20, #48]
	adrp	x8, _rc_frames@PAGE
	ldr	x9, [x8, _rc_frames@PAGEOFF]
	str	x9, [x20]
	str	x20, [x8, _rc_frames@PAGEOFF]
	ldp	x29, x30, [sp, #16]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp], #32             ; 16-byte Folded Reload
	ret
LBB9_13:
	mov	x0, x1
	bl	_malloc
	cbnz	x0, LBB9_8
LBB9_14:
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
Lloh26:
	adrp	x0, l_.str.47@PAGE
Lloh27:
	add	x0, x0, l_.str.47@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh26, Lloh27
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_rc_leave                ; -- Begin function minyar_rc_leave
	.p2align	2
_minyar_rc_leave:                       ; @minyar_rc_leave
	.cfi_startproc
; %bb.0:
Lloh28:
	adrp	x9, _rc_frames@PAGE
	ldr	x8, [x9, _rc_frames@PAGEOFF]
	ldr	x10, [x8]
	str	x10, [x9, _rc_frames@PAGEOFF]
	mov	x10, x8
	ldr	x11, [x10, #32]!
Lloh29:
	adrp	x9, _rc_pending_count@PAGE
	cbz	x11, LBB11_2
; %bb.1:
	adrp	x12, _rc_bounded_chunk_tail@PAGE
	ldr	x13, [x12, _rc_bounded_chunk_tail@PAGEOFF]
Lloh30:
	adrp	x14, _rc_bounded_chunk_head@PAGE
Lloh31:
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
LBB11_2:
	ldr	x10, [x8, #56]
	str	x10, [x8, #16]
	str	xzr, [x8]
	adrp	x10, _rc_bounded_frame_tail@PAGE
	ldr	x11, [x10, _rc_bounded_frame_tail@PAGEOFF]
Lloh32:
	adrp	x12, _rc_bounded_frame_head@PAGE
Lloh33:
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
	.loh AdrpAdrp	Lloh28, Lloh29
	.loh AdrpAdd	Lloh30, Lloh31
	.loh AdrpAdd	Lloh32, Lloh33
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
	cbz	x0, LBB12_10
; %bb.1:
	mov	x8, x0
	ldur	x9, [x0, #-8]
	cmp	x9, #8
	b.lo	LBB12_10
; %bb.2:
Lloh34:
	adrp	x9, _rc_frames@PAGE
Lloh35:
	ldr	x19, [x9, _rc_frames@PAGEOFF]
	ldr	x0, [x19, #40]
	adrp	x20, _rc_pending_count@PAGE
	cbz	x0, LBB12_4
; %bb.3:
	ldr	x9, [x0, #8]
	cmp	x9, #8
	b.ne	LBB12_8
LBB12_4:
	mov	x21, x8
	ldr	x8, [x20, _rc_pending_count@PAGEOFF]
	cbz	x8, LBB12_6
; %bb.5:
	mov	w0, #32                         ; =0x20
	bl	_minyar_rc_poll
LBB12_6:
	mov	w0, #80                         ; =0x50
	bl	_malloc
	cbz	x0, LBB12_11
; %bb.7:
	mov	x9, #0                          ; =0x0
	stp	xzr, xzr, [x0]
	ldr	x8, [x19, #40]
	add	x10, x19, #32
	cmp	x8, #0
	csel	x8, x10, x8, eq
	str	x0, [x8]
	str	x0, [x19, #40]
	mov	x8, x21
LBB12_8:
	add	x10, x0, x9, lsl #3
	add	x9, x9, #1
	str	x9, [x0, #8]
	str	x8, [x10, #16]
	ldr	x8, [x19, #48]
	add	x8, x8, #1
	str	x8, [x19, #48]
	ldr	x8, [x20, _rc_pending_count@PAGEOFF]
	cbz	x8, LBB12_10
; %bb.9:
	mov	w0, #32                         ; =0x20
	ldp	x29, x30, [sp, #32]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp, #16]             ; 16-byte Folded Reload
	ldp	x22, x21, [sp], #48             ; 16-byte Folded Reload
	b	_minyar_rc_poll
LBB12_10:
	ldp	x29, x30, [sp, #32]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp, #16]             ; 16-byte Folded Reload
	ldp	x22, x21, [sp], #48             ; 16-byte Folded Reload
	ret
LBB12_11:
	bl	_out_of_memory
	.loh AdrpLdr	Lloh34, Lloh35
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_rc_local_take           ; -- Begin function minyar_rc_local_take
	.p2align	2
_minyar_rc_local_take:                  ; @minyar_rc_local_take
	.cfi_startproc
; %bb.0:
Lloh36:
	adrp	x8, _rc_frames@PAGE
Lloh37:
	ldr	x10, [x8, _rc_frames@PAGEOFF]
	ldr	x9, [x10, #8]
	ldr	x8, [x9, x0, lsl #3]
	cbz	x1, LBB13_4
; %bb.1:
	tbnz	w8, #0, LBB13_4
; %bb.2:
	ldr	x11, [x10, #24]
	add	x11, x9, x11, lsl #3
	ldr	x12, [x10, #56]
	add	x13, x12, #1
	str	x13, [x10, #56]
	str	x0, [x11, x12, lsl #3]
LBB13_3:
	orr	x10, x1, #0x1
	str	x10, [x9, x0, lsl #3]
	b	LBB13_6
LBB13_4:
	tbnz	w8, #0, LBB13_3
; %bb.5:
	cbnz	x1, LBB13_3
LBB13_6:
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
	and	x0, x8, #0xfffffffffffffffe
	bl	_rc_drop
Lloh38:
	adrp	x8, _rc_pending_count@PAGE
Lloh39:
	ldr	x8, [x8, _rc_pending_count@PAGEOFF]
	ldp	x29, x30, [sp], #16             ; 16-byte Folded Reload
	cbz	x8, LBB13_8
; %bb.7:
	mov	w8, #32                         ; =0x20
	sub	w0, w8, w0
	b	_minyar_rc_poll
LBB13_8:
	ret
	.loh AdrpLdr	Lloh36, Lloh37
	.loh AdrpLdr	Lloh38, Lloh39
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_rc_local_move           ; -- Begin function minyar_rc_local_move
	.p2align	2
_minyar_rc_local_move:                  ; @minyar_rc_local_move
	.cfi_startproc
; %bb.0:
Lloh40:
	adrp	x8, _rc_frames@PAGE
Lloh41:
	ldr	x8, [x8, _rc_frames@PAGEOFF]
	ldr	x8, [x8, #8]
	ldr	x9, [x8, x0, lsl #3]
	and	x9, x9, #0x1
	str	x9, [x8, x0, lsl #3]
	ret
	.loh AdrpLdr	Lloh40, Lloh41
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_rc_local                ; -- Begin function minyar_rc_local
	.p2align	2
_minyar_rc_local:                       ; @minyar_rc_local
	.cfi_startproc
; %bb.0:
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
	cbz	x1, LBB15_4
; %bb.1:
	ldur	x8, [x1, #-8]
	cmp	x8, #8
	b.lo	LBB15_4
; %bb.2:
	cmn	x8, #8
	b.hs	LBB15_13
; %bb.3:
	add	x8, x8, #8
	stur	x8, [x1, #-8]
LBB15_4:
Lloh42:
	adrp	x8, _rc_frames@PAGE
Lloh43:
	ldr	x10, [x8, _rc_frames@PAGEOFF]
	ldr	x9, [x10, #8]
	ldr	x8, [x9, x0, lsl #3]
	cbz	x1, LBB15_8
; %bb.5:
	tbnz	w8, #0, LBB15_8
; %bb.6:
	ldr	x11, [x10, #24]
	add	x11, x9, x11, lsl #3
	ldr	x12, [x10, #56]
	add	x13, x12, #1
	str	x13, [x10, #56]
	str	x0, [x11, x12, lsl #3]
LBB15_7:
	orr	x10, x1, #0x1
	str	x10, [x9, x0, lsl #3]
	b	LBB15_10
LBB15_8:
	tbnz	w8, #0, LBB15_7
; %bb.9:
	cbnz	x1, LBB15_7
LBB15_10:
	and	x0, x8, #0xfffffffffffffffe
	bl	_rc_drop
Lloh44:
	adrp	x8, _rc_pending_count@PAGE
Lloh45:
	ldr	x8, [x8, _rc_pending_count@PAGEOFF]
	cbz	x8, LBB15_12
; %bb.11:
	mov	w8, #32                         ; =0x20
	sub	w0, w8, w0
	ldp	x29, x30, [sp], #16             ; 16-byte Folded Reload
	b	_minyar_rc_poll
LBB15_12:
	ldp	x29, x30, [sp], #16             ; 16-byte Folded Reload
	ret
LBB15_13:
	bl	_minyar_rc_local.cold.1
	.loh AdrpLdr	Lloh42, Lloh43
	.loh AdrpLdr	Lloh44, Lloh45
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_rc_borrow               ; -- Begin function minyar_rc_borrow
	.p2align	2
_minyar_rc_borrow:                      ; @minyar_rc_borrow
	.cfi_startproc
; %bb.0:
	cbz	x0, LBB16_4
; %bb.1:
	ldur	x8, [x0, #-8]
	cmp	x8, #8
	b.lo	LBB16_4
; %bb.2:
	cmn	x8, #8
	b.hs	LBB16_5
; %bb.3:
	add	x8, x8, #8
	stur	x8, [x0, #-8]
LBB16_4:
	b	_minyar_rc_keep
LBB16_5:
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
Lloh46:
	adrp	x8, _rc_frames@PAGE
Lloh47:
	ldr	x9, [x8, _rc_frames@PAGEOFF]
	mov	x8, x9
	ldr	x10, [x8, #32]!
	cbz	x10, LBB17_2
; %bb.1:
	adrp	x11, _rc_bounded_chunk_tail@PAGE
	ldr	x12, [x11, _rc_bounded_chunk_tail@PAGEOFF]
Lloh48:
	adrp	x13, _rc_bounded_chunk_head@PAGE
Lloh49:
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
LBB17_2:
	mov	w0, #32                         ; =0x20
	b	_minyar_rc_poll
	.loh AdrpLdr	Lloh46, Lloh47
	.loh AdrpAdd	Lloh48, Lloh49
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
Lloh50:
	adrp	x8, _rc_pending_count@PAGE
Lloh51:
	ldr	x8, [x8, _rc_pending_count@PAGEOFF]
	cbz	x8, LBB19_2
; %bb.1:
	mov	w0, #32                         ; =0x20
	bl	_minyar_rc_poll
LBB19_2:
	mov	w0, #32                         ; =0x20
	bl	_malloc
	cbz	x0, LBB19_4
; %bb.3:
	mov	w8, #10                         ; =0xa
	str	x8, [x0]
	stp	xzr, xzr, [x0, #16]
	str	xzr, [x0, #8]!
	ldp	x29, x30, [sp], #16             ; 16-byte Folded Reload
	ret
LBB19_4:
	bl	_out_of_memory
	.loh AdrpLdr	Lloh50, Lloh51
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
	b.ne	LBB20_2
; %bb.1:
	ret
LBB20_2:
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
	b.eq	LBB21_15
LBB21_1:
	ldur	x8, [x0, #-8]
	and	w9, w8, #0x7
	cmp	w9, #2
	b.ne	LBB21_3
; %bb.2:
	ldp	x8, x9, [x0]
	add	x10, x9, #1
	str	x10, [x0, #8]
	str	x1, [x8, x9, lsl #3]
	b	LBB21_14
LBB21_3:
	cbz	x1, LBB21_7
; %bb.4:
	cmp	w9, #6
	b.ne	LBB21_7
; %bb.5:
	ldur	x9, [x1, #-8]
	cmp	x9, #8
	b.lo	LBB21_12
; %bb.6:
	and	x8, x8, #0xfffffffffffffff8
	orr	x8, x8, #0x3
	stur	x8, [x0, #-8]
	b	LBB21_9
LBB21_7:
	cbz	x1, LBB21_12
; %bb.8:
	cmp	w9, #3
	b.ne	LBB21_12
LBB21_9:
	ldur	x8, [x1, #-8]
	cmp	x8, #8
	b.lo	LBB21_12
; %bb.10:
	cmn	x8, #8
	b.hs	LBB21_16
; %bb.11:
	add	x8, x8, #8
	stur	x8, [x1, #-8]
LBB21_12:
	ldp	x8, x9, [x0]
	add	x10, x9, #1
	str	x10, [x0, #8]
	str	x1, [x8, x9, lsl #3]
Lloh52:
	adrp	x8, _rc_pending_count@PAGE
Lloh53:
	ldr	x8, [x8, _rc_pending_count@PAGEOFF]
	cbz	x8, LBB21_14
; %bb.13:
	mov	w0, #32                         ; =0x20
	ldp	x29, x30, [sp, #16]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp], #32             ; 16-byte Folded Reload
	b	_minyar_rc_poll
LBB21_14:
	ldp	x29, x30, [sp, #16]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp], #32             ; 16-byte Folded Reload
	ret
LBB21_15:
	mov	x19, x0
	mov	x20, x1
	bl	_list_grow
	mov	x0, x19
	mov	x1, x20
	b	LBB21_1
LBB21_16:
	bl	_minyar_list_add.cold.1
	.loh AdrpLdr	Lloh52, Lloh53
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
	tbnz	x8, #63, LBB22_4
; %bb.1:
	lsr	x9, x8, #61
	cbnz	x9, LBB22_4
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
	b.ne	LBB22_4
; %bb.3:
	mov	x19, x0
	ldr	x0, [x0]
	lsl	x1, x20, #3
	bl	_rc_reallocate_data
	str	x0, [x19]
	str	x20, [x19, #16]
	ldp	x29, x30, [sp, #16]             ; 16-byte Folded Reload
	b	_OUTLINED_FUNCTION_2
LBB22_4:
Lloh54:
	adrp	x0, l_.str.3@PAGE
Lloh55:
	add	x0, x0, l_.str.3@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh54, Lloh55
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
	b.eq	LBB23_10
LBB23_1:
	ldur	x8, [x0, #-8]
	and	w9, w8, #0x7
	cmp	w9, #2
	b.ne	LBB23_3
; %bb.2:
	ldp	x8, x9, [x0]
	add	x10, x9, #1
	str	x10, [x0, #8]
	str	x1, [x8, x9, lsl #3]
	b	LBB23_9
LBB23_3:
	cbz	x1, LBB23_7
; %bb.4:
	cmp	w9, #6
	b.ne	LBB23_7
; %bb.5:
	ldur	x9, [x1, #-8]
	cmp	x9, #8
	b.lo	LBB23_7
; %bb.6:
	and	x8, x8, #0xfffffffffffffff8
	orr	x8, x8, #0x3
	stur	x8, [x0, #-8]
LBB23_7:
	ldp	x8, x9, [x0]
	add	x10, x9, #1
	str	x10, [x0, #8]
	str	x1, [x8, x9, lsl #3]
Lloh56:
	adrp	x8, _rc_pending_count@PAGE
Lloh57:
	ldr	x8, [x8, _rc_pending_count@PAGEOFF]
	cbz	x8, LBB23_9
; %bb.8:
	mov	w0, #32                         ; =0x20
	ldp	x29, x30, [sp, #16]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp], #32             ; 16-byte Folded Reload
	b	_minyar_rc_poll
LBB23_9:
	ldp	x29, x30, [sp, #16]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp], #32             ; 16-byte Folded Reload
	ret
LBB23_10:
	mov	x19, x0
	mov	x20, x1
	bl	_list_grow
	mov	x0, x19
	mov	x1, x20
	b	LBB23_1
	.loh AdrpLdr	Lloh56, Lloh57
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
	b.ls	LBB25_2
; %bb.1:
	ldr	x8, [x0]
	ldr	x0, [x8, x1, lsl #3]
	ret
LBB25_2:
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
Lloh58:
	adrp	x2, l_.str.48@PAGE
Lloh59:
	add	x2, x2, l_.str.48@PAGEOFF
	add	x0, sp, #16
	mov	w1, #128                        ; =0x80
	bl	_snprintf
	add	x0, sp, #16
	bl	_minyar_stop
	.loh AdrpAdd	Lloh58, Lloh59
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
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
	ldr	x8, [x0, #8]
	cmp	x8, x1
	b.ls	LBB28_15
; %bb.1:
	ldur	x8, [x0, #-8]
	and	w9, w8, #0x7
	cbz	x2, LBB28_5
; %bb.2:
	cmp	w9, #6
	b.ne	LBB28_5
; %bb.3:
	ldur	x9, [x2, #-8]
	cmp	x9, #8
	b.lo	LBB28_13
; %bb.4:
	and	x8, x8, #0xfffffffffffffff8
	orr	x8, x8, #0x3
	stur	x8, [x0, #-8]
	b	LBB28_6
LBB28_5:
	cmp	w9, #3
	b.ne	LBB28_13
LBB28_6:
	cbz	x2, LBB28_11
; %bb.7:
	cbz	w3, LBB28_11
; %bb.8:
	ldur	x8, [x2, #-8]
	cmp	x8, #8
	b.lo	LBB28_11
; %bb.9:
	cmn	x8, #8
	b.hs	LBB28_16
; %bb.10:
	add	x8, x8, #8
	stur	x8, [x2, #-8]
LBB28_11:
	ldr	x8, [x0]
	ldr	x0, [x8, x1, lsl #3]
	str	x2, [x8, x1, lsl #3]
	bl	_rc_drop
Lloh60:
	adrp	x8, _rc_pending_count@PAGE
Lloh61:
	ldr	x8, [x8, _rc_pending_count@PAGEOFF]
	cbz	x8, LBB28_14
; %bb.12:
	mov	w8, #32                         ; =0x20
	sub	w0, w8, w0
	ldp	x29, x30, [sp], #16             ; 16-byte Folded Reload
	b	_minyar_rc_poll
LBB28_13:
	ldr	x8, [x0]
	str	x2, [x8, x1, lsl #3]
LBB28_14:
	ldp	x29, x30, [sp], #16             ; 16-byte Folded Reload
	ret
LBB28_15:
	mov	x0, x1
	mov	x1, x8
	bl	_list_position_stop
LBB28_16:
	bl	_minyar_list_set_owned.cold.1
	.loh AdrpLdr	Lloh60, Lloh61
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_list_set_take           ; -- Begin function minyar_list_set_take
	.p2align	2
_minyar_list_set_take:                  ; @minyar_list_set_take
	.cfi_startproc
; %bb.0:
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
	ldr	x8, [x0, #8]
	cmp	x8, x1
	b.ls	LBB29_10
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
	b.lo	LBB29_8
; %bb.4:
	and	x8, x8, #0xfffffffffffffff8
	orr	x8, x8, #0x3
	stur	x8, [x0, #-8]
	b	LBB29_6
LBB29_5:
	cmp	w9, #3
	b.ne	LBB29_8
LBB29_6:
	ldr	x8, [x0]
	ldr	x0, [x8, x1, lsl #3]
	str	x2, [x8, x1, lsl #3]
	bl	_rc_drop
Lloh62:
	adrp	x8, _rc_pending_count@PAGE
Lloh63:
	ldr	x8, [x8, _rc_pending_count@PAGEOFF]
	cbz	x8, LBB29_9
; %bb.7:
	mov	w8, #32                         ; =0x20
	sub	w0, w8, w0
	ldp	x29, x30, [sp], #16             ; 16-byte Folded Reload
	b	_minyar_rc_poll
LBB29_8:
	ldr	x8, [x0]
	str	x2, [x8, x1, lsl #3]
LBB29_9:
	ldp	x29, x30, [sp], #16             ; 16-byte Folded Reload
	ret
LBB29_10:
	mov	x0, x1
	mov	x1, x8
	bl	_list_position_stop
	.loh AdrpLdr	Lloh62, Lloh63
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
	cbz	x8, LBB30_2
; %bb.1:
	mov	w0, #32                         ; =0x20
	bl	_minyar_rc_poll
LBB30_2:
	mov	w0, #32                         ; =0x20
	bl	_malloc
	cbz	x0, LBB30_30
; %bb.3:
	mov	x21, x0
	mov	w8, #10                         ; =0xa
	str	x8, [x0]
	mov	x20, x0
	str	xzr, [x20, #8]!
	stp	xzr, xzr, [x0, #16]
	cbz	x24, LBB30_5
; %bb.4:
	mov	w8, #14                         ; =0xe
	str	x8, [x21]
LBB30_5:
	ldr	x8, [x23, #8]
	mov	x9, #9223372036854775807        ; =0x7fffffffffffffff
	cmp	x8, x9
	b.eq	LBB30_31
; %bb.6:
	ldr	x9, [x25, _rc_pending_count@PAGEOFF]
	orr	x24, x9, x24
	cbz	x9, LBB30_23
; %bb.7:
	tbnz	x8, #63, LBB30_9
LBB30_8:                                ; =>This Inner Loop Header: Depth=1
	add	x0, x21, #8
	bl	_list_grow
	ldr	x8, [x21, #24]
	ldr	x9, [x23, #8]
	cmp	x8, x9
	b.le	LBB30_8
LBB30_9:
	ldr	x8, [x23, #8]
	cbz	x24, LBB30_24
LBB30_10:
	cmp	x8, #1
	b.lt	LBB30_13
; %bb.11:
	mov	x24, #0                         ; =0x0
LBB30_12:                               ; =>This Inner Loop Header: Depth=1
	ldr	x8, [x23]
	ldr	x1, [x8, x24, lsl #3]
	mov	x0, x20
	bl	_minyar_list_add
	add	x24, x24, #1
	ldr	x8, [x23, #8]
	cmp	x24, x8
	b.lt	LBB30_12
LBB30_13:
	cbz	x22, LBB30_27
LBB30_14:
	ldp	x8, x9, [x21, #16]
	cmp	x8, x9
	b.eq	LBB30_29
LBB30_15:
	ldr	x8, [x21]
	and	w9, w8, #0x7
	cmp	w9, #2
	b.ne	LBB30_17
; %bb.16:
	ldp	x8, x9, [x21, #8]
	add	x10, x9, #1
	str	x10, [x21, #16]
	str	x19, [x8, x9, lsl #3]
	b	LBB30_28
LBB30_17:
	cbz	x19, LBB30_21
; %bb.18:
	cmp	w9, #6
	b.ne	LBB30_21
; %bb.19:
	ldur	x9, [x19, #-8]
	cmp	x9, #8
	b.lo	LBB30_21
; %bb.20:
	and	x8, x8, #0xfffffffffffffff8
	orr	x8, x8, #0x3
	str	x8, [x21]
LBB30_21:
	ldp	x8, x9, [x21, #8]
	add	x10, x9, #1
	str	x10, [x21, #16]
	str	x19, [x8, x9, lsl #3]
	ldr	x8, [x25, _rc_pending_count@PAGEOFF]
	cbz	x8, LBB30_28
; %bb.22:
	mov	w0, #32                         ; =0x20
	bl	_minyar_rc_poll
	b	LBB30_28
LBB30_23:
	add	x1, x8, #1
	mov	x0, x20
	bl	_list_reserve
	ldr	x8, [x23, #8]
	cbnz	x24, LBB30_10
LBB30_24:
	cbz	x8, LBB30_26
; %bb.25:
	ldr	x0, [x20]
	ldr	x1, [x23]
	lsl	x2, x8, #3
	bl	_memcpy
	ldr	x8, [x23, #8]
LBB30_26:
	str	x8, [x21, #16]
	cbnz	x22, LBB30_14
LBB30_27:
	mov	x0, x20
	mov	x1, x19
	bl	_minyar_list_add
LBB30_28:
	mov	x0, x20
	ldp	x29, x30, [sp, #64]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp, #48]             ; 16-byte Folded Reload
	ldp	x22, x21, [sp, #32]             ; 16-byte Folded Reload
	ldp	x24, x23, [sp, #16]             ; 16-byte Folded Reload
	ldp	x26, x25, [sp], #80             ; 16-byte Folded Reload
	ret
LBB30_29:
	mov	x0, x20
	bl	_list_grow
	b	LBB30_15
LBB30_30:
	bl	_out_of_memory
LBB30_31:
	bl	_minyar_list_appended.cold.1
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
	b.ge	LBB31_5
; %bb.1:
	mov	w9, #1                          ; =0x1
	mov	w10, #2                         ; =0x2
	mov	x20, x8
LBB31_2:                                ; =>This Inner Loop Header: Depth=1
	tbnz	x20, #63, LBB31_8
; %bb.3:                                ;   in Loop: Header=BB31_2 Depth=1
	lsr	x11, x20, #61
	cbnz	x11, LBB31_8
; %bb.4:                                ;   in Loop: Header=BB31_2 Depth=1
	cmp	x20, #4095
	cinc	x11, x9, hi
	lsl	x11, x20, x11
	cmp	x20, #0
	csel	x20, x10, x11, eq
	cmp	x20, x1
	b.lt	LBB31_2
	b	LBB31_6
LBB31_5:
	mov	x20, x8
LBB31_6:
	cmp	x8, x20
	lsr	x8, x20, #61
	ccmp	x8, #0, #0, le
	b.ne	LBB31_8
; %bb.7:
	ldr	x0, [x19]
	lsl	x1, x20, #3
	bl	_rc_reallocate_data
	str	x0, [x19]
	str	x20, [x19, #16]
	ldp	x29, x30, [sp, #16]             ; 16-byte Folded Reload
	b	_OUTLINED_FUNCTION_2
LBB31_8:
Lloh64:
	adrp	x0, l_.str.3@PAGE
Lloh65:
	add	x0, x0, l_.str.3@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh64, Lloh65
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
	cbnz	x8, LBB32_7
; %bb.1:
	mov	x19, x0
	mov	x8, #7280                       ; =0x1c70
	movk	x8, #29127, lsl #16
	movk	x8, #50972, lsl #32
	movk	x8, #7281, lsl #48
	cmp	x0, x8
	b.hs	LBB32_6
; %bb.2:
	add	x20, x19, x19, lsl #3
Lloh66:
	adrp	x8, _rc_pending_count@PAGE
Lloh67:
	ldr	x8, [x8, _rc_pending_count@PAGEOFF]
	cbz	x8, LBB32_4
; %bb.3:
	mov	w0, #32                         ; =0x20
	bl	_minyar_rc_poll
LBB32_4:
	add	x0, x20, #16
	bl	_malloc
	cbz	x0, LBB32_6
; %bb.5:
	mov	w9, #12                         ; =0xc
	mov	x8, x0
	str	x9, [x8], #16
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
LBB32_6:
	bl	_out_of_memory
LBB32_7:
	bl	_minyar_record_new.cold.1
	.loh AdrpLdr	Lloh66, Lloh67
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
	cbnz	x8, LBB33_7
; %bb.1:
	mov	x19, x0
	mov	x8, #2305843009213693950        ; =0x1ffffffffffffffe
	cmp	x0, x8
	b.hs	LBB33_6
; %bb.2:
	lsl	x20, x19, #3
Lloh68:
	adrp	x8, _rc_pending_count@PAGE
Lloh69:
	ldr	x8, [x8, _rc_pending_count@PAGEOFF]
	cbz	x8, LBB33_4
; %bb.3:
	mov	w0, #32                         ; =0x20
	bl	_minyar_rc_poll
LBB33_4:
	add	x0, x20, #16
	bl	_malloc
	cbz	x0, LBB33_6
; %bb.5:
	mov	w9, #13                         ; =0xd
	mov	x8, x0
	str	x9, [x8], #16
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
LBB33_6:
	bl	_out_of_memory
LBB33_7:
	bl	_minyar_record_new_scalar.cold.1
	.loh AdrpLdr	Lloh68, Lloh69
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_record_get              ; -- Begin function minyar_record_get
	.p2align	2
_minyar_record_get:                     ; @minyar_record_get
	.cfi_startproc
; %bb.0:
	ldr	x8, [x0]
	cmp	x8, x1
	b.ls	LBB34_2
; %bb.1:
	add	x8, x0, x1, lsl #3
	ldr	x0, [x8, #8]
	ret
LBB34_2:
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
	b.ls	LBB35_2
; %bb.1:
	add	x8, x0, x1, lsl #3
	str	x2, [x8, #8]
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
	.globl	_minyar_record_set              ; -- Begin function minyar_record_set
	.p2align	2
_minyar_record_set:                     ; @minyar_record_set
	.cfi_startproc
; %bb.0:
	ldr	x8, [x0]
	cmp	x8, x1
	b.ls	LBB36_4
; %bb.1:
	add	x8, x0, x1, lsl #3
	str	x2, [x8, #8]
	ldur	x8, [x0, #-8]
	and	x8, x8, #0x7
	cmp	x8, #4
	b.ne	LBB36_3
; %bb.2:
	mov	w0, #32                         ; =0x20
	b	_minyar_rc_poll
LBB36_3:
	ret
LBB36_4:
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
	b.ls	LBB37_5
; %bb.1:
	add	x9, x0, #8
	add	x8, x9, x8, lsl #3
	mov	w10, #1                         ; =0x1
	strb	w10, [x8, x1]
	ldr	x8, [x0]
	cmp	x8, x1
	b.ls	LBB37_5
; %bb.2:
	str	x2, [x9, x1, lsl #3]
	ldur	x8, [x0, #-8]
	and	x8, x8, #0x7
	cmp	x8, #4
	b.ne	LBB37_4
; %bb.3:
	mov	w0, #32                         ; =0x20
	ldp	x29, x30, [sp], #16             ; 16-byte Folded Reload
	b	_minyar_rc_poll
LBB37_4:
	ldp	x29, x30, [sp], #16             ; 16-byte Folded Reload
	ret
LBB37_5:
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
	cbz	x2, LBB38_4
; %bb.1:
	ldur	x8, [x2, #-8]
	cmp	x8, #8
	b.lo	LBB38_4
; %bb.2:
	cmn	x8, #8
	b.hs	LBB38_10
; %bb.3:
	add	x8, x8, #8
	stur	x8, [x2, #-8]
LBB38_4:
	ldr	x8, [x0]
	cmp	x8, x1
	b.ls	LBB38_9
; %bb.5:
	add	x9, x0, #8
	add	x8, x9, x8, lsl #3
	mov	w10, #1                         ; =0x1
	strb	w10, [x8, x1]
	ldr	x8, [x0]
	cmp	x8, x1
	b.ls	LBB38_9
; %bb.6:
	str	x2, [x9, x1, lsl #3]
	ldur	x8, [x0, #-8]
	and	x8, x8, #0x7
	cmp	x8, #4
	b.ne	LBB38_8
; %bb.7:
	mov	w0, #32                         ; =0x20
	ldp	x29, x30, [sp], #16             ; 16-byte Folded Reload
	b	_minyar_rc_poll
LBB38_8:
	ldp	x29, x30, [sp], #16             ; 16-byte Folded Reload
	ret
LBB38_9:
	mov	x0, x1
	mov	x1, x8
	bl	_list_position_stop
LBB38_10:
	bl	_minyar_record_set_reference.cold.1
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_record_replace          ; -- Begin function minyar_record_replace
	.p2align	2
_minyar_record_replace:                 ; @minyar_record_replace
	.cfi_startproc
; %bb.0:
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
	ldr	x8, [x0]
	cmp	x8, x1
	b.ls	LBB39_9
; %bb.1:
	cbz	x2, LBB39_6
; %bb.2:
	cbnz	x3, LBB39_6
; %bb.3:
	ldur	x8, [x2, #-8]
	cmp	x8, #8
	b.lo	LBB39_6
; %bb.4:
	cmn	x8, #8
	b.hs	LBB39_10
; %bb.5:
	add	x8, x8, #8
	stur	x8, [x2, #-8]
LBB39_6:
	add	x8, x0, x1, lsl #3
	ldr	x0, [x8, #8]
	str	x2, [x8, #8]
	bl	_rc_drop
Lloh70:
	adrp	x8, _rc_pending_count@PAGE
Lloh71:
	ldr	x8, [x8, _rc_pending_count@PAGEOFF]
	cbz	x8, LBB39_8
; %bb.7:
	mov	w8, #32                         ; =0x20
	sub	w0, w8, w0
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
	bl	_minyar_record_replace.cold.1
	.loh AdrpLdr	Lloh70, Lloh71
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
Lloh72:
	adrp	x20, ___stdoutp@GOTPAGE
Lloh73:
	ldr	x20, [x20, ___stdoutp@GOTPAGEOFF]
	ldr	x3, [x20]
	mov	w1, #1                          ; =0x1
	bl	_fwrite
	ldr	x8, [x19, #8]
	cmp	x0, x8
	b.ne	LBB40_4
; %bb.1:
	mov	w0, #10                         ; =0xa
	bl	_putchar
	cmn	w0, #1
	b.eq	LBB40_4
; %bb.2:
	ldr	x0, [x20]
	bl	_fflush
	cmn	w0, #1
	b.eq	LBB40_4
; %bb.3:
	ldp	x29, x30, [sp, #16]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp], #32             ; 16-byte Folded Reload
	ret
LBB40_4:
	bl	_output_error
	.loh AdrpLdrGot	Lloh72, Lloh73
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
Lloh74:
	adrp	x0, l_.str.50@PAGE
Lloh75:
	add	x0, x0, l_.str.50@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh74, Lloh75
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
Lloh76:
	adrp	x20, ___stderrp@GOTPAGE
Lloh77:
	ldr	x20, [x20, ___stderrp@GOTPAGEOFF]
	ldr	x1, [x20]
Lloh78:
	adrp	x0, l_.str.4@PAGE
Lloh79:
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
	.loh AdrpAdd	Lloh78, Lloh79
	.loh AdrpLdrGot	Lloh76, Lloh77
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
Lloh80:
	adrp	x0, l_.str.5@PAGE
Lloh81:
	add	x0, x0, l_.str.5@PAGEOFF
	bl	_printf
	tbnz	w0, #31, LBB43_3
; %bb.1:
Lloh82:
	adrp	x8, ___stdoutp@GOTPAGE
Lloh83:
	ldr	x8, [x8, ___stdoutp@GOTPAGEOFF]
Lloh84:
	ldr	x0, [x8]
	bl	_fflush
	cmn	w0, #1
	b.eq	LBB43_3
; %bb.2:
	ldp	x29, x30, [sp, #16]             ; 16-byte Folded Reload
	add	sp, sp, #32
	ret
LBB43_3:
	bl	_output_error
	.loh AdrpAdd	Lloh80, Lloh81
	.loh AdrpLdrGotLdr	Lloh82, Lloh83, Lloh84
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
	b.hi	LBB44_14
; %bb.1:
	and	w9, w0, #0x1ff800
	mov	w10, #55296                     ; =0xd800
	cmp	w9, w10
	b.eq	LBB44_14
; %bb.2:
	cmp	w0, #127
	b.hi	LBB44_4
; %bb.3:
	strb	w0, [sp, #12]
	mov	w19, #1                         ; =0x1
	b	LBB44_9
LBB44_4:
	cmp	w0, #2047
	b.hi	LBB44_6
; %bb.5:
	lsr	w8, w0, #6
	orr	w8, w8, #0xc0
	strb	w8, [sp, #12]
	mov	w8, #128                        ; =0x80
	bfxil	w8, w0, #0, #6
	strb	w8, [sp, #13]
	mov	w19, #2                         ; =0x2
	b	LBB44_9
LBB44_6:
	cbnz	w8, LBB44_8
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
	b	LBB44_9
LBB44_8:
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
LBB44_9:
Lloh85:
	adrp	x20, ___stdoutp@GOTPAGE
Lloh86:
	ldr	x20, [x20, ___stdoutp@GOTPAGEOFF]
	ldr	x3, [x20]
	add	x0, sp, #12
	mov	w1, #1                          ; =0x1
	mov	x2, x19
	bl	_fwrite
	cmp	x0, x19
	b.ne	LBB44_13
; %bb.10:
	mov	w0, #10                         ; =0xa
	bl	_putchar
	cmn	w0, #1
	b.eq	LBB44_13
; %bb.11:
	ldr	x0, [x20]
	bl	_fflush
	cmn	w0, #1
	b.eq	LBB44_13
; %bb.12:
	ldp	x29, x30, [sp, #32]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp, #16]             ; 16-byte Folded Reload
	add	sp, sp, #48
	ret
LBB44_13:
	bl	_output_error
LBB44_14:
	bl	_minyar_print_character.cold.1
	.loh AdrpLdrGot	Lloh85, Lloh86
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
Lloh87:
	adrp	x8, l_.str.7@PAGE
Lloh88:
	add	x8, x8, l_.str.7@PAGEOFF
Lloh89:
	adrp	x9, l_.str.6@PAGE
Lloh90:
	add	x9, x9, l_.str.6@PAGEOFF
	cmp	w0, #0
	csel	x0, x9, x8, ne
	bl	_puts
	cmn	w0, #1
	b.eq	LBB45_3
; %bb.1:
Lloh91:
	adrp	x8, ___stdoutp@GOTPAGE
Lloh92:
	ldr	x8, [x8, ___stdoutp@GOTPAGEOFF]
Lloh93:
	ldr	x0, [x8]
	bl	_fflush
	cmn	w0, #1
	b.eq	LBB45_3
; %bb.2:
	ldp	x29, x30, [sp], #16             ; 16-byte Folded Reload
	ret
LBB45_3:
	bl	_output_error
	.loh AdrpAdd	Lloh89, Lloh90
	.loh AdrpAdd	Lloh87, Lloh88
	.loh AdrpLdrGotLdr	Lloh91, Lloh92, Lloh93
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_texts_are_equal         ; -- Begin function minyar_texts_are_equal
	.p2align	2
_minyar_texts_are_equal:                ; @minyar_texts_are_equal
	.cfi_startproc
; %bb.0:
	cmp	x0, x1
	b.eq	LBB46_14
; %bb.1:
	ldr	x2, [x0, #8]
	ldr	x8, [x1, #8]
	cmp	x2, x8
	b.ne	LBB46_4
; %bb.2:
	ldr	x0, [x0]
	ldr	x1, [x1]
	cmp	x2, #17
	b.lo	LBB46_5
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
LBB46_4:
	mov	w0, #0                          ; =0x0
	ret
LBB46_5:
	cmp	x2, #8
	b.lo	LBB46_7
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
LBB46_7:
	cmp	x2, #4
	b.lo	LBB46_9
; %bb.8:
	ldr	w8, [x0]
	ldr	w9, [x1]
	add	x10, x0, x2
	ldur	w10, [x10, #-4]
	add	x11, x1, x2
	ldur	w11, [x11, #-4]
	b	LBB46_11
LBB46_9:
	cmp	x2, #2
	b.lo	LBB46_12
; %bb.10:
	ldrh	w8, [x0]
	ldrh	w9, [x1]
	add	x10, x0, x2
	ldurh	w10, [x10, #-2]
	and	w10, w10, #0xffff
	add	x11, x1, x2
	ldurh	w11, [x11, #-2]
	and	w11, w11, #0xffff
LBB46_11:
	cmp	w8, w9
	ccmp	w10, w11, #0, eq
	cset	w0, eq
	ret
LBB46_12:
	cbz	x2, LBB46_14
; %bb.13:
	ldrb	w8, [x0]
	ldrb	w9, [x1]
	cmp	w8, w9
	cset	w0, eq
	ret
LBB46_14:
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
	b.gt	LBB47_2
; %bb.1:
	b	_join_by_copying
LBB47_2:
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
Lloh94:
	adrp	x0, l_.str.51@PAGE
Lloh95:
	add	x0, x0, l_.str.51@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh94, Lloh95
	.cfi_endproc
                                        ; -- End function
	.p2align	2                               ; -- Begin function join_by_copying
_join_by_copying:                       ; @join_by_copying
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
	mov	x20, x1
	mov	x21, x0
	ldr	x8, [x0, #8]
	ldr	x9, [x1, #8]
	add	x24, x9, x8
	add	x22, x24, #1
	adrp	x25, _rc_pending_count@PAGE
	ldr	x8, [x25, _rc_pending_count@PAGEOFF]
	cbz	x8, LBB49_2
; %bb.1:
	mov	w0, #32                         ; =0x20
	bl	_minyar_rc_poll
LBB49_2:
	cmn	x22, #8
	b.hs	LBB49_30
; %bb.3:
	add	x0, x24, #9
	bl	_malloc
	cbz	x0, LBB49_30
; %bb.4:
	mov	x19, x0
	str	x22, [x19], #8
	ldp	x1, x22, [x21]
	cmp	x22, #17
	b.lo	LBB49_6
; %bb.5:
	mov	x0, x19
	mov	x2, x22
	bl	_memcpy
	b	LBB49_14
LBB49_6:
	cmp	x22, #8
	b.lo	LBB49_8
; %bb.7:
	ldr	x8, [x1]
	add	x9, x1, x22
	ldur	x9, [x9, #-8]
	str	x8, [x19]
	add	x8, x19, x22
	stur	x9, [x8, #-8]
	b	LBB49_14
LBB49_8:
	cmp	x22, #4
	b.lo	LBB49_10
; %bb.9:
	ldr	w8, [x1]
	add	x9, x1, x22
	ldur	w9, [x9, #-4]
	str	w8, [x19]
	add	x8, x19, x22
	stur	w9, [x8, #-4]
	b	LBB49_14
LBB49_10:
	cmp	x22, #2
	b.lo	LBB49_12
; %bb.11:
	ldrh	w8, [x1]
	add	x9, x1, x22
	ldurh	w9, [x9, #-2]
	strh	w8, [x19]
	add	x8, x19, x22
	sturh	w9, [x8, #-2]
	b	LBB49_14
LBB49_12:
	cmp	x22, #1
	b.ne	LBB49_14
; %bb.13:
	ldrb	w8, [x1]
	strb	w8, [x19]
LBB49_14:
	add	x0, x19, x22
	ldp	x1, x23, [x20]
	cmp	x23, #17
	b.lo	LBB49_16
; %bb.15:
	mov	x2, x23
	bl	_memcpy
	b	LBB49_24
LBB49_16:
	cmp	x23, #8
	b.lo	LBB49_18
; %bb.17:
	ldr	x8, [x1]
	add	x9, x1, x23
	ldur	x9, [x9, #-8]
	str	x8, [x0]
	add	x8, x0, x23
	stur	x9, [x8, #-8]
	b	LBB49_24
LBB49_18:
	cmp	x23, #4
	b.lo	LBB49_20
; %bb.19:
	ldr	w8, [x1]
	add	x9, x1, x23
	ldur	w9, [x9, #-4]
	str	w8, [x0]
	add	x8, x0, x23
	stur	w9, [x8, #-4]
	b	LBB49_24
LBB49_20:
	cmp	x23, #2
	b.lo	LBB49_22
; %bb.21:
	ldrh	w8, [x1]
	add	x9, x1, x23
	ldurh	w9, [x9, #-2]
	strh	w8, [x0]
	add	x8, x0, x23
	sturh	w9, [x8, #-2]
	b	LBB49_24
LBB49_22:
	cmp	x23, #1
	b.ne	LBB49_24
; %bb.23:
	ldrb	w8, [x1]
	strb	w8, [x0]
LBB49_24:
	strb	wzr, [x19, x24]
	ldr	x8, [x21, #16]
	cmp	x8, x22
	b.ne	LBB49_26
; %bb.25:
	ldr	x8, [x20, #16]
	cmp	x8, x23
	csinv	x20, x24, xzr, eq
	ldr	x8, [x25, _rc_pending_count@PAGEOFF]
	cbnz	x8, LBB49_27
	b	LBB49_28
LBB49_26:
	mov	x20, #-1                        ; =0xffffffffffffffff
	ldr	x8, [x25, _rc_pending_count@PAGEOFF]
	cbz	x8, LBB49_28
LBB49_27:
	mov	w0, #32                         ; =0x20
	bl	_minyar_rc_poll
LBB49_28:
	mov	w0, #48                         ; =0x30
	bl	_malloc
	cbz	x0, LBB49_30
; %bb.29:
	mov	x8, x0
	str	x19, [x8, #8]!
	mov	w9, #9                          ; =0x9
	str	x9, [x0]
	stp	x24, x20, [x0, #16]
	stp	xzr, xzr, [x0, #32]
	mov	x0, x8
	ldp	x29, x30, [sp, #64]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp, #48]             ; 16-byte Folded Reload
	ldp	x22, x21, [sp, #32]             ; 16-byte Folded Reload
	ldp	x24, x23, [sp, #16]             ; 16-byte Folded Reload
	ldp	x26, x25, [sp], #80             ; 16-byte Folded Reload
	ret
LBB49_30:
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
	b.gt	LBB50_27
; %bb.1:
	ldur	x8, [x0, #-8]
	cmp	x8, #9
	b.ne	LBB50_3
; %bb.2:
	ldr	x8, [x0, #32]
	cbz	x8, LBB50_7
LBB50_3:
	mov	x20, x0
	bl	_join_by_copying
	mov	x19, x0
	mov	x0, x20
	bl	_rc_drop
Lloh96:
	adrp	x8, _rc_pending_count@PAGE
Lloh97:
	ldr	x8, [x8, _rc_pending_count@PAGEOFF]
	cbz	x8, LBB50_5
; %bb.4:
	mov	w8, #32                         ; =0x20
	sub	w0, w8, w0
	bl	_minyar_rc_poll
LBB50_5:
	mov	x0, x19
LBB50_6:
	ldp	x29, x30, [sp, #48]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp, #32]             ; 16-byte Folded Reload
	ldp	x22, x21, [sp, #16]             ; 16-byte Folded Reload
	ldp	x24, x23, [sp], #64             ; 16-byte Folded Reload
	ret
LBB50_7:
	add	x22, x19, x21
	ldr	x20, [x0]
	add	x8, x22, #1
	ldur	x9, [x20, #-8]
	cmp	x8, x9
	mov	x23, x0
	mov	x24, x1
	b.ls	LBB50_9
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
LBB50_9:
	mov	x8, x20
	cmp	x1, x0
	b.eq	LBB50_11
; %bb.10:
	ldr	x8, [x1]
LBB50_11:
	add	x9, x20, x21
	cmp	x19, #17
	b.lo	LBB50_13
; %bb.12:
	mov	x0, x9
	mov	x1, x8
	mov	x2, x19
	bl	_memcpy
	mov	x1, x24
	mov	x0, x23
	b	LBB50_21
LBB50_13:
	cmp	x19, #8
	b.lo	LBB50_15
; %bb.14:
	ldr	x10, [x8]
	add	x8, x8, x19
	ldur	x8, [x8, #-8]
	str	x10, [x9]
	add	x9, x9, x19
	stur	x8, [x9, #-8]
	b	LBB50_21
LBB50_15:
	cmp	x19, #4
	b.lo	LBB50_17
; %bb.16:
	ldr	w10, [x8]
	add	x8, x8, x19
	ldur	w8, [x8, #-4]
	str	w10, [x9]
	add	x9, x9, x19
	stur	w8, [x9, #-4]
	b	LBB50_21
LBB50_17:
	cmp	x19, #2
	b.lo	LBB50_19
; %bb.18:
	ldrh	w10, [x8]
	add	x8, x8, x19
	ldurh	w8, [x8, #-2]
	strh	w10, [x9]
	add	x9, x9, x19
	sturh	w8, [x9, #-2]
	b	LBB50_21
LBB50_19:
	cmp	x19, #1
	b.ne	LBB50_21
; %bb.20:
	ldrb	w8, [x8]
	strb	w8, [x9]
LBB50_21:
	strb	wzr, [x20, x22]
	ldr	x8, [x0, #24]
	cbz	x8, LBB50_23
; %bb.22:
	sub	x0, x8, #8
	bl	_free
	mov	x1, x24
	mov	x0, x23
LBB50_23:
	stp	x20, x22, [x0]
	ldr	x8, [x0, #16]
	cmp	x8, x21
	b.ne	LBB50_25
; %bb.24:
	ldr	x8, [x1, #16]
	cmp	x8, x19
	b.eq	LBB50_26
LBB50_25:
	mov	x22, #-1                        ; =0xffffffffffffffff
LBB50_26:
	stp	x22, xzr, [x0, #16]
	b	LBB50_6
LBB50_27:
	bl	_join_too_large
	.loh AdrpLdr	Lloh96, Lloh97
	.cfi_endproc
                                        ; -- End function
	.p2align	2                               ; -- Begin function rc_reallocate_data
_rc_reallocate_data:                    ; @rc_reallocate_data
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
Lloh98:
	adrp	x8, _rc_pending_count@PAGE
Lloh99:
	ldr	x8, [x8, _rc_pending_count@PAGEOFF]
	cbz	x0, LBB51_5
; %bb.1:
	mov	x20, x0
	cbz	x8, LBB51_3
; %bb.2:
	mov	w0, #32                         ; =0x20
	bl	_minyar_rc_poll
LBB51_3:
	cmn	x19, #8
	b.hs	LBB51_10
; %bb.4:
	sub	x0, x20, #8
	add	x1, x19, #8
	bl	_realloc
	cbnz	x0, LBB51_9
	b	LBB51_10
LBB51_5:
	cbz	x8, LBB51_7
; %bb.6:
	mov	w0, #32                         ; =0x20
	bl	_minyar_rc_poll
LBB51_7:
	cmn	x19, #8
	b.hs	LBB51_10
; %bb.8:
	add	x0, x19, #8
	bl	_malloc
	cbz	x0, LBB51_10
LBB51_9:
	str	x19, [x0], #8
	ldp	x29, x30, [sp, #16]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp], #32             ; 16-byte Folded Reload
	ret
LBB51_10:
	bl	_out_of_memory
	.loh AdrpLdr	Lloh98, Lloh99
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_join_texts              ; -- Begin function minyar_join_texts
	.p2align	2
_minyar_join_texts:                     ; @minyar_join_texts
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
	mov	x20, x0
	ldr	x8, [x0, #8]
	cmp	x8, #1
	b.lt	LBB52_4
; %bb.1:
	mov	x21, #0                         ; =0x0
	ldr	x9, [x20]
LBB52_2:                                ; =>This Inner Loop Header: Depth=1
	ldr	x10, [x9], #8
	ldr	x10, [x10, #8]
	eor	x11, x21, #0x7fffffffffffffff
	cmp	x10, x11
	b.gt	LBB52_26
; %bb.3:                                ;   in Loop: Header=BB52_2 Depth=1
	add	x21, x10, x21
	subs	x8, x8, #1
	b.ne	LBB52_2
	b	LBB52_5
LBB52_4:
	mov	x21, #0                         ; =0x0
LBB52_5:
	add	x23, x21, #1
	adrp	x22, _rc_pending_count@PAGE
	ldr	x8, [x22, _rc_pending_count@PAGEOFF]
	cbz	x8, LBB52_7
; %bb.6:
	mov	w0, #32                         ; =0x20
	bl	_minyar_rc_poll
LBB52_7:
	cmn	x23, #8
	b.hs	LBB52_27
; %bb.8:
	add	x0, x21, #9
	bl	_malloc
	cbz	x0, LBB52_27
; %bb.9:
	mov	x19, x0
	str	x23, [x19], #8
	ldr	x23, [x20, #8]
	cmp	x23, #1
	b.lt	LBB52_22
; %bb.10:
	mov	x24, #0                         ; =0x0
	ldr	x20, [x20]
	b	LBB52_13
LBB52_11:                               ;   in Loop: Header=BB52_13 Depth=1
	bl	_memcpy
LBB52_12:                               ;   in Loop: Header=BB52_13 Depth=1
	ldr	x8, [x25, #8]
	add	x24, x8, x24
	subs	x23, x23, #1
	b.eq	LBB52_22
LBB52_13:                               ; =>This Inner Loop Header: Depth=1
	ldr	x25, [x20], #8
	add	x0, x19, x24
	ldp	x1, x2, [x25]
	cmp	x2, #17
	b.hs	LBB52_11
; %bb.14:                               ;   in Loop: Header=BB52_13 Depth=1
	cmp	x2, #8
	b.lo	LBB52_16
; %bb.15:                               ;   in Loop: Header=BB52_13 Depth=1
	ldr	x8, [x1]
	add	x9, x1, x2
	ldur	x9, [x9, #-8]
	str	x8, [x0]
	add	x8, x0, x2
	stur	x9, [x8, #-8]
	b	LBB52_12
LBB52_16:                               ;   in Loop: Header=BB52_13 Depth=1
	cmp	x2, #4
	b.lo	LBB52_18
; %bb.17:                               ;   in Loop: Header=BB52_13 Depth=1
	ldr	w8, [x1]
	add	x9, x1, x2
	ldur	w9, [x9, #-4]
	str	w8, [x0]
	add	x8, x0, x2
	stur	w9, [x8, #-4]
	b	LBB52_12
LBB52_18:                               ;   in Loop: Header=BB52_13 Depth=1
	cmp	x2, #2
	b.lo	LBB52_20
; %bb.19:                               ;   in Loop: Header=BB52_13 Depth=1
	ldrh	w8, [x1]
	add	x9, x1, x2
	ldurh	w9, [x9, #-2]
	strh	w8, [x0]
	add	x8, x0, x2
	sturh	w9, [x8, #-2]
	b	LBB52_12
LBB52_20:                               ;   in Loop: Header=BB52_13 Depth=1
	cmp	x2, #1
	b.ne	LBB52_12
; %bb.21:                               ;   in Loop: Header=BB52_13 Depth=1
	ldrb	w8, [x1]
	strb	w8, [x0]
	b	LBB52_12
LBB52_22:
	strb	wzr, [x19, x21]
	ldr	x8, [x22, _rc_pending_count@PAGEOFF]
	cbz	x8, LBB52_24
; %bb.23:
	mov	w0, #32                         ; =0x20
	bl	_minyar_rc_poll
LBB52_24:
	mov	w0, #48                         ; =0x30
	bl	_malloc
	cbz	x0, LBB52_27
; %bb.25:
	mov	w8, #9                          ; =0x9
	str	x8, [x0]
	mov	x8, x0
	str	x19, [x8, #8]!
	mov	x9, #-1                         ; =0xffffffffffffffff
	stp	x21, x9, [x0, #16]
	stp	xzr, xzr, [x0, #32]
	mov	x0, x8
	ldp	x29, x30, [sp, #64]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp, #48]             ; 16-byte Folded Reload
	ldp	x22, x21, [sp, #32]             ; 16-byte Folded Reload
	ldp	x24, x23, [sp, #16]             ; 16-byte Folded Reload
	ldp	x26, x25, [sp], #80             ; 16-byte Folded Reload
	ret
LBB52_26:
	bl	_join_too_large
LBB52_27:
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
	tbnz	x0, #63, LBB53_2
LBB53_1:
	ldp	x29, x30, [sp, #16]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp], #32             ; 16-byte Folded Reload
	ret
LBB53_2:
	mov	x0, x19
	bl	_build_text_index
	ldr	x0, [x19, #16]
	b	LBB53_1
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
	tbnz	x8, #63, LBB55_4
; %bb.1:
	cmp	x8, x1
	b.ls	LBB55_4
; %bb.2:
	ldr	x8, [x0, #24]
	cbnz	x8, LBB55_5
; %bb.3:
	ldr	x8, [x0]
	ldrb	w0, [x8, x1]
	ret
LBB55_4:
	b	_character_at_slowly
LBB55_5:
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
	tbnz	x1, #63, LBB56_7
; %bb.1:
	mov	x19, x1
	mov	x20, x0
	ldr	x8, [x0, #16]
	tbnz	x8, #63, LBB56_5
LBB56_2:
	cmp	x8, x19
	b.le	LBB56_8
; %bb.3:
	ldr	x8, [x20, #24]
	cbnz	x8, LBB56_6
; %bb.4:
	ldr	x8, [x20]
	ldrb	w0, [x8, x19]
	ldp	x29, x30, [sp, #16]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp], #32             ; 16-byte Folded Reload
	ret
LBB56_5:
	mov	x0, x20
	bl	_build_text_index
	ldr	x8, [x20, #16]
	b	LBB56_2
LBB56_6:
	mov	x0, x20
	mov	x1, x19
	ldp	x29, x30, [sp, #16]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp], #32             ; 16-byte Folded Reload
	b	_indexed_character_at
LBB56_7:
	bl	_negative_text_position
LBB56_8:
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
	mov	w8, #64                         ; =0x40
	ldp	x12, x9, [x20, #8]
	sdiv	x11, x9, x8
	add	x9, x11, #1
	add	x10, x21, #1
	mov	w8, #-1                         ; =0xffffffff
	cmp	x12, x8
	b.gt	LBB57_2
; %bb.1:
	ldr	x8, [x20, #24]
	str	w10, [x8, x9, lsl #2]
	add	x9, x11, #2
	ldr	x10, [sp, #8]
	add	x10, x10, x19
	b	LBB57_3
LBB57_2:
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
	b.gt	LBB57_4
LBB57_3:
	str	w10, [x8, x9, lsl #2]
	b	LBB57_5
LBB57_4:
	str	x10, [x8, x9, lsl #3]
LBB57_5:
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
	mov	x21, x2
	mov	x20, x1
	mov	x19, x0
	ldr	x8, [x0, #16]
	tbnz	x8, #63, LBB58_27
; %bb.1:
	tbnz	x20, #63, LBB58_28
LBB58_2:
	subs	x23, x21, x20
	b.lt	LBB58_28
; %bb.3:
	ldr	x8, [x19, #16]
	cmp	x8, x21
	b.lt	LBB58_28
; %bb.4:
	ldr	x8, [x19, #24]
	cbz	x8, LBB58_6
; %bb.5:
	mov	x0, x19
	mov	x1, x20
	bl	_indexed_byte_offset
	mov	x20, x0
	mov	x0, x19
	mov	x1, x21
	bl	_indexed_byte_offset
	mov	x21, x0
LBB58_6:
	sub	x21, x21, x20
	ldr	x8, [x19, #32]
	cmp	x8, #0
	csel	x22, x19, x8, eq
	cbnz	x20, LBB58_11
; %bb.7:
	ldr	x8, [x19, #8]
	cmp	x21, x8
	b.ne	LBB58_11
; %bb.8:
	ldur	x8, [x19, #-8]
	cmp	x8, #8
	b.lo	LBB58_26
; %bb.9:
	cmn	x8, #8
	b.hs	LBB58_31
; %bb.10:
	add	x8, x8, #8
	stur	x8, [x19, #-8]
	b	LBB58_26
LBB58_11:
	ldr	x8, [x22, #8]
	lsl	x9, x21, #3
	cmp	x8, #1, lsl #12                 ; =4096
	ccmp	x9, x8, #2, gt
	b.lo	LBB58_18
; %bb.12:
	ldr	x19, [x19]
	cmp	x21, x23
	csinv	x23, x23, xzr, eq
Lloh100:
	adrp	x8, _rc_pending_count@PAGE
Lloh101:
	ldr	x8, [x8, _rc_pending_count@PAGEOFF]
	cbz	x8, LBB58_14
; %bb.13:
	mov	w0, #32                         ; =0x20
	bl	_minyar_rc_poll
LBB58_14:
	mov	w0, #48                         ; =0x30
	bl	_malloc
	cbz	x0, LBB58_29
; %bb.15:
	add	x8, x19, x20
	mov	w9, #9                          ; =0x9
	str	x9, [x0]
	mov	x19, x0
	str	x8, [x19, #8]!
	stp	x21, x23, [x0, #16]
	stp	xzr, x22, [x0, #32]
	ldur	x8, [x22, #-8]
	cmp	x8, #8
	b.lo	LBB58_26
; %bb.16:
	cmn	x8, #8
	b.hs	LBB58_30
; %bb.17:
	add	x8, x8, #8
	stur	x8, [x22, #-8]
	b	LBB58_26
LBB58_18:
	add	x25, x21, #1
	adrp	x24, _rc_pending_count@PAGE
	ldr	x8, [x24, _rc_pending_count@PAGEOFF]
	cbz	x8, LBB58_20
; %bb.19:
	mov	w0, #32                         ; =0x20
	bl	_minyar_rc_poll
LBB58_20:
	cmn	x25, #8
	b.hs	LBB58_29
; %bb.21:
	add	x0, x21, #9
	bl	_malloc
	cbz	x0, LBB58_29
; %bb.22:
	mov	x22, x0
	str	x25, [x22], #8
	ldr	x8, [x19]
	add	x1, x8, x20
	mov	x0, x22
	mov	x2, x21
	bl	_memcpy
	strb	wzr, [x22, x21]
	cmp	x21, x23
	csinv	x20, x23, xzr, eq
	ldr	x8, [x24, _rc_pending_count@PAGEOFF]
	cbz	x8, LBB58_24
; %bb.23:
	mov	w0, #32                         ; =0x20
	bl	_minyar_rc_poll
LBB58_24:
	mov	w0, #48                         ; =0x30
	bl	_malloc
	cbz	x0, LBB58_29
; %bb.25:
	mov	w8, #9                          ; =0x9
	str	x8, [x0]
	mov	x19, x0
	str	x22, [x19, #8]!
	stp	x21, x20, [x0, #16]
	stp	xzr, xzr, [x0, #32]
LBB58_26:
	mov	x0, x19
	ldp	x29, x30, [sp, #64]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp, #48]             ; 16-byte Folded Reload
	ldp	x22, x21, [sp, #32]             ; 16-byte Folded Reload
	ldp	x24, x23, [sp, #16]             ; 16-byte Folded Reload
	ldp	x26, x25, [sp], #80             ; 16-byte Folded Reload
	ret
LBB58_27:
	mov	x0, x19
	bl	_build_text_index
	tbz	x20, #63, LBB58_2
LBB58_28:
	bl	_slice_outside_text
LBB58_29:
	bl	_out_of_memory
LBB58_30:
	bl	_minyar_text_slice.cold.1
LBB58_31:
	bl	_minyar_text_slice.cold.2
	.loh AdrpLdr	Lloh100, Lloh101
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
Lloh102:
	adrp	x0, l_.str.56@PAGE
Lloh103:
	add	x0, x0, l_.str.56@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh102, Lloh103
	.cfi_endproc
                                        ; -- End function
	.p2align	2                               ; -- Begin function indexed_byte_offset
_indexed_byte_offset:                   ; @indexed_byte_offset
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
	mov	x19, x1
	mov	x20, x0
	lsr	x10, x1, #6
	and	x9, x1, #0xffffffffffffffc0
	ldr	x8, [x0, #8]
	ldr	x11, [x0, #24]
	mov	w12, #-1                        ; =0xffffffff
	cmp	x8, x12
	b.gt	LBB60_2
; %bb.1:
	ldr	w21, [x11, x10, lsl #2]
	ldr	x10, [x20, #16]
	add	x12, x10, #63
	cmp	x10, #0
	csel	x10, x12, x10, lt
	asr	x12, x10, #6
	add	x23, x12, #1
	ldr	w10, [x11, x23, lsl #2]
	add	x22, x12, #2
	ldr	w11, [x11, x22, lsl #2]
	b	LBB60_3
LBB60_2:
	ldr	x21, [x11, x10, lsl #3]
	ldr	x10, [x20, #16]
	add	x12, x10, #63
	cmp	x10, #0
	csel	x10, x12, x10, lt
	asr	x12, x10, #6
	add	x23, x12, #1
	ldr	x10, [x11, x23, lsl #3]
	add	x22, x12, #2
	ldr	x11, [x11, x22, lsl #3]
LBB60_3:
	cmp	x10, x9
	cset	w12, ge
	cmp	x10, x19
	cset	w13, le
	tst	w12, w13
	csel	x12, x11, x21, ne
	csel	x13, x10, x9, ne
	subs	x14, x10, x19
	b.gt	LBB60_5
; %bb.4:
	mov	x21, x12
	mov	x9, x13
	b	LBB60_6
LBB60_5:
	and	x12, x19, #0x3f
	cmp	x14, x12
	b.le	LBB60_9
LBB60_6:
	subs	x24, x19, x9
	b.le	LBB60_13
LBB60_7:                                ; =>This Inner Loop Header: Depth=1
	ldp	x8, x9, [x20]
	sub	x1, x9, x21
	add	x0, x8, x21
	add	x2, sp, #8
	bl	_decode_character
	ldr	x8, [sp, #8]
	add	x21, x8, x21
	subs	x24, x24, #1
	b.ne	LBB60_7
; %bb.8:
	ldr	x8, [x20, #8]
	b	LBB60_13
LBB60_9:
	ldr	x9, [x20]
	sub	x9, x9, #1
LBB60_10:                               ; =>This Inner Loop Header: Depth=1
	ldrb	w12, [x9, x11]
	sub	x11, x11, #1
	and	w12, w12, #0xc0
	cmp	w12, #128
	b.eq	LBB60_10
; %bb.11:                               ;   in Loop: Header=BB60_10 Depth=1
	sub	x10, x10, #1
	cmp	x10, x19
	b.gt	LBB60_10
; %bb.12:
	mov	x21, x11
LBB60_13:
	mov	w9, #-1                         ; =0xffffffff
	cmp	x8, x9
	b.gt	LBB60_15
; %bb.14:
	ldr	x8, [x20, #24]
	str	w19, [x8, x23, lsl #2]
	str	w21, [x8, x22, lsl #2]
	b	LBB60_18
LBB60_15:
	ldr	x8, [x20, #24]
	str	x19, [x8, x23, lsl #3]
	ldr	x9, [x20, #8]
	mov	w10, #-1                        ; =0xffffffff
	cmp	x9, x10
	b.gt	LBB60_17
; %bb.16:
	str	w21, [x8, x22, lsl #2]
	b	LBB60_18
LBB60_17:
	str	x21, [x8, x22, lsl #3]
LBB60_18:
	mov	x0, x21
	ldp	x29, x30, [sp, #64]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp, #48]             ; 16-byte Folded Reload
	ldp	x22, x21, [sp, #32]             ; 16-byte Folded Reload
	ldp	x24, x23, [sp, #16]             ; 16-byte Folded Reload
	add	sp, sp, #80
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
	cbnz	x9, LBB61_3
; %bb.1:
Lloh104:
	adrp	x20, _minyar_integer_text.integer_cache@PAGE
Lloh105:
	add	x20, x20, _minyar_integer_text.integer_cache@PAGEOFF
	ldr	x0, [x20, x19, lsl #3]
	cbz	x0, LBB61_4
LBB61_2:
	ldp	x29, x30, [sp, #16]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp], #32             ; 16-byte Folded Reload
	ret
LBB61_3:
	mov	x0, x19
	ldp	x29, x30, [sp, #16]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp], #32             ; 16-byte Folded Reload
	b	_format_integer_text
LBB61_4:
	mov	x0, x19
	bl	_format_integer_text
	str	x0, [x20, x19, lsl #3]
	mov	w8, #1                          ; =0x1
	stur	x8, [x0, #-8]
	b	LBB61_2
	.loh AdrpAdd	Lloh104, Lloh105
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
Lloh106:
	adrp	x8, ___stack_chk_guard@GOTPAGE
Lloh107:
	ldr	x8, [x8, ___stack_chk_guard@GOTPAGEOFF]
Lloh108:
	ldr	x8, [x8]
	str	x8, [sp, #40]
	add	x10, sp, #8
	add	x8, x10, #32
	cmp	x0, #0
	cneg	x9, x0, mi
	add	x19, x10, #31
	mov	w10, #10                        ; =0xa
LBB62_1:                                ; =>This Inner Loop Header: Depth=1
	udiv	x11, x9, x10
	msub	w12, w11, w10, w9
	orr	w12, w12, #0x30
	strb	w12, [x19], #-1
	cmp	x9, #9
	mov	x9, x11
	b.hi	LBB62_1
; %bb.2:
	tbnz	x0, #63, LBB62_4
; %bb.3:
	add	x19, x19, #1
	b	LBB62_5
LBB62_4:
	mov	w9, #45                         ; =0x2d
	strb	w9, [x19]
LBB62_5:
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
Lloh109:
	adrp	x9, ___stack_chk_guard@GOTPAGE
Lloh110:
	ldr	x9, [x9, ___stack_chk_guard@GOTPAGEOFF]
Lloh111:
	ldr	x9, [x9]
	cmp	x9, x8
	b.ne	LBB62_7
; %bb.6:
	ldp	x29, x30, [sp, #80]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp, #64]             ; 16-byte Folded Reload
	ldp	x22, x21, [sp, #48]             ; 16-byte Folded Reload
	add	sp, sp, #96
	ret
LBB62_7:
	bl	___stack_chk_fail
	.loh AdrpLdrGotLdr	Lloh106, Lloh107, Lloh108
	.loh AdrpLdrGotLdr	Lloh109, Lloh110, Lloh111
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_character_text          ; -- Begin function minyar_character_text
	.p2align	2
_minyar_character_text:                 ; @minyar_character_text
	.cfi_startproc
; %bb.0:
	cmp	w0, #127
	b.hi	LBB63_4
; %bb.1:
Lloh112:
	adrp	x8, _minyar_character_text.ascii_texts@PAGE
Lloh113:
	add	x8, x8, _minyar_character_text.ascii_texts@PAGEOFF
	mov	w9, #48                         ; =0x30
	umaddl	x8, w0, w9, x8
	ldr	x9, [x8, #16]
	cbz	x9, LBB63_3
; %bb.2:
	add	x0, x8, #8
	ret
LBB63_3:
	mov	w9, w0
Lloh114:
	adrp	x10, _minyar_character_text.ascii_bytes@PAGE
Lloh115:
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
LBB63_4:
	b	_encode_character_text
	.loh AdrpAdd	Lloh112, Lloh113
	.loh AdrpAdd	Lloh114, Lloh115
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
	b.eq	LBB64_9
; %bb.1:
	cmp	w0, #127
	b.hi	LBB64_3
; %bb.2:
	strb	w0, [sp, #12]
	mov	w19, #1                         ; =0x1
	b	LBB64_8
LBB64_3:
	cmp	w0, #2047
	b.hi	LBB64_5
; %bb.4:
	lsr	w8, w0, #6
	orr	w8, w8, #0xc0
	strb	w8, [sp, #12]
	mov	w8, #128                        ; =0x80
	bfxil	w8, w0, #0, #6
	strb	w8, [sp, #13]
	mov	w19, #2                         ; =0x2
	b	LBB64_8
LBB64_5:
	cbnz	w8, LBB64_7
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
	b	LBB64_8
LBB64_7:
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
LBB64_8:
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
LBB64_9:
Lloh116:
	adrp	x0, l_.str.57@PAGE
Lloh117:
	add	x0, x0, l_.str.57@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh116, Lloh117
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_boolean_text            ; -- Begin function minyar_boolean_text
	.p2align	2
_minyar_boolean_text:                   ; @minyar_boolean_text
	.cfi_startproc
; %bb.0:
Lloh118:
	adrp	x8, l_.str.7@PAGE
Lloh119:
	add	x8, x8, l_.str.7@PAGEOFF
Lloh120:
	adrp	x9, l_.str.6@PAGE
Lloh121:
	add	x9, x9, l_.str.6@PAGEOFF
	cmp	w0, #0
	csel	x0, x9, x8, ne
	b	_copy_c_text
	.loh AdrpAdd	Lloh120, Lloh121
	.loh AdrpAdd	Lloh118, Lloh119
	.cfi_endproc
                                        ; -- End function
	.p2align	2                               ; -- Begin function copy_c_text
_copy_c_text:                           ; @copy_c_text
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
	mov	x21, x0
	bl	_strlen
	mov	x19, x0
	add	x22, x0, #1
	adrp	x23, _rc_pending_count@PAGE
	ldr	x8, [x23, _rc_pending_count@PAGEOFF]
	cbz	x8, LBB66_2
; %bb.1:
	mov	w0, #32                         ; =0x20
	bl	_minyar_rc_poll
LBB66_2:
	cmn	x22, #8
	b.hs	LBB66_8
; %bb.3:
	add	x0, x19, #9
	bl	_malloc
	cbz	x0, LBB66_8
; %bb.4:
	mov	x20, x0
	str	x22, [x20], #8
	mov	x0, x20
	mov	x1, x21
	mov	x2, x22
	bl	_memcpy
	ldr	x8, [x23, _rc_pending_count@PAGEOFF]
	cbz	x8, LBB66_6
; %bb.5:
	mov	w0, #32                         ; =0x20
	bl	_minyar_rc_poll
LBB66_6:
	mov	w0, #48                         ; =0x30
	bl	_malloc
	cbz	x0, LBB66_8
; %bb.7:
	mov	w8, #9                          ; =0x9
	str	x8, [x0]
	mov	x8, x0
	str	x20, [x8, #8]!
	mov	x9, #-1                         ; =0xffffffffffffffff
	stp	x19, x9, [x0, #16]
	stp	xzr, xzr, [x0, #32]
	mov	x0, x8
	ldp	x29, x30, [sp, #48]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp, #32]             ; 16-byte Folded Reload
	ldp	x22, x21, [sp, #16]             ; 16-byte Folded Reload
	ldp	x24, x23, [sp], #64             ; 16-byte Folded Reload
	ret
LBB66_8:
	bl	_out_of_memory
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_initialize_arguments    ; -- Begin function minyar_initialize_arguments
	.p2align	2
_minyar_initialize_arguments:           ; @minyar_initialize_arguments
	.cfi_startproc
; %bb.0:
Lloh122:
	adrp	x8, _saved_argument_count@PAGE
	str	w0, [x8, _saved_argument_count@PAGEOFF]
Lloh123:
	adrp	x8, _saved_argument_values@PAGE
	str	x1, [x8, _saved_argument_values@PAGEOFF]
	mov	w0, #13                         ; =0xd
	mov	w1, #1                          ; =0x1
	b	_signal
	.loh AdrpAdrp	Lloh122, Lloh123
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_argument_count          ; -- Begin function minyar_argument_count
	.p2align	2
_minyar_argument_count:                 ; @minyar_argument_count
	.cfi_startproc
; %bb.0:
Lloh124:
	adrp	x8, _saved_argument_count@PAGE
Lloh125:
	ldr	w8, [x8, _saved_argument_count@PAGEOFF]
	sub	w9, w8, #1
	cmp	w8, #0
	csel	w8, w9, wzr, gt
	sxtw	x0, w8
	ret
	.loh AdrpLdr	Lloh124, Lloh125
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_argument                ; -- Begin function minyar_argument
	.p2align	2
_minyar_argument:                       ; @minyar_argument
	.cfi_startproc
; %bb.0:
	tbnz	x0, #63, LBB69_3
; %bb.1:
Lloh126:
	adrp	x8, _saved_argument_count@PAGE
Lloh127:
	ldr	w8, [x8, _saved_argument_count@PAGEOFF]
	sub	w9, w8, #1
	cmp	w8, #0
	csel	w8, w9, wzr, gt
	sxtw	x8, w8
	cmp	x8, x0
	b.le	LBB69_3
; %bb.2:
Lloh128:
	adrp	x8, _saved_argument_values@PAGE
Lloh129:
	ldr	x8, [x8, _saved_argument_values@PAGEOFF]
	add	x8, x8, x0, lsl #3
	ldr	x0, [x8, #8]
	b	_copy_c_text
LBB69_3:
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
	bl	_minyar_argument.cold.1
	.loh AdrpLdr	Lloh126, Lloh127
	.loh AdrpLdr	Lloh128, Lloh129
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_read_text_file          ; -- Begin function minyar_read_text_file
	.p2align	2
_minyar_read_text_file:                 ; @minyar_read_text_file
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
	ldp	x21, x20, [x0]
	mov	x0, x21
	mov	w1, #0                          ; =0x0
	mov	x2, x20
	bl	_memchr
	cbnz	x0, LBB70_12
; %bb.1:
	add	x0, x20, #1
	bl	_malloc
	cbz	x0, LBB70_11
; %bb.2:
	mov	x19, x0
	mov	x1, x21
	mov	x2, x20
	bl	_memcpy
	strb	wzr, [x19, x20]
Lloh130:
	adrp	x1, l_.str.9@PAGE
Lloh131:
	add	x1, x1, l_.str.9@PAGEOFF
	mov	x0, x19
	bl	_fopen
	cbz	x0, LBB70_13
; %bb.3:
	mov	x22, x0
	bl	_text_file_length
	mov	x20, x0
	adrp	x23, _rc_pending_count@PAGE
	ldr	x8, [x23, _rc_pending_count@PAGEOFF]
	cbz	x8, LBB70_5
; %bb.4:
	mov	w0, #32                         ; =0x20
	bl	_minyar_rc_poll
LBB70_5:
	add	x0, x20, #9
	bl	_malloc
	cbz	x0, LBB70_11
; %bb.6:
	mov	x21, x0
	add	x8, x20, #1
	str	x8, [x21], #8
	mov	x0, x21
	mov	w1, #1                          ; =0x1
	mov	x2, x20
	mov	x3, x22
	bl	_fread
	cmp	x0, x20
	b.ne	LBB70_14
; %bb.7:
	mov	x0, x22
	bl	_fclose
	mov	x0, x19
	bl	_free
	strb	wzr, [x21, x20]
	ldr	x8, [x23, _rc_pending_count@PAGEOFF]
	cbz	x8, LBB70_9
; %bb.8:
	mov	w0, #32                         ; =0x20
	bl	_minyar_rc_poll
LBB70_9:
	mov	w0, #48                         ; =0x30
	bl	_malloc
	cbz	x0, LBB70_11
; %bb.10:
	mov	w8, #9                          ; =0x9
	str	x8, [x0]
	mov	x8, x0
	str	x21, [x8, #8]!
	mov	x9, #-1                         ; =0xffffffffffffffff
	stp	x20, x9, [x0, #16]
	stp	xzr, xzr, [x0, #32]
	mov	x0, x8
	ldp	x29, x30, [sp, #64]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp, #48]             ; 16-byte Folded Reload
	ldp	x22, x21, [sp, #32]             ; 16-byte Folded Reload
	ldp	x24, x23, [sp, #16]             ; 16-byte Folded Reload
	add	sp, sp, #80
	ret
LBB70_11:
	bl	_out_of_memory
LBB70_12:
	bl	_minyar_read_text_file.cold.1
LBB70_13:
Lloh132:
	adrp	x8, ___stderrp@GOTPAGE
Lloh133:
	ldr	x8, [x8, ___stderrp@GOTPAGEOFF]
Lloh134:
	ldr	x0, [x8]
	str	x19, [sp]
Lloh135:
	adrp	x1, l_.str.10@PAGE
Lloh136:
	add	x1, x1, l_.str.10@PAGEOFF
	bl	_fprintf
	mov	x0, x19
	bl	_rc_heap_deallocate
	mov	w0, #1                          ; =0x1
	bl	_exit
LBB70_14:
	bl	_minyar_read_text_file.cold.2
	.loh AdrpAdd	Lloh130, Lloh131
	.loh AdrpAdd	Lloh135, Lloh136
	.loh AdrpLdrGotLdr	Lloh132, Lloh133, Lloh134
	.cfi_endproc
                                        ; -- End function
	.p2align	2                               ; -- Begin function rc_heap_deallocate
_rc_heap_deallocate:                    ; @rc_heap_deallocate
	.cfi_startproc
; %bb.0:
	cbz	x0, LBB71_2
; %bb.1:
	b	_free
LBB71_2:
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
	b.ne	LBB72_2
; %bb.1:
	mov	x0, x19
	bl	_ferror
	cbnz	w0, LBB72_7
LBB72_2:
	mov	x0, x19
	mov	x1, #0                          ; =0x0
	mov	w2, #2                          ; =0x2
	bl	_fseek
	cbnz	w0, LBB72_6
; %bb.3:
	mov	x0, x19
	bl	_ftell
	tbnz	x0, #63, LBB72_6
; %bb.4:
	mov	x20, x0
	mov	x0, x19
	mov	x1, #0                          ; =0x0
	mov	w2, #0                          ; =0x0
	bl	_fseek
	cbnz	w0, LBB72_6
; %bb.5:
	mov	x0, x20
	ldp	x29, x30, [sp, #16]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp], #32             ; 16-byte Folded Reload
	ret
LBB72_6:
	bl	_text_file_length.cold.2
LBB72_7:
	bl	_text_file_length.cold.1
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_write_text_file         ; -- Begin function minyar_write_text_file
	.p2align	2
_minyar_write_text_file:                ; @minyar_write_text_file
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
	ldp	x21, x20, [x0]
	mov	x0, x21
	mov	w1, #0                          ; =0x0
	mov	x2, x20
	bl	_memchr
	cbnz	x0, LBB73_7
; %bb.1:
	add	x0, x20, #1
	bl	_malloc
	cbz	x0, LBB73_8
; %bb.2:
	mov	x22, x0
	mov	x1, x21
	mov	x2, x20
	bl	_memcpy
	strb	wzr, [x22, x20]
Lloh137:
	adrp	x1, l_.str.12@PAGE
Lloh138:
	add	x1, x1, l_.str.12@PAGEOFF
	mov	x0, x22
	bl	_fopen
	mov	x20, x0
	mov	x0, x22
	bl	_free
	cbz	x20, LBB73_9
; %bb.3:
	ldp	x0, x2, [x19]
	mov	w1, #1                          ; =0x1
	mov	x3, x20
	bl	_fwrite
	ldr	x8, [x19, #8]
	cmp	x0, x8
	b.ne	LBB73_6
; %bb.4:
	mov	x0, x20
	bl	_fclose
	cbnz	w0, LBB73_6
; %bb.5:
	ldp	x29, x30, [sp, #32]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp, #16]             ; 16-byte Folded Reload
	ldp	x22, x21, [sp], #48             ; 16-byte Folded Reload
	ret
LBB73_6:
	bl	_minyar_write_text_file.cold.2
LBB73_7:
	bl	_minyar_write_text_file.cold.1
LBB73_8:
	bl	_out_of_memory
LBB73_9:
	bl	_minyar_write_text_file.cold.3
	.loh AdrpAdd	Lloh137, Lloh138
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
Lloh139:
	adrp	x8, ___stderrp@GOTPAGE
Lloh140:
	ldr	x8, [x8, ___stderrp@GOTPAGEOFF]
Lloh141:
	ldr	x1, [x8]
Lloh142:
	adrp	x0, l_.str.15@PAGE
Lloh143:
	add	x0, x0, l_.str.15@PAGEOFF
	bl	_fputs
	bl	_OUTLINED_FUNCTION_0
	.loh AdrpAdd	Lloh142, Lloh143
	.loh AdrpLdrGotLdr	Lloh139, Lloh140, Lloh141
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_check_integer_overflow  ; -- Begin function minyar_check_integer_overflow
	.p2align	2
_minyar_check_integer_overflow:         ; @minyar_check_integer_overflow
	.cfi_startproc
; %bb.0:
	cbnz	w0, LBB75_2
; %bb.1:
	ret
LBB75_2:
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
Lloh144:
	adrp	x8, l_.str.17@PAGE
Lloh145:
	add	x8, x8, l_.str.17@PAGEOFF
Lloh146:
	adrp	x9, l_.str.16@PAGE
Lloh147:
	add	x9, x9, l_.str.16@PAGEOFF
	cmp	x0, #0
	csel	x0, x9, x8, eq
	bl	_integer_division_stop
	.loh AdrpAdd	Lloh146, Lloh147
	.loh AdrpAdd	Lloh144, Lloh145
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
Lloh148:
	adrp	x20, ___stderrp@GOTPAGE
Lloh149:
	ldr	x20, [x20, ___stderrp@GOTPAGEOFF]
	ldr	x1, [x20]
Lloh150:
	adrp	x0, l_.str.4@PAGE
Lloh151:
	add	x0, x0, l_.str.4@PAGEOFF
	bl	_fputs
	ldr	x1, [x20]
	mov	x0, x19
	bl	_fputs
	ldr	x1, [x20]
	mov	w0, #10                         ; =0xa
	bl	_fputc
	bl	_OUTLINED_FUNCTION_0
	.loh AdrpAdd	Lloh150, Lloh151
	.loh AdrpLdrGot	Lloh148, Lloh149
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_check_integer_division  ; -- Begin function minyar_check_integer_division
	.p2align	2
_minyar_check_integer_division:         ; @minyar_check_integer_division
	.cfi_startproc
; %bb.0:
	cbz	x1, LBB78_4
; %bb.1:
	mov	x8, #-9223372036854775808       ; =0x8000000000000000
	cmp	x0, x8
	b.ne	LBB78_3
; %bb.2:
	cmn	x1, #1
	b.eq	LBB78_4
LBB78_3:
	ret
LBB78_4:
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
Lloh152:
	adrp	x8, ___stack_chk_guard@GOTPAGE
Lloh153:
	ldr	x8, [x8, ___stack_chk_guard@GOTPAGEOFF]
Lloh154:
	ldr	x8, [x8]
	stur	x8, [x29, #-8]
	add	x0, sp, #8
	bl	_format_float
	add	x0, sp, #8
	bl	_puts
	cmn	w0, #1
	b.eq	LBB79_4
; %bb.1:
Lloh155:
	adrp	x8, ___stdoutp@GOTPAGE
Lloh156:
	ldr	x8, [x8, ___stdoutp@GOTPAGEOFF]
Lloh157:
	ldr	x0, [x8]
	bl	_fflush
	cmn	w0, #1
	b.eq	LBB79_4
; %bb.2:
	ldur	x8, [x29, #-8]
Lloh158:
	adrp	x9, ___stack_chk_guard@GOTPAGE
Lloh159:
	ldr	x9, [x9, ___stack_chk_guard@GOTPAGEOFF]
Lloh160:
	ldr	x9, [x9]
	cmp	x9, x8
	b.ne	LBB79_5
; %bb.3:
	ldp	x29, x30, [sp, #64]             ; 16-byte Folded Reload
	add	sp, sp, #80
	ret
LBB79_4:
	bl	_output_error
LBB79_5:
	bl	___stack_chk_fail
	.loh AdrpLdrGotLdr	Lloh152, Lloh153, Lloh154
	.loh AdrpLdrGotLdr	Lloh155, Lloh156, Lloh157
	.loh AdrpLdrGotLdr	Lloh158, Lloh159, Lloh160
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
Lloh161:
	adrp	x8, ___stack_chk_guard@GOTPAGE
Lloh162:
	ldr	x8, [x8, ___stack_chk_guard@GOTPAGEOFF]
Lloh163:
	ldr	x8, [x8]
	stur	x8, [x29, #-72]
	fcmp	d0, d0
	b.vs	LBB80_73
; %bb.1:
	fmov	d8, d0
	fabs	d0, d0
	mov	x8, #9218868437227405312        ; =0x7ff0000000000000
	fmov	d1, x8
	fcmp	d0, d1
	b.eq	LBB80_4
; %bb.2:
	fcmp	d8, #0.0
	b.ne	LBB80_8
; %bb.3:
	fmov	x8, d8
Lloh164:
	adrp	x9, l_.str.63@PAGE
Lloh165:
	add	x9, x9, l_.str.63@PAGEOFF
Lloh166:
	adrp	x10, l_.str.64@PAGE
Lloh167:
	add	x10, x10, l_.str.64@PAGEOFF
	cmp	x8, #0
	csel	x2, x10, x9, eq
	b	LBB80_5
LBB80_4:
Lloh168:
	adrp	x8, l_.str.62@PAGE
Lloh169:
	add	x8, x8, l_.str.62@PAGEOFF
Lloh170:
	adrp	x9, l_.str.61@PAGE
Lloh171:
	add	x9, x9, l_.str.61@PAGEOFF
	fcmp	d8, #0.0
	csel	x2, x9, x8, mi
LBB80_5:
	mov	w1, #48                         ; =0x30
	bl	_snprintf
                                        ; kill: def $w0 killed $w0 def $x0
	sxtw	x0, w0
LBB80_6:
	ldur	x8, [x29, #-72]
Lloh172:
	adrp	x9, ___stack_chk_guard@GOTPAGE
Lloh173:
	ldr	x9, [x9, ___stack_chk_guard@GOTPAGEOFF]
Lloh174:
	ldr	x9, [x9]
	cmp	x9, x8
	b.ne	LBB80_74
; %bb.7:
	ldp	x29, x30, [sp, #160]            ; 16-byte Folded Reload
	ldp	x20, x19, [sp, #144]            ; 16-byte Folded Reload
	ldp	x22, x21, [sp, #128]            ; 16-byte Folded Reload
	ldp	x24, x23, [sp, #112]            ; 16-byte Folded Reload
	ldp	d9, d8, [sp, #96]               ; 16-byte Folded Reload
	add	sp, sp, #176
	ret
LBB80_8:
	mov	x8, #4845873199050653696        ; =0x4340000000000000
	fmov	d1, x8
	fcmp	d0, d1
	fcvtzs	d0, d8
	scvtf	d0, d0
	fccmp	d0, d8, #0, mi
	b.eq	LBB80_42
; %bb.9:
	mov	x20, x0
	fmov	x8, d8
	tst	x8, #0xfffffffffffff
	cset	w9, eq
	tst	x8, #0x7fe0000000000000
	csel	w21, wzr, w9, eq
	str	d8, [sp, #8]
	str	xzr, [sp]
Lloh175:
	adrp	x19, l_.str.66@PAGE
Lloh176:
	add	x19, x19, l_.str.66@PAGEOFF
	add	x0, sp, #48
	mov	w1, #40                         ; =0x28
	mov	x2, x19
	bl	_snprintf
	mov	w22, #1                         ; =0x1
	b	LBB80_11
LBB80_10:                               ;   in Loop: Header=BB80_11 Depth=1
	add	w23, w22, #1
	str	d8, [sp, #8]
	str	x22, [sp]
	add	x0, sp, #48
	mov	w1, #40                         ; =0x28
	mov	x2, x19
	bl	_snprintf
	mov	x22, x23
	cmp	w23, #17
	b.eq	LBB80_15
LBB80_11:                               ; =>This Inner Loop Header: Depth=1
	add	x0, sp, #48
	mov	x1, #0                          ; =0x0
	bl	_strtod
	fcmp	d0, d8
	b.eq	LBB80_15
; %bb.12:                               ;   in Loop: Header=BB80_11 Depth=1
	cbz	w21, LBB80_10
; %bb.13:                               ;   in Loop: Header=BB80_11 Depth=1
	add	x0, sp, #48
	fmov	d0, d8
	mov	w1, #1                          ; =0x1
	bl	_adjacent_float_decimal
	tbnz	w0, #0, LBB80_15
; %bb.14:                               ;   in Loop: Header=BB80_11 Depth=1
	add	x0, sp, #48
	fmov	d0, d8
	mov	w1, #-1                         ; =0xffffffff
	bl	_adjacent_float_decimal
	tbz	w0, #0, LBB80_10
LBB80_15:
	mov	x21, #0                         ; =0x0
	ldrb	w19, [sp, #48]
	cmp	w19, #45
	add	x8, sp, #48
	cinc	x8, x8, eq
	add	x0, x8, #1
	add	x8, sp, #24
	b	LBB80_17
LBB80_16:                               ;   in Loop: Header=BB80_17 Depth=1
	add	x0, x0, #1
LBB80_17:                               ; =>This Inner Loop Header: Depth=1
	ldurb	w9, [x0, #-1]
	cbz	w9, LBB80_21
; %bb.18:                               ;   in Loop: Header=BB80_17 Depth=1
	cmp	w9, #101
	b.eq	LBB80_21
; %bb.19:                               ;   in Loop: Header=BB80_17 Depth=1
	sub	w10, w9, #48
	cmp	w10, #9
	b.hi	LBB80_16
; %bb.20:                               ;   in Loop: Header=BB80_17 Depth=1
	strb	w9, [x8, x21]
	add	x21, x21, #1
	b	LBB80_16
LBB80_21:
	bl	_atoi
                                        ; kill: def $w0 killed $w0 def $x0
	cmp	x21, #0
	cset	w9, ne
	add	x10, sp, #24
	mov	x8, x20
LBB80_22:                               ; =>This Inner Loop Header: Depth=1
	mov	x11, x21
	cmp	x21, #2
	b.lo	LBB80_25
; %bb.23:                               ;   in Loop: Header=BB80_22 Depth=1
	sub	x21, x11, #1
	add	x12, x10, x11
	ldurb	w12, [x12, #-1]
	cmp	w12, #48
	b.eq	LBB80_22
; %bb.24:
	add	x9, x21, #1
LBB80_25:
	cmp	w19, #45
	b.ne	LBB80_27
; %bb.26:
	mov	w10, #45                        ; =0x2d
	strb	w10, [x8]
	mov	w10, #1                         ; =0x1
	b	LBB80_28
LBB80_27:
	mov	x10, #0                         ; =0x0
LBB80_28:
	add	w12, w0, #7
	cmp	w12, #27
	b.hi	LBB80_37
; %bb.29:
	tbnz	w0, #31, LBB80_56
; %bb.30:
	mov	x11, #0                         ; =0x0
	mov	w12, w0
	add	x12, x12, #1
	add	x13, x8, x10
	add	x14, sp, #24
	b	LBB80_34
LBB80_31:                               ;   in Loop: Header=BB80_34 Depth=1
	ldrb	w15, [x14, x11]
LBB80_32:                               ;   in Loop: Header=BB80_34 Depth=1
	strb	w15, [x13, x11]
LBB80_33:                               ;   in Loop: Header=BB80_34 Depth=1
	add	x11, x11, #1
	cmp	x12, x11
	b.eq	LBB80_43
LBB80_34:                               ; =>This Inner Loop Header: Depth=1
	add	x15, x10, x11
	cmp	x15, #46
	b.hi	LBB80_33
; %bb.35:                               ;   in Loop: Header=BB80_34 Depth=1
	cmp	x9, x11
	b.hi	LBB80_31
; %bb.36:                               ;   in Loop: Header=BB80_34 Depth=1
	mov	w15, #48                        ; =0x30
	b	LBB80_32
LBB80_37:
	ldrb	w12, [sp, #24]
	add	x13, x8, x10
	strb	w12, [x13]
	orr	x12, x10, #0x2
	mov	w14, #46                        ; =0x2e
	strb	w14, [x13, #1]
	cmp	x11, #2
	b.lo	LBB80_50
; %bb.38:
	mov	w10, #2                         ; =0x2
	cmp	x9, #2
	csel	x9, x9, x10, hi
	sub	x9, x9, #1
	add	x10, sp, #24
	add	x10, x10, #1
	b	LBB80_40
LBB80_39:                               ;   in Loop: Header=BB80_40 Depth=1
	add	x10, x10, #1
	mov	x12, x19
	subs	x9, x9, #1
	b.eq	LBB80_51
LBB80_40:                               ; =>This Inner Loop Header: Depth=1
	add	x19, x12, #1
	cmp	x19, #47
	b.hi	LBB80_39
; %bb.41:                               ;   in Loop: Header=BB80_40 Depth=1
	ldrb	w11, [x10]
	strb	w11, [x8, x12]
	b	LBB80_39
LBB80_42:
	fcvtzs	x8, d8
	str	x8, [sp]
Lloh177:
	adrp	x2, l_.str.65@PAGE
Lloh178:
	add	x2, x2, l_.str.65@PAGEOFF
	b	LBB80_5
LBB80_43:
	add	x13, x10, x11
	sub	x13, x13, #1
	cmp	x13, #46
	b.hs	LBB80_45
; %bb.44:
	add	x14, x8, x10
	mov	w15, #46                        ; =0x2e
	strb	w15, [x14, x11]
LBB80_45:
	subs	x9, x9, x12
	b.ls	LBB80_62
; %bb.46:
	mov	x13, #0                         ; =0x0
	add	x14, sp, #24
	add	x12, x14, x12
	add	x14, x8, x10
	add	x15, x10, x11
	b	LBB80_48
LBB80_47:                               ;   in Loop: Header=BB80_48 Depth=1
	add	x13, x13, #1
	cmp	x9, x13
	b.eq	LBB80_64
LBB80_48:                               ; =>This Inner Loop Header: Depth=1
	add	x16, x15, x13
	add	x16, x16, #2
	cmp	x16, #47
	b.hi	LBB80_47
; %bb.49:                               ;   in Loop: Header=BB80_48 Depth=1
	ldrb	w16, [x12, x13]
	add	x17, x14, x13
	add	x17, x17, x11
	strb	w16, [x17, #1]
	b	LBB80_47
LBB80_50:
	add	x19, x10, #3
	mov	w9, #48                         ; =0x30
	strb	w9, [x8, x12]
LBB80_51:
	str	x0, [sp]
Lloh179:
	adrp	x2, l_.str.67@PAGE
Lloh180:
	add	x2, x2, l_.str.67@PAGEOFF
	add	x21, sp, #16
	add	x0, sp, #16
	mov	w1, #8                          ; =0x8
	bl	_snprintf
	ldrb	w10, [sp, #16]
	cbz	w10, LBB80_61
; %bb.52:
	add	x9, x21, #1
	mov	x8, x20
	b	LBB80_54
LBB80_53:                               ;   in Loop: Header=BB80_54 Depth=1
	ldrb	w10, [x9], #1
	mov	x19, x0
	cbz	w10, LBB80_72
LBB80_54:                               ; =>This Inner Loop Header: Depth=1
	add	x0, x19, #1
	cmp	x0, #47
	b.hi	LBB80_53
; %bb.55:                               ;   in Loop: Header=BB80_54 Depth=1
	strb	w10, [x8, x19]
	b	LBB80_53
LBB80_56:
	mov	w11, #11824                     ; =0x2e30
	strh	w11, [x8, x10]
	orr	x11, x10, #0x2
	cmn	w0, #1
	b.eq	LBB80_66
; %bb.57:
	sub	w10, w10, w0
	add	w10, w10, #1
	mov	w12, #48                        ; =0x30
	b	LBB80_59
LBB80_58:                               ;   in Loop: Header=BB80_59 Depth=1
	add	x11, x11, #1
	cmp	x10, x11
	b.eq	LBB80_65
LBB80_59:                               ; =>This Inner Loop Header: Depth=1
	cmp	x11, #46
	b.hi	LBB80_58
; %bb.60:                               ;   in Loop: Header=BB80_59 Depth=1
	strb	w12, [x8, x11]
	b	LBB80_58
LBB80_61:
	mov	x0, x19
	mov	x8, x20
	b	LBB80_72
LBB80_62:
	add	x9, x10, x11
	add	x0, x9, #2
	cmp	x13, #44
	b.hi	LBB80_72
; %bb.63:
	add	x9, x8, x10
	add	x9, x9, x11
	mov	w10, #48                        ; =0x30
	strb	w10, [x9, #1]
	b	LBB80_72
LBB80_64:
	add	x9, x10, x11
	add	x9, x9, x13
	add	x0, x9, #1
	b	LBB80_72
LBB80_65:
	mov	x11, x10
LBB80_66:
	cbz	x9, LBB80_71
; %bb.67:
	add	x10, sp, #24
	b	LBB80_69
LBB80_68:                               ;   in Loop: Header=BB80_69 Depth=1
	add	x10, x10, #1
	mov	x11, x0
	subs	x9, x9, #1
	b.eq	LBB80_72
LBB80_69:                               ; =>This Inner Loop Header: Depth=1
	add	x0, x11, #1
	cmp	x0, #47
	b.hi	LBB80_68
; %bb.70:                               ;   in Loop: Header=BB80_69 Depth=1
	ldrb	w12, [x10]
	strb	w12, [x8, x11]
	b	LBB80_68
LBB80_71:
	mov	x0, x11
LBB80_72:
	mov	w9, #47                         ; =0x2f
	cmp	x0, #47
	csel	x9, x0, x9, lo
	strb	wzr, [x8, x9]
	b	LBB80_6
LBB80_73:
	mov	w8, #24910                      ; =0x614e
	movk	w8, #78, lsl #16
	str	w8, [x0]
	mov	w0, #3                          ; =0x3
	b	LBB80_6
LBB80_74:
	bl	___stack_chk_fail
	.loh AdrpLdrGotLdr	Lloh161, Lloh162, Lloh163
	.loh AdrpAdd	Lloh166, Lloh167
	.loh AdrpAdd	Lloh164, Lloh165
	.loh AdrpAdd	Lloh170, Lloh171
	.loh AdrpAdd	Lloh168, Lloh169
	.loh AdrpLdrGotLdr	Lloh172, Lloh173, Lloh174
	.loh AdrpAdd	Lloh175, Lloh176
	.loh AdrpAdd	Lloh177, Lloh178
	.loh AdrpAdd	Lloh179, Lloh180
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_float_text              ; -- Begin function minyar_float_text
	.p2align	2
_minyar_float_text:                     ; @minyar_float_text
	.cfi_startproc
; %bb.0:
	sub	sp, sp, #112
	stp	x22, x21, [sp, #64]             ; 16-byte Folded Spill
	stp	x20, x19, [sp, #80]             ; 16-byte Folded Spill
	stp	x29, x30, [sp, #96]             ; 16-byte Folded Spill
	add	x29, sp, #96
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
	.cfi_offset w19, -24
	.cfi_offset w20, -32
	.cfi_offset w21, -40
	.cfi_offset w22, -48
Lloh181:
	adrp	x8, ___stack_chk_guard@GOTPAGE
Lloh182:
	ldr	x8, [x8, ___stack_chk_guard@GOTPAGEOFF]
Lloh183:
	ldr	x8, [x8]
	stur	x8, [x29, #-40]
	add	x0, sp, #8
	bl	_format_float
	mov	x19, x0
	add	x21, x0, #1
	adrp	x22, _rc_pending_count@PAGE
	ldr	x8, [x22, _rc_pending_count@PAGEOFF]
	cbz	x8, LBB81_2
; %bb.1:
	mov	w0, #32                         ; =0x20
	bl	_minyar_rc_poll
LBB81_2:
	cmn	x21, #8
	b.hs	LBB81_9
; %bb.3:
	add	x0, x19, #9
	bl	_malloc
	cbz	x0, LBB81_9
; %bb.4:
	mov	x20, x0
	str	x21, [x20], #8
	add	x1, sp, #8
	mov	x0, x20
	mov	x2, x21
	bl	_memcpy
	ldr	x8, [x22, _rc_pending_count@PAGEOFF]
	cbz	x8, LBB81_6
; %bb.5:
	mov	w0, #32                         ; =0x20
	bl	_minyar_rc_poll
LBB81_6:
	mov	w0, #48                         ; =0x30
	bl	_malloc
	cbz	x0, LBB81_9
; %bb.7:
	mov	w8, #9                          ; =0x9
	str	x8, [x0]
	mov	x8, x0
	str	x20, [x8, #8]!
	stp	x19, x19, [x0, #16]
	stp	xzr, xzr, [x0, #32]
	ldur	x9, [x29, #-40]
Lloh184:
	adrp	x10, ___stack_chk_guard@GOTPAGE
Lloh185:
	ldr	x10, [x10, ___stack_chk_guard@GOTPAGEOFF]
Lloh186:
	ldr	x10, [x10]
	cmp	x10, x9
	b.ne	LBB81_10
; %bb.8:
	mov	x0, x8
	ldp	x29, x30, [sp, #96]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp, #80]             ; 16-byte Folded Reload
	ldp	x22, x21, [sp, #64]             ; 16-byte Folded Reload
	add	sp, sp, #112
	ret
LBB81_9:
	bl	_out_of_memory
LBB81_10:
	bl	___stack_chk_fail
	.loh AdrpLdrGotLdr	Lloh181, Lloh182, Lloh183
	.loh AdrpLdrGotLdr	Lloh184, Lloh185, Lloh186
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
	b.pl	LBB82_2
; %bb.1:
	fcvtzs	x0, d0
	ret
LBB82_2:
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
	b.hi	LBB83_3
; %bb.1:
	and	x8, x0, #0x1ff800
	mov	w9, #55296                      ; =0xd800
	cmp	x8, x9
	b.eq	LBB83_3
; %bb.2:
                                        ; kill: def $w0 killed $w0 killed $x0
	ret
LBB83_3:
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
	b.eq	LBB84_2
; %bb.1:
	cmp	x0, #0
	cneg	x0, x0, mi
	ret
LBB84_2:
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
	b.gt	LBB85_2
; %bb.1:
	ret
LBB85_2:
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
	b.hi	LBB86_2
; %bb.1:
	ret
LBB86_2:
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
	b.hs	LBB87_2
; %bb.1:
	ret
LBB87_2:
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
	tbnz	x0, #63, LBB93_10
; %bb.1:
	mov	x19, x0
	mov	x8, #9223372036854775807        ; =0x7fffffffffffffff
	cmp	x0, x8
	b.eq	LBB93_11
; %bb.2:
	adrp	x21, _rc_pending_count@PAGE
	ldr	x8, [x21, _rc_pending_count@PAGEOFF]
	cbz	x8, LBB93_4
; %bb.3:
	mov	w0, #32                         ; =0x20
	bl	_minyar_rc_poll
LBB93_4:
	add	x0, x19, #9
	bl	_malloc
	cbz	x0, LBB93_9
; %bb.5:
	mov	x20, x0
	add	x1, x19, #1
	str	x1, [x20], #8
	mov	x0, x20
	bl	_bzero
	ldr	x8, [x21, _rc_pending_count@PAGEOFF]
	cbz	x8, LBB93_7
; %bb.6:
	mov	w0, #32                         ; =0x20
	bl	_minyar_rc_poll
LBB93_7:
	mov	w0, #48                         ; =0x30
	bl	_malloc
	cbz	x0, LBB93_9
; %bb.8:
	mov	x8, x0
	str	x20, [x8, #8]!
	mov	w9, #9                          ; =0x9
	str	x9, [x0]
	stp	x19, x19, [x0, #16]
	stp	xzr, xzr, [x0, #32]
	mov	x0, x8
	ldp	x29, x30, [sp, #32]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp, #16]             ; 16-byte Folded Reload
	ldp	x22, x21, [sp], #48             ; 16-byte Folded Reload
	ret
LBB93_9:
	bl	_out_of_memory
LBB93_10:
	bl	_minyar_bytes_new.cold.2
LBB93_11:
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
	tbnz	x1, #63, LBB95_9
; %bb.1:
	mov	x19, x1
	mov	x20, x0
	ldr	x8, [x0, #8]
	cmp	x8, x1
	b.ge	LBB95_8
; %bb.2:
	lsr	x9, x19, #61
	cbnz	x9, LBB95_10
; %bb.3:
	ldr	x9, [x20, #16]
	cmp	x9, x19
	b.ge	LBB95_6
; %bb.4:
	lsl	x8, x9, #1
	mov	w10, #16                        ; =0x10
	cmp	x9, #16
	csel	x8, x10, x8, lt
	cmp	x8, x19
	csel	x21, x8, x19, gt
	mov	x8, #9223372036854775807        ; =0x7fffffffffffffff
	cmp	x21, x8
	b.hs	LBB95_11
; %bb.5:
	ldr	x0, [x20]
	add	x1, x21, #1
	bl	_rc_reallocate_data
	strb	wzr, [x0, x21]
	str	x0, [x20]
	str	x21, [x20, #16]
	ldr	x8, [x20, #8]
	b	LBB95_7
LBB95_6:
	ldr	x0, [x20]
LBB95_7:
	sub	x1, x19, x8
	add	x0, x0, x8
	bl	_bzero
LBB95_8:
	str	x19, [x20, #8]
	ldp	x29, x30, [sp, #32]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp, #16]             ; 16-byte Folded Reload
	ldp	x22, x21, [sp], #48             ; 16-byte Folded Reload
	ret
LBB95_9:
	bl	_minyar_bytes_resize.cold.3
LBB95_10:
	bl	_minyar_bytes_resize.cold.2
LBB95_11:
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
	tbz	x8, #63, LBB96_8
; %bb.1:
	ldr	x9, [x19, #16]
	ldr	x20, [x19]
	tbz	x9, #63, LBB96_7
; %bb.2:
Lloh187:
	adrp	x8, _rc_pending_count@PAGE
Lloh188:
	ldr	x8, [x8, _rc_pending_count@PAGEOFF]
	cbz	x20, LBB96_9
; %bb.3:
	cbz	x8, LBB96_5
; %bb.4:
	mov	w0, #32                         ; =0x20
	bl	_minyar_rc_poll
LBB96_5:
	sub	x0, x20, #8
	mov	w1, #25                         ; =0x19
	bl	_realloc
	cbz	x0, LBB96_12
LBB96_6:
	mov	w8, #17                         ; =0x11
	str	x8, [x0]
	add	x20, x0, #8
	strb	wzr, [x0, #24]
	str	x20, [x19]
	mov	w8, #16                         ; =0x10
	str	x8, [x19, #16]
	ldr	x8, [x19, #8]
LBB96_7:
	neg	x1, x8
	add	x0, x20, x8
	bl	_bzero
LBB96_8:
	str	xzr, [x19, #8]
	ldp	x29, x30, [sp, #16]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp], #32             ; 16-byte Folded Reload
	ret
LBB96_9:
	cbz	x8, LBB96_11
; %bb.10:
	mov	w0, #32                         ; =0x20
	bl	_minyar_rc_poll
LBB96_11:
	mov	w0, #25                         ; =0x19
	bl	_malloc
	cbnz	x0, LBB96_6
LBB96_12:
	bl	_out_of_memory
	.loh AdrpLdr	Lloh187, Lloh188
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_bytes_get               ; -- Begin function minyar_bytes_get
	.p2align	2
_minyar_bytes_get:                      ; @minyar_bytes_get
	.cfi_startproc
; %bb.0:
	ldr	x2, [x0, #8]
	cmp	x2, x1
	b.ls	LBB97_2
; %bb.1:
	ldr	x8, [x0]
	ldrb	w0, [x8, x1]
	ret
LBB97_2:
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
	b.ne	LBB98_2
; %bb.1:
	stp	x0, x2, [sp]
Lloh189:
	adrp	x2, l_.str.68@PAGE
Lloh190:
	add	x2, x2, l_.str.68@PAGEOFF
	b	LBB98_3
LBB98_2:
	stp	x0, x2, [sp, #8]
	str	x1, [sp]
Lloh191:
	adrp	x2, l_.str.69@PAGE
Lloh192:
	add	x2, x2, l_.str.69@PAGEOFF
LBB98_3:
	add	x0, sp, #32
	mov	w1, #160                        ; =0xa0
	bl	_snprintf
	add	x0, sp, #32
	bl	_minyar_stop
	.loh AdrpAdd	Lloh189, Lloh190
	.loh AdrpAdd	Lloh191, Lloh192
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
	b.ls	LBB99_3
; %bb.1:
	cmp	x2, #256
	b.hs	LBB99_4
; %bb.2:
	ldr	x8, [x0]
	strb	w2, [x8, x1]
	ldp	x29, x30, [sp], #16             ; 16-byte Folded Reload
	ret
LBB99_3:
	mov	x0, x1
	mov	w1, #1                          ; =0x1
	mov	x2, x8
	bl	_bytes_position_stop
LBB99_4:
Lloh193:
	adrp	x1, l_.str.26@PAGE
Lloh194:
	add	x1, x1, l_.str.26@PAGEOFF
	mov	x0, x2
	bl	_bytes_value_stop
	.loh AdrpAdd	Lloh193, Lloh194
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
Lloh195:
	adrp	x2, l_.str.70@PAGE
Lloh196:
	add	x2, x2, l_.str.70@PAGEOFF
	add	x0, sp, #16
	mov	w1, #160                        ; =0xa0
	bl	_snprintf
	add	x0, sp, #16
	bl	_minyar_stop
	.loh AdrpAdd	Lloh195, Lloh196
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
	b.ne	LBB101_7
; %bb.1:
	mov	x20, x0
	ldr	x8, [x0, #8]
	mov	x9, #2305843009213693950        ; =0x1ffffffffffffffe
	cmp	x8, x9
	b.ge	LBB101_8
; %bb.2:
	ldr	x10, [x20, #16]
	add	x9, x8, #2
	cmp	x9, x10
	b.le	LBB101_5
; %bb.3:
	lsl	x8, x10, #1
	mov	w11, #16                        ; =0x10
	cmp	x10, #16
	csel	x8, x11, x8, lt
	cmp	x8, x9
	csel	x21, x8, x9, gt
	mov	x8, #9223372036854775807        ; =0x7fffffffffffffff
	cmp	x21, x8
	b.hs	LBB101_9
; %bb.4:
	ldr	x0, [x20]
	add	x1, x21, #1
	bl	_rc_reallocate_data
	strb	wzr, [x0, x21]
	str	x0, [x20]
	str	x21, [x20, #16]
	ldr	x8, [x20, #8]
	b	LBB101_6
LBB101_5:
	ldr	x0, [x20]
LBB101_6:
	strh	w19, [x0, x8]
	ldr	x8, [x20, #8]
	add	x8, x8, #2
	str	x8, [x20, #8]
	ldp	x29, x30, [sp, #32]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp, #16]             ; 16-byte Folded Reload
	ldp	x22, x21, [sp], #48             ; 16-byte Folded Reload
	ret
LBB101_7:
Lloh197:
	adrp	x1, l_.str.74@PAGE
Lloh198:
	add	x1, x1, l_.str.74@PAGEOFF
	mov	x0, x19
	bl	_bytes_value_stop
LBB101_8:
	bl	_minyar_bytes_add_int16.cold.2
LBB101_9:
	bl	_minyar_bytes_add_int16.cold.1
	.loh AdrpAdd	Lloh197, Lloh198
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
	tbnz	x1, #63, LBB102_4
; %bb.1:
	sub	x9, x8, #2
	cmp	x9, x1
	b.lt	LBB102_4
; %bb.2:
	cmp	x2, w2, sxth
	b.ne	LBB102_5
; %bb.3:
	ldr	x8, [x0]
	strh	w2, [x8, x1]
	ldp	x29, x30, [sp], #16             ; 16-byte Folded Reload
	ret
LBB102_4:
	mov	x0, x1
	mov	w1, #2                          ; =0x2
	mov	x2, x8
	bl	_bytes_position_stop
LBB102_5:
Lloh199:
	adrp	x1, l_.str.74@PAGE
Lloh200:
	add	x1, x1, l_.str.74@PAGEOFF
	mov	x0, x2
	bl	_bytes_value_stop
	.loh AdrpAdd	Lloh199, Lloh200
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_bytes_get_int16         ; -- Begin function minyar_bytes_get_int16
	.p2align	2
_minyar_bytes_get_int16:                ; @minyar_bytes_get_int16
	.cfi_startproc
; %bb.0:
	ldr	x2, [x0, #8]
	tbnz	x1, #63, LBB103_3
; %bb.1:
	sub	x8, x2, #2
	cmp	x8, x1
	b.lt	LBB103_3
; %bb.2:
	ldr	x8, [x0]
	add	x8, x8, x1
	ldrb	w9, [x8]
	ldrb	w8, [x8, #1]
	lsl	x9, x9, #48
	orr	x8, x9, x8, lsl #56
	asr	x0, x8, #48
	ret
LBB103_3:
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
	b.hs	LBB104_7
; %bb.1:
	mov	x20, x0
	ldr	x8, [x0, #8]
	mov	x9, #2305843009213693950        ; =0x1ffffffffffffffe
	cmp	x8, x9
	b.ge	LBB104_8
; %bb.2:
	ldr	x10, [x20, #16]
	add	x9, x8, #2
	cmp	x9, x10
	b.le	LBB104_5
; %bb.3:
	lsl	x8, x10, #1
	mov	w11, #16                        ; =0x10
	cmp	x10, #16
	csel	x8, x11, x8, lt
	cmp	x8, x9
	csel	x21, x8, x9, gt
	mov	x8, #9223372036854775807        ; =0x7fffffffffffffff
	cmp	x21, x8
	b.hs	LBB104_9
; %bb.4:
	ldr	x0, [x20]
	add	x1, x21, #1
	bl	_rc_reallocate_data
	strb	wzr, [x0, x21]
	str	x0, [x20]
	str	x21, [x20, #16]
	ldr	x8, [x20, #8]
	b	LBB104_6
LBB104_5:
	ldr	x0, [x20]
LBB104_6:
	strh	w19, [x0, x8]
	ldr	x8, [x20, #8]
	add	x8, x8, #2
	str	x8, [x20, #8]
	ldp	x29, x30, [sp, #32]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp, #16]             ; 16-byte Folded Reload
	ldp	x22, x21, [sp], #48             ; 16-byte Folded Reload
	ret
LBB104_7:
Lloh201:
	adrp	x1, l_.str.72@PAGE
Lloh202:
	add	x1, x1, l_.str.72@PAGEOFF
	mov	x0, x19
	bl	_bytes_value_stop
LBB104_8:
	bl	_minyar_bytes_add_uint16.cold.2
LBB104_9:
	bl	_minyar_bytes_add_uint16.cold.1
	.loh AdrpAdd	Lloh201, Lloh202
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
	tbnz	x1, #63, LBB105_4
; %bb.1:
	sub	x9, x8, #2
	cmp	x9, x1
	b.lt	LBB105_4
; %bb.2:
	cmp	x2, #16, lsl #12                ; =65536
	b.hs	LBB105_5
; %bb.3:
	ldr	x8, [x0]
	strh	w2, [x8, x1]
	ldp	x29, x30, [sp], #16             ; 16-byte Folded Reload
	ret
LBB105_4:
	mov	x0, x1
	mov	w1, #2                          ; =0x2
	mov	x2, x8
	bl	_bytes_position_stop
LBB105_5:
Lloh203:
	adrp	x1, l_.str.72@PAGE
Lloh204:
	add	x1, x1, l_.str.72@PAGEOFF
	mov	x0, x2
	bl	_bytes_value_stop
	.loh AdrpAdd	Lloh203, Lloh204
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_bytes_get_uint16        ; -- Begin function minyar_bytes_get_uint16
	.p2align	2
_minyar_bytes_get_uint16:               ; @minyar_bytes_get_uint16
	.cfi_startproc
; %bb.0:
	ldr	x2, [x0, #8]
	tbnz	x1, #63, LBB106_3
; %bb.1:
	sub	x8, x2, #2
	cmp	x8, x1
	b.lt	LBB106_3
; %bb.2:
	ldr	x8, [x0]
	ldrh	w0, [x8, x1]
	ret
LBB106_3:
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
	b.ne	LBB107_7
; %bb.1:
	mov	x20, x0
	ldr	x8, [x0, #8]
	mov	x9, #2305843009213693948        ; =0x1ffffffffffffffc
	cmp	x8, x9
	b.ge	LBB107_8
; %bb.2:
	ldr	x10, [x20, #16]
	add	x9, x8, #4
	cmp	x9, x10
	b.le	LBB107_5
; %bb.3:
	lsl	x8, x10, #1
	mov	w11, #16                        ; =0x10
	cmp	x10, #16
	csel	x8, x11, x8, lt
	cmp	x8, x9
	csel	x21, x8, x9, gt
	mov	x8, #9223372036854775807        ; =0x7fffffffffffffff
	cmp	x21, x8
	b.hs	LBB107_9
; %bb.4:
	ldr	x0, [x20]
	add	x1, x21, #1
	bl	_rc_reallocate_data
	strb	wzr, [x0, x21]
	str	x0, [x20]
	str	x21, [x20, #16]
	ldr	x8, [x20, #8]
	b	LBB107_6
LBB107_5:
	ldr	x0, [x20]
LBB107_6:
	str	w19, [x0, x8]
	ldr	x8, [x20, #8]
	add	x8, x8, #4
	str	x8, [x20, #8]
	ldp	x29, x30, [sp, #32]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp, #16]             ; 16-byte Folded Reload
	ldp	x22, x21, [sp], #48             ; 16-byte Folded Reload
	ret
LBB107_7:
Lloh205:
	adrp	x1, l_.str.75@PAGE
Lloh206:
	add	x1, x1, l_.str.75@PAGEOFF
	mov	x0, x19
	bl	_bytes_value_stop
LBB107_8:
	bl	_minyar_bytes_add_int32.cold.2
LBB107_9:
	bl	_minyar_bytes_add_int32.cold.1
	.loh AdrpAdd	Lloh205, Lloh206
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
	tbnz	x1, #63, LBB108_4
; %bb.1:
	sub	x9, x8, #4
	cmp	x9, x1
	b.lt	LBB108_4
; %bb.2:
	cmp	x2, w2, sxtw
	b.ne	LBB108_5
; %bb.3:
	ldr	x8, [x0]
	str	w2, [x8, x1]
	ldp	x29, x30, [sp], #16             ; 16-byte Folded Reload
	ret
LBB108_4:
	mov	x0, x1
	mov	w1, #4                          ; =0x4
	mov	x2, x8
	bl	_bytes_position_stop
LBB108_5:
Lloh207:
	adrp	x1, l_.str.75@PAGE
Lloh208:
	add	x1, x1, l_.str.75@PAGEOFF
	mov	x0, x2
	bl	_bytes_value_stop
	.loh AdrpAdd	Lloh207, Lloh208
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_bytes_get_int32         ; -- Begin function minyar_bytes_get_int32
	.p2align	2
_minyar_bytes_get_int32:                ; @minyar_bytes_get_int32
	.cfi_startproc
; %bb.0:
	ldr	x2, [x0, #8]
	tbnz	x1, #63, LBB109_3
; %bb.1:
	sub	x8, x2, #4
	cmp	x8, x1
	b.lt	LBB109_3
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
LBB109_3:
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
	cbnz	x8, LBB110_7
; %bb.1:
	mov	x20, x0
	ldr	x8, [x0, #8]
	mov	x9, #2305843009213693948        ; =0x1ffffffffffffffc
	cmp	x8, x9
	b.ge	LBB110_8
; %bb.2:
	ldr	x10, [x20, #16]
	add	x9, x8, #4
	cmp	x9, x10
	b.le	LBB110_5
; %bb.3:
	lsl	x8, x10, #1
	mov	w11, #16                        ; =0x10
	cmp	x10, #16
	csel	x8, x11, x8, lt
	cmp	x8, x9
	csel	x21, x8, x9, gt
	mov	x8, #9223372036854775807        ; =0x7fffffffffffffff
	cmp	x21, x8
	b.hs	LBB110_9
; %bb.4:
	ldr	x0, [x20]
	add	x1, x21, #1
	bl	_rc_reallocate_data
	strb	wzr, [x0, x21]
	str	x0, [x20]
	str	x21, [x20, #16]
	ldr	x8, [x20, #8]
	b	LBB110_6
LBB110_5:
	ldr	x0, [x20]
LBB110_6:
	str	w19, [x0, x8]
	ldr	x8, [x20, #8]
	add	x8, x8, #4
	str	x8, [x20, #8]
	ldp	x29, x30, [sp, #32]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp, #16]             ; 16-byte Folded Reload
	ldp	x22, x21, [sp], #48             ; 16-byte Folded Reload
	ret
LBB110_7:
Lloh209:
	adrp	x1, l_.str.73@PAGE
Lloh210:
	add	x1, x1, l_.str.73@PAGEOFF
	mov	x0, x19
	bl	_bytes_value_stop
LBB110_8:
	bl	_minyar_bytes_add_uint32.cold.2
LBB110_9:
	bl	_minyar_bytes_add_uint32.cold.1
	.loh AdrpAdd	Lloh209, Lloh210
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
	tbnz	x1, #63, LBB111_4
; %bb.1:
	sub	x9, x8, #4
	cmp	x9, x1
	b.lt	LBB111_4
; %bb.2:
	lsr	x8, x2, #32
	cbnz	x8, LBB111_5
; %bb.3:
	ldr	x8, [x0]
	str	w2, [x8, x1]
	ldp	x29, x30, [sp], #16             ; 16-byte Folded Reload
	ret
LBB111_4:
	mov	x0, x1
	mov	w1, #4                          ; =0x4
	mov	x2, x8
	bl	_bytes_position_stop
LBB111_5:
Lloh211:
	adrp	x1, l_.str.73@PAGE
Lloh212:
	add	x1, x1, l_.str.73@PAGEOFF
	mov	x0, x2
	bl	_bytes_value_stop
	.loh AdrpAdd	Lloh211, Lloh212
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_bytes_get_uint32        ; -- Begin function minyar_bytes_get_uint32
	.p2align	2
_minyar_bytes_get_uint32:               ; @minyar_bytes_get_uint32
	.cfi_startproc
; %bb.0:
	ldr	x2, [x0, #8]
	tbnz	x1, #63, LBB112_3
; %bb.1:
	sub	x8, x2, #4
	cmp	x8, x1
	b.lt	LBB112_3
; %bb.2:
	ldr	x8, [x0]
	ldr	w0, [x8, x1]
	ret
LBB112_3:
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
	b.ge	LBB113_6
; %bb.1:
	mov	x20, x1
	mov	x19, x0
	ldr	x10, [x0, #16]
	add	x9, x8, #8
	cmp	x9, x10
	b.le	LBB113_4
; %bb.2:
	lsl	x8, x10, #1
	mov	w11, #16                        ; =0x10
	cmp	x10, #16
	csel	x8, x11, x8, lt
	cmp	x8, x9
	csel	x21, x8, x9, gt
	mov	x8, #9223372036854775807        ; =0x7fffffffffffffff
	cmp	x21, x8
	b.hs	LBB113_7
; %bb.3:
	ldr	x0, [x19]
	add	x1, x21, #1
	bl	_rc_reallocate_data
	strb	wzr, [x0, x21]
	str	x0, [x19]
	str	x21, [x19, #16]
	ldr	x8, [x19, #8]
	b	LBB113_5
LBB113_4:
	ldr	x0, [x19]
LBB113_5:
	str	x20, [x0, x8]
	ldr	x8, [x19, #8]
	add	x8, x8, #8
	str	x8, [x19, #8]
	ldp	x29, x30, [sp, #32]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp, #16]             ; 16-byte Folded Reload
	ldp	x22, x21, [sp], #48             ; 16-byte Folded Reload
	ret
LBB113_6:
	bl	_minyar_bytes_add_int64.cold.2
LBB113_7:
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
	tbnz	x1, #63, LBB114_3
; %bb.1:
	sub	x9, x2, #8
	cmp	x9, x1
	b.lt	LBB114_3
; %bb.2:
	ldr	x9, [x0]
	str	x8, [x9, x1]
	ret
LBB114_3:
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
	tbnz	x1, #63, LBB115_3
; %bb.1:
	sub	x8, x2, #8
	cmp	x8, x1
	b.lt	LBB115_3
; %bb.2:
	ldr	x8, [x0]
	ldr	x0, [x8, x1]
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
	b.hs	LBB116_7
; %bb.1:
	mov	x20, x0
	ldr	x8, [x0, #8]
	mov	x9, #2305843009213693951        ; =0x1fffffffffffffff
	cmp	x8, x9
	b.ge	LBB116_8
; %bb.2:
	ldr	x9, [x20, #16]
	cmp	x8, x9
	b.ge	LBB116_4
; %bb.3:
	ldr	x0, [x20]
	b	LBB116_6
LBB116_4:
	add	x10, x8, #1
	lsl	x11, x9, #1
	mov	w12, #16                        ; =0x10
	cmp	x9, #16
	csel	x9, x12, x11, lt
	cmp	x9, x10
	csinc	x21, x9, x8, gt
	mov	x8, #9223372036854775807        ; =0x7fffffffffffffff
	cmp	x21, x8
	b.hs	LBB116_9
; %bb.5:
	ldr	x0, [x20]
	add	x1, x21, #1
	bl	_rc_reallocate_data
	strb	wzr, [x0, x21]
	str	x0, [x20]
	str	x21, [x20, #16]
	ldr	x8, [x20, #8]
LBB116_6:
	add	x9, x8, #1
	str	x9, [x20, #8]
	strb	w19, [x0, x8]
	ldp	x29, x30, [sp, #32]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp, #16]             ; 16-byte Folded Reload
	ldp	x22, x21, [sp], #48             ; 16-byte Folded Reload
	ret
LBB116_7:
Lloh213:
	adrp	x1, l_.str.26@PAGE
Lloh214:
	add	x1, x1, l_.str.26@PAGEOFF
	mov	x0, x19
	bl	_bytes_value_stop
LBB116_8:
	bl	_minyar_bytes_add.cold.2
LBB116_9:
	bl	_minyar_bytes_add.cold.1
	.loh AdrpAdd	Lloh213, Lloh214
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
	b.ge	LBB117_6
; %bb.1:
	fmov	d8, d0
	mov	x19, x0
	ldr	x10, [x0, #16]
	add	x9, x8, #4
	cmp	x9, x10
	b.le	LBB117_4
; %bb.2:
	lsl	x8, x10, #1
	mov	w11, #16                        ; =0x10
	cmp	x10, #16
	csel	x8, x11, x8, lt
	cmp	x8, x9
	csel	x20, x8, x9, gt
	mov	x8, #9223372036854775807        ; =0x7fffffffffffffff
	cmp	x20, x8
	b.hs	LBB117_7
; %bb.3:
	ldr	x0, [x19]
	add	x1, x20, #1
	bl	_rc_reallocate_data
	strb	wzr, [x0, x20]
	str	x0, [x19]
	str	x20, [x19, #16]
	ldr	x8, [x19, #8]
	b	LBB117_5
LBB117_4:
	ldr	x0, [x19]
LBB117_5:
	fcvt	s0, d8
	str	s0, [x0, x8]
	ldr	x8, [x19, #8]
	add	x8, x8, #4
	str	x8, [x19, #8]
	ldp	x29, x30, [sp, #32]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp, #16]             ; 16-byte Folded Reload
	ldp	d9, d8, [sp], #48               ; 16-byte Folded Reload
	ret
LBB117_6:
	bl	_minyar_bytes_add_float32.cold.2
LBB117_7:
	bl	_minyar_bytes_add_float32.cold.1
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_bytes_set_float32       ; -- Begin function minyar_bytes_set_float32
	.p2align	2
_minyar_bytes_set_float32:              ; @minyar_bytes_set_float32
	.cfi_startproc
; %bb.0:
	ldr	x2, [x0, #8]
	tbnz	x1, #63, LBB118_3
; %bb.1:
	sub	x8, x2, #4
	cmp	x8, x1
	b.lt	LBB118_3
; %bb.2:
	ldr	x8, [x0]
	fcvt	s0, d0
	str	s0, [x8, x1]
	ret
LBB118_3:
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
	tbnz	x1, #63, LBB119_3
; %bb.1:
	sub	x8, x2, #4
	cmp	x8, x1
	b.lt	LBB119_3
; %bb.2:
	ldr	x8, [x0]
	ldr	s0, [x8, x1]
	fcvt	d0, s0
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
	b.ge	LBB120_6
; %bb.1:
	fmov	d8, d0
	mov	x19, x0
	ldr	x10, [x0, #16]
	add	x9, x8, #8
	cmp	x9, x10
	b.le	LBB120_4
; %bb.2:
	lsl	x8, x10, #1
	mov	w11, #16                        ; =0x10
	cmp	x10, #16
	csel	x8, x11, x8, lt
	cmp	x8, x9
	csel	x20, x8, x9, gt
	mov	x8, #9223372036854775807        ; =0x7fffffffffffffff
	cmp	x20, x8
	b.hs	LBB120_7
; %bb.3:
	ldr	x0, [x19]
	add	x1, x20, #1
	bl	_rc_reallocate_data
	strb	wzr, [x0, x20]
	str	x0, [x19]
	str	x20, [x19, #16]
	ldr	x8, [x19, #8]
	b	LBB120_5
LBB120_4:
	ldr	x0, [x19]
LBB120_5:
	str	d8, [x0, x8]
	ldr	x8, [x19, #8]
	add	x8, x8, #8
	str	x8, [x19, #8]
	ldp	x29, x30, [sp, #32]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp, #16]             ; 16-byte Folded Reload
	ldp	d9, d8, [sp], #48               ; 16-byte Folded Reload
	ret
LBB120_6:
	bl	_minyar_bytes_add_float64.cold.2
LBB120_7:
	bl	_minyar_bytes_add_float64.cold.1
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_bytes_set_float64       ; -- Begin function minyar_bytes_set_float64
	.p2align	2
_minyar_bytes_set_float64:              ; @minyar_bytes_set_float64
	.cfi_startproc
; %bb.0:
	ldr	x2, [x0, #8]
	tbnz	x1, #63, LBB121_3
; %bb.1:
	sub	x8, x2, #8
	cmp	x8, x1
	b.lt	LBB121_3
; %bb.2:
	ldr	x8, [x0]
	str	d0, [x8, x1]
	ret
LBB121_3:
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
	tbnz	x1, #63, LBB122_3
; %bb.1:
	sub	x8, x2, #8
	cmp	x8, x1
	b.lt	LBB122_3
; %bb.2:
	ldr	x8, [x0]
	ldr	d0, [x8, x1]
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
Lloh215:
	adrp	x8, ___stack_chk_guard@GOTPAGE
Lloh216:
	ldr	x8, [x8, ___stack_chk_guard@GOTPAGEOFF]
Lloh217:
	ldr	x8, [x8]
	stur	x8, [x29, #-40]
	ldr	x8, [x0, #8]
	tbnz	x1, #63, LBB123_5
; %bb.1:
	subs	x21, x2, x19
	b.lt	LBB123_5
; %bb.2:
	cmp	x8, x2
	b.lt	LBB123_5
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
Lloh218:
	adrp	x9, ___stack_chk_guard@GOTPAGE
Lloh219:
	ldr	x9, [x9, ___stack_chk_guard@GOTPAGEOFF]
Lloh220:
	ldr	x9, [x9]
	cmp	x9, x8
	b.ne	LBB123_6
; %bb.4:
	mov	x0, x22
	ldp	x29, x30, [sp, #224]            ; 16-byte Folded Reload
	ldp	x20, x19, [sp, #208]            ; 16-byte Folded Reload
	ldp	x22, x21, [sp, #192]            ; 16-byte Folded Reload
	add	sp, sp, #240
	ret
LBB123_5:
	stp	x2, x8, [sp, #8]
	str	x19, [sp]
Lloh221:
	adrp	x2, l_.str.27@PAGE
Lloh222:
	add	x2, x2, l_.str.27@PAGEOFF
	add	x0, sp, #24
	mov	w1, #160                        ; =0xa0
	bl	_snprintf
	add	x0, sp, #24
	bl	_minyar_stop
LBB123_6:
	bl	___stack_chk_fail
	.loh AdrpLdrGotLdr	Lloh215, Lloh216, Lloh217
	.loh AdrpLdrGotLdr	Lloh218, Lloh219, Lloh220
	.loh AdrpAdd	Lloh221, Lloh222
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
	b.lt	LBB124_6
; %bb.1:
	mov	x21, x1
	mov	x19, x0
	ldr	x10, [x0, #16]
	add	x9, x8, x20
	cmp	x9, x10
	b.le	LBB124_4
; %bb.2:
	lsl	x8, x10, #1
	mov	w11, #16                        ; =0x10
	cmp	x10, #16
	csel	x8, x11, x8, lt
	cmp	x8, x9
	csel	x22, x8, x9, gt
	mov	x8, #9223372036854775807        ; =0x7fffffffffffffff
	cmp	x22, x8
	b.hs	LBB124_7
; %bb.3:
	ldr	x0, [x19]
	add	x1, x22, #1
	bl	_rc_reallocate_data
	strb	wzr, [x0, x22]
	str	x0, [x19]
	str	x22, [x19, #16]
	ldr	x8, [x19, #8]
	b	LBB124_5
LBB124_4:
	ldr	x0, [x19]
LBB124_5:
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
LBB124_6:
	bl	_minyar_bytes_append.cold.2
LBB124_7:
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
	ldp	x21, x19, [x0]
	mov	x0, x21
	mov	w1, #0                          ; =0x0
	mov	x2, x19
	bl	_memchr
	cbnz	x0, LBB125_5
; %bb.1:
	add	x0, x19, #1
	bl	_malloc
	cbz	x0, LBB125_6
; %bb.2:
	mov	x20, x0
	mov	x1, x21
	mov	x2, x19
	bl	_memcpy
	strb	wzr, [x20, x19]
Lloh223:
	adrp	x1, l_.str.9@PAGE
Lloh224:
	add	x1, x1, l_.str.9@PAGEOFF
	mov	x0, x20
	bl	_fopen
	cbz	x0, LBB125_7
; %bb.3:
	mov	x19, x0
	mov	x0, x20
	bl	_free
	mov	x0, x19
	bl	_text_file_length
	mov	x21, x0
	bl	_minyar_bytes_new
	mov	x20, x0
	ldr	x0, [x0]
	mov	w1, #1                          ; =0x1
	mov	x2, x21
	mov	x3, x19
	bl	_fread
	cmp	x0, x21
	b.ne	LBB125_8
; %bb.4:
	mov	x0, x19
	bl	_fclose
	mov	x0, x20
	ldp	x29, x30, [sp, #48]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp, #32]             ; 16-byte Folded Reload
	ldp	x22, x21, [sp, #16]             ; 16-byte Folded Reload
	add	sp, sp, #64
	ret
LBB125_5:
	bl	_minyar_read_bytes_file.cold.1
LBB125_6:
	bl	_out_of_memory
LBB125_7:
Lloh225:
	adrp	x8, ___stderrp@GOTPAGE
Lloh226:
	ldr	x8, [x8, ___stderrp@GOTPAGEOFF]
Lloh227:
	ldr	x0, [x8]
	str	x20, [sp]
Lloh228:
	adrp	x1, l_.str.10@PAGE
Lloh229:
	add	x1, x1, l_.str.10@PAGEOFF
	bl	_fprintf
	mov	w0, #1                          ; =0x1
	bl	_exit
LBB125_8:
	bl	_minyar_read_bytes_file.cold.2
	.loh AdrpAdd	Lloh223, Lloh224
	.loh AdrpAdd	Lloh228, Lloh229
	.loh AdrpLdrGotLdr	Lloh225, Lloh226, Lloh227
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_write_bytes_file        ; -- Begin function minyar_write_bytes_file
	.p2align	2
_minyar_write_bytes_file:               ; @minyar_write_bytes_file
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
	ldp	x21, x20, [x0]
	mov	x0, x21
	mov	w1, #0                          ; =0x0
	mov	x2, x20
	bl	_memchr
	cbnz	x0, LBB126_7
; %bb.1:
	add	x0, x20, #1
	bl	_malloc
	cbz	x0, LBB126_8
; %bb.2:
	mov	x22, x0
	mov	x1, x21
	mov	x2, x20
	bl	_memcpy
	strb	wzr, [x22, x20]
Lloh230:
	adrp	x1, l_.str.12@PAGE
Lloh231:
	add	x1, x1, l_.str.12@PAGEOFF
	mov	x0, x22
	bl	_fopen
	mov	x20, x0
	mov	x0, x22
	bl	_free
	cbz	x20, LBB126_9
; %bb.3:
	ldp	x0, x2, [x19]
	mov	w1, #1                          ; =0x1
	mov	x3, x20
	bl	_fwrite
	ldr	x8, [x19, #8]
	cmp	x0, x8
	b.ne	LBB126_6
; %bb.4:
	mov	x0, x20
	bl	_fclose
	cbnz	w0, LBB126_6
; %bb.5:
	ldp	x29, x30, [sp, #32]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp, #16]             ; 16-byte Folded Reload
	ldp	x22, x21, [sp], #48             ; 16-byte Folded Reload
	ret
LBB126_6:
	bl	_minyar_write_bytes_file.cold.2
LBB126_7:
	bl	_minyar_write_bytes_file.cold.1
LBB126_8:
	bl	_out_of_memory
LBB126_9:
	bl	_minyar_write_bytes_file.cold.3
	.loh AdrpAdd	Lloh230, Lloh231
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
	cbnz	x0, LBB127_5
; %bb.1:
	add	x0, x19, #1
	bl	_malloc
	cbz	x0, LBB127_6
; %bb.2:
	mov	x21, x0
	mov	x1, x20
	mov	x2, x19
	bl	_memcpy
	strb	wzr, [x21, x19]
Lloh232:
	adrp	x1, l_.str.9@PAGE
Lloh233:
	add	x1, x1, l_.str.9@PAGEOFF
	mov	x0, x21
	bl	_fopen
	mov	x19, x0
	mov	x0, x21
	bl	_free
	cbz	x19, LBB127_4
; %bb.3:
	mov	x0, x19
	bl	_fclose
LBB127_4:
	cmp	x19, #0
	cset	w0, ne
	ldp	x29, x30, [sp, #32]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp, #16]             ; 16-byte Folded Reload
	ldp	x22, x21, [sp], #48             ; 16-byte Folded Reload
	ret
LBB127_5:
	bl	_minyar_file_exists.cold.1
LBB127_6:
	bl	_out_of_memory
	.loh AdrpAdd	Lloh232, Lloh233
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
	tbnz	x1, #63, LBB128_7
; %bb.1:
	mov	x20, x1
	mov	x19, x0
	ldr	x22, [x0, #8]
	mov	x8, #2305843009213693951        ; =0x1fffffffffffffff
	sub	x8, x8, x22
	cmp	x8, x1
	b.lt	LBB128_8
; %bb.2:
	ldr	x9, [x19, #16]
	add	x8, x22, x20
	cmp	x8, x9
	b.le	LBB128_5
; %bb.3:
	lsl	x10, x9, #1
	mov	w11, #16                        ; =0x10
	cmp	x9, #16
	csel	x9, x11, x10, lt
	cmp	x9, x8
	csel	x22, x9, x8, gt
	mov	x8, #9223372036854775807        ; =0x7fffffffffffffff
	cmp	x22, x8
	b.hs	LBB128_9
; %bb.4:
	ldr	x0, [x19]
	add	x1, x22, #1
	bl	_rc_reallocate_data
	mov	x21, x0
	strb	wzr, [x0, x22]
	str	x0, [x19]
	str	x22, [x19, #16]
	ldr	x22, [x19, #8]
	b	LBB128_6
LBB128_5:
	ldr	x21, [x19]
LBB128_6:
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
LBB128_7:
	bl	_minyar_bytes_extend.cold.3
LBB128_8:
	bl	_minyar_bytes_extend.cold.2
LBB128_9:
	bl	_minyar_bytes_extend.cold.1
	.cfi_endproc
                                        ; -- End function
	.section	__TEXT,__literal16,16byte_literals
	.p2align	4, 0x0                          ; -- Begin function main
lCPI129_0:
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
	b.ne	LBB129_65
; %bb.1:
	mov	x20, x1
	ldr	x0, [x1, #8]
	mov	x1, #0                          ; =0x0
	mov	w2, #10                         ; =0xa
	bl	_strtoull
	mov	x26, x0
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
	str	x0, [sp, #104]                  ; 8-byte Folded Spill
	mov	w8, #8193                       ; =0x2001
	cmp	x26, x8
	b.hi	LBB129_66
; %bb.2:
	sub	x8, x22, #2048, lsl #12         ; =8388608
	sub	x8, x8, #1
	cmn	x8, #2048, lsl #12              ; =8388608
	ccmp	w24, #3, #2, hs
	b.hs	LBB129_66
; %bb.3:
	cmp	w24, #2
	b.ne	LBB129_5
; %bb.4:
Lloh234:
	adrp	x0, l_.str.35@PAGE
Lloh235:
	add	x0, x0, l_.str.35@PAGEOFF
	bl	_copy_c_text
	mov	x21, x0
	b	LBB129_6
LBB129_5:
	mov	x21, #0                         ; =0x0
LBB129_6:
	adrp	x19, _rc_pending_count@PAGE
	ldr	x8, [x19, _rc_pending_count@PAGEOFF]
	cbz	x8, LBB129_8
; %bb.7:
	mov	w0, #32                         ; =0x20
	bl	_minyar_rc_poll
LBB129_8:
	mov	w0, #32                         ; =0x20
	bl	_malloc
	cbz	x0, LBB129_73
; %bb.9:
	mov	x28, x0
	mov	w8, #10                         ; =0xa
	str	x8, [x0]
	mov	x23, x0
	str	xzr, [x23, #8]!
	stp	xzr, xzr, [x0, #16]
	cmp	w24, #2
	b.ne	LBB129_11
; %bb.10:
	mov	w8, #14                         ; =0xe
	str	x8, [x28]
LBB129_11:
	mov	x9, #31765                      ; =0x7c15
	movk	x9, #32586, lsl #16
	movk	x9, #31161, lsl #32
	movk	x9, #40503, lsl #48
	str	x22, [sp, #88]                  ; 8-byte Folded Spill
	cbz	x26, LBB129_16
; %bb.12:
	mov	x20, x25
	mov	x27, x26
	mov	x22, x26
LBB129_13:                              ; =>This Inner Loop Header: Depth=1
	cmp	w24, #2
	csel	x1, x21, x20, eq
	mov	x0, x23
	mov	x26, x9
	bl	_minyar_list_add
	mov	x9, x26
	add	x20, x20, x26
	subs	x22, x22, #1
	b.ne	LBB129_13
; %bb.14:
	ldr	x8, [x28]
	cmp	x8, #8
	ldr	x22, [sp, #88]                  ; 8-byte Folded Reload
	mov	x26, x27
	b.lo	LBB129_17
; %bb.15:
	cmn	x8, #8
	b.hs	LBB129_75
LBB129_16:
	add	x8, x8, #8
	str	x8, [x28]
LBB129_17:
	cmp	w24, #2
	mov	x8, #12816                      ; =0x3210
	movk	x8, #30292, lsl #16
	movk	x8, #47768, lsl #32
	movk	x8, #65244, lsl #48
	csel	x8, x21, x8, eq
	str	x8, [sp, #96]                   ; 8-byte Folded Spill
	ldr	x8, [x19, _rc_pending_count@PAGEOFF]
	cbz	x8, LBB129_19
LBB129_18:                              ; =>This Inner Loop Header: Depth=1
	mov	w0, #32                         ; =0x20
	bl	_minyar_rc_poll
	ldr	x8, [x19, _rc_pending_count@PAGEOFF]
	cbnz	x8, LBB129_18
LBB129_19:
	sub	x1, x29, #96
	mov	w0, #12                         ; =0xc
	bl	_clock_gettime
	cbnz	w0, LBB129_67
; %bb.20:
	stp	x28, x26, [sp, #48]             ; 16-byte Folded Spill
	ldp	x9, x8, [x29, #-96]
	stp	x9, x8, [sp, #32]               ; 16-byte Folded Spill
	mov	x27, #0                         ; =0x0
	cbz	x22, LBB129_35
; %bb.21:
	mov	x26, #0                         ; =0x0
	cmp	w24, #2
	cset	w28, eq
	ldr	x8, [sp, #56]                   ; 8-byte Folded Reload
	add	x20, x8, #1
Lloh236:
	adrp	x8, lCPI129_0@PAGE
Lloh237:
	ldr	q0, [x8, lCPI129_0@PAGEOFF]
	str	q0, [sp, #64]                   ; 16-byte Folded Spill
	b	LBB129_23
LBB129_22:                              ;   in Loop: Header=BB129_23 Depth=1
	ldr	x8, [sp, #104]                  ; 8-byte Folded Reload
	add	x8, x8, x26
	eor	x27, x8, x27
	add	x26, x26, #1
	ldr	x8, [sp, #88]                   ; 8-byte Folded Reload
	cmp	x26, x8
	b.eq	LBB129_35
LBB129_23:                              ; =>This Loop Header: Depth=1
                                        ;     Child Loop BB129_33 Depth 2
	cmp	w24, #1
	b.ne	LBB129_28
; %bb.24:                               ;   in Loop: Header=BB129_23 Depth=1
	ldr	x8, [x19, _rc_pending_count@PAGEOFF]
	cbz	x8, LBB129_26
; %bb.25:                               ;   in Loop: Header=BB129_23 Depth=1
	mov	w0, #32                         ; =0x20
	bl	_minyar_rc_poll
LBB129_26:                              ;   in Loop: Header=BB129_23 Depth=1
	mov	w0, #1186                       ; =0x4a2
	bl	_malloc
	cbz	x0, LBB129_73
; %bb.27:                               ;   in Loop: Header=BB129_23 Depth=1
	mov	x22, x0
	add	x0, x0, #16
	mov	w1, #1170                       ; =0x492
	bl	_bzero
	ldr	q0, [sp, #64]                   ; 16-byte Folded Reload
	str	q0, [x22], #8
	mov	x0, x22
	bl	_rc_drop
LBB129_28:                              ;   in Loop: Header=BB129_23 Depth=1
	mov	x0, x23
	ldr	x1, [sp, #96]                   ; 8-byte Folded Reload
	mov	x2, x28
	mov	x3, #0                          ; =0x0
	bl	_minyar_list_appended
	cmp	x0, x23
	b.eq	LBB129_61
; %bb.29:                               ;   in Loop: Header=BB129_23 Depth=1
	mov	x22, x0
	ldr	x8, [x0, #8]
	cmp	x8, x20
	b.ne	LBB129_61
; %bb.30:                               ;   in Loop: Header=BB129_23 Depth=1
	ldr	x0, [x22]
	mov	x1, x20
	mov	x2, x21
	bl	_research_checksum
	ldr	x8, [sp, #104]                  ; 8-byte Folded Reload
	cmp	x0, x8
	b.ne	LBB129_62
; %bb.31:                               ;   in Loop: Header=BB129_23 Depth=1
	mov	x0, x22
	bl	_rc_drop
	ldr	x8, [x19, _rc_pending_count@PAGEOFF]
	cbz	x8, LBB129_22
; %bb.32:                               ;   in Loop: Header=BB129_23 Depth=1
	mov	w8, #32                         ; =0x20
	sub	w0, w8, w0
LBB129_33:                              ;   Parent Loop BB129_23 Depth=1
                                        ; =>  This Inner Loop Header: Depth=2
	bl	_minyar_rc_poll
	ldr	x8, [x19, _rc_pending_count@PAGEOFF]
	cbz	x8, LBB129_22
; %bb.34:                               ;   in Loop: Header=BB129_33 Depth=2
	mov	w0, #32                         ; =0x20
	b	LBB129_33
LBB129_35:
	sub	x1, x29, #96
	mov	w0, #12                         ; =0xc
	bl	_clock_gettime
	cbnz	w0, LBB129_68
; %bb.36:
	cmp	w24, #2
	cset	w2, eq
	ldp	x22, x20, [x29, #-96]
	mov	x0, x23
	ldr	x1, [sp, #96]                   ; 8-byte Folded Reload
	mov	x3, #0                          ; =0x0
	bl	_minyar_list_appended
	ldr	x9, [x0]
	ldr	x8, [x23]
	ldr	x26, [sp, #56]                  ; 8-byte Folded Reload
	cbz	x26, LBB129_38
; %bb.37:
	cmp	x9, x8
	b.eq	LBB129_69
LBB129_38:
	ldr	x28, [sp, #48]                  ; 8-byte Folded Reload
	mov	x15, #31765                     ; =0x7c15
	movk	x15, #32586, lsl #16
	movk	x15, #31161, lsl #32
	movk	x15, #40503, lsl #48
	cbz	x26, LBB129_43
; %bb.39:
	mov	x10, x8
	mov	x11, x9
	mov	x12, x26
LBB129_40:                              ; =>This Inner Loop Header: Depth=1
	ldr	x13, [x10], #8
	cmp	w24, #2
	csel	x14, x21, x25, eq
	cmp	x13, x14
	b.ne	LBB129_63
; %bb.41:                               ;   in Loop: Header=BB129_40 Depth=1
	ldr	x14, [x11]
	cmp	x14, x13
	b.ne	LBB129_64
; %bb.42:                               ;   in Loop: Header=BB129_40 Depth=1
	add	x11, x11, #8
	add	x25, x25, x15
	subs	x12, x12, #1
	b.ne	LBB129_40
LBB129_43:
	ldr	x10, [x9, x26, lsl #3]
	ldr	x11, [sp, #96]                  ; 8-byte Folded Reload
	cmp	x10, x11
	b.ne	LBB129_70
; %bb.44:
	cbz	x26, LBB129_51
; %bb.45:
	ldr	x10, [x0, #8]
	cbz	x10, LBB129_74
; %bb.46:
	ldr	x24, [x8]
	ldur	x8, [x0, #-8]
	and	x8, x8, #0x7
	cmp	x8, #3
	b.ne	LBB129_49
; %bb.47:
	ldr	x8, [x9]
	str	xzr, [x9]
	mov	x25, x0
	mov	x0, x8
	bl	_rc_drop
	mov	x8, x0
	mov	x0, x25
	ldr	x9, [x19, _rc_pending_count@PAGEOFF]
	cbz	x9, LBB129_50
; %bb.48:
	mov	w9, #32                         ; =0x20
	sub	w0, w9, w8
	bl	_minyar_rc_poll
	mov	x0, x25
	b	LBB129_50
LBB129_49:
	str	xzr, [x9]
LBB129_50:
	ldr	x8, [x23]
	ldr	x8, [x8]
	cmp	x8, x24
	b.ne	LBB129_72
LBB129_51:
	bl	_rc_drop
	ldr	x8, [x19, _rc_pending_count@PAGEOFF]
	cbz	x8, LBB129_53
; %bb.52:
	mov	w8, #32                         ; =0x20
	sub	w0, w8, w0
	bl	_minyar_rc_poll
LBB129_53:
	mov	x0, x23
	bl	_rc_drop
	ldr	x8, [x19, _rc_pending_count@PAGEOFF]
	cbz	x8, LBB129_55
; %bb.54:
	mov	w8, #32                         ; =0x20
	sub	w0, w8, w0
	bl	_minyar_rc_poll
LBB129_55:
	ldr	x8, [x28, #16]
	cmp	x8, x26
	b.ne	LBB129_71
; %bb.56:
	mov	x0, x23
	bl	_rc_drop
	ldr	x8, [x19, _rc_pending_count@PAGEOFF]
	cbz	x8, LBB129_58
; %bb.57:
	mov	w8, #32                         ; =0x20
	sub	w0, w8, w0
	bl	_minyar_rc_poll
LBB129_58:
	cbz	x21, LBB129_78
; %bb.59:
	mov	x0, x21
	bl	_rc_drop
	ldr	x8, [x19, _rc_pending_count@PAGEOFF]
	cbz	x8, LBB129_79
; %bb.60:
	mov	w8, #32                         ; =0x20
	sub	w0, w8, w0
	b	LBB129_77
LBB129_61:
	bl	_main.cold.5
LBB129_62:
	bl	_main.cold.4
LBB129_63:
	bl	_main.cold.7
LBB129_64:
	bl	_main.cold.8
LBB129_65:
	bl	_main.cold.1
LBB129_66:
	bl	_main.cold.15
LBB129_67:
	bl	_main.cold.3
LBB129_68:
	bl	_main.cold.6
LBB129_69:
	bl	_main.cold.14
LBB129_70:
	bl	_main.cold.9
LBB129_71:
	bl	_main.cold.11
LBB129_72:
	bl	_main.cold.10
LBB129_73:
	bl	_out_of_memory
LBB129_74:
	bl	_main.cold.13
LBB129_75:
	bl	_main.cold.2
LBB129_76:
	mov	w0, #32                         ; =0x20
LBB129_77:
	bl	_minyar_rc_poll
LBB129_78:
	ldr	x8, [x19, _rc_pending_count@PAGEOFF]
	cbnz	x8, LBB129_76
LBB129_79:
Lloh238:
	adrp	x8, _rc_frames@PAGE
Lloh239:
	ldr	x8, [x8, _rc_frames@PAGEOFF]
Lloh240:
	adrp	x9, _rc_free_frames@PAGE
Lloh241:
	ldr	x9, [x9, _rc_free_frames@PAGEOFF]
	orr	x8, x8, x9
	cbnz	x8, LBB129_81
; %bb.80:
	ldp	x8, x10, [sp, #32]              ; 16-byte Folded Reload
	sub	x8, x22, x8
	mov	w9, #51712                      ; =0xca00
	movk	w9, #15258, lsl #16
	sub	x10, x20, x10
	madd	x8, x8, x9, x10
	ldr	x9, [sp, #88]                   ; 8-byte Folded Reload
	stp	x27, x9, [sp, #8]
	str	x8, [sp]
Lloh242:
	adrp	x0, l_.str.45@PAGE
Lloh243:
	add	x0, x0, l_.str.45@PAGEOFF
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
LBB129_81:
	bl	_main.cold.12
	.loh AdrpAdd	Lloh234, Lloh235
	.loh AdrpLdr	Lloh236, Lloh237
	.loh AdrpLdr	Lloh240, Lloh241
	.loh AdrpLdr	Lloh238, Lloh239
	.loh AdrpAdd	Lloh242, Lloh243
	.cfi_endproc
                                        ; -- End function
	.p2align	2                               ; -- Begin function rc_bounded_enqueue
_rc_bounded_enqueue:                    ; @rc_bounded_enqueue
	.cfi_startproc
; %bb.0:
	ldr	x8, [x0]
	and	x9, x8, #0x7
	cmp	x9, #1
	b.eq	LBB130_8
; %bb.1:
	cmp	x9, #3
	b.ne	LBB130_3
; %bb.2:
	str	xzr, [x0, #24]
	b	LBB130_8
LBB130_3:
	ldr	x9, [x0, #8]
	cbz	x9, LBB130_8
; %bb.4:
	mov	x8, #0                          ; =0x0
	add	x9, x0, x9, lsl #3
	add	x9, x9, #16
LBB130_5:                               ; =>This Inner Loop Header: Depth=1
	ldrb	w10, [x9, x8]
	and	w10, w10, #0x1
	strb	w10, [x9, x8]
	cmp	x8, #8
	b.hi	LBB130_7
; %bb.6:                                ;   in Loop: Header=BB130_5 Depth=1
	add	x8, x8, #1
	ldr	x10, [x0, #8]
	cmp	x8, x10
	b.lo	LBB130_5
LBB130_7:
	ldr	x8, [x0]
LBB130_8:
	adrp	x9, _rc_bounded_recent_head@PAGE
	ldr	x10, [x9, _rc_bounded_recent_head@PAGEOFF]
	orr	x8, x8, x10
	str	x8, [x0]
	str	x0, [x9, _rc_bounded_recent_head@PAGEOFF]
	adrp	x8, _rc_bounded_recent_tail@PAGE
	ldr	x9, [x8, _rc_bounded_recent_tail@PAGEOFF]
	cbnz	x9, LBB130_10
; %bb.9:
	str	x0, [x8, _rc_bounded_recent_tail@PAGEOFF]
LBB130_10:
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
	adrp	x20, _rc_bounded_active@PAGE
	ldr	x19, [x20, _rc_bounded_active@PAGEOFF]
	cbz	x19, LBB131_2
; %bb.1:
	ldr	x8, [x19]
	b	LBB131_10
LBB131_2:
	adrp	x8, _rc_bounded_head@PAGE
	ldr	x19, [x8, _rc_bounded_head@PAGEOFF]
	str	x19, [x20, _rc_bounded_active@PAGEOFF]
	ldr	x9, [x19]
	and	x10, x9, #0xfffffffffffffff8
	str	x10, [x8, _rc_bounded_head@PAGEOFF]
	and	x8, x9, #0x7
	str	x8, [x19]
	cmp	x8, #1
	b.eq	LBB131_8
; %bb.3:
	cmp	x8, #3
	b.ne	LBB131_5
; %bb.4:
	ldr	x9, [x19, #24]
	b	LBB131_9
LBB131_5:
	ldr	x12, [x19, #8]
	cbz	x12, LBB131_8
; %bb.6:
	mov	x10, #0                         ; =0x0
	mov	x9, #0                          ; =0x0
	add	x11, x19, x12, lsl #3
	add	x11, x11, #16
	sub	x12, x12, #1
	mov	w13, #9                         ; =0x9
	cmp	x12, #9
	csel	x12, x12, x13, lo
	lsl	x13, x12, #3
	sub	x12, x13, x12
	add	x12, x12, #7
LBB131_7:                               ; =>This Inner Loop Header: Depth=1
	ldrb	w13, [x11], #1
	lsr	x13, x13, #1
	lsl	x13, x13, x10
	orr	x9, x13, x9
	add	x10, x10, #7
	cmp	x12, x10
	b.ne	LBB131_7
	b	LBB131_9
LBB131_8:
	mov	x9, #0                          ; =0x0
LBB131_9:
	adrp	x10, _rc_bounded_cursor@PAGE
	str	x9, [x10, _rc_bounded_cursor@PAGEOFF]
LBB131_10:
	and	w8, w8, #0x7
	cmp	w8, #2
	b.le	LBB131_16
; %bb.11:
	cmp	w8, #6
	b.eq	LBB131_18
; %bb.12:
	cmp	w8, #4
	b.eq	LBB131_19
; %bb.13:
	cmp	w8, #3
	b.ne	LBB131_27
; %bb.14:
	adrp	x9, _rc_bounded_cursor@PAGE
	ldr	x8, [x9, _rc_bounded_cursor@PAGEOFF]
	ldr	x10, [x19, #16]
	cmp	x8, x10
	b.hs	LBB131_18
; %bb.15:
	ldr	x10, [x19, #8]
	add	x11, x8, #1
	str	x11, [x9, _rc_bounded_cursor@PAGEOFF]
	b	LBB131_21
LBB131_16:
	cmp	w8, #1
	b.eq	LBB131_22
; %bb.17:
	cmp	w8, #2
	b.ne	LBB131_27
LBB131_18:
	ldr	x8, [x19, #8]
	cbnz	x8, LBB131_26
	b	LBB131_27
LBB131_19:
	adrp	x9, _rc_bounded_cursor@PAGE
	ldr	x8, [x9, _rc_bounded_cursor@PAGEOFF]
	ldr	x11, [x19, #8]
	cmp	x8, x11
	b.hs	LBB131_27
; %bb.20:
	add	x10, x19, #16
	add	x11, x10, x11, lsl #3
	add	x12, x8, #1
	str	x12, [x9, _rc_bounded_cursor@PAGEOFF]
	ldrb	w9, [x11, x8]
	tbz	w9, #0, LBB131_28
LBB131_21:
	ldr	x0, [x10, x8, lsl #3]
	ldp	x29, x30, [sp, #16]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp], #32             ; 16-byte Folded Reload
	b	_rc_drop
LBB131_22:
	ldr	x8, [x19, #40]
	cbnz	x8, LBB131_25
; %bb.23:
	ldr	x8, [x19, #8]
	cbz	x8, LBB131_25
; %bb.24:
	sub	x0, x8, #8
	bl	_free
LBB131_25:
	ldr	x8, [x19, #32]
	cbz	x8, LBB131_27
LBB131_26:
	sub	x0, x8, #8
	bl	_free
LBB131_27:
	mov	x0, x19
	bl	_free
	adrp	x8, _rc_pending_count@PAGE
	ldr	x9, [x8, _rc_pending_count@PAGEOFF]
	sub	x9, x9, #1
	str	x9, [x8, _rc_pending_count@PAGEOFF]
	str	xzr, [x20, _rc_bounded_active@PAGEOFF]
LBB131_28:
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
Lloh244:
	adrp	x8, _rc_pending_count@PAGE
Lloh245:
	ldr	x8, [x8, _rc_pending_count@PAGEOFF]
	cbz	x8, LBB132_2
; %bb.1:
	mov	w0, #32                         ; =0x20
	bl	_minyar_rc_poll
LBB132_2:
	cmn	x20, #8
	b.hs	LBB132_5
; %bb.3:
	add	x0, x20, #8
	bl	_malloc
	cbz	x0, LBB132_5
; %bb.4:
	orr	w8, w19, #0x8
	str	x8, [x0], #8
	ldp	x29, x30, [sp, #16]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp], #32             ; 16-byte Folded Reload
	ret
LBB132_5:
	bl	_out_of_memory
	.loh AdrpLdr	Lloh244, Lloh245
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
Lloh246:
	adrp	x8, _rc_pending_count@PAGE
Lloh247:
	ldr	x8, [x8, _rc_pending_count@PAGEOFF]
	cbz	x8, LBB133_2
; %bb.1:
	mov	w0, #32                         ; =0x20
	bl	_minyar_rc_poll
LBB133_2:
	cmn	x19, #8
	b.hs	LBB133_5
; %bb.3:
	add	x0, x19, #8
	bl	_malloc
	cbz	x0, LBB133_5
; %bb.4:
	str	x19, [x0], #8
	ldp	x29, x30, [sp, #16]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp], #32             ; 16-byte Folded Reload
	ret
LBB133_5:
	bl	_out_of_memory
	.loh AdrpLdr	Lloh246, Lloh247
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
LBB134_1:                               ; =>This Inner Loop Header: Depth=1
	mov	x20, x9
	subs	x8, x8, #8
	b.lt	LBB134_3
; %bb.2:                                ;   in Loop: Header=BB134_1 Depth=1
	ldr	x9, [x19]
	ldr	x10, [x9, x20]
	add	x9, x20, #8
	and	x10, x10, #0x8080808080808080
	cbz	x10, LBB134_1
LBB134_3:
	cmp	x20, x21
	b.ge	LBB134_8
; %bb.4:
	ldr	x8, [x19]
LBB134_5:                               ; =>This Inner Loop Header: Depth=1
	ldrsb	w9, [x8, x20]
	tbnz	w9, #31, LBB134_8
; %bb.6:                                ;   in Loop: Header=BB134_5 Depth=1
	add	x20, x20, #1
	cmp	x21, x20
	b.ne	LBB134_5
; %bb.7:
	mov	x22, x21
	b	LBB134_13
LBB134_8:
	cmp	x20, x21
	b.ge	LBB134_11
; %bb.9:
	mov	x22, x20
LBB134_10:                              ; =>This Inner Loop Header: Depth=1
	ldr	x8, [x19]
	sub	x1, x21, x20
	add	x0, x8, x20
	bl	_OUTLINED_FUNCTION_1
	ldr	x8, [sp, #8]
	add	x22, x22, #1
	ldr	x21, [x19, #8]
	add	x20, x8, x20
	cmp	x20, x21
	b.lt	LBB134_10
	b	LBB134_12
LBB134_11:
	mov	x22, x20
LBB134_12:
	cmp	x22, x21
	b.ne	LBB134_14
LBB134_13:
	str	x22, [x19, #16]
	b	LBB134_34
LBB134_14:
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
	b.lt	LBB134_23
; %bb.15:
	mov	x23, #0                         ; =0x0
	mov	x22, #0                         ; =0x0
	mov	w24, #-1                        ; =0xffffffff
LBB134_16:                              ; =>This Inner Loop Header: Depth=1
	tst	x22, #0x3f
	b.ne	LBB134_20
; %bb.17:                               ;   in Loop: Header=BB134_16 Depth=1
	lsr	x9, x22, #6
	cmp	x21, x24
	b.gt	LBB134_19
; %bb.18:                               ;   in Loop: Header=BB134_16 Depth=1
	str	w23, [x20, x9, lsl #2]
	b	LBB134_20
LBB134_19:                              ;   in Loop: Header=BB134_16 Depth=1
	str	x23, [x20, x9, lsl #3]
LBB134_20:                              ;   in Loop: Header=BB134_16 Depth=1
	add	x22, x22, #1
	ldr	x9, [x19]
	sub	x1, x8, x23
	add	x0, x9, x23
	bl	_OUTLINED_FUNCTION_1
	ldr	x9, [sp, #8]
	ldr	x8, [x19, #8]
	add	x23, x9, x23
	cmp	x23, x8
	b.lt	LBB134_16
; %bb.21:
	lsr	x9, x22, #6
	tst	x22, #0x3f
	b.eq	LBB134_25
; %bb.22:
	stp	x22, x20, [x19, #16]
	add	x10, x9, #1
	mov	x11, #4294967296                ; =0x100000000
	b	LBB134_31
LBB134_23:
	mov	w8, #-1                         ; =0xffffffff
	cmp	x21, x8
	b.gt	LBB134_27
; %bb.24:
	str	wzr, [x20]
	b	LBB134_28
LBB134_25:
	mov	x11, #4294967296                ; =0x100000000
	cmp	x21, x11
	b.ge	LBB134_29
; %bb.26:
	str	w23, [x20, x9, lsl #2]
	b	LBB134_30
LBB134_27:
	str	xzr, [x20]
LBB134_28:
	mov	x22, #0                         ; =0x0
	stp	xzr, x20, [x19, #16]
	mov	w10, #1                         ; =0x1
	b	LBB134_32
LBB134_29:
	str	x23, [x20, x9, lsl #3]
LBB134_30:
	add	x10, x9, #1
	stp	x22, x20, [x19, #16]
LBB134_31:
	cmp	x8, x11
	b.ge	LBB134_33
LBB134_32:
	str	wzr, [x20, x10, lsl #2]
	mov	w8, #64                         ; =0x40
	sdiv	x8, x22, x8
	add	x8, x20, x8, lsl #2
	str	wzr, [x8, #8]
	b	LBB134_34
LBB134_33:
	str	xzr, [x20, x10, lsl #3]
	add	x8, x20, x9, lsl #3
	str	xzr, [x8, #16]
LBB134_34:
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
	b.le	LBB135_28
; %bb.1:
	mov	x8, x0
	ldrsb	w9, [x0]
	and	w0, w9, #0xff
	tbnz	w9, #31, LBB135_3
; %bb.2:
	mov	w8, #1                          ; =0x1
	str	x8, [x2]
	ldp	x29, x30, [sp], #16             ; 16-byte Folded Reload
	ret
LBB135_3:
	cmp	x1, #1
	b.eq	LBB135_7
; %bb.4:
	sub	w9, w0, #194
	cmp	w9, #29
	b.hi	LBB135_7
; %bb.5:
	ldrb	w9, [x8, #1]
	and	w9, w9, #0xc0
	cmp	w9, #128
	b.ne	LBB135_7
; %bb.6:
	mov	w9, #2                          ; =0x2
	str	x9, [x2]
	ldrb	w8, [x8, #1]
	and	w8, w8, #0x3f
	bfi	w8, w0, #6, #5
	mov	x0, x8
	ldp	x29, x30, [sp], #16             ; 16-byte Folded Reload
	ret
LBB135_7:
	cmp	x1, #3
	b.lo	LBB135_16
; %bb.8:
	and	w9, w0, #0xf0
	cmp	w9, #224
	b.ne	LBB135_16
; %bb.9:
	ldrb	w9, [x8, #1]
	and	w10, w9, #0xc0
	cmp	w10, #128
	b.ne	LBB135_16
; %bb.10:
	ldrb	w10, [x8, #2]
	and	w10, w10, #0xc0
	cmp	w10, #128
	b.ne	LBB135_16
; %bb.11:
	cmp	w0, #224
	b.ne	LBB135_13
; %bb.12:
	cmp	w9, #160
	b.lo	LBB135_27
LBB135_13:
	cmp	w0, #237
	b.ne	LBB135_15
; %bb.14:
	cmp	w9, #159
	b.hi	LBB135_27
LBB135_15:
	mov	w9, #3                          ; =0x3
	str	x9, [x2]
	ubfiz	w0, w0, #12, #4
	ldrb	w9, [x8, #1]
	bfi	w0, w9, #6, #6
	ldrb	w8, [x8, #2]
	b	LBB135_26
LBB135_16:
	cmp	x1, #4
	b.lo	LBB135_27
; %bb.17:
	sub	w9, w0, #240
	cmp	w9, #4
	b.hi	LBB135_27
; %bb.18:
	ldrb	w9, [x8, #1]
	and	w10, w9, #0xc0
	cmp	w10, #128
	b.ne	LBB135_27
; %bb.19:
	ldrb	w10, [x8, #2]
	and	w10, w10, #0xc0
	cmp	w10, #128
	b.ne	LBB135_27
; %bb.20:
	ldrb	w10, [x8, #3]
	and	w10, w10, #0xc0
	cmp	w10, #128
	b.ne	LBB135_27
; %bb.21:
	cmp	w0, #240
	b.ne	LBB135_23
; %bb.22:
	cmp	w9, #144
	b.lo	LBB135_27
LBB135_23:
	cmp	w0, #244
	b.ne	LBB135_25
; %bb.24:
	cmp	w9, #143
	b.hi	LBB135_27
LBB135_25:
	mov	w9, #4                          ; =0x4
	str	x9, [x2]
	ubfiz	w0, w0, #18, #3
	ldrb	w9, [x8, #1]
	bfi	w0, w9, #12, #6
	ldrb	w9, [x8, #2]
	bfi	w0, w9, #6, #6
	ldrb	w8, [x8, #3]
LBB135_26:
	bfxil	w0, w8, #0, #6
	ldp	x29, x30, [sp], #16             ; 16-byte Folded Reload
	ret
LBB135_27:
	bl	_invalid_utf8
LBB135_28:
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
Lloh248:
	adrp	x0, l_.str.53@PAGE
Lloh249:
	add	x0, x0, l_.str.53@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh248, Lloh249
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
Lloh250:
	adrp	x0, l_.str.54@PAGE
Lloh251:
	add	x0, x0, l_.str.54@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh250, Lloh251
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
Lloh252:
	adrp	x0, l_.str.55@PAGE
Lloh253:
	add	x0, x0, l_.str.55@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh252, Lloh253
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
Lloh254:
	adrp	x8, ___stack_chk_guard@GOTPAGE
Lloh255:
	ldr	x8, [x8, ___stack_chk_guard@GOTPAGEOFF]
Lloh256:
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
	b.ls	LBB139_10
; %bb.1:
	mov	x10, x21
	mov	x9, x21
	b	LBB139_4
LBB139_2:                               ;   in Loop: Header=BB139_4 Depth=1
	strb	w10, [x9]
LBB139_3:                               ;   in Loop: Header=BB139_4 Depth=1
	mov	x10, x9
	cmp	x9, x23
	b.ls	LBB139_10
LBB139_4:                               ; =>This Inner Loop Header: Depth=1
	ldrsb	w11, [x9, #-1]!
	cmp	w11, #46
	b.eq	LBB139_3
; %bb.5:                                ;   in Loop: Header=BB139_4 Depth=1
	cmp	w20, #1
	b.lt	LBB139_8
; %bb.6:                                ;   in Loop: Header=BB139_4 Depth=1
	cmp	w11, #57
	b.lt	LBB139_15
; %bb.7:                                ;   in Loop: Header=BB139_4 Depth=1
	mov	w10, #48                        ; =0x30
	b	LBB139_2
LBB139_8:                               ;   in Loop: Header=BB139_4 Depth=1
	cmp	w11, #48
	b.gt	LBB139_16
; %bb.9:                                ;   in Loop: Header=BB139_4 Depth=1
	mov	w10, #57                        ; =0x39
	b	LBB139_2
LBB139_10:
	mov	w9, #49                         ; =0x31
	strb	w9, [x23]
	add	w8, w8, #1
LBB139_11:
	add	x9, sp, #16
	sub	x9, x9, x21
	str	x8, [sp]
Lloh257:
	adrp	x2, l_.str.67@PAGE
Lloh258:
	add	x2, x2, l_.str.67@PAGEOFF
	add	x1, x9, #40
	mov	x0, x21
	bl	_snprintf
	add	x0, sp, #16
	mov	x1, #0                          ; =0x0
	bl	_strtod
	fmov	d9, d0
	fcmp	d0, d8
	b.ne	LBB139_13
; %bb.12:
	add	x0, sp, #16
	bl	_strlen
	add	x1, sp, #16
	add	x2, x0, #1
	mov	x0, x19
	bl	_memcpy
LBB139_13:
	fcmp	d9, d8
	cset	w0, eq
	ldr	x8, [sp, #56]
Lloh259:
	adrp	x9, ___stack_chk_guard@GOTPAGE
Lloh260:
	ldr	x9, [x9, ___stack_chk_guard@GOTPAGEOFF]
Lloh261:
	ldr	x9, [x9]
	cmp	x9, x8
	b.ne	LBB139_23
; %bb.14:
	ldp	x29, x30, [sp, #128]            ; 16-byte Folded Reload
	ldp	x20, x19, [sp, #112]            ; 16-byte Folded Reload
	ldp	x22, x21, [sp, #96]             ; 16-byte Folded Reload
	ldp	x24, x23, [sp, #80]             ; 16-byte Folded Reload
	ldp	d9, d8, [sp, #64]               ; 16-byte Folded Reload
	add	sp, sp, #144
	ret
LBB139_15:
	mov	w9, #1                          ; =0x1
	b	LBB139_17
LBB139_16:
	mov	w9, #255                        ; =0xff
LBB139_17:
	add	w9, w11, w9
	sturb	w9, [x10, #-1]
	ldrb	w9, [x23]
	cmp	w9, #48
	b.ne	LBB139_11
; %bb.18:
	add	x9, sp, #16
	add	x9, x22, x9
	add	x9, x9, #1
	mov	w11, #48                        ; =0x30
	mov	w10, #57                        ; =0x39
	cmp	w11, #46
	b.eq	LBB139_20
LBB139_19:
	sturb	w10, [x9, #-1]
LBB139_20:                              ; =>This Inner Loop Header: Depth=1
	cmp	x9, x21
	b.hs	LBB139_22
; %bb.21:                               ;   in Loop: Header=BB139_20 Depth=1
	ldrb	w11, [x9], #1
	cmp	w11, #46
	b.ne	LBB139_19
	b	LBB139_20
LBB139_22:
	sub	w8, w8, #1
	b	LBB139_11
LBB139_23:
	bl	___stack_chk_fail
	.loh AdrpLdrGotLdr	Lloh254, Lloh255, Lloh256
	.loh AdrpAdd	Lloh257, Lloh258
	.loh AdrpLdrGotLdr	Lloh259, Lloh260, Lloh261
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
Lloh262:
	adrp	x0, l_.str@PAGE
Lloh263:
	add	x0, x0, l_.str@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh262, Lloh263
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
Lloh264:
	adrp	x0, l_.str.1@PAGE
Lloh265:
	add	x0, x0, l_.str.1@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh264, Lloh265
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
Lloh266:
	adrp	x0, l_.str.2@PAGE
Lloh267:
	add	x0, x0, l_.str.2@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh266, Lloh267
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
Lloh268:
	adrp	x0, l_.str.2@PAGE
Lloh269:
	add	x0, x0, l_.str.2@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh268, Lloh269
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
Lloh270:
	adrp	x0, l_.str.2@PAGE
Lloh271:
	add	x0, x0, l_.str.2@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh270, Lloh271
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
Lloh272:
	adrp	x0, l_.str.2@PAGE
Lloh273:
	add	x0, x0, l_.str.2@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh272, Lloh273
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
Lloh274:
	adrp	x0, l_.str.2@PAGE
Lloh275:
	add	x0, x0, l_.str.2@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh274, Lloh275
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
Lloh276:
	adrp	x0, l_.str.3@PAGE
Lloh277:
	add	x0, x0, l_.str.3@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh276, Lloh277
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
Lloh278:
	adrp	x0, l_.str.49@PAGE
Lloh279:
	add	x0, x0, l_.str.49@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh278, Lloh279
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
Lloh280:
	adrp	x0, l_.str.49@PAGE
Lloh281:
	add	x0, x0, l_.str.49@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh280, Lloh281
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
Lloh282:
	adrp	x0, l_.str.2@PAGE
Lloh283:
	add	x0, x0, l_.str.2@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh282, Lloh283
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
Lloh284:
	adrp	x0, l_.str.2@PAGE
Lloh285:
	add	x0, x0, l_.str.2@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh284, Lloh285
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
Lloh286:
	adrp	x0, l_.str.57@PAGE
Lloh287:
	add	x0, x0, l_.str.57@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh286, Lloh287
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
Lloh288:
	adrp	x0, l_.str.2@PAGE
Lloh289:
	add	x0, x0, l_.str.2@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh288, Lloh289
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
Lloh290:
	adrp	x0, l_.str.2@PAGE
Lloh291:
	add	x0, x0, l_.str.2@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh290, Lloh291
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
Lloh292:
	adrp	x0, l_.str.8@PAGE
Lloh293:
	add	x0, x0, l_.str.8@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh292, Lloh293
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
Lloh294:
	adrp	x0, l_.str.58@PAGE
Lloh295:
	add	x0, x0, l_.str.58@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh294, Lloh295
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
Lloh296:
	adrp	x0, l_.str.11@PAGE
Lloh297:
	add	x0, x0, l_.str.11@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh296, Lloh297
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
Lloh298:
	adrp	x0, l_.str.11@PAGE
Lloh299:
	add	x0, x0, l_.str.11@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh298, Lloh299
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
Lloh300:
	adrp	x0, l_.str.11@PAGE
Lloh301:
	add	x0, x0, l_.str.11@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh300, Lloh301
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
Lloh302:
	adrp	x0, l_.str.58@PAGE
Lloh303:
	add	x0, x0, l_.str.58@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh302, Lloh303
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
Lloh304:
	adrp	x0, l_.str.14@PAGE
Lloh305:
	add	x0, x0, l_.str.14@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh304, Lloh305
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
Lloh306:
	adrp	x0, l_.str.13@PAGE
Lloh307:
	add	x0, x0, l_.str.13@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh306, Lloh307
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
Lloh308:
	adrp	x8, l_.str.18@PAGE
Lloh309:
	add	x8, x8, l_.str.18@PAGEOFF
Lloh310:
	adrp	x9, l_.str.19@PAGE
Lloh311:
	add	x9, x9, l_.str.19@PAGEOFF
	fcmp	d0, d0
	csel	x0, x9, x8, vc
	bl	_minyar_stop
	.loh AdrpAdd	Lloh310, Lloh311
	.loh AdrpAdd	Lloh308, Lloh309
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
Lloh312:
	adrp	x0, l_.str.20@PAGE
Lloh313:
	add	x0, x0, l_.str.20@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh312, Lloh313
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
Lloh314:
	adrp	x0, l_.str.21@PAGE
Lloh315:
	add	x0, x0, l_.str.21@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh314, Lloh315
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
Lloh316:
	adrp	x0, l_.str.22@PAGE
Lloh317:
	add	x0, x0, l_.str.22@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh316, Lloh317
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
Lloh318:
	adrp	x0, l_.str.22@PAGE
Lloh319:
	add	x0, x0, l_.str.22@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh318, Lloh319
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
Lloh320:
	adrp	x0, l_.str.23@PAGE
Lloh321:
	add	x0, x0, l_.str.23@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh320, Lloh321
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
Lloh322:
	adrp	x0, l_.str.25@PAGE
Lloh323:
	add	x0, x0, l_.str.25@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh322, Lloh323
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
Lloh324:
	adrp	x0, l_.str.24@PAGE
Lloh325:
	add	x0, x0, l_.str.24@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh324, Lloh325
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
Lloh326:
	adrp	x0, l_.str.25@PAGE
Lloh327:
	add	x0, x0, l_.str.25@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh326, Lloh327
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
Lloh328:
	adrp	x0, l_.str.25@PAGE
Lloh329:
	add	x0, x0, l_.str.25@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh328, Lloh329
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
Lloh330:
	adrp	x0, l_.str.24@PAGE
Lloh331:
	add	x0, x0, l_.str.24@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh330, Lloh331
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
Lloh332:
	adrp	x0, l_.str.25@PAGE
Lloh333:
	add	x0, x0, l_.str.25@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh332, Lloh333
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
Lloh334:
	adrp	x0, l_.str.25@PAGE
Lloh335:
	add	x0, x0, l_.str.25@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh334, Lloh335
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
Lloh336:
	adrp	x0, l_.str.25@PAGE
Lloh337:
	add	x0, x0, l_.str.25@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh336, Lloh337
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
Lloh338:
	adrp	x0, l_.str.25@PAGE
Lloh339:
	add	x0, x0, l_.str.25@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh338, Lloh339
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
Lloh340:
	adrp	x0, l_.str.25@PAGE
Lloh341:
	add	x0, x0, l_.str.25@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh340, Lloh341
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
Lloh342:
	adrp	x0, l_.str.25@PAGE
Lloh343:
	add	x0, x0, l_.str.25@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh342, Lloh343
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
Lloh344:
	adrp	x0, l_.str.25@PAGE
Lloh345:
	add	x0, x0, l_.str.25@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh344, Lloh345
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
Lloh346:
	adrp	x0, l_.str.25@PAGE
Lloh347:
	add	x0, x0, l_.str.25@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh346, Lloh347
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
Lloh348:
	adrp	x0, l_.str.25@PAGE
Lloh349:
	add	x0, x0, l_.str.25@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh348, Lloh349
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
Lloh350:
	adrp	x0, l_.str.25@PAGE
Lloh351:
	add	x0, x0, l_.str.25@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh350, Lloh351
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
Lloh352:
	adrp	x0, l_.str.25@PAGE
Lloh353:
	add	x0, x0, l_.str.25@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh352, Lloh353
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
Lloh354:
	adrp	x0, l_.str.25@PAGE
Lloh355:
	add	x0, x0, l_.str.25@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh354, Lloh355
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
Lloh356:
	adrp	x0, l_.str.25@PAGE
Lloh357:
	add	x0, x0, l_.str.25@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh356, Lloh357
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
Lloh358:
	adrp	x0, l_.str.25@PAGE
Lloh359:
	add	x0, x0, l_.str.25@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh358, Lloh359
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
Lloh360:
	adrp	x0, l_.str.25@PAGE
Lloh361:
	add	x0, x0, l_.str.25@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh360, Lloh361
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
Lloh362:
	adrp	x0, l_.str.25@PAGE
Lloh363:
	add	x0, x0, l_.str.25@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh362, Lloh363
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
Lloh364:
	adrp	x0, l_.str.25@PAGE
Lloh365:
	add	x0, x0, l_.str.25@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh364, Lloh365
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
Lloh366:
	adrp	x0, l_.str.25@PAGE
Lloh367:
	add	x0, x0, l_.str.25@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh366, Lloh367
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
Lloh368:
	adrp	x0, l_.str.58@PAGE
Lloh369:
	add	x0, x0, l_.str.58@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh368, Lloh369
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
Lloh370:
	adrp	x0, l_.str.28@PAGE
Lloh371:
	add	x0, x0, l_.str.28@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh370, Lloh371
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
Lloh372:
	adrp	x0, l_.str.58@PAGE
Lloh373:
	add	x0, x0, l_.str.58@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh372, Lloh373
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
Lloh374:
	adrp	x0, l_.str.30@PAGE
Lloh375:
	add	x0, x0, l_.str.30@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh374, Lloh375
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
Lloh376:
	adrp	x0, l_.str.29@PAGE
Lloh377:
	add	x0, x0, l_.str.29@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh376, Lloh377
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
Lloh378:
	adrp	x0, l_.str.58@PAGE
Lloh379:
	add	x0, x0, l_.str.58@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh378, Lloh379
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
Lloh380:
	adrp	x0, l_.str.25@PAGE
Lloh381:
	add	x0, x0, l_.str.25@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh380, Lloh381
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
Lloh382:
	adrp	x0, l_.str.25@PAGE
Lloh383:
	add	x0, x0, l_.str.25@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh382, Lloh383
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
Lloh384:
	adrp	x0, l_.str.31@PAGE
Lloh385:
	add	x0, x0, l_.str.31@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh384, Lloh385
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
Lloh386:
	adrp	x0, l___func__.main@PAGE
Lloh387:
	add	x0, x0, l___func__.main@PAGEOFF
Lloh388:
	adrp	x1, l_.str.32@PAGE
Lloh389:
	add	x1, x1, l_.str.32@PAGEOFF
Lloh390:
	adrp	x3, l_.str.33@PAGE
Lloh391:
	add	x3, x3, l_.str.33@PAGEOFF
	mov	w2, #31                         ; =0x1f
	bl	___assert_rtn
	.loh AdrpAdd	Lloh390, Lloh391
	.loh AdrpAdd	Lloh388, Lloh389
	.loh AdrpAdd	Lloh386, Lloh387
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
Lloh392:
	adrp	x0, l_.str.2@PAGE
Lloh393:
	add	x0, x0, l_.str.2@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh392, Lloh393
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
Lloh394:
	adrp	x0, l___func__.cpu_nanoseconds@PAGE
Lloh395:
	add	x0, x0, l___func__.cpu_nanoseconds@PAGEOFF
Lloh396:
	adrp	x1, l_.str.32@PAGE
Lloh397:
	add	x1, x1, l_.str.32@PAGEOFF
Lloh398:
	adrp	x3, l_.str.76@PAGE
Lloh399:
	add	x3, x3, l_.str.76@PAGEOFF
	mov	w2, #26                         ; =0x1a
	bl	___assert_rtn
	.loh AdrpAdd	Lloh398, Lloh399
	.loh AdrpAdd	Lloh396, Lloh397
	.loh AdrpAdd	Lloh394, Lloh395
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
Lloh400:
	adrp	x0, l___func__.main@PAGE
Lloh401:
	add	x0, x0, l___func__.main@PAGEOFF
Lloh402:
	adrp	x1, l_.str.32@PAGE
Lloh403:
	add	x1, x1, l_.str.32@PAGEOFF
Lloh404:
	adrp	x3, l_.str.37@PAGE
Lloh405:
	add	x3, x3, l_.str.37@PAGEOFF
	mov	w2, #73                         ; =0x49
	bl	___assert_rtn
	.loh AdrpAdd	Lloh404, Lloh405
	.loh AdrpAdd	Lloh402, Lloh403
	.loh AdrpAdd	Lloh400, Lloh401
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
Lloh406:
	adrp	x0, l___func__.main@PAGE
Lloh407:
	add	x0, x0, l___func__.main@PAGEOFF
Lloh408:
	adrp	x1, l_.str.32@PAGE
Lloh409:
	add	x1, x1, l_.str.32@PAGEOFF
Lloh410:
	adrp	x3, l_.str.36@PAGE
Lloh411:
	add	x3, x3, l_.str.36@PAGEOFF
	mov	w2, #71                         ; =0x47
	bl	___assert_rtn
	.loh AdrpAdd	Lloh410, Lloh411
	.loh AdrpAdd	Lloh408, Lloh409
	.loh AdrpAdd	Lloh406, Lloh407
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
Lloh412:
	adrp	x0, l___func__.cpu_nanoseconds@PAGE
Lloh413:
	add	x0, x0, l___func__.cpu_nanoseconds@PAGEOFF
Lloh414:
	adrp	x1, l_.str.32@PAGE
Lloh415:
	add	x1, x1, l_.str.32@PAGEOFF
Lloh416:
	adrp	x3, l_.str.76@PAGE
Lloh417:
	add	x3, x3, l_.str.76@PAGEOFF
	mov	w2, #26                         ; =0x1a
	bl	___assert_rtn
	.loh AdrpAdd	Lloh416, Lloh417
	.loh AdrpAdd	Lloh414, Lloh415
	.loh AdrpAdd	Lloh412, Lloh413
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
Lloh418:
	adrp	x0, l___func__.main@PAGE
Lloh419:
	add	x0, x0, l___func__.main@PAGEOFF
Lloh420:
	adrp	x1, l_.str.32@PAGE
Lloh421:
	add	x1, x1, l_.str.32@PAGEOFF
Lloh422:
	adrp	x3, l_.str.39@PAGE
Lloh423:
	add	x3, x3, l_.str.39@PAGEOFF
	mov	w2, #85                         ; =0x55
	bl	___assert_rtn
	.loh AdrpAdd	Lloh422, Lloh423
	.loh AdrpAdd	Lloh420, Lloh421
	.loh AdrpAdd	Lloh418, Lloh419
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
Lloh424:
	adrp	x0, l___func__.main@PAGE
Lloh425:
	add	x0, x0, l___func__.main@PAGEOFF
Lloh426:
	adrp	x1, l_.str.32@PAGE
Lloh427:
	add	x1, x1, l_.str.32@PAGEOFF
Lloh428:
	adrp	x3, l_.str.40@PAGE
Lloh429:
	add	x3, x3, l_.str.40@PAGEOFF
	mov	w2, #86                         ; =0x56
	bl	___assert_rtn
	.loh AdrpAdd	Lloh428, Lloh429
	.loh AdrpAdd	Lloh426, Lloh427
	.loh AdrpAdd	Lloh424, Lloh425
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
Lloh430:
	adrp	x0, l___func__.main@PAGE
Lloh431:
	add	x0, x0, l___func__.main@PAGEOFF
Lloh432:
	adrp	x1, l_.str.32@PAGE
Lloh433:
	add	x1, x1, l_.str.32@PAGEOFF
Lloh434:
	adrp	x3, l_.str.41@PAGE
Lloh435:
	add	x3, x3, l_.str.41@PAGEOFF
	mov	w2, #88                         ; =0x58
	bl	___assert_rtn
	.loh AdrpAdd	Lloh434, Lloh435
	.loh AdrpAdd	Lloh432, Lloh433
	.loh AdrpAdd	Lloh430, Lloh431
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
Lloh436:
	adrp	x0, l___func__.main@PAGE
Lloh437:
	add	x0, x0, l___func__.main@PAGEOFF
Lloh438:
	adrp	x1, l_.str.32@PAGE
Lloh439:
	add	x1, x1, l_.str.32@PAGEOFF
Lloh440:
	adrp	x3, l_.str.42@PAGE
Lloh441:
	add	x3, x3, l_.str.42@PAGEOFF
	mov	w2, #92                         ; =0x5c
	bl	___assert_rtn
	.loh AdrpAdd	Lloh440, Lloh441
	.loh AdrpAdd	Lloh438, Lloh439
	.loh AdrpAdd	Lloh436, Lloh437
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
Lloh442:
	adrp	x0, l___func__.main@PAGE
Lloh443:
	add	x0, x0, l___func__.main@PAGEOFF
Lloh444:
	adrp	x1, l_.str.32@PAGE
Lloh445:
	add	x1, x1, l_.str.32@PAGEOFF
Lloh446:
	adrp	x3, l_.str.43@PAGE
Lloh447:
	add	x3, x3, l_.str.43@PAGEOFF
	mov	w2, #96                         ; =0x60
	bl	___assert_rtn
	.loh AdrpAdd	Lloh446, Lloh447
	.loh AdrpAdd	Lloh444, Lloh445
	.loh AdrpAdd	Lloh442, Lloh443
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
Lloh448:
	adrp	x0, l___func__.main@PAGE
Lloh449:
	add	x0, x0, l___func__.main@PAGEOFF
Lloh450:
	adrp	x1, l_.str.32@PAGE
Lloh451:
	add	x1, x1, l_.str.32@PAGEOFF
Lloh452:
	adrp	x3, l_.str.44@PAGE
Lloh453:
	add	x3, x3, l_.str.44@PAGEOFF
	mov	w2, #101                        ; =0x65
	bl	___assert_rtn
	.loh AdrpAdd	Lloh452, Lloh453
	.loh AdrpAdd	Lloh450, Lloh451
	.loh AdrpAdd	Lloh448, Lloh449
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
	mov	x0, #0                          ; =0x0
	mov	x1, #0                          ; =0x0
	bl	_list_position_stop
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
Lloh454:
	adrp	x0, l___func__.main@PAGE
Lloh455:
	add	x0, x0, l___func__.main@PAGEOFF
Lloh456:
	adrp	x1, l_.str.32@PAGE
Lloh457:
	add	x1, x1, l_.str.32@PAGEOFF
Lloh458:
	adrp	x3, l_.str.38@PAGE
Lloh459:
	add	x3, x3, l_.str.38@PAGEOFF
	mov	w2, #81                         ; =0x51
	bl	___assert_rtn
	.loh AdrpAdd	Lloh458, Lloh459
	.loh AdrpAdd	Lloh456, Lloh457
	.loh AdrpAdd	Lloh454, Lloh455
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
Lloh460:
	adrp	x0, l___func__.main@PAGE
Lloh461:
	add	x0, x0, l___func__.main@PAGEOFF
Lloh462:
	adrp	x1, l_.str.32@PAGE
Lloh463:
	add	x1, x1, l_.str.32@PAGEOFF
Lloh464:
	adrp	x3, l_.str.34@PAGE
Lloh465:
	add	x3, x3, l_.str.34@PAGEOFF
	mov	w2, #37                         ; =0x25
	bl	___assert_rtn
	.loh AdrpAdd	Lloh464, Lloh465
	.loh AdrpAdd	Lloh462, Lloh463
	.loh AdrpAdd	Lloh460, Lloh461
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
	.asciz	"length <= 8193 && repetitions && repetitions <= 8388608 && mode <= 2"

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

l_.str.44:                              ; @.str.44
	.asciz	"!rc_pending_count && !rc_frames && !rc_free_frames"

l_.str.45:                              ; @.str.45
	.asciz	"{\"kind\":\"result\",\"cpu_nanoseconds\":%llu,\"checksum\":\"%016llx\",\"repetitions\":%zu,\"quiescent\":true,\"recovery_scope\":\"pending-zero;frames-absent;fixed-pool-zero;managed-gauges-only-if-testing\"}\n"

l_.str.46:                              ; @.str.46
	.asciz	"Minyar stopped: %s\n"

.zerofill __DATA,__bss,_rc_bounded_chunk_tail,8,3 ; @rc_bounded_chunk_tail
l_.str.47:                              ; @.str.47
	.asciz	"the computer ran out of memory."

l_.str.48:                              ; @.str.48
	.asciz	"List position %lld is outside its length of %lld."

l_.str.49:                              ; @.str.49
	.asciz	"this record has too many fields."

l_.str.50:                              ; @.str.50
	.asciz	"standard output could not be written."

l_.str.51:                              ; @.str.51
	.asciz	"the joined Text would be too large."

l_.str.53:                              ; @.str.53
	.asciz	"a Text position was outside the Text."

l_.str.54:                              ; @.str.54
	.asciz	"Text contained invalid UTF-8."

l_.str.55:                              ; @.str.55
	.asciz	"a Text position cannot be negative."

l_.str.56:                              ; @.str.56
	.asciz	"a Text slice must stay within the Text and end after it starts."

l_.str.57:                              ; @.str.57
	.asciz	"this Character is not valid Unicode."

l_.str.58:                              ; @.str.58
	.asciz	"a file path cannot contain a zero byte."

l_.str.61:                              ; @.str.61
	.asciz	"-Infinity"

l_.str.62:                              ; @.str.62
	.asciz	"Infinity"

l_.str.63:                              ; @.str.63
	.asciz	"-0.0"

l_.str.64:                              ; @.str.64
	.asciz	"0.0"

l_.str.65:                              ; @.str.65
	.asciz	"%lld.0"

l_.str.66:                              ; @.str.66
	.asciz	"%.*e"

l_.str.67:                              ; @.str.67
	.asciz	"e%+d"

l_.str.68:                              ; @.str.68
	.asciz	"Bytes position %lld is outside its length of %lld."

l_.str.69:                              ; @.str.69
	.asciz	"a %lld-byte value at position %lld does not fit in Bytes of length %lld."

l_.str.70:                              ; @.str.70
	.asciz	"%lld does not fit in %s."

l_.str.72:                              ; @.str.72
	.asciz	"an unsigned 16-bit Integer"

l_.str.73:                              ; @.str.73
	.asciz	"an unsigned 32-bit Integer"

l_.str.74:                              ; @.str.74
	.asciz	"a signed 16-bit Integer"

l_.str.75:                              ; @.str.75
	.asciz	"a signed 32-bit Integer"

l___func__.cpu_nanoseconds:             ; @__func__.cpu_nanoseconds
	.asciz	"cpu_nanoseconds"

l_.str.76:                              ; @.str.76
	.asciz	"clock_gettime(CLOCK_PROCESS_CPUTIME_ID, &value) == 0"

.zerofill __DATA,__bss,__MergedGlobals,24,3 ; @_MergedGlobals
.subsections_via_symbols
