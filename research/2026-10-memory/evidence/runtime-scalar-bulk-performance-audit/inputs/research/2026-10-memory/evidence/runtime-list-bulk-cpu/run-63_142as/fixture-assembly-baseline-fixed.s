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
	.p2align	2                               ; -- Begin function minyar_pool_initialize
_minyar_pool_initialize:                ; @minyar_pool_initialize
	.cfi_startproc
; %bb.0:
	mov	x9, #-4096                      ; =0xfffffffffffff000
Lloh9:
	adrp	x8, _minyar_pool@PAGE
Lloh10:
	add	x8, x8, _minyar_pool@PAGEOFF
LBB4_1:                                 ; =>This Inner Loop Header: Depth=1
	add	x9, x9, #1, lsl #12             ; =4096
	strb	wzr, [x9, x8]
	cmp	x9, #4095, lsl #12              ; =16773120
	b.lo	LBB4_1
; %bb.2:
	mov	x9, #-4096                      ; =0xfffffffffffff000
Lloh11:
	adrp	x10, _minyar_pool_map@PAGE
Lloh12:
	add	x10, x10, _minyar_pool_map@PAGEOFF
LBB4_3:                                 ; =>This Inner Loop Header: Depth=1
	add	x9, x9, #1, lsl #12             ; =4096
	strb	wzr, [x9, x10]
	cmp	x9, #127, lsl #12               ; =520192
	b.lo	LBB4_3
; %bb.4:
Lloh13:
	adrp	x10, _minyar_pool_max_order@PAGE
	ldr	w9, [x10, _minyar_pool_max_order@PAGEOFF]
	add	w9, w9, #19
	str	w9, [x10, _minyar_pool_max_order@PAGEOFF]
Lloh14:
	adrp	x10, _minyar_pool_free@PAGE
Lloh15:
	add	x10, x10, _minyar_pool_free@PAGEOFF
	ldr	x11, [x10, w9, uxtw #3]
	stp	xzr, x11, [x8]
	cbz	x11, LBB4_6
; %bb.5:
	str	x8, [x11]
LBB4_6:
	str	x8, [x10, x9, lsl #3]
	mov	w8, #1                          ; =0x1
	lsl	x8, x8, x9
	adrp	x10, _minyar_pool_mask@PAGE
	ldr	x11, [x10, _minyar_pool_mask@PAGEOFF]
	orr	x8, x11, x8
	str	x8, [x10, _minyar_pool_mask@PAGEOFF]
	add	w8, w9, #1
	adrp	x9, _minyar_pool_map@PAGE
	strb	w8, [x9, _minyar_pool_map@PAGEOFF]
	ret
	.loh AdrpAdd	Lloh9, Lloh10
	.loh AdrpAdd	Lloh11, Lloh12
	.loh AdrpAdd	Lloh14, Lloh15
	.loh AdrpAdrp	Lloh13, Lloh14
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_rc_retain               ; -- Begin function minyar_rc_retain
	.p2align	2
_minyar_rc_retain:                      ; @minyar_rc_retain
	.cfi_startproc
; %bb.0:
	cbz	x0, LBB5_4
; %bb.1:
	ldur	x8, [x0, #-8]
	cmp	x8, #8
	b.lo	LBB5_4
; %bb.2:
	cmn	x8, #8
	b.hs	LBB5_5
; %bb.3:
	add	x8, x8, #8
	stur	x8, [x0, #-8]
LBB5_4:
	ret
LBB5_5:
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
	sub	sp, sp, #112
	stp	x28, x27, [sp, #16]             ; 16-byte Folded Spill
	stp	x26, x25, [sp, #32]             ; 16-byte Folded Spill
	stp	x24, x23, [sp, #48]             ; 16-byte Folded Spill
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
	ldr	x10, [x23, _rc_bounded_frame_head@PAGEOFF]
	adrp	x24, _rc_bounded_chunk_head@PAGE
	ldr	x11, [x24, _rc_bounded_chunk_head@PAGEOFF]
	cmp	x0, #0
	adrp	x22, _rc_pending_count@PAGE
	ldr	x8, [x22, _rc_pending_count@PAGEOFF]
	ccmp	x8, #0, #4, ne
	cset	w9, ne
	mov	x19, #0                         ; =0x0
	orr	x10, x10, x11
	cbz	x10, LBB6_52
; %bb.1:
	cbz	w9, LBB6_84
; %bb.2:
	adrp	x25, _rc_bounded_next_queue@PAGE
	adrp	x26, _rc_bounded_active@PAGE
	adrp	x27, _rc_bounded_head@PAGE
	adrp	x28, _rc_bounded_recent_head@PAGE
Lloh16:
	adrp	x9, _minyar_pool@PAGE
Lloh17:
	add	x9, x9, _minyar_pool@PAGEOFF
	mov	w10, #16777216                  ; =0x1000000
	add	x9, x9, x10
	str	x9, [sp, #8]                    ; 8-byte Folded Spill
LBB6_3:                                 ; =>This Inner Loop Header: Depth=1
	ldr	w11, [x25, _rc_bounded_next_queue@PAGEOFF]
	ldr	x20, [x23, _rc_bounded_frame_head@PAGEOFF]
	cmp	x20, #0
	cset	w9, ne
	ldr	x0, [x24, _rc_bounded_chunk_head@PAGEOFF]
	ldr	x10, [x26, _rc_bounded_active@PAGEOFF]
	ldr	x12, [x27, _rc_bounded_head@PAGEOFF]
	orr	x10, x10, x12
	ldr	x12, [x28, _rc_bounded_recent_head@PAGEOFF]
	orr	x10, x10, x12
	cmp	x10, #0
	cset	w10, ne
	cbz	w11, LBB6_9
; %bb.4:                                ;   in Loop: Header=BB6_3 Depth=1
	cmp	w11, #1
	ccmp	x20, #0, #4, eq
	b.ne	LBB6_14
; %bb.5:                                ;   in Loop: Header=BB6_3 Depth=1
	cmp	w11, #2
	ccmp	x0, #0, #4, eq
	b.ne	LBB6_34
; %bb.6:                                ;   in Loop: Header=BB6_3 Depth=1
	add	w11, w11, #1
	mov	w12, #43691                     ; =0xaaab
	movk	w12, #43690, lsl #16
	umull	x12, w11, w12
	lsr	x12, x12, #33
	add	w12, w12, w12, lsl #1
	subs	w11, w11, w12
	b.ne	LBB6_12
; %bb.7:                                ;   in Loop: Header=BB6_3 Depth=1
	tbnz	w10, #0, LBB6_10
; %bb.8:                                ;   in Loop: Header=BB6_3 Depth=1
	mov	w11, #0                         ; =0x0
	mov	w10, #1                         ; =0x1
	tbnz	w9, #0, LBB6_14
	b	LBB6_48
LBB6_9:                                 ;   in Loop: Header=BB6_3 Depth=1
	cbz	w10, LBB6_11
LBB6_10:                                ;   in Loop: Header=BB6_3 Depth=1
	mov	w8, #1                          ; =0x1
	str	w8, [x25, _rc_bounded_next_queue@PAGEOFF]
	bl	_rc_bounded_object_unit
	b	LBB6_41
LBB6_11:                                ;   in Loop: Header=BB6_3 Depth=1
	mov	w11, #1                         ; =0x1
LBB6_12:                                ;   in Loop: Header=BB6_3 Depth=1
	cmp	w11, #1
	b.ne	LBB6_32
; %bb.13:                               ;   in Loop: Header=BB6_3 Depth=1
	cbz	x20, LBB6_32
LBB6_14:                                ;   in Loop: Header=BB6_3 Depth=1
	mov	w9, #2                          ; =0x2
	str	w9, [x25, _rc_bounded_next_queue@PAGEOFF]
LBB6_15:                                ;   in Loop: Header=BB6_3 Depth=1
	ldr	x9, [x20, #16]
	cbz	x9, LBB6_17
; %bb.16:                               ;   in Loop: Header=BB6_3 Depth=1
	sub	x8, x9, #1
	str	x8, [x20, #16]
	ldr	x9, [x20, #8]
	ldr	x10, [x20, #24]
	add	x10, x9, x10, lsl #3
	ldr	x8, [x10, x8, lsl #3]
	ldr	x8, [x9, x8, lsl #3]
	and	x0, x8, #0xfffffffffffffffe
	bl	_rc_drop
	b	LBB6_41
LBB6_17:                                ;   in Loop: Header=BB6_3 Depth=1
	ldr	x9, [x20]
	str	x9, [x23, _rc_bounded_frame_head@PAGEOFF]
	cbnz	x9, LBB6_19
; %bb.18:                               ;   in Loop: Header=BB6_3 Depth=1
	adrp	x9, _rc_bounded_frame_tail@PAGE
	str	xzr, [x9, _rc_bounded_frame_tail@PAGEOFF]
LBB6_19:                                ;   in Loop: Header=BB6_3 Depth=1
Lloh18:
	adrp	x9, _minyar_pool@PAGE
Lloh19:
	add	x9, x9, _minyar_pool@PAGEOFF
	subs	x9, x20, x9
	b.lo	LBB6_85
; %bb.20:                               ;   in Loop: Header=BB6_3 Depth=1
	ldr	x10, [sp, #8]                   ; 8-byte Folded Reload
	cmp	x20, x10
	b.hs	LBB6_85
; %bb.21:                               ;   in Loop: Header=BB6_3 Depth=1
	tst	x9, #0x1f
	b.ne	LBB6_85
; %bb.22:                               ;   in Loop: Header=BB6_3 Depth=1
	lsr	x9, x9, #5
Lloh20:
	adrp	x10, _minyar_pool_map@PAGE
Lloh21:
	add	x10, x10, _minyar_pool_map@PAGEOFF
	ldrsb	w9, [x10, x9]
	tbz	w9, #31, LBB6_87
; %bb.23:                               ;   in Loop: Header=BB6_3 Depth=1
	and	x9, x9, #0xff
	and	w9, w9, #0x7f
	sub	w9, w9, #1
	mov	w10, #32                        ; =0x20
	lsl	x9, x10, x9
	ldr	x0, [x20, #8]
	cbz	x0, LBB6_29
; %bb.24:                               ;   in Loop: Header=BB6_3 Depth=1
Lloh22:
	adrp	x10, _minyar_pool@PAGE
Lloh23:
	add	x10, x10, _minyar_pool@PAGEOFF
	subs	x10, x0, x10
	b.lo	LBB6_86
; %bb.25:                               ;   in Loop: Header=BB6_3 Depth=1
Lloh24:
	adrp	x11, _minyar_pool@PAGE
Lloh25:
	add	x11, x11, _minyar_pool@PAGEOFF
	mov	w12, #16777216                  ; =0x1000000
	add	x11, x11, x12
	cmp	x0, x11
	b.hs	LBB6_86
; %bb.26:                               ;   in Loop: Header=BB6_3 Depth=1
	tst	x10, #0x1f
	b.ne	LBB6_86
; %bb.27:                               ;   in Loop: Header=BB6_3 Depth=1
	lsr	x10, x10, #5
Lloh26:
	adrp	x11, _minyar_pool_map@PAGE
Lloh27:
	add	x11, x11, _minyar_pool_map@PAGEOFF
	ldrsb	w10, [x11, x10]
	tbz	w10, #31, LBB6_88
; %bb.28:                               ;   in Loop: Header=BB6_3 Depth=1
	and	x10, x10, #0xff
	and	w10, w10, #0x7f
	sub	w10, w10, #1
	mov	w11, #32                        ; =0x20
	lsl	x10, x11, x10
	add	x9, x10, x9
LBB6_29:                                ;   in Loop: Header=BB6_3 Depth=1
	cmp	x9, #64, lsl #12                ; =262144
	b.hi	LBB6_31
; %bb.30:                               ;   in Loop: Header=BB6_3 Depth=1
Lloh28:
	adrp	x10, _rc_bounded_cached_frame_bytes@PAGE
Lloh29:
	ldr	x10, [x10, _rc_bounded_cached_frame_bytes@PAGEOFF]
	mov	w11, #262144                    ; =0x40000
	sub	x11, x11, x9
	cmp	x10, x11
	b.ls	LBB6_46
LBB6_31:                                ;   in Loop: Header=BB6_3 Depth=1
	bl	_minyar_pool_deallocate
	mov	x0, x20
	b	LBB6_39
LBB6_32:                                ;   in Loop: Header=BB6_3 Depth=1
	cmp	w11, #2
	b.ne	LBB6_43
; %bb.33:                               ;   in Loop: Header=BB6_3 Depth=1
	cbz	x0, LBB6_43
LBB6_34:                                ;   in Loop: Header=BB6_3 Depth=1
	str	wzr, [x25, _rc_bounded_next_queue@PAGEOFF]
LBB6_35:                                ;   in Loop: Header=BB6_3 Depth=1
	ldr	x8, [x0, #8]
	cbz	x8, LBB6_37
; %bb.36:                               ;   in Loop: Header=BB6_3 Depth=1
	sub	x8, x8, #1
	add	x9, x0, x8, lsl #3
	str	x8, [x0, #8]
	ldr	x0, [x9, #16]
	bl	_rc_drop
	b	LBB6_41
LBB6_37:                                ;   in Loop: Header=BB6_3 Depth=1
	ldr	x8, [x0]
	str	x8, [x24, _rc_bounded_chunk_head@PAGEOFF]
	cbnz	x8, LBB6_39
; %bb.38:                               ;   in Loop: Header=BB6_3 Depth=1
	adrp	x8, _rc_bounded_chunk_tail@PAGE
	str	xzr, [x8, _rc_bounded_chunk_tail@PAGEOFF]
LBB6_39:                                ;   in Loop: Header=BB6_3 Depth=1
	bl	_minyar_pool_deallocate
	ldr	x8, [x22, _rc_pending_count@PAGEOFF]
LBB6_40:                                ;   in Loop: Header=BB6_3 Depth=1
	sub	x8, x8, #1
	str	x8, [x22, _rc_pending_count@PAGEOFF]
LBB6_41:                                ;   in Loop: Header=BB6_3 Depth=1
	add	x19, x19, #1
	cmp	x19, x21
	b.hs	LBB6_84
; %bb.42:                               ;   in Loop: Header=BB6_3 Depth=1
	ldr	x8, [x22, _rc_pending_count@PAGEOFF]
	cbnz	x8, LBB6_3
	b	LBB6_84
LBB6_43:                                ;   in Loop: Header=BB6_3 Depth=1
	cmp	w11, #2
	b.ne	LBB6_47
; %bb.44:                               ;   in Loop: Header=BB6_3 Depth=1
	tbnz	w10, #0, LBB6_10
; %bb.45:                               ;   in Loop: Header=BB6_3 Depth=1
	mov	w10, #0                         ; =0x0
	b	LBB6_49
LBB6_46:                                ;   in Loop: Header=BB6_3 Depth=1
	adrp	x12, _rc_free_frames@PAGE
	ldr	x11, [x12, _rc_free_frames@PAGEOFF]
	str	x11, [x20]
	str	x20, [x12, _rc_free_frames@PAGEOFF]
	add	x9, x10, x9
	adrp	x10, _rc_bounded_cached_frame_bytes@PAGE
	str	x9, [x10, _rc_bounded_cached_frame_bytes@PAGEOFF]
	b	LBB6_40
LBB6_47:                                ;   in Loop: Header=BB6_3 Depth=1
	mov	w9, #0                          ; =0x0
	mov	w10, #2                         ; =0x2
	mov	w11, #1                         ; =0x1
	tbnz	w9, #0, LBB6_14
LBB6_48:                                ;   in Loop: Header=BB6_3 Depth=1
	cmp	x0, #0
	csel	w9, wzr, w11, eq
	tbnz	w9, #0, LBB6_34
LBB6_49:                                ;   in Loop: Header=BB6_3 Depth=1
	add	w9, w10, #1
	sub	w11, w10, #2
	cmp	w9, #3
	csinc	w9, w11, w10, hs
	add	w10, w9, #1
	cmp	w10, #3
	csinc	w10, wzr, w9, eq
	str	w10, [x25, _rc_bounded_next_queue@PAGEOFF]
	cmp	w9, #1
	b.eq	LBB6_15
; %bb.50:                               ;   in Loop: Header=BB6_3 Depth=1
	cbnz	w9, LBB6_35
; %bb.51:                               ;   in Loop: Header=BB6_3 Depth=1
	bl	_rc_bounded_object_unit
	b	LBB6_41
LBB6_52:
	cbz	w9, LBB6_84
; %bb.53:
	adrp	x24, _rc_bounded_recent_head@PAGE
	adrp	x25, _rc_bounded_cursor@PAGE
	adrp	x26, _rc_bounded_recent_turn@PAGE
	adrp	x27, _rc_bytes@PAGE
	adrp	x28, _rc_object_count@PAGE
LBB6_54:                                ; =>This Loop Header: Depth=1
                                        ;     Child Loop BB6_62 Depth 2
                                        ;     Child Loop BB6_75 Depth 2
	sub	x23, x21, x19
Lloh30:
	adrp	x9, _rc_bounded_active@PAGE
Lloh31:
	ldr	x20, [x9, _rc_bounded_active@PAGEOFF]
	ldr	x9, [x24, _rc_bounded_recent_head@PAGEOFF]
	cmp	x23, #2
	b.lo	LBB6_67
; %bb.55:                               ;   in Loop: Header=BB6_54 Depth=1
	cmp	x8, #1
	b.ne	LBB6_67
; %bb.56:                               ;   in Loop: Header=BB6_54 Depth=1
	cbnz	x20, LBB6_67
; %bb.57:                               ;   in Loop: Header=BB6_54 Depth=1
Lloh32:
	adrp	x8, _rc_bounded_head@PAGE
Lloh33:
	ldr	x8, [x8, _rc_bounded_head@PAGEOFF]
	cmp	x8, #0
	csel	x0, x9, x8, eq
	cbz	x0, LBB6_79
; %bb.58:                               ;   in Loop: Header=BB6_54 Depth=1
	ldr	x8, [x0]
	and	x8, x8, #0x7
	cmp	x8, #4
	b.ne	LBB6_79
; %bb.59:                               ;   in Loop: Header=BB6_54 Depth=1
	mov	x9, x0
	ldr	x8, [x9, #8]!
	cmp	x8, #1
	b.ne	LBB6_79
; %bb.60:                               ;   in Loop: Header=BB6_54 Depth=1
	mov	x8, x0
	ldrb	w10, [x8, #24]!
	cmp	w10, #1
	b.hi	LBB6_79
; %bb.61:                               ;   in Loop: Header=BB6_54 Depth=1
Lloh34:
	adrp	x10, _rc_bounded_head@PAGE
	str	xzr, [x10, _rc_bounded_head@PAGEOFF]
Lloh35:
	adrp	x10, _rc_bounded_recent_tail@PAGE
	str	xzr, [x10, _rc_bounded_recent_tail@PAGEOFF]
	str	xzr, [x24, _rc_bounded_recent_head@PAGEOFF]
	mov	w10, #4                         ; =0x4
	str	x10, [x0]
	adrp	x10, _rc_bounded_active@PAGE
	str	x0, [x10, _rc_bounded_active@PAGEOFF]
	mov	w10, #1                         ; =0x1
	str	x10, [x25, _rc_bounded_cursor@PAGEOFF]
	cmp	x23, #4
	b.lo	LBB6_70
LBB6_62:                                ;   Parent Loop BB6_54 Depth=1
                                        ; =>  This Inner Loop Header: Depth=2
	ldrb	w10, [x8]
	tbz	w10, #0, LBB6_70
; %bb.63:                               ;   in Loop: Header=BB6_62 Depth=2
	ldr	x22, [x9, #8]
	cbz	x22, LBB6_70
; %bb.64:                               ;   in Loop: Header=BB6_62 Depth=2
	mov	x20, x22
	ldr	x10, [x20, #-8]!
	cmp	x10, #12
	b.ne	LBB6_70
; %bb.65:                               ;   in Loop: Header=BB6_62 Depth=2
	ldr	x10, [x22]
	cmp	x10, #1
	b.ne	LBB6_70
; %bb.66:                               ;   in Loop: Header=BB6_62 Depth=2
	mov	w8, #4                          ; =0x4
	stur	x8, [x22, #-8]
	ldr	x8, [x0, #8]
	add	x8, x8, x8, lsl #3
	ldr	x9, [x27, _rc_bytes@PAGEOFF]
	sub	x8, x9, x8
	sub	x8, x8, #16
	str	x8, [x27, _rc_bytes@PAGEOFF]
	bl	_minyar_pool_deallocate
	ldr	x8, [x28, _rc_object_count@PAGEOFF]
	sub	x8, x8, #1
	str	x8, [x28, _rc_object_count@PAGEOFF]
	add	x8, x22, #16
	adrp	x9, _rc_bounded_active@PAGE
	str	x20, [x9, _rc_bounded_active@PAGEOFF]
	add	x19, x19, #2
	sub	x23, x23, #2
	mov	x0, x20
	mov	x9, x22
	cmp	x23, #3
	b.hi	LBB6_62
	b	LBB6_71
LBB6_67:                                ;   in Loop: Header=BB6_54 Depth=1
	cmp	x9, #0
	ccmp	x20, #0, #4, eq
	b.eq	LBB6_79
; %bb.68:                               ;   in Loop: Header=BB6_54 Depth=1
	ldr	x8, [x20]
	and	x8, x8, #0x7
	cmp	x8, #3
	b.ne	LBB6_79
; %bb.69:                               ;   in Loop: Header=BB6_54 Depth=1
	ldr	x9, [x20, #16]
	ldr	x8, [x25, _rc_bounded_cursor@PAGEOFF]
	sub	x9, x9, x8
	cmp	x23, x9
	csel	x22, x23, x9, lo
	add	x23, x22, x8
	cmp	x8, x23
	b.lo	LBB6_75
	b	LBB6_78
LBB6_70:                                ;   in Loop: Header=BB6_54 Depth=1
	mov	x22, x9
	mov	x20, x0
LBB6_71:                                ;   in Loop: Header=BB6_54 Depth=1
	ldr	w9, [x26, _rc_bounded_recent_turn@PAGEOFF]
	eor	w10, w9, #0x1
	str	w10, [x26, _rc_bounded_recent_turn@PAGEOFF]
	ldrb	w8, [x8]
	tbz	w8, #0, LBB6_73
; %bb.72:                               ;   in Loop: Header=BB6_54 Depth=1
	ldr	x0, [x22, #8]
	bl	_rc_drop
	ldr	w8, [x26, _rc_bounded_recent_turn@PAGEOFF]
	eor	w9, w8, #0x1
LBB6_73:                                ;   in Loop: Header=BB6_54 Depth=1
	str	w9, [x26, _rc_bounded_recent_turn@PAGEOFF]
	ldr	x8, [x20, #8]
	add	x8, x8, x8, lsl #3
	ldr	x9, [x27, _rc_bytes@PAGEOFF]
	sub	x8, x9, x8
	sub	x8, x8, #16
	str	x8, [x27, _rc_bytes@PAGEOFF]
	mov	x0, x20
	bl	_minyar_pool_deallocate
	ldr	x8, [x28, _rc_object_count@PAGEOFF]
	sub	x8, x8, #1
	str	x8, [x28, _rc_object_count@PAGEOFF]
	adrp	x9, _rc_pending_count@PAGE
	ldr	x8, [x9, _rc_pending_count@PAGEOFF]
	sub	x8, x8, #1
	str	x8, [x9, _rc_pending_count@PAGEOFF]
	adrp	x8, _rc_bounded_active@PAGE
	str	xzr, [x8, _rc_bounded_active@PAGEOFF]
	add	x19, x19, #2
	b	LBB6_80
LBB6_74:                                ;   in Loop: Header=BB6_75 Depth=2
	bl	_rc_drop
	ldr	x9, [x24, _rc_bounded_recent_head@PAGEOFF]
	ldr	x8, [x25, _rc_bounded_cursor@PAGEOFF]
	cmp	x9, #0
	ccmp	x8, x23, #2, eq
	b.hs	LBB6_78
LBB6_75:                                ;   Parent Loop BB6_54 Depth=1
                                        ; =>  This Inner Loop Header: Depth=2
	add	x19, x19, #1
	ldr	w9, [x26, _rc_bounded_recent_turn@PAGEOFF]
	eor	w9, w9, #0x1
	str	w9, [x26, _rc_bounded_recent_turn@PAGEOFF]
	ldr	x9, [x20, #8]
	add	x10, x8, #1
	str	x10, [x25, _rc_bounded_cursor@PAGEOFF]
	ldr	x0, [x9, x8, lsl #3]
	cbz	x0, LBB6_74
; %bb.76:                               ;   in Loop: Header=BB6_75 Depth=2
	sub	x8, x0, #8
	ldr	x9, [x8]
	cmp	x9, #13
	b.ne	LBB6_74
; %bb.77:                               ;   in Loop: Header=BB6_75 Depth=2
	ldr	x9, [x0]
	ldr	x10, [x27, _rc_bytes@PAGEOFF]
	sub	x9, x10, x9, lsl #3
	sub	x9, x9, #16
	str	x9, [x27, _rc_bytes@PAGEOFF]
	mov	x0, x8
	bl	_minyar_pool_deallocate
	ldr	x8, [x28, _rc_object_count@PAGEOFF]
	sub	x8, x8, #1
	str	x8, [x28, _rc_object_count@PAGEOFF]
	ldr	x8, [x25, _rc_bounded_cursor@PAGEOFF]
	cmp	x8, x23
	b.lo	LBB6_75
LBB6_78:                                ;   in Loop: Header=BB6_54 Depth=1
	cbnz	x22, LBB6_80
LBB6_79:                                ;   in Loop: Header=BB6_54 Depth=1
	bl	_rc_bounded_object_unit
	add	x19, x19, #1
LBB6_80:                                ;   in Loop: Header=BB6_54 Depth=1
	cmp	x19, x21
	adrp	x8, _rc_pending_count@PAGE
	b.hs	LBB6_82
; %bb.81:                               ;   in Loop: Header=BB6_54 Depth=1
	ldr	x8, [x8, _rc_pending_count@PAGEOFF]
	cbnz	x8, LBB6_54
LBB6_82:
	cbz	x19, LBB6_84
; %bb.83:
	mov	w8, #1                          ; =0x1
	adrp	x9, _rc_bounded_next_queue@PAGE
	str	w8, [x9, _rc_bounded_next_queue@PAGEOFF]
LBB6_84:
	adrp	x8, _rc_bounded_last_work@PAGE
	str	x19, [x8, _rc_bounded_last_work@PAGEOFF]
	mov	x0, x19
	ldp	x29, x30, [sp, #96]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp, #80]             ; 16-byte Folded Reload
	ldp	x22, x21, [sp, #64]             ; 16-byte Folded Reload
	ldp	x24, x23, [sp, #48]             ; 16-byte Folded Reload
	ldp	x26, x25, [sp, #32]             ; 16-byte Folded Reload
	ldp	x28, x27, [sp, #16]             ; 16-byte Folded Reload
	add	sp, sp, #112
	ret
LBB6_85:
	bl	_minyar_rc_poll.cold.4
LBB6_86:
	bl	_minyar_rc_poll.cold.2
LBB6_87:
	bl	_minyar_rc_poll.cold.3
LBB6_88:
	bl	_minyar_rc_poll.cold.1
	.loh AdrpAdd	Lloh16, Lloh17
	.loh AdrpAdd	Lloh18, Lloh19
	.loh AdrpAdd	Lloh20, Lloh21
	.loh AdrpAdd	Lloh22, Lloh23
	.loh AdrpAdd	Lloh24, Lloh25
	.loh AdrpAdd	Lloh26, Lloh27
	.loh AdrpLdr	Lloh28, Lloh29
	.loh AdrpLdr	Lloh30, Lloh31
	.loh AdrpLdr	Lloh32, Lloh33
	.loh AdrpAdrp	Lloh34, Lloh35
	.cfi_endproc
                                        ; -- End function
	.p2align	2                               ; -- Begin function rc_bounded_finish_object
_rc_bounded_finish_object:              ; @rc_bounded_finish_object
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
	sub	w8, w1, #2
	cmp	w8, #2
	ccmp	w1, #6, #4, hs
	adrp	x19, _rc_bytes@PAGE
	b.ne	LBB7_4
; %bb.1:
	ldr	x8, [x0, #8]
	cbz	x8, LBB7_3
; %bb.2:
	ldr	x9, [x8, #-8]!
	ldr	x10, [x19, _rc_bytes@PAGEOFF]
	sub	x9, x10, x9
	sub	x9, x9, #8
	str	x9, [x19, _rc_bytes@PAGEOFF]
	mov	x20, x0
	mov	x0, x8
	bl	_minyar_pool_deallocate
	mov	x0, x20
LBB7_3:
	ldr	x8, [x19, _rc_bytes@PAGEOFF]
	sub	x8, x8, #32
	b	LBB7_12
LBB7_4:
	cmp	w1, #1
	b.ne	LBB7_11
; %bb.5:
	ldr	x8, [x0, #40]
	cbnz	x8, LBB7_8
; %bb.6:
	ldr	x8, [x0, #8]
	cbz	x8, LBB7_8
; %bb.7:
	ldr	x9, [x8, #-8]!
	ldr	x10, [x19, _rc_bytes@PAGEOFF]
	sub	x9, x10, x9
	sub	x9, x9, #8
	str	x9, [x19, _rc_bytes@PAGEOFF]
	mov	x20, x0
	mov	x0, x8
	bl	_minyar_pool_deallocate
	mov	x0, x20
LBB7_8:
	ldr	x8, [x0, #32]
	cbz	x8, LBB7_10
; %bb.9:
	ldr	x9, [x8, #-8]!
	ldr	x10, [x19, _rc_bytes@PAGEOFF]
	sub	x9, x10, x9
	sub	x9, x9, #8
	str	x9, [x19, _rc_bytes@PAGEOFF]
	mov	x20, x0
	mov	x0, x8
	bl	_minyar_pool_deallocate
	mov	x0, x20
LBB7_10:
	ldr	x8, [x19, _rc_bytes@PAGEOFF]
	sub	x8, x8, #48
	b	LBB7_12
LBB7_11:
	ldr	x8, [x0, #8]
	cmp	w1, #4
	mov	x9, #-9                         ; =0xfffffffffffffff7
	cinc	x9, x9, ne
	ldr	x10, [x19, _rc_bytes@PAGEOFF]
	madd	x8, x8, x9, x10
	sub	x8, x8, #16
LBB7_12:
	str	x8, [x19, _rc_bytes@PAGEOFF]
	bl	_minyar_pool_deallocate
	adrp	x8, _rc_object_count@PAGE
	ldr	x9, [x8, _rc_object_count@PAGEOFF]
	sub	x9, x9, #1
	str	x9, [x8, _rc_object_count@PAGEOFF]
	ldp	x29, x30, [sp, #16]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp], #32             ; 16-byte Folded Reload
	ret
	.cfi_endproc
                                        ; -- End function
	.p2align	2                               ; -- Begin function rc_drop
_rc_drop:                               ; @rc_drop
	.cfi_startproc
; %bb.0:
	cbz	x0, LBB8_25
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
	ldr	x8, [x0, #-8]!
	cmp	x8, #13
	b.ne	LBB8_4
; %bb.2:
	ldr	x8, [x19]
	adrp	x9, _rc_bytes@PAGE
	ldr	x10, [x9, _rc_bytes@PAGEOFF]
	sub	x8, x10, x8, lsl #3
	sub	x8, x8, #16
	str	x8, [x9, _rc_bytes@PAGEOFF]
	bl	_minyar_pool_deallocate
	adrp	x8, _rc_object_count@PAGE
	ldr	x9, [x8, _rc_object_count@PAGEOFF]
	sub	x9, x9, #1
	str	x9, [x8, _rc_object_count@PAGEOFF]
LBB8_3:
	mov	w0, #1                          ; =0x1
	b	LBB8_24
LBB8_4:
	subs	x9, x8, #8
	b.lo	LBB8_23
; %bb.5:
	str	x9, [x0]
	cmp	x9, #7
	b.hi	LBB8_23
; %bb.6:
	and	w1, w8, #0x7
	cmp	w1, #1
	b.ne	LBB8_16
; %bb.7:
	ldr	x20, [x19, #32]
	adrp	x21, _rc_bytes@PAGE
	cbnz	x20, LBB8_10
; %bb.8:
	ldr	x8, [x19]
	cbz	x8, LBB8_10
; %bb.9:
	ldr	x9, [x8, #-8]!
	ldr	x10, [x21, _rc_bytes@PAGEOFF]
	sub	x9, x10, x9
	sub	x9, x9, #8
	str	x9, [x21, _rc_bytes@PAGEOFF]
	mov	x22, x0
	mov	x0, x8
	bl	_minyar_pool_deallocate
	mov	x0, x22
LBB8_10:
	ldr	x8, [x19, #24]
	cbz	x8, LBB8_12
; %bb.11:
	ldr	x9, [x8, #-8]!
	ldr	x10, [x21, _rc_bytes@PAGEOFF]
	sub	x9, x10, x9
	sub	x9, x9, #8
	str	x9, [x21, _rc_bytes@PAGEOFF]
	mov	x19, x0
	mov	x0, x8
	bl	_minyar_pool_deallocate
	mov	x0, x19
LBB8_12:
	ldr	x8, [x21, _rc_bytes@PAGEOFF]
	sub	x8, x8, #48
	str	x8, [x21, _rc_bytes@PAGEOFF]
	bl	_minyar_pool_deallocate
	adrp	x8, _rc_object_count@PAGE
	ldr	x9, [x8, _rc_object_count@PAGEOFF]
	sub	x9, x9, #1
	str	x9, [x8, _rc_object_count@PAGEOFF]
	cbz	x20, LBB8_3
; %bb.13:
	ldr	x8, [x20, #-8]!
	subs	x8, x8, #8
	b.lo	LBB8_3
; %bb.14:
	str	x8, [x20]
	cmp	x8, #7
	b.hi	LBB8_3
; %bb.15:
	mov	x0, x20
	bl	_rc_bounded_enqueue
	b	LBB8_3
LBB8_16:
	and	w8, w8, #0x3
	cmp	w8, #2
	b.ne	LBB8_18
LBB8_17:
	bl	_rc_bounded_finish_object
	b	LBB8_3
LBB8_18:
	cmp	w1, #4
	b.eq	LBB8_21
; %bb.19:
	cmp	w1, #3
	b.ne	LBB8_22
; %bb.20:
	ldr	x8, [x19, #8]
	cbnz	x8, LBB8_22
	b	LBB8_17
LBB8_21:
	ldr	x8, [x19]
	cbz	x8, LBB8_17
LBB8_22:
	bl	_rc_bounded_enqueue
LBB8_23:
	mov	w0, #0                          ; =0x0
LBB8_24:
	ldp	x29, x30, [sp, #32]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp, #16]             ; 16-byte Folded Reload
	ldp	x22, x21, [sp], #48             ; 16-byte Folded Reload
LBB8_25:
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
Lloh36:
	adrp	x8, _rc_bounded_active@PAGE
Lloh37:
	ldr	x9, [x8, _rc_bounded_active@PAGEOFF]
	adrp	x11, _rc_bounded_head@PAGE
	ldr	x10, [x11, _rc_bounded_head@PAGEOFF]
Lloh38:
	adrp	x8, _rc_bounded_recent_head@PAGE
	ldr	x0, [x8, _rc_bounded_recent_head@PAGEOFF]
	orr	x12, x9, x10
	cbz	x12, LBB9_8
; %bb.1:
	adrp	x11, _rc_bounded_recent_turn@PAGE
	ldr	w12, [x11, _rc_bounded_recent_turn@PAGEOFF]
	eor	w13, w12, #0x1
	str	w13, [x11, _rc_bounded_recent_turn@PAGEOFF]
	cmp	w12, #0
	ccmp	x0, #0, #4, ne
	b.eq	LBB9_9
; %bb.2:
	cmp	x9, #0
	ccmp	x10, #0, #0, ne
	b.ne	LBB9_5
; %bb.3:
	ldr	x10, [x9]
	and	x10, x10, #0x7
	cmp	x10, #4
	b.ne	LBB9_5
; %bb.4:
	ldr	x9, [x9, #8]
Lloh39:
	adrp	x10, _rc_bounded_cursor@PAGE
Lloh40:
	ldr	x10, [x10, _rc_bounded_cursor@PAGEOFF]
	cmp	x9, #1
	ccmp	x10, #1, #0, eq
	b.eq	LBB9_9
LBB9_5:
	ldr	x11, [x0]
	and	w1, w11, #0x7
	and	x9, x11, #0x7
	cmp	x9, #1
	b.eq	LBB9_21
; %bb.6:
	cmp	x9, #3
	b.ne	LBB9_10
; %bb.7:
	ldr	x10, [x0, #24]
	cmp	w1, #4
	b.ne	LBB9_14
	b	LBB9_22
LBB9_8:
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
LBB9_9:
	ldp	x29, x30, [sp], #16             ; 16-byte Folded Reload
	b	_rc_bounded_old_object_unit
LBB9_10:
	ldr	x14, [x0, #8]
	cbz	x14, LBB9_21
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
LBB9_12:                                ; =>This Inner Loop Header: Depth=1
	ldrb	w15, [x13], #1
	lsr	x15, x15, #1
	lsl	x15, x15, x12
	orr	x10, x15, x10
	add	x12, x12, #7
	cmp	x14, x12
	b.ne	LBB9_12
; %bb.13:
	cmp	w1, #4
	b.eq	LBB9_22
LBB9_14:
	cmp	w1, #3
	b.ne	LBB9_25
; %bb.15:
	mov	x12, x0
	ldr	x13, [x12, #16]!
	cmp	x10, x13
	b.hs	LBB9_25
; %bb.16:
	ldr	x11, [x0, #8]
	ldr	x8, [x11, x10, lsl #3]
	cmp	x9, #1
	b.eq	LBB9_32
; %bb.17:
	add	x10, x10, #1
	cmp	x9, #3
	b.eq	LBB9_31
; %bb.18:
	mov	x9, #0                          ; =0x0
	add	x11, x12, x11, lsl #3
LBB9_19:                                ; =>This Inner Loop Header: Depth=1
	ldrb	w12, [x11, x9]
	bfi	w12, w10, #1, #31
	strb	w12, [x11, x9]
	cmp	x9, #8
	b.hi	LBB9_32
; %bb.20:                               ;   in Loop: Header=BB9_19 Depth=1
	lsr	x10, x10, #7
	add	x9, x9, #1
	ldr	x12, [x0, #8]
	cmp	x9, x12
	b.lo	LBB9_19
	b	LBB9_32
LBB9_21:
	mov	x10, #0                         ; =0x0
	cmp	w1, #4
	b.ne	LBB9_14
LBB9_22:
	ldr	x12, [x0, #8]
	cmp	x10, x12
	b.hs	LBB9_25
; %bb.23:
	add	x8, x0, #16
	add	x11, x8, x12, lsl #3
	ldrb	w12, [x11, x10]
	tbnz	w12, #0, LBB9_28
; %bb.24:
	mov	x8, #0                          ; =0x0
	b	LBB9_29
LBB9_25:
	ands	x9, x11, #0xfffffffffffffff8
	str	x9, [x8, _rc_bounded_recent_head@PAGEOFF]
	b.ne	LBB9_27
; %bb.26:
	adrp	x8, _rc_bounded_recent_tail@PAGE
	str	xzr, [x8, _rc_bounded_recent_tail@PAGEOFF]
LBB9_27:
	bl	_rc_bounded_finish_object
	adrp	x8, _rc_pending_count@PAGE
	ldr	x9, [x8, _rc_pending_count@PAGEOFF]
	sub	x9, x9, #1
	str	x9, [x8, _rc_pending_count@PAGEOFF]
	ldp	x29, x30, [sp], #16             ; 16-byte Folded Reload
	ret
LBB9_28:
	ldr	x8, [x8, x10, lsl #3]
LBB9_29:
	cmp	x9, #1
	b.eq	LBB9_32
; %bb.30:
	add	x10, x10, #1
	cmp	x9, #3
	b.ne	LBB9_33
LBB9_31:
	str	x10, [x0, #24]
LBB9_32:
	mov	x0, x8
	ldp	x29, x30, [sp], #16             ; 16-byte Folded Reload
	b	_rc_drop
LBB9_33:
	mov	x9, #0                          ; =0x0
LBB9_34:                                ; =>This Inner Loop Header: Depth=1
	ldrb	w12, [x11, x9]
	bfi	w12, w10, #1, #31
	strb	w12, [x11, x9]
	cmp	x9, #8
	b.hi	LBB9_32
; %bb.35:                               ;   in Loop: Header=BB9_34 Depth=1
	lsr	x10, x10, #7
	add	x9, x9, #1
	ldr	x12, [x0, #8]
	cmp	x9, x12
	b.lo	LBB9_34
	b	LBB9_32
	.loh AdrpAdrp	Lloh36, Lloh38
	.loh AdrpLdr	Lloh36, Lloh37
	.loh AdrpLdr	Lloh39, Lloh40
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
Lloh41:
	adrp	x8, _rc_pending_count@PAGE
Lloh42:
	ldr	x8, [x8, _rc_pending_count@PAGEOFF]
	adrp	x20, _rc_bounded_last_work@PAGE
	cbz	x8, LBB10_2
; %bb.1:
	mov	w8, #32                         ; =0x20
	sub	w0, w8, w19
	bl	_minyar_rc_poll
	ldr	x8, [x20, _rc_bounded_last_work@PAGEOFF]
LBB10_2:
	add	x8, x8, w19, uxtw
	str	x8, [x20, _rc_bounded_last_work@PAGEOFF]
	ldp	x29, x30, [sp, #16]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp], #32             ; 16-byte Folded Reload
	ret
	.loh AdrpLdr	Lloh41, Lloh42
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_rc_enter                ; -- Begin function minyar_rc_enter
	.p2align	2
_minyar_rc_enter:                       ; @minyar_rc_enter
	.cfi_startproc
; %bb.0:
	sub	sp, sp, #144
	stp	x28, x27, [sp, #48]             ; 16-byte Folded Spill
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
	.cfi_offset w27, -88
	.cfi_offset w28, -96
	mov	x19, x0
	mov	w0, #32                         ; =0x20
	bl	_minyar_rc_poll
	adrp	x8, _rc_free_frames@PAGE
	ldr	x20, [x8, _rc_free_frames@PAGEOFF]
	cbz	x20, LBB11_10
; %bb.1:
	ldr	x9, [x20]
	str	x9, [x8, _rc_free_frames@PAGEOFF]
Lloh43:
	adrp	x8, _minyar_pool@PAGE
Lloh44:
	add	x8, x8, _minyar_pool@PAGEOFF
	subs	x9, x20, x8
	mov	w10, #16777216                  ; =0x1000000
	add	x10, x8, x10
	ccmp	x20, x10, #2, hs
	b.hs	LBB11_53
; %bb.2:
	tst	x9, #0x1f
	b.ne	LBB11_53
; %bb.3:
	lsr	x10, x9, #5
Lloh45:
	adrp	x9, _minyar_pool_map@PAGE
Lloh46:
	add	x9, x9, _minyar_pool_map@PAGEOFF
	ldrsb	w10, [x9, x10]
	tbz	w10, #31, LBB11_55
; %bb.4:
	and	x10, x10, #0xff
	and	w10, w10, #0x7f
	sub	w10, w10, #1
	mov	x11, #-32                       ; =0xffffffffffffffe0
	lsl	x11, x11, x10
	adrp	x10, _rc_bounded_cached_frame_bytes@PAGE
	ldr	x12, [x10, _rc_bounded_cached_frame_bytes@PAGEOFF]
	add	x11, x12, x11
	str	x11, [x10, _rc_bounded_cached_frame_bytes@PAGEOFF]
	ldr	x13, [x20, #8]
	cbz	x13, LBB11_11
; %bb.5:
	subs	x12, x13, x8
	b.lo	LBB11_54
; %bb.6:
	mov	w14, #16777216                  ; =0x1000000
	add	x8, x8, x14
	cmp	x13, x8
	b.hs	LBB11_54
; %bb.7:
	tst	x12, #0x1f
	b.ne	LBB11_54
; %bb.8:
	lsr	x8, x12, #5
	ldrsb	w8, [x9, x8]
	tbz	w8, #31, LBB11_57
; %bb.9:
	and	x8, x8, #0xff
	and	w8, w8, #0x7f
	sub	w8, w8, #1
	mov	x9, #-32                        ; =0xffffffffffffffe0
	lsl	x8, x9, x8
	add	x8, x8, x11
	str	x8, [x10, _rc_bounded_cached_frame_bytes@PAGEOFF]
	b	LBB11_11
LBB11_10:
	mov	w0, #64                         ; =0x40
	bl	_minyar_pool_allocate
	mov	x20, x0
	movi.2d	v0, #0000000000000000
	stp	q0, q0, [x0]
	stp	q0, q0, [x0, #32]
LBB11_11:
	lsr	x8, x19, #60
	cbnz	x8, LBB11_49
; %bb.12:
	ldr	x8, [x20, #24]
	cmp	x8, x19
	b.hs	LBB11_28
; %bb.13:
	ldr	x21, [x20, #8]
	lsl	x22, x19, #4
	cbz	x21, LBB11_23
; %bb.14:
	adrp	x24, _minyar_pool_last_steps@PAGE
	str	xzr, [x24, _minyar_pool_last_steps@PAGEOFF]
Lloh47:
	adrp	x9, _minyar_pool@PAGE
Lloh48:
	add	x9, x9, _minyar_pool@PAGEOFF
	subs	x25, x21, x9
	b.lo	LBB11_56
; %bb.15:
	mov	w8, #16777216                   ; =0x1000000
	add	x8, x9, x8
	cmp	x21, x8
	b.hs	LBB11_56
; %bb.16:
	tst	x25, #0x1f
	b.ne	LBB11_56
; %bb.17:
	lsr	x9, x25, #5
Lloh49:
	adrp	x8, _minyar_pool_map@PAGE
Lloh50:
	add	x8, x8, _minyar_pool_map@PAGEOFF
	ldrsb	w8, [x8, x9]
	tbz	w8, #31, LBB11_58
; %bb.18:
	cmp	x19, #256, lsl #12              ; =1048576
	b.hi	LBB11_59
; %bb.19:
	and	w8, w8, #0xff
	and	w8, w8, #0x7f
	str	w8, [sp, #4]                    ; 4-byte Folded Spill
	sub	w27, w8, #1
	mov	w8, #32                         ; =0x20
	lsl	x26, x8, x27
	cmp	x19, #3
	str	x9, [sp, #8]                    ; 8-byte Folded Spill
	b.lo	LBB11_24
; %bb.20:
	mov	x28, #0                         ; =0x0
	mov	w23, #32                        ; =0x20
LBB11_21:                               ; =>This Inner Loop Header: Depth=1
	lsl	x23, x23, #1
	add	x28, x28, #1
	cmp	x23, x22
	b.lo	LBB11_21
; %bb.22:
	str	x28, [x24, _minyar_pool_last_steps@PAGEOFF]
	b	LBB11_25
LBB11_23:
	mov	x0, x22
	bl	_minyar_pool_allocate
	cbnz	x0, LBB11_27
	b	LBB11_49
LBB11_24:
	mov	w28, #0                         ; =0x0
	mov	w23, #32                        ; =0x20
LBB11_25:
	stp	w27, w28, [sp, #16]
	stp	x26, x23, [sp, #24]
	str	x25, [sp, #40]
	add	x1, sp, #16
	mov	x0, x21
	bl	_pool_try_resize_same_base
	cbz	x0, LBB11_31
LBB11_26:
	ldr	x8, [x24, _minyar_pool_last_steps@PAGEOFF]
	adrp	x9, _minyar_pool_max_steps@PAGE
	ldr	x10, [x9, _minyar_pool_max_steps@PAGEOFF]
	cmp	x8, x10
	csel	x8, x8, x10, hi
	str	x8, [x9, _minyar_pool_max_steps@PAGEOFF]
LBB11_27:
	str	x0, [x20, #8]
	str	x19, [x20, #24]
LBB11_28:
	cbz	x19, LBB11_30
; %bb.29:
	ldr	x0, [x20, #8]
	lsl	x1, x19, #3
	bl	_bzero
LBB11_30:
	str	x19, [x20, #16]
	stp	xzr, xzr, [x20, #48]
	adrp	x8, _rc_frames@PAGE
	ldr	x9, [x8, _rc_frames@PAGEOFF]
	str	x9, [x20]
	str	x20, [x8, _rc_frames@PAGEOFF]
	ldp	x29, x30, [sp, #128]            ; 16-byte Folded Reload
	ldp	x20, x19, [sp, #112]            ; 16-byte Folded Reload
	ldp	x22, x21, [sp, #96]             ; 16-byte Folded Reload
	ldp	x24, x23, [sp, #80]             ; 16-byte Folded Reload
	ldp	x26, x25, [sp, #64]             ; 16-byte Folded Reload
	ldp	x28, x27, [sp, #48]             ; 16-byte Folded Reload
	add	sp, sp, #144
	ret
LBB11_31:
	sub	x8, x23, #1
	tst	x8, x25
	b.eq	LBB11_45
; %bb.32:
	cmp	w27, w28
	b.hs	LBB11_46
; %bb.33:
	mov	x0, x24
	ldr	x24, [x24, _minyar_pool_last_steps@PAGEOFF]
	mov	w9, #32                         ; =0x20
	mov	x8, x27
	mov	x10, x25
	mov	w11, w28
Lloh51:
	adrp	x1, _minyar_pool@PAGE
Lloh52:
	add	x1, x1, _minyar_pool@PAGEOFF
Lloh53:
	adrp	x3, _minyar_pool_map@PAGE
Lloh54:
	add	x3, x3, _minyar_pool_map@PAGEOFF
LBB11_34:                               ; =>This Inner Loop Header: Depth=1
	lsl	x13, x9, x8
	eor	x12, x10, x13
	lsr	x12, x12, #5
	ldrb	w12, [x3, x12]
	add	x8, x8, #1
	add	x24, x24, #1
	cmp	x8, x11
	b.hs	LBB11_36
; %bb.35:                               ;   in Loop: Header=BB11_34 Depth=1
	bic	x10, x10, x13
	cmp	x8, x12
	b.eq	LBB11_34
LBB11_36:
	str	x24, [x0, _minyar_pool_last_steps@PAGEOFF]
	cmp	x8, x12
	b.ne	LBB11_47
; %bb.37:
	adrp	x8, _minyar_pool_mask@PAGE
	ldr	x9, [x8, _minyar_pool_mask@PAGEOFF]
	ldr	w10, [sp, #4]                   ; 4-byte Folded Reload
	sub	w10, w28, w10
	add	w10, w10, #1
	mov	w11, #32                        ; =0x20
Lloh55:
	adrp	x12, _minyar_pool_free@PAGE
Lloh56:
	add	x12, x12, _minyar_pool_free@PAGEOFF
	mov	w13, #1                         ; =0x1
	b	LBB11_39
LBB11_38:                               ;   in Loop: Header=BB11_39 Depth=1
	lsr	x15, x15, #5
	strb	wzr, [x3, x15]
	bic	x25, x25, x14
	add	x24, x24, #1
	add	x27, x27, #1
	subs	w10, w10, #1
	b.eq	LBB11_50
LBB11_39:                               ; =>This Inner Loop Header: Depth=1
	lsl	x14, x11, x27
	eor	x15, x14, x25
	add	x17, x1, x15
	ldp	x16, x17, [x17]
	cbz	x16, LBB11_44
; %bb.40:                               ;   in Loop: Header=BB11_39 Depth=1
	str	x17, [x16, #8]
	cbz	x17, LBB11_42
LBB11_41:                               ;   in Loop: Header=BB11_39 Depth=1
	str	x16, [x17]
LBB11_42:                               ;   in Loop: Header=BB11_39 Depth=1
	ldr	x16, [x12, x27, lsl #3]
	cbnz	x16, LBB11_38
; %bb.43:                               ;   in Loop: Header=BB11_39 Depth=1
	lsl	x16, x13, x27
	bic	x9, x9, x16
	str	x9, [x8, _minyar_pool_mask@PAGEOFF]
	b	LBB11_38
LBB11_44:                               ;   in Loop: Header=BB11_39 Depth=1
	str	x17, [x12, x27, lsl #3]
	cbnz	x17, LBB11_41
	b	LBB11_42
LBB11_45:
	mov	x25, x24
	ldr	x24, [x24, _minyar_pool_last_steps@PAGEOFF]
	b	LBB11_48
LBB11_46:
	ldr	x9, [sp, #8]                    ; 8-byte Folded Reload
	mov	x8, x9
Lloh57:
	adrp	x1, _minyar_pool@PAGE
Lloh58:
	add	x1, x1, _minyar_pool@PAGEOFF
Lloh59:
	adrp	x3, _minyar_pool_map@PAGE
Lloh60:
	add	x3, x3, _minyar_pool_map@PAGEOFF
	b	LBB11_51
LBB11_47:
	mov	x25, x0
LBB11_48:
	adrp	x23, _minyar_pool_max_steps@PAGE
	ldr	x8, [x23, _minyar_pool_max_steps@PAGEOFF]
	cmp	x24, x8
	csel	x8, x24, x8, hi
	str	x8, [x23, _minyar_pool_max_steps@PAGEOFF]
	mov	x0, x22
	bl	_minyar_pool_allocate
	mov	x22, x0
	ldr	x8, [x25, _minyar_pool_last_steps@PAGEOFF]
	add	x24, x8, x24
	mov	x0, x21
	bl	_minyar_pool_deallocate
	mov	x0, x22
	ldr	x8, [x25, _minyar_pool_last_steps@PAGEOFF]
	ldr	x9, [x23, _minyar_pool_max_steps@PAGEOFF]
	add	x8, x24, x8
	cmp	x8, x9
	str	x8, [x25, _minyar_pool_last_steps@PAGEOFF]
	csel	x8, x8, x9, hi
	str	x8, [x23, _minyar_pool_max_steps@PAGEOFF]
	cbnz	x0, LBB11_27
LBB11_49:
	bl	_out_of_memory
LBB11_50:
	str	x24, [x0, _minyar_pool_last_steps@PAGEOFF]
	mov	x24, x0
	lsr	x8, x25, #5
	ldr	x9, [sp, #8]                    ; 8-byte Folded Reload
LBB11_51:
	strb	wzr, [x3, x9]
	add	x0, x1, x25
	add	w9, w28, #1
	orr	w9, w9, #0x80
	strb	w9, [x3, x8]
Lloh61:
	adrp	x9, _minyar_pool_used@PAGE
	ldr	x8, [x9, _minyar_pool_used@PAGEOFF]
	sub	x10, x23, x26
	add	x8, x8, x10
	str	x8, [x9, _minyar_pool_used@PAGEOFF]
Lloh62:
	adrp	x9, _minyar_pool_high_water@PAGE
	ldr	x10, [x9, _minyar_pool_high_water@PAGEOFF]
	cmp	x8, x10
	b.ls	LBB11_26
; %bb.52:
	str	x8, [x9, _minyar_pool_high_water@PAGEOFF]
	b	LBB11_26
LBB11_53:
	bl	_minyar_rc_enter.cold.4
LBB11_54:
	bl	_minyar_rc_enter.cold.2
LBB11_55:
	bl	_minyar_rc_enter.cold.3
LBB11_56:
	bl	_minyar_rc_enter.cold.7
LBB11_57:
	bl	_minyar_rc_enter.cold.1
LBB11_58:
	bl	_minyar_rc_enter.cold.6
LBB11_59:
	bl	_minyar_rc_enter.cold.5
	.loh AdrpAdd	Lloh43, Lloh44
	.loh AdrpAdd	Lloh45, Lloh46
	.loh AdrpAdd	Lloh47, Lloh48
	.loh AdrpAdd	Lloh49, Lloh50
	.loh AdrpAdd	Lloh53, Lloh54
	.loh AdrpAdd	Lloh51, Lloh52
	.loh AdrpAdd	Lloh55, Lloh56
	.loh AdrpAdd	Lloh59, Lloh60
	.loh AdrpAdd	Lloh57, Lloh58
	.loh AdrpAdrp	Lloh61, Lloh62
	.cfi_endproc
                                        ; -- End function
	.p2align	2                               ; -- Begin function minyar_pool_allocate
_minyar_pool_allocate:                  ; @minyar_pool_allocate
	.cfi_startproc
; %bb.0:
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
	adrp	x9, _minyar_pool_last_steps@PAGE
	str	xzr, [x9, _minyar_pool_last_steps@PAGEOFF]
	mov	w8, #16777216                   ; =0x1000000
	cmp	x0, x8
	b.hi	LBB12_23
; %bb.1:
	cmp	x0, #33
	b.lo	LBB12_5
; %bb.2:
	mov	x8, #0                          ; =0x0
	mov	w10, #32                        ; =0x20
LBB12_3:                                ; =>This Inner Loop Header: Depth=1
	lsl	x10, x10, #1
	add	x8, x8, #1
	cmp	x10, x0
	b.lo	LBB12_3
; %bb.4:
	str	x8, [x9, _minyar_pool_last_steps@PAGEOFF]
	mov	x11, x8
	b	LBB12_6
LBB12_5:
	mov	x8, #0                          ; =0x0
	mov	w11, #0                         ; =0x0
	mov	w10, #32                        ; =0x20
LBB12_6:
	adrp	x12, _minyar_pool_mask@PAGE
	ldr	x13, [x12, _minyar_pool_mask@PAGEOFF]
	mov	x14, #-1                        ; =0xffffffffffffffff
	lsl	x14, x14, x11
	ands	x14, x14, x13
	b.eq	LBB12_22
; %bb.7:
	rbit	x14, x14
	clz	x1, x14
Lloh63:
	adrp	x14, _minyar_pool_free@PAGE
Lloh64:
	add	x14, x14, _minyar_pool_free@PAGEOFF
	ldr	x0, [x14, x1, lsl #3]
	ldp	x15, x16, [x0]
	cbz	x15, LBB12_21
; %bb.8:
	str	x16, [x15, #8]
	cbz	x16, LBB12_10
LBB12_9:
	str	x15, [x16]
LBB12_10:
	ldr	x15, [x14, x1, lsl #3]
	cbnz	x15, LBB12_12
; %bb.11:
	mov	w15, #1                         ; =0x1
	lsl	x15, x15, x1
	bic	x13, x13, x15
	str	x13, [x12, _minyar_pool_mask@PAGEOFF]
LBB12_12:
Lloh65:
	adrp	x17, _minyar_pool@PAGE
Lloh66:
	add	x17, x17, _minyar_pool@PAGEOFF
	sub	x15, x0, x17
	lsr	x15, x15, #5
Lloh67:
	adrp	x16, _minyar_pool_map@PAGE
Lloh68:
	add	x16, x16, _minyar_pool_map@PAGEOFF
	cmp	w11, w1
	b.hs	LBB12_18
; %bb.13:
	sub	x1, x1, #1
	neg	w2, w11
	mov	w3, #32                         ; =0x20
	mov	w4, #1                          ; =0x1
	b	LBB12_15
LBB12_14:                               ;   in Loop: Header=BB12_15 Depth=1
	mov	w6, w1
	str	x5, [x14, x6, lsl #3]
	lsl	x6, x4, x6
	orr	x13, x6, x13
	add	w6, w1, #1
	sub	x5, x5, x17
	lsr	x5, x5, #5
	strb	w6, [x16, x5]
	add	x8, x8, #1
	sub	x1, x1, #1
	add	w5, w2, w1
	cmn	w5, #1
	b.eq	LBB12_17
LBB12_15:                               ; =>This Inner Loop Header: Depth=1
	lsl	x5, x3, x1
	ldr	x6, [x14, w1, uxtw #3]
	add	x5, x0, x5
	stp	xzr, x6, [x5]
	cbz	x6, LBB12_14
; %bb.16:                               ;   in Loop: Header=BB12_15 Depth=1
	str	x5, [x6]
	b	LBB12_14
LBB12_17:
	str	x13, [x12, _minyar_pool_mask@PAGEOFF]
	str	x8, [x9, _minyar_pool_last_steps@PAGEOFF]
LBB12_18:
	add	w9, w11, #1
	orr	w9, w9, #0x80
	strb	w9, [x16, x15]
Lloh69:
	adrp	x11, _minyar_pool_used@PAGE
	ldr	x12, [x11, _minyar_pool_used@PAGEOFF]
	adrp	x9, _minyar_pool_high_water@PAGE
	ldr	x13, [x9, _minyar_pool_high_water@PAGEOFF]
	add	x10, x12, x10
	cmp	x10, x13
	str	x10, [x11, _minyar_pool_used@PAGEOFF]
Lloh70:
	adrp	x11, _minyar_pool_allocation_count@PAGE
	ldr	x12, [x11, _minyar_pool_allocation_count@PAGEOFF]
	add	x12, x12, #1
	str	x12, [x11, _minyar_pool_allocation_count@PAGEOFF]
	b.ls	LBB12_20
; %bb.19:
	str	x10, [x9, _minyar_pool_high_water@PAGEOFF]
LBB12_20:
	adrp	x9, _minyar_pool_max_steps@PAGE
	ldr	x10, [x9, _minyar_pool_max_steps@PAGEOFF]
	cmp	x8, x10
	csel	x8, x8, x10, hi
	str	x8, [x9, _minyar_pool_max_steps@PAGEOFF]
	ldp	x29, x30, [sp], #16             ; 16-byte Folded Reload
	ret
LBB12_21:
	str	x16, [x14, x1, lsl #3]
	cbnz	x16, LBB12_9
	b	LBB12_10
LBB12_22:
	adrp	x9, _minyar_pool_max_steps@PAGE
	ldr	x10, [x9, _minyar_pool_max_steps@PAGEOFF]
	cmp	x8, x10
	csel	x8, x8, x10, hi
	str	x8, [x9, _minyar_pool_max_steps@PAGEOFF]
LBB12_23:
	bl	_minyar_pool_allocate.cold.1
	.loh AdrpAdd	Lloh63, Lloh64
	.loh AdrpAdd	Lloh67, Lloh68
	.loh AdrpAdd	Lloh65, Lloh66
	.loh AdrpAdrp	Lloh69, Lloh70
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
Lloh71:
	adrp	x0, l_.str.51@PAGE
Lloh72:
	add	x0, x0, l_.str.51@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh71, Lloh72
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_rc_leave                ; -- Begin function minyar_rc_leave
	.p2align	2
_minyar_rc_leave:                       ; @minyar_rc_leave
	.cfi_startproc
; %bb.0:
Lloh73:
	adrp	x9, _rc_frames@PAGE
	ldr	x8, [x9, _rc_frames@PAGEOFF]
	ldr	x10, [x8]
	str	x10, [x9, _rc_frames@PAGEOFF]
	mov	x10, x8
	ldr	x11, [x10, #32]!
Lloh74:
	adrp	x9, _rc_pending_count@PAGE
	cbz	x11, LBB14_2
; %bb.1:
	adrp	x12, _rc_bounded_chunk_tail@PAGE
	ldr	x13, [x12, _rc_bounded_chunk_tail@PAGEOFF]
Lloh75:
	adrp	x14, _rc_bounded_chunk_head@PAGE
Lloh76:
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
LBB14_2:
	ldr	x10, [x8, #56]
	str	x10, [x8, #16]
	str	xzr, [x8]
	adrp	x10, _rc_bounded_frame_tail@PAGE
	ldr	x11, [x10, _rc_bounded_frame_tail@PAGEOFF]
Lloh77:
	adrp	x12, _rc_bounded_frame_head@PAGE
Lloh78:
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
	.loh AdrpAdrp	Lloh73, Lloh74
	.loh AdrpAdd	Lloh75, Lloh76
	.loh AdrpAdd	Lloh77, Lloh78
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_rc_keep                 ; -- Begin function minyar_rc_keep
	.p2align	2
_minyar_rc_keep:                        ; @minyar_rc_keep
	.cfi_startproc
; %bb.0:
	cbz	x0, LBB15_11
; %bb.1:
	mov	x8, x0
	ldur	x9, [x0, #-8]
	cmp	x9, #8
	b.lo	LBB15_11
; %bb.2:
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
Lloh79:
	adrp	x9, _rc_frames@PAGE
Lloh80:
	ldr	x19, [x9, _rc_frames@PAGEOFF]
	ldr	x0, [x19, #40]
	adrp	x20, _rc_pending_count@PAGE
	cbz	x0, LBB15_4
; %bb.3:
	ldr	x9, [x0, #8]
	cmp	x9, #8
	b.ne	LBB15_8
LBB15_4:
	mov	x21, x8
	ldr	x8, [x20, _rc_pending_count@PAGEOFF]
	cbz	x8, LBB15_6
; %bb.5:
	mov	w0, #32                         ; =0x20
	bl	_minyar_rc_poll
	b	LBB15_7
LBB15_6:
	adrp	x8, _rc_bounded_last_work@PAGE
	str	xzr, [x8, _rc_bounded_last_work@PAGEOFF]
LBB15_7:
	mov	w0, #80                         ; =0x50
	bl	_minyar_pool_allocate
	mov	x9, #0                          ; =0x0
	stp	xzr, xzr, [x0]
	ldr	x8, [x19, #40]
	add	x10, x19, #32
	cmp	x8, #0
	csel	x8, x10, x8, eq
	str	x0, [x8]
	str	x0, [x19, #40]
	mov	x8, x21
LBB15_8:
	add	x10, x0, x9, lsl #3
	add	x9, x9, #1
	str	x9, [x0, #8]
	str	x8, [x10, #16]
	ldr	x8, [x19, #48]
	add	x8, x8, #1
	str	x8, [x19, #48]
	ldr	x8, [x20, _rc_pending_count@PAGEOFF]
	ldp	x29, x30, [sp, #32]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp, #16]             ; 16-byte Folded Reload
	ldp	x22, x21, [sp], #48             ; 16-byte Folded Reload
	cbz	x8, LBB15_10
; %bb.9:
	mov	w0, #32                         ; =0x20
	b	_minyar_rc_poll
LBB15_10:
	adrp	x8, _rc_bounded_last_work@PAGE
	str	xzr, [x8, _rc_bounded_last_work@PAGEOFF]
LBB15_11:
	ret
	.loh AdrpLdr	Lloh79, Lloh80
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_rc_local_take           ; -- Begin function minyar_rc_local_take
	.p2align	2
_minyar_rc_local_take:                  ; @minyar_rc_local_take
	.cfi_startproc
; %bb.0:
Lloh81:
	adrp	x8, _rc_frames@PAGE
Lloh82:
	ldr	x10, [x8, _rc_frames@PAGEOFF]
	ldr	x9, [x10, #8]
	ldr	x8, [x9, x0, lsl #3]
	cbz	x1, LBB16_4
; %bb.1:
	tbnz	w8, #0, LBB16_4
; %bb.2:
	ldr	x11, [x10, #24]
	add	x11, x9, x11, lsl #3
	ldr	x12, [x10, #56]
	add	x13, x12, #1
	str	x13, [x10, #56]
	str	x0, [x11, x12, lsl #3]
LBB16_3:
	orr	x10, x1, #0x1
	str	x10, [x9, x0, lsl #3]
	b	LBB16_6
LBB16_4:
	tbnz	w8, #0, LBB16_3
; %bb.5:
	cbnz	x1, LBB16_3
LBB16_6:
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
Lloh83:
	adrp	x8, _rc_pending_count@PAGE
Lloh84:
	ldr	x8, [x8, _rc_pending_count@PAGEOFF]
	adrp	x20, _rc_bounded_last_work@PAGE
	cbz	x8, LBB16_8
; %bb.7:
	mov	w8, #32                         ; =0x20
	sub	w0, w8, w19
	bl	_minyar_rc_poll
	ldr	x8, [x20, _rc_bounded_last_work@PAGEOFF]
LBB16_8:
	add	x8, x8, w19, uxtw
	str	x8, [x20, _rc_bounded_last_work@PAGEOFF]
	ldp	x29, x30, [sp, #16]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp], #32             ; 16-byte Folded Reload
	ret
	.loh AdrpLdr	Lloh81, Lloh82
	.loh AdrpLdr	Lloh83, Lloh84
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_rc_local_move           ; -- Begin function minyar_rc_local_move
	.p2align	2
_minyar_rc_local_move:                  ; @minyar_rc_local_move
	.cfi_startproc
; %bb.0:
Lloh85:
	adrp	x8, _rc_frames@PAGE
Lloh86:
	ldr	x8, [x8, _rc_frames@PAGEOFF]
	ldr	x8, [x8, #8]
	ldr	x9, [x8, x0, lsl #3]
	and	x9, x9, #0x1
	str	x9, [x8, x0, lsl #3]
	ret
	.loh AdrpLdr	Lloh85, Lloh86
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
	cbz	x1, LBB18_4
; %bb.1:
	ldur	x8, [x1, #-8]
	cmp	x8, #8
	b.lo	LBB18_4
; %bb.2:
	cmn	x8, #8
	b.hs	LBB18_13
; %bb.3:
	add	x8, x8, #8
	stur	x8, [x1, #-8]
LBB18_4:
Lloh87:
	adrp	x8, _rc_frames@PAGE
Lloh88:
	ldr	x10, [x8, _rc_frames@PAGEOFF]
	ldr	x9, [x10, #8]
	ldr	x8, [x9, x0, lsl #3]
	cbz	x1, LBB18_8
; %bb.5:
	tbnz	w8, #0, LBB18_8
; %bb.6:
	ldr	x11, [x10, #24]
	add	x11, x9, x11, lsl #3
	ldr	x12, [x10, #56]
	add	x13, x12, #1
	str	x13, [x10, #56]
	str	x0, [x11, x12, lsl #3]
LBB18_7:
	orr	x10, x1, #0x1
	str	x10, [x9, x0, lsl #3]
	b	LBB18_10
LBB18_8:
	tbnz	w8, #0, LBB18_7
; %bb.9:
	cbnz	x1, LBB18_7
LBB18_10:
	and	x0, x8, #0xfffffffffffffffe
	bl	_rc_drop
	mov	x19, x0
Lloh89:
	adrp	x8, _rc_pending_count@PAGE
Lloh90:
	ldr	x8, [x8, _rc_pending_count@PAGEOFF]
	adrp	x20, _rc_bounded_last_work@PAGE
	cbz	x8, LBB18_12
; %bb.11:
	mov	w8, #32                         ; =0x20
	sub	w0, w8, w19
	bl	_minyar_rc_poll
	ldr	x8, [x20, _rc_bounded_last_work@PAGEOFF]
LBB18_12:
	add	x8, x8, w19, uxtw
	str	x8, [x20, _rc_bounded_last_work@PAGEOFF]
	ldp	x29, x30, [sp, #16]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp], #32             ; 16-byte Folded Reload
	ret
LBB18_13:
	bl	_minyar_rc_local.cold.1
	.loh AdrpLdr	Lloh87, Lloh88
	.loh AdrpLdr	Lloh89, Lloh90
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_rc_borrow               ; -- Begin function minyar_rc_borrow
	.p2align	2
_minyar_rc_borrow:                      ; @minyar_rc_borrow
	.cfi_startproc
; %bb.0:
	cbz	x0, LBB19_4
; %bb.1:
	ldur	x8, [x0, #-8]
	cmp	x8, #8
	b.lo	LBB19_4
; %bb.2:
	cmn	x8, #8
	b.hs	LBB19_5
; %bb.3:
	add	x8, x8, #8
	stur	x8, [x0, #-8]
LBB19_4:
	b	_minyar_rc_keep
LBB19_5:
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
Lloh91:
	adrp	x8, _rc_frames@PAGE
Lloh92:
	ldr	x9, [x8, _rc_frames@PAGEOFF]
	mov	x8, x9
	ldr	x10, [x8, #32]!
	cbz	x10, LBB20_2
; %bb.1:
	adrp	x11, _rc_bounded_chunk_tail@PAGE
	ldr	x12, [x11, _rc_bounded_chunk_tail@PAGEOFF]
Lloh93:
	adrp	x13, _rc_bounded_chunk_head@PAGE
Lloh94:
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
LBB20_2:
	mov	w0, #32                         ; =0x20
	b	_minyar_rc_poll
	.loh AdrpLdr	Lloh91, Lloh92
	.loh AdrpAdd	Lloh93, Lloh94
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
Lloh95:
	adrp	x8, _rc_pending_count@PAGE
Lloh96:
	ldr	x8, [x8, _rc_pending_count@PAGEOFF]
	cbz	x8, LBB22_2
; %bb.1:
	mov	w0, #32                         ; =0x20
	bl	_minyar_rc_poll
	b	LBB22_3
LBB22_2:
	adrp	x8, _rc_bounded_last_work@PAGE
	str	xzr, [x8, _rc_bounded_last_work@PAGEOFF]
LBB22_3:
	mov	w0, #32                         ; =0x20
	bl	_minyar_pool_allocate
	mov	w8, #10                         ; =0xa
	str	x8, [x0]
Lloh97:
	adrp	x8, _rc_object_count@PAGE
	ldr	x9, [x8, _rc_object_count@PAGEOFF]
	add	x9, x9, #1
	str	x9, [x8, _rc_object_count@PAGEOFF]
Lloh98:
	adrp	x8, _rc_bytes@PAGE
	ldr	x9, [x8, _rc_bytes@PAGEOFF]
	add	x9, x9, #32
	str	x9, [x8, _rc_bytes@PAGEOFF]
	stp	xzr, xzr, [x0, #16]
	str	xzr, [x0, #8]!
	ldp	x29, x30, [sp], #16             ; 16-byte Folded Reload
	ret
	.loh AdrpLdr	Lloh95, Lloh96
	.loh AdrpAdrp	Lloh97, Lloh98
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
	b.ne	LBB23_2
; %bb.1:
	ret
LBB23_2:
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
	b.eq	LBB24_15
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
	b	LBB24_14
LBB24_3:
	cbz	x1, LBB24_7
; %bb.4:
	cmp	w9, #6
	b.ne	LBB24_7
; %bb.5:
	ldur	x9, [x1, #-8]
	cmp	x9, #8
	b.lo	LBB24_12
; %bb.6:
	and	x8, x8, #0xfffffffffffffff8
	orr	x8, x8, #0x3
	stur	x8, [x0, #-8]
	b	LBB24_9
LBB24_7:
	cbz	x1, LBB24_12
; %bb.8:
	cmp	w9, #3
	b.ne	LBB24_12
LBB24_9:
	ldur	x8, [x1, #-8]
	cmp	x8, #8
	b.lo	LBB24_12
; %bb.10:
	cmn	x8, #8
	b.hs	LBB24_16
; %bb.11:
	add	x8, x8, #8
	stur	x8, [x1, #-8]
LBB24_12:
	ldp	x8, x9, [x0]
	add	x10, x9, #1
	str	x10, [x0, #8]
	str	x1, [x8, x9, lsl #3]
Lloh99:
	adrp	x8, _rc_pending_count@PAGE
Lloh100:
	ldr	x8, [x8, _rc_pending_count@PAGEOFF]
	cbz	x8, LBB24_14
; %bb.13:
	mov	w0, #32                         ; =0x20
	ldp	x29, x30, [sp, #16]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp], #32             ; 16-byte Folded Reload
	b	_minyar_rc_poll
LBB24_14:
	ldp	x29, x30, [sp, #16]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp], #32             ; 16-byte Folded Reload
	ret
LBB24_15:
	mov	x19, x0
	mov	x20, x1
	bl	_list_grow
	mov	x0, x19
	mov	x1, x20
	b	LBB24_1
LBB24_16:
	bl	_minyar_list_add.cold.1
	.loh AdrpLdr	Lloh99, Lloh100
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
	tbnz	x8, #63, LBB25_4
; %bb.1:
	lsr	x9, x8, #62
	cbnz	x9, LBB25_4
; %bb.2:
	lsl	x9, x8, #1
	cmp	x8, #0
	mov	w10, #3                         ; =0x3
	csinc	x20, x10, x9, eq
	cmp	x8, x20
	lsr	x8, x20, #61
	ccmp	x8, #0, #0, ls
	b.ne	LBB25_4
; %bb.3:
	mov	x19, x0
	ldr	x0, [x0]
	lsl	x1, x20, #3
	bl	_rc_reallocate_data
	str	x0, [x19]
	str	x20, [x19, #16]
	ldp	x29, x30, [sp, #16]             ; 16-byte Folded Reload
	b	_OUTLINED_FUNCTION_2
LBB25_4:
Lloh101:
	adrp	x0, l_.str.3@PAGE
Lloh102:
	add	x0, x0, l_.str.3@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh101, Lloh102
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
	b.eq	LBB26_10
LBB26_1:
	ldur	x8, [x0, #-8]
	and	w9, w8, #0x7
	cmp	w9, #2
	b.ne	LBB26_3
; %bb.2:
	ldp	x8, x9, [x0]
	add	x10, x9, #1
	str	x10, [x0, #8]
	str	x1, [x8, x9, lsl #3]
	b	LBB26_9
LBB26_3:
	cbz	x1, LBB26_7
; %bb.4:
	cmp	w9, #6
	b.ne	LBB26_7
; %bb.5:
	ldur	x9, [x1, #-8]
	cmp	x9, #8
	b.lo	LBB26_7
; %bb.6:
	and	x8, x8, #0xfffffffffffffff8
	orr	x8, x8, #0x3
	stur	x8, [x0, #-8]
LBB26_7:
	ldp	x8, x9, [x0]
	add	x10, x9, #1
	str	x10, [x0, #8]
	str	x1, [x8, x9, lsl #3]
Lloh103:
	adrp	x8, _rc_pending_count@PAGE
Lloh104:
	ldr	x8, [x8, _rc_pending_count@PAGEOFF]
	cbz	x8, LBB26_9
; %bb.8:
	mov	w0, #32                         ; =0x20
	ldp	x29, x30, [sp, #16]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp], #32             ; 16-byte Folded Reload
	b	_minyar_rc_poll
LBB26_9:
	ldp	x29, x30, [sp, #16]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp], #32             ; 16-byte Folded Reload
	ret
LBB26_10:
	mov	x19, x0
	mov	x20, x1
	bl	_list_grow
	mov	x0, x19
	mov	x1, x20
	b	LBB26_1
	.loh AdrpLdr	Lloh103, Lloh104
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
	b.ls	LBB28_2
; %bb.1:
	ldr	x8, [x0]
	ldr	x0, [x8, x1, lsl #3]
	ret
LBB28_2:
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
Lloh105:
	adrp	x2, l_.str.52@PAGE
Lloh106:
	add	x2, x2, l_.str.52@PAGEOFF
	add	x0, sp, #16
	mov	w1, #128                        ; =0x80
	bl	_snprintf
	add	x0, sp, #16
	bl	_minyar_stop
	.loh AdrpAdd	Lloh105, Lloh106
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
	b.ls	LBB31_16
; %bb.1:
	ldur	x8, [x0, #-8]
	and	w9, w8, #0x7
	cbz	x2, LBB31_5
; %bb.2:
	cmp	w9, #6
	b.ne	LBB31_5
; %bb.3:
	ldur	x9, [x2, #-8]
	cmp	x9, #8
	b.lo	LBB31_14
; %bb.4:
	and	x8, x8, #0xfffffffffffffff8
	orr	x8, x8, #0x3
	stur	x8, [x0, #-8]
	b	LBB31_6
LBB31_5:
	cmp	w9, #3
	b.ne	LBB31_14
LBB31_6:
	cbz	x2, LBB31_11
; %bb.7:
	cbz	w3, LBB31_11
; %bb.8:
	ldur	x8, [x2, #-8]
	cmp	x8, #8
	b.lo	LBB31_11
; %bb.9:
	cmn	x8, #8
	b.hs	LBB31_17
; %bb.10:
	add	x8, x8, #8
	stur	x8, [x2, #-8]
LBB31_11:
	ldr	x8, [x0]
	ldr	x0, [x8, x1, lsl #3]
	str	x2, [x8, x1, lsl #3]
	bl	_rc_drop
	mov	x19, x0
Lloh107:
	adrp	x8, _rc_pending_count@PAGE
Lloh108:
	ldr	x8, [x8, _rc_pending_count@PAGEOFF]
	adrp	x20, _rc_bounded_last_work@PAGE
	cbz	x8, LBB31_13
; %bb.12:
	mov	w8, #32                         ; =0x20
	sub	w0, w8, w19
	bl	_minyar_rc_poll
	ldr	x8, [x20, _rc_bounded_last_work@PAGEOFF]
LBB31_13:
	add	x8, x8, w19, uxtw
	str	x8, [x20, _rc_bounded_last_work@PAGEOFF]
	b	LBB31_15
LBB31_14:
	ldr	x8, [x0]
	str	x2, [x8, x1, lsl #3]
LBB31_15:
	ldp	x29, x30, [sp, #16]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp], #32             ; 16-byte Folded Reload
	ret
LBB31_16:
	mov	x0, x1
	mov	x1, x8
	bl	_list_position_stop
LBB31_17:
	bl	_minyar_list_set_owned.cold.1
	.loh AdrpLdr	Lloh107, Lloh108
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
	b.ls	LBB32_11
; %bb.1:
	ldur	x8, [x0, #-8]
	and	w9, w8, #0x7
	cbz	x2, LBB32_5
; %bb.2:
	cmp	w9, #6
	b.ne	LBB32_5
; %bb.3:
	ldur	x9, [x2, #-8]
	cmp	x9, #8
	b.lo	LBB32_9
; %bb.4:
	and	x8, x8, #0xfffffffffffffff8
	orr	x8, x8, #0x3
	stur	x8, [x0, #-8]
	b	LBB32_6
LBB32_5:
	cmp	w9, #3
	b.ne	LBB32_9
LBB32_6:
	ldr	x8, [x0]
	ldr	x0, [x8, x1, lsl #3]
	str	x2, [x8, x1, lsl #3]
	bl	_rc_drop
	mov	x19, x0
Lloh109:
	adrp	x8, _rc_pending_count@PAGE
Lloh110:
	ldr	x8, [x8, _rc_pending_count@PAGEOFF]
	adrp	x20, _rc_bounded_last_work@PAGE
	cbz	x8, LBB32_8
; %bb.7:
	mov	w8, #32                         ; =0x20
	sub	w0, w8, w19
	bl	_minyar_rc_poll
	ldr	x8, [x20, _rc_bounded_last_work@PAGEOFF]
LBB32_8:
	add	x8, x8, w19, uxtw
	str	x8, [x20, _rc_bounded_last_work@PAGEOFF]
	b	LBB32_10
LBB32_9:
	ldr	x8, [x0]
	str	x2, [x8, x1, lsl #3]
LBB32_10:
	ldp	x29, x30, [sp, #16]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp], #32             ; 16-byte Folded Reload
	ret
LBB32_11:
	mov	x0, x1
	mov	x1, x8
	bl	_list_position_stop
	.loh AdrpLdr	Lloh109, Lloh110
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
	cbz	x8, LBB33_2
; %bb.1:
	mov	w0, #32                         ; =0x20
	bl	_minyar_rc_poll
	b	LBB33_3
LBB33_2:
	adrp	x8, _rc_bounded_last_work@PAGE
	str	xzr, [x8, _rc_bounded_last_work@PAGEOFF]
LBB33_3:
	mov	w0, #32                         ; =0x20
	bl	_minyar_pool_allocate
	mov	x21, x0
	mov	w8, #10                         ; =0xa
	str	x8, [x0]
Lloh111:
	adrp	x8, _rc_object_count@PAGE
	ldr	x9, [x8, _rc_object_count@PAGEOFF]
	add	x9, x9, #1
	str	x9, [x8, _rc_object_count@PAGEOFF]
Lloh112:
	adrp	x8, _rc_bytes@PAGE
	ldr	x9, [x8, _rc_bytes@PAGEOFF]
	add	x9, x9, #32
	str	x9, [x8, _rc_bytes@PAGEOFF]
	mov	x20, x0
	str	xzr, [x20, #8]!
	stp	xzr, xzr, [x0, #16]
	cbz	x24, LBB33_5
; %bb.4:
	mov	w8, #14                         ; =0xe
	str	x8, [x21]
LBB33_5:
	ldr	x8, [x23, #8]
	mov	x9, #9223372036854775807        ; =0x7fffffffffffffff
	cmp	x8, x9
	b.eq	LBB33_26
; %bb.6:
	ldr	x9, [x25, _rc_pending_count@PAGEOFF]
	cbz	x9, LBB33_24
; %bb.7:
	tbnz	x8, #63, LBB33_12
LBB33_8:                                ; =>This Inner Loop Header: Depth=1
	add	x0, x21, #8
	bl	_list_grow
	ldr	x9, [x21, #24]
	ldr	x8, [x23, #8]
	cmp	x9, x8
	b.le	LBB33_8
; %bb.9:
	cmp	x8, #1
	b.lt	LBB33_12
LBB33_10:
	mov	x24, #0                         ; =0x0
LBB33_11:                               ; =>This Inner Loop Header: Depth=1
	ldr	x8, [x23]
	ldr	x1, [x8, x24, lsl #3]
	mov	x0, x20
	bl	_minyar_list_add
	add	x24, x24, #1
	ldr	x8, [x23, #8]
	cmp	x24, x8
	b.lt	LBB33_11
LBB33_12:
	cbz	x22, LBB33_16
; %bb.13:
	ldp	x8, x9, [x21, #16]
	cmp	x8, x9
	b.eq	LBB33_25
LBB33_14:
	ldr	x8, [x21]
	and	w9, w8, #0x7
	cmp	w9, #2
	b.ne	LBB33_17
; %bb.15:
	ldp	x8, x9, [x21, #8]
	add	x10, x9, #1
	str	x10, [x21, #16]
	str	x19, [x8, x9, lsl #3]
	b	LBB33_23
LBB33_16:
	mov	x0, x20
	mov	x1, x19
	bl	_minyar_list_add
	b	LBB33_23
LBB33_17:
	cbz	x19, LBB33_21
; %bb.18:
	cmp	w9, #6
	b.ne	LBB33_21
; %bb.19:
	ldur	x9, [x19, #-8]
	cmp	x9, #8
	b.lo	LBB33_21
; %bb.20:
	and	x8, x8, #0xfffffffffffffff8
	orr	x8, x8, #0x3
	str	x8, [x21]
LBB33_21:
	ldp	x8, x9, [x21, #8]
	add	x10, x9, #1
	str	x10, [x21, #16]
	str	x19, [x8, x9, lsl #3]
	ldr	x8, [x25, _rc_pending_count@PAGEOFF]
	cbz	x8, LBB33_23
; %bb.22:
	mov	w0, #32                         ; =0x20
	bl	_minyar_rc_poll
LBB33_23:
	mov	x0, x20
	ldp	x29, x30, [sp, #64]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp, #48]             ; 16-byte Folded Reload
	ldp	x22, x21, [sp, #32]             ; 16-byte Folded Reload
	ldp	x24, x23, [sp, #16]             ; 16-byte Folded Reload
	ldp	x26, x25, [sp], #80             ; 16-byte Folded Reload
	ret
LBB33_24:
	add	x1, x8, #1
	mov	x0, x20
	bl	_list_reserve
	ldr	x8, [x23, #8]
	cmp	x8, #1
	b.ge	LBB33_10
	b	LBB33_12
LBB33_25:
	mov	x0, x20
	bl	_list_grow
	b	LBB33_14
LBB33_26:
	bl	_minyar_list_appended.cold.1
	.loh AdrpAdrp	Lloh111, Lloh112
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
	b.ge	LBB34_5
; %bb.1:
	mov	w9, #3                          ; =0x3
	mov	x20, x8
LBB34_2:                                ; =>This Inner Loop Header: Depth=1
	tbnz	x20, #63, LBB34_8
; %bb.3:                                ;   in Loop: Header=BB34_2 Depth=1
	lsr	x10, x20, #62
	cbnz	x10, LBB34_8
; %bb.4:                                ;   in Loop: Header=BB34_2 Depth=1
	lsl	x10, x20, #1
	cmp	x20, #0
	csinc	x20, x9, x10, eq
	cmp	x20, x1
	b.lt	LBB34_2
	b	LBB34_6
LBB34_5:
	mov	x20, x8
LBB34_6:
	cmp	x8, x20
	lsr	x8, x20, #61
	ccmp	x8, #0, #0, le
	b.ne	LBB34_8
; %bb.7:
	ldr	x0, [x19]
	lsl	x1, x20, #3
	bl	_rc_reallocate_data
	str	x0, [x19]
	str	x20, [x19, #16]
	ldp	x29, x30, [sp, #16]             ; 16-byte Folded Reload
	b	_OUTLINED_FUNCTION_2
LBB34_8:
Lloh113:
	adrp	x0, l_.str.3@PAGE
Lloh114:
	add	x0, x0, l_.str.3@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh113, Lloh114
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
	cbnz	x8, LBB35_6
; %bb.1:
	mov	x19, x0
	mov	x8, #7280                       ; =0x1c70
	movk	x8, #29127, lsl #16
	movk	x8, #50972, lsl #32
	movk	x8, #7281, lsl #48
	cmp	x0, x8
	b.hs	LBB35_7
; %bb.2:
Lloh115:
	adrp	x8, _rc_pending_count@PAGE
Lloh116:
	ldr	x8, [x8, _rc_pending_count@PAGEOFF]
	cbz	x8, LBB35_4
; %bb.3:
	mov	w0, #32                         ; =0x20
	bl	_minyar_rc_poll
	b	LBB35_5
LBB35_4:
	adrp	x8, _rc_bounded_last_work@PAGE
	str	xzr, [x8, _rc_bounded_last_work@PAGEOFF]
LBB35_5:
	add	x20, x19, x19, lsl #3
	add	x21, x20, #16
	mov	x0, x21
	bl	_minyar_pool_allocate
	mov	x22, x0
	mov	w8, #12                         ; =0xc
	str	x8, [x0], #16
Lloh117:
	adrp	x8, _rc_object_count@PAGE
	ldr	x9, [x8, _rc_object_count@PAGEOFF]
	add	x9, x9, #1
	str	x9, [x8, _rc_object_count@PAGEOFF]
Lloh118:
	adrp	x8, _rc_bytes@PAGE
	ldr	x9, [x8, _rc_bytes@PAGEOFF]
	add	x9, x9, x21
	str	x9, [x8, _rc_bytes@PAGEOFF]
	mov	x1, x20
	bl	_bzero
	str	x19, [x22, #8]!
	mov	x0, x22
	ldp	x29, x30, [sp, #32]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp, #16]             ; 16-byte Folded Reload
	ldp	x22, x21, [sp], #48             ; 16-byte Folded Reload
	ret
LBB35_6:
	bl	_minyar_record_new.cold.1
LBB35_7:
	bl	_out_of_memory
	.loh AdrpLdr	Lloh115, Lloh116
	.loh AdrpAdrp	Lloh117, Lloh118
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
	cbnz	x8, LBB36_6
; %bb.1:
	mov	x19, x0
	mov	x8, #2305843009213693950        ; =0x1ffffffffffffffe
	cmp	x0, x8
	b.hs	LBB36_7
; %bb.2:
Lloh119:
	adrp	x8, _rc_pending_count@PAGE
Lloh120:
	ldr	x8, [x8, _rc_pending_count@PAGEOFF]
	cbz	x8, LBB36_4
; %bb.3:
	mov	w0, #32                         ; =0x20
	bl	_minyar_rc_poll
	b	LBB36_5
LBB36_4:
	adrp	x8, _rc_bounded_last_work@PAGE
	str	xzr, [x8, _rc_bounded_last_work@PAGEOFF]
LBB36_5:
	lsl	x20, x19, #3
	add	x21, x20, #16
	mov	x0, x21
	bl	_minyar_pool_allocate
	mov	x22, x0
	mov	w8, #13                         ; =0xd
	str	x8, [x0], #16
Lloh121:
	adrp	x8, _rc_object_count@PAGE
	ldr	x9, [x8, _rc_object_count@PAGEOFF]
	add	x9, x9, #1
	str	x9, [x8, _rc_object_count@PAGEOFF]
Lloh122:
	adrp	x8, _rc_bytes@PAGE
	ldr	x9, [x8, _rc_bytes@PAGEOFF]
	add	x9, x9, x21
	str	x9, [x8, _rc_bytes@PAGEOFF]
	mov	x1, x20
	bl	_bzero
	str	x19, [x22, #8]!
	mov	x0, x22
	ldp	x29, x30, [sp, #32]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp, #16]             ; 16-byte Folded Reload
	ldp	x22, x21, [sp], #48             ; 16-byte Folded Reload
	ret
LBB36_6:
	bl	_minyar_record_new_scalar.cold.1
LBB36_7:
	bl	_out_of_memory
	.loh AdrpLdr	Lloh119, Lloh120
	.loh AdrpAdrp	Lloh121, Lloh122
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_record_get              ; -- Begin function minyar_record_get
	.p2align	2
_minyar_record_get:                     ; @minyar_record_get
	.cfi_startproc
; %bb.0:
	ldr	x8, [x0]
	cmp	x8, x1
	b.ls	LBB37_2
; %bb.1:
	add	x8, x0, x1, lsl #3
	ldr	x0, [x8, #8]
	ret
LBB37_2:
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
	b.ls	LBB38_2
; %bb.1:
	add	x8, x0, x1, lsl #3
	str	x2, [x8, #8]
	ret
LBB38_2:
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
	b.ls	LBB39_4
; %bb.1:
	add	x8, x0, x1, lsl #3
	str	x2, [x8, #8]
	ldur	x8, [x0, #-8]
	and	x8, x8, #0x7
	cmp	x8, #4
	b.ne	LBB39_3
; %bb.2:
	mov	w0, #32                         ; =0x20
	b	_minyar_rc_poll
LBB39_3:
	ret
LBB39_4:
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
	b.ls	LBB40_5
; %bb.1:
	add	x9, x0, #8
	add	x8, x9, x8, lsl #3
	mov	w10, #1                         ; =0x1
	strb	w10, [x8, x1]
	ldr	x8, [x0]
	cmp	x8, x1
	b.ls	LBB40_5
; %bb.2:
	str	x2, [x9, x1, lsl #3]
	ldur	x8, [x0, #-8]
	and	x8, x8, #0x7
	cmp	x8, #4
	b.ne	LBB40_4
; %bb.3:
	mov	w0, #32                         ; =0x20
	ldp	x29, x30, [sp], #16             ; 16-byte Folded Reload
	b	_minyar_rc_poll
LBB40_4:
	ldp	x29, x30, [sp], #16             ; 16-byte Folded Reload
	ret
LBB40_5:
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
	cbz	x2, LBB41_4
; %bb.1:
	ldur	x8, [x2, #-8]
	cmp	x8, #8
	b.lo	LBB41_4
; %bb.2:
	cmn	x8, #8
	b.hs	LBB41_10
; %bb.3:
	add	x8, x8, #8
	stur	x8, [x2, #-8]
LBB41_4:
	ldr	x8, [x0]
	cmp	x8, x1
	b.ls	LBB41_9
; %bb.5:
	add	x9, x0, #8
	add	x8, x9, x8, lsl #3
	mov	w10, #1                         ; =0x1
	strb	w10, [x8, x1]
	ldr	x8, [x0]
	cmp	x8, x1
	b.ls	LBB41_9
; %bb.6:
	str	x2, [x9, x1, lsl #3]
	ldur	x8, [x0, #-8]
	and	x8, x8, #0x7
	cmp	x8, #4
	b.ne	LBB41_8
; %bb.7:
	mov	w0, #32                         ; =0x20
	ldp	x29, x30, [sp], #16             ; 16-byte Folded Reload
	b	_minyar_rc_poll
LBB41_8:
	ldp	x29, x30, [sp], #16             ; 16-byte Folded Reload
	ret
LBB41_9:
	mov	x0, x1
	mov	x1, x8
	bl	_list_position_stop
LBB41_10:
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
	b.ls	LBB42_9
; %bb.1:
	cbz	x2, LBB42_6
; %bb.2:
	cbnz	x3, LBB42_6
; %bb.3:
	ldur	x8, [x2, #-8]
	cmp	x8, #8
	b.lo	LBB42_6
; %bb.4:
	cmn	x8, #8
	b.hs	LBB42_10
; %bb.5:
	add	x8, x8, #8
	stur	x8, [x2, #-8]
LBB42_6:
	add	x8, x0, x1, lsl #3
	ldr	x0, [x8, #8]
	str	x2, [x8, #8]
	bl	_rc_drop
	mov	x19, x0
Lloh123:
	adrp	x8, _rc_pending_count@PAGE
Lloh124:
	ldr	x8, [x8, _rc_pending_count@PAGEOFF]
	adrp	x20, _rc_bounded_last_work@PAGE
	cbz	x8, LBB42_8
; %bb.7:
	mov	w8, #32                         ; =0x20
	sub	w0, w8, w19
	bl	_minyar_rc_poll
	ldr	x8, [x20, _rc_bounded_last_work@PAGEOFF]
LBB42_8:
	add	x8, x8, w19, uxtw
	str	x8, [x20, _rc_bounded_last_work@PAGEOFF]
	ldp	x29, x30, [sp, #16]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp], #32             ; 16-byte Folded Reload
	ret
LBB42_9:
	mov	x0, x1
	mov	x1, x8
	bl	_list_position_stop
LBB42_10:
	bl	_minyar_record_replace.cold.1
	.loh AdrpLdr	Lloh123, Lloh124
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
Lloh125:
	adrp	x20, ___stdoutp@GOTPAGE
Lloh126:
	ldr	x20, [x20, ___stdoutp@GOTPAGEOFF]
	ldr	x3, [x20]
	mov	w1, #1                          ; =0x1
	bl	_fwrite
	ldr	x8, [x19, #8]
	cmp	x0, x8
	b.ne	LBB43_4
; %bb.1:
	mov	w0, #10                         ; =0xa
	bl	_putchar
	cmn	w0, #1
	b.eq	LBB43_4
; %bb.2:
	ldr	x0, [x20]
	bl	_fflush
	cmn	w0, #1
	b.eq	LBB43_4
; %bb.3:
	ldp	x29, x30, [sp, #16]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp], #32             ; 16-byte Folded Reload
	ret
LBB43_4:
	bl	_output_error
	.loh AdrpLdrGot	Lloh125, Lloh126
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
Lloh127:
	adrp	x0, l_.str.54@PAGE
Lloh128:
	add	x0, x0, l_.str.54@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh127, Lloh128
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
Lloh129:
	adrp	x20, ___stderrp@GOTPAGE
Lloh130:
	ldr	x20, [x20, ___stderrp@GOTPAGEOFF]
	ldr	x1, [x20]
Lloh131:
	adrp	x0, l_.str.4@PAGE
Lloh132:
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
	.loh AdrpAdd	Lloh131, Lloh132
	.loh AdrpLdrGot	Lloh129, Lloh130
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
Lloh133:
	adrp	x0, l_.str.5@PAGE
Lloh134:
	add	x0, x0, l_.str.5@PAGEOFF
	bl	_printf
	tbnz	w0, #31, LBB46_3
; %bb.1:
Lloh135:
	adrp	x8, ___stdoutp@GOTPAGE
Lloh136:
	ldr	x8, [x8, ___stdoutp@GOTPAGEOFF]
Lloh137:
	ldr	x0, [x8]
	bl	_fflush
	cmn	w0, #1
	b.eq	LBB46_3
; %bb.2:
	ldp	x29, x30, [sp, #16]             ; 16-byte Folded Reload
	add	sp, sp, #32
	ret
LBB46_3:
	bl	_output_error
	.loh AdrpAdd	Lloh133, Lloh134
	.loh AdrpLdrGotLdr	Lloh135, Lloh136, Lloh137
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
	b.hi	LBB47_14
; %bb.1:
	and	w9, w0, #0x1ff800
	mov	w10, #55296                     ; =0xd800
	cmp	w9, w10
	b.eq	LBB47_14
; %bb.2:
	cmp	w0, #127
	b.hi	LBB47_4
; %bb.3:
	strb	w0, [sp, #12]
	mov	w19, #1                         ; =0x1
	b	LBB47_9
LBB47_4:
	cmp	w0, #2047
	b.hi	LBB47_6
; %bb.5:
	lsr	w8, w0, #6
	orr	w8, w8, #0xc0
	strb	w8, [sp, #12]
	mov	w8, #128                        ; =0x80
	bfxil	w8, w0, #0, #6
	strb	w8, [sp, #13]
	mov	w19, #2                         ; =0x2
	b	LBB47_9
LBB47_6:
	cbnz	w8, LBB47_8
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
	b	LBB47_9
LBB47_8:
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
LBB47_9:
Lloh138:
	adrp	x20, ___stdoutp@GOTPAGE
Lloh139:
	ldr	x20, [x20, ___stdoutp@GOTPAGEOFF]
	ldr	x3, [x20]
	add	x0, sp, #12
	mov	w1, #1                          ; =0x1
	mov	x2, x19
	bl	_fwrite
	cmp	x0, x19
	b.ne	LBB47_13
; %bb.10:
	mov	w0, #10                         ; =0xa
	bl	_putchar
	cmn	w0, #1
	b.eq	LBB47_13
; %bb.11:
	ldr	x0, [x20]
	bl	_fflush
	cmn	w0, #1
	b.eq	LBB47_13
; %bb.12:
	ldp	x29, x30, [sp, #32]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp, #16]             ; 16-byte Folded Reload
	add	sp, sp, #48
	ret
LBB47_13:
	bl	_output_error
LBB47_14:
	bl	_minyar_print_character.cold.1
	.loh AdrpLdrGot	Lloh138, Lloh139
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
Lloh140:
	adrp	x8, l_.str.7@PAGE
Lloh141:
	add	x8, x8, l_.str.7@PAGEOFF
Lloh142:
	adrp	x9, l_.str.6@PAGE
Lloh143:
	add	x9, x9, l_.str.6@PAGEOFF
	cmp	w0, #0
	csel	x0, x9, x8, ne
	bl	_puts
	cmn	w0, #1
	b.eq	LBB48_3
; %bb.1:
Lloh144:
	adrp	x8, ___stdoutp@GOTPAGE
Lloh145:
	ldr	x8, [x8, ___stdoutp@GOTPAGEOFF]
Lloh146:
	ldr	x0, [x8]
	bl	_fflush
	cmn	w0, #1
	b.eq	LBB48_3
; %bb.2:
	ldp	x29, x30, [sp], #16             ; 16-byte Folded Reload
	ret
LBB48_3:
	bl	_output_error
	.loh AdrpAdd	Lloh142, Lloh143
	.loh AdrpAdd	Lloh140, Lloh141
	.loh AdrpLdrGotLdr	Lloh144, Lloh145, Lloh146
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_texts_are_equal         ; -- Begin function minyar_texts_are_equal
	.p2align	2
_minyar_texts_are_equal:                ; @minyar_texts_are_equal
	.cfi_startproc
; %bb.0:
	cmp	x0, x1
	b.eq	LBB49_14
; %bb.1:
	ldr	x2, [x0, #8]
	ldr	x8, [x1, #8]
	cmp	x2, x8
	b.ne	LBB49_4
; %bb.2:
	ldr	x0, [x0]
	ldr	x1, [x1]
	cmp	x2, #17
	b.lo	LBB49_5
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
LBB49_4:
	mov	w0, #0                          ; =0x0
	ret
LBB49_5:
	cmp	x2, #8
	b.lo	LBB49_7
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
LBB49_7:
	cmp	x2, #4
	b.lo	LBB49_9
; %bb.8:
	ldr	w8, [x0]
	ldr	w9, [x1]
	add	x10, x0, x2
	ldur	w10, [x10, #-4]
	add	x11, x1, x2
	ldur	w11, [x11, #-4]
	b	LBB49_11
LBB49_9:
	cmp	x2, #2
	b.lo	LBB49_12
; %bb.10:
	ldrh	w8, [x0]
	ldrh	w9, [x1]
	add	x10, x0, x2
	ldurh	w10, [x10, #-2]
	and	w10, w10, #0xffff
	add	x11, x1, x2
	ldurh	w11, [x11, #-2]
	and	w11, w11, #0xffff
LBB49_11:
	cmp	w8, w9
	ccmp	w10, w11, #0, eq
	cset	w0, eq
	ret
LBB49_12:
	cbz	x2, LBB49_14
; %bb.13:
	ldrb	w8, [x0]
	ldrb	w9, [x1]
	cmp	w8, w9
	cset	w0, eq
	ret
LBB49_14:
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
	b.gt	LBB50_2
; %bb.1:
	b	_join_by_copying
LBB50_2:
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
Lloh147:
	adrp	x0, l_.str.55@PAGE
Lloh148:
	add	x0, x0, l_.str.55@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh147, Lloh148
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
	add	x23, x9, x8
	add	x24, x23, #1
	adrp	x25, _rc_pending_count@PAGE
	ldr	x8, [x25, _rc_pending_count@PAGEOFF]
	cbz	x8, LBB52_6
; %bb.1:
	mov	w0, #32                         ; =0x20
	bl	_minyar_rc_poll
	cmn	x24, #8
	b.hs	LBB52_7
LBB52_2:
	add	x22, x23, #9
	mov	x0, x22
	bl	_minyar_pool_allocate
	mov	x19, x0
	str	x24, [x19], #8
	adrp	x24, _rc_bytes@PAGE
	ldr	x8, [x24, _rc_bytes@PAGEOFF]
	add	x8, x8, x22
	str	x8, [x24, _rc_bytes@PAGEOFF]
	ldp	x1, x2, [x21]
	cmp	x2, #17
	b.lo	LBB52_4
; %bb.3:
	mov	x0, x19
	bl	_memcpy
	b	LBB52_14
LBB52_4:
	cmp	x2, #8
	b.lo	LBB52_8
; %bb.5:
	ldr	x8, [x1]
	add	x9, x1, x2
	ldur	x9, [x9, #-8]
	str	x8, [x19]
	add	x8, x19, x2
	stur	x9, [x8, #-8]
	b	LBB52_14
LBB52_6:
	adrp	x8, _rc_bounded_last_work@PAGE
	str	xzr, [x8, _rc_bounded_last_work@PAGEOFF]
	cmn	x24, #8
	b.lo	LBB52_2
LBB52_7:
	bl	_out_of_memory
LBB52_8:
	cmp	x2, #4
	b.lo	LBB52_10
; %bb.9:
	ldr	w8, [x1]
	add	x9, x1, x2
	ldur	w9, [x9, #-4]
	str	w8, [x19]
	add	x8, x19, x2
	stur	w9, [x8, #-4]
	b	LBB52_14
LBB52_10:
	cmp	x2, #2
	b.lo	LBB52_12
; %bb.11:
	ldrh	w8, [x1]
	add	x9, x1, x2
	ldurh	w9, [x9, #-2]
	strh	w8, [x19]
	add	x8, x19, x2
	sturh	w9, [x8, #-2]
	b	LBB52_14
LBB52_12:
	cmp	x2, #1
	b.ne	LBB52_14
; %bb.13:
	ldrb	w8, [x1]
	strb	w8, [x19]
LBB52_14:
	ldr	x8, [x21, #8]
	add	x0, x19, x8
	ldp	x1, x2, [x20]
	cmp	x2, #17
	b.lo	LBB52_16
; %bb.15:
	bl	_memcpy
	b	LBB52_24
LBB52_16:
	cmp	x2, #8
	b.lo	LBB52_18
; %bb.17:
	ldr	x8, [x1]
	add	x9, x1, x2
	ldur	x9, [x9, #-8]
	str	x8, [x0]
	add	x8, x0, x2
	stur	x9, [x8, #-8]
	b	LBB52_24
LBB52_18:
	cmp	x2, #4
	b.lo	LBB52_20
; %bb.19:
	ldr	w8, [x1]
	add	x9, x1, x2
	ldur	w9, [x9, #-4]
	str	w8, [x0]
	add	x8, x0, x2
	stur	w9, [x8, #-4]
	b	LBB52_24
LBB52_20:
	cmp	x2, #2
	b.lo	LBB52_22
; %bb.21:
	ldrh	w8, [x1]
	add	x9, x1, x2
	ldurh	w9, [x9, #-2]
	strh	w8, [x0]
	add	x8, x0, x2
	sturh	w9, [x8, #-2]
	b	LBB52_24
LBB52_22:
	cmp	x2, #1
	b.ne	LBB52_24
; %bb.23:
	ldrb	w8, [x1]
	strb	w8, [x0]
LBB52_24:
	strb	wzr, [x19, x23]
	ldp	x9, x8, [x21, #8]
	cmp	x8, x9
	b.ne	LBB52_27
; %bb.25:
	ldp	x9, x8, [x20, #8]
	cmp	x8, x9
	csinv	x20, x23, xzr, eq
	ldr	x8, [x25, _rc_pending_count@PAGEOFF]
	cbz	x8, LBB52_28
LBB52_26:
	mov	w0, #32                         ; =0x20
	bl	_minyar_rc_poll
	b	LBB52_29
LBB52_27:
	mov	x20, #-1                        ; =0xffffffffffffffff
	ldr	x8, [x25, _rc_pending_count@PAGEOFF]
	cbnz	x8, LBB52_26
LBB52_28:
	adrp	x8, _rc_bounded_last_work@PAGE
	str	xzr, [x8, _rc_bounded_last_work@PAGEOFF]
LBB52_29:
	mov	w0, #48                         ; =0x30
	bl	_minyar_pool_allocate
	mov	w8, #9                          ; =0x9
	str	x8, [x0]
	adrp	x8, _rc_object_count@PAGE
	ldr	x9, [x8, _rc_object_count@PAGEOFF]
	add	x9, x9, #1
	str	x9, [x8, _rc_object_count@PAGEOFF]
	ldr	x8, [x24, _rc_bytes@PAGEOFF]
	add	x8, x8, #48
	str	x8, [x24, _rc_bytes@PAGEOFF]
	stp	x23, x20, [x0, #16]
	stp	xzr, xzr, [x0, #32]
	str	x19, [x0, #8]!
	ldp	x29, x30, [sp, #64]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp, #48]             ; 16-byte Folded Reload
	ldp	x22, x21, [sp, #32]             ; 16-byte Folded Reload
	ldp	x24, x23, [sp, #16]             ; 16-byte Folded Reload
	ldp	x26, x25, [sp], #80             ; 16-byte Folded Reload
	ret
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
	b.gt	LBB53_27
; %bb.1:
	ldur	x8, [x0, #-8]
	cmp	x8, #9
	b.ne	LBB53_3
; %bb.2:
	ldr	x8, [x0, #32]
	cbz	x8, LBB53_7
LBB53_3:
	mov	x20, x0
	bl	_join_by_copying
	mov	x19, x0
	mov	x0, x20
	bl	_rc_drop
	mov	x20, x0
Lloh149:
	adrp	x8, _rc_pending_count@PAGE
Lloh150:
	ldr	x8, [x8, _rc_pending_count@PAGEOFF]
	adrp	x21, _rc_bounded_last_work@PAGE
	cbz	x8, LBB53_5
; %bb.4:
	mov	w8, #32                         ; =0x20
	sub	w0, w8, w20
	bl	_minyar_rc_poll
	ldr	x8, [x21, _rc_bounded_last_work@PAGEOFF]
LBB53_5:
	add	x8, x8, w20, uxtw
	str	x8, [x21, _rc_bounded_last_work@PAGEOFF]
	mov	x0, x19
LBB53_6:
	ldp	x29, x30, [sp, #48]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp, #32]             ; 16-byte Folded Reload
	ldp	x22, x21, [sp, #16]             ; 16-byte Folded Reload
	ldp	x24, x23, [sp], #64             ; 16-byte Folded Reload
	ret
LBB53_7:
	add	x22, x19, x21
	ldr	x20, [x0]
	add	x8, x22, #1
	ldur	x9, [x20, #-8]
	cmp	x8, x9
	mov	x23, x0
	mov	x24, x1
	b.ls	LBB53_9
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
LBB53_9:
	mov	x8, x20
	cmp	x1, x0
	b.eq	LBB53_11
; %bb.10:
	ldr	x8, [x1]
LBB53_11:
	add	x9, x20, x21
	cmp	x19, #17
	b.lo	LBB53_13
; %bb.12:
	mov	x0, x9
	mov	x1, x8
	mov	x2, x19
	bl	_memcpy
	mov	x1, x24
	mov	x0, x23
	b	LBB53_21
LBB53_13:
	cmp	x19, #8
	b.lo	LBB53_15
; %bb.14:
	ldr	x10, [x8]
	add	x8, x8, x19
	ldur	x8, [x8, #-8]
	str	x10, [x9]
	add	x9, x9, x19
	stur	x8, [x9, #-8]
	b	LBB53_21
LBB53_15:
	cmp	x19, #4
	b.lo	LBB53_17
; %bb.16:
	ldr	w10, [x8]
	add	x8, x8, x19
	ldur	w8, [x8, #-4]
	str	w10, [x9]
	add	x9, x9, x19
	stur	w8, [x9, #-4]
	b	LBB53_21
LBB53_17:
	cmp	x19, #2
	b.lo	LBB53_19
; %bb.18:
	ldrh	w10, [x8]
	add	x8, x8, x19
	ldurh	w8, [x8, #-2]
	strh	w10, [x9]
	add	x9, x9, x19
	sturh	w8, [x9, #-2]
	b	LBB53_21
LBB53_19:
	cmp	x19, #1
	b.ne	LBB53_21
; %bb.20:
	ldrb	w8, [x8]
	strb	w8, [x9]
LBB53_21:
	strb	wzr, [x20, x22]
	ldr	x8, [x0, #24]
	cbz	x8, LBB53_23
; %bb.22:
	ldr	x9, [x8, #-8]!
	adrp	x10, _rc_bytes@PAGE
	ldr	x11, [x10, _rc_bytes@PAGEOFF]
	sub	x9, x11, x9
	sub	x9, x9, #8
	str	x9, [x10, _rc_bytes@PAGEOFF]
	mov	x0, x8
	bl	_minyar_pool_deallocate
	mov	x1, x24
	mov	x0, x23
LBB53_23:
	stp	x20, x22, [x0]
	ldr	x8, [x0, #16]
	cmp	x8, x21
	b.ne	LBB53_25
; %bb.24:
	ldr	x8, [x1, #16]
	cmp	x8, x19
	b.eq	LBB53_26
LBB53_25:
	mov	x22, #-1                        ; =0xffffffffffffffff
LBB53_26:
	stp	x22, xzr, [x0, #16]
	b	LBB53_6
LBB53_27:
	bl	_join_too_large
	.loh AdrpLdr	Lloh149, Lloh150
	.cfi_endproc
                                        ; -- End function
	.p2align	2                               ; -- Begin function rc_reallocate_data
_rc_reallocate_data:                    ; @rc_reallocate_data
	.cfi_startproc
; %bb.0:
	sub	sp, sp, #128
	stp	x28, x27, [sp, #32]             ; 16-byte Folded Spill
	stp	x26, x25, [sp, #48]             ; 16-byte Folded Spill
	stp	x24, x23, [sp, #64]             ; 16-byte Folded Spill
	stp	x22, x21, [sp, #80]             ; 16-byte Folded Spill
	stp	x20, x19, [sp, #96]             ; 16-byte Folded Spill
	stp	x29, x30, [sp, #112]            ; 16-byte Folded Spill
	add	x29, sp, #112
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
	mov	x19, x1
Lloh151:
	adrp	x8, _rc_pending_count@PAGE
Lloh152:
	ldr	x8, [x8, _rc_pending_count@PAGEOFF]
	adrp	x23, _rc_bytes@PAGE
	cbz	x0, LBB54_3
; %bb.1:
	mov	x20, x0
	cbz	x8, LBB54_5
; %bb.2:
	mov	w0, #32                         ; =0x20
	bl	_minyar_rc_poll
	cmn	x19, #8
	b.lo	LBB54_6
	b	LBB54_23
LBB54_3:
	cbz	x8, LBB54_19
; %bb.4:
	mov	w0, #32                         ; =0x20
	bl	_minyar_rc_poll
	cmn	x19, #8
	b.lo	LBB54_20
	b	LBB54_23
LBB54_5:
	adrp	x8, _rc_bounded_last_work@PAGE
	str	xzr, [x8, _rc_bounded_last_work@PAGEOFF]
	cmn	x19, #8
	b.hs	LBB54_23
LBB54_6:
	ldr	x22, [x20, #-8]!
	ldr	x8, [x23, _rc_bytes@PAGEOFF]
	sub	x8, x8, x22
	str	x8, [x23, _rc_bytes@PAGEOFF]
	adrp	x24, _minyar_pool_last_steps@PAGE
	str	xzr, [x24, _minyar_pool_last_steps@PAGEOFF]
Lloh153:
	adrp	x9, _minyar_pool@PAGE
Lloh154:
	add	x9, x9, _minyar_pool@PAGEOFF
	subs	x8, x20, x9
	b.lo	LBB54_22
; %bb.7:
	mov	w10, #16777216                  ; =0x1000000
	add	x9, x9, x10
	cmp	x20, x9
	b.hs	LBB54_22
; %bb.8:
	tst	x8, #0x1f
	b.ne	LBB54_22
; %bb.9:
	lsr	x9, x8, #5
Lloh155:
	adrp	x10, _minyar_pool_map@PAGE
Lloh156:
	add	x10, x10, _minyar_pool_map@PAGEOFF
	ldrsb	w9, [x10, x9]
	tbz	w9, #31, LBB54_24
; %bb.10:
	mov	w10, #16777208                  ; =0xfffff8
	cmp	x19, x10
	b.hi	LBB54_25
; %bb.11:
	add	x21, x19, #8
	and	w9, w9, #0xff
	and	w9, w9, #0x7f
	sub	w9, w9, #1
	mov	w10, #32                        ; =0x20
	lsl	x10, x10, x9
	cmp	x19, #25
	b.lo	LBB54_15
; %bb.12:
	mov	x11, #0                         ; =0x0
	mov	w12, #32                        ; =0x20
LBB54_13:                               ; =>This Inner Loop Header: Depth=1
	lsl	x12, x12, #1
	add	x11, x11, #1
	cmp	x12, x21
	b.lo	LBB54_13
; %bb.14:
	str	x11, [x24, _minyar_pool_last_steps@PAGEOFF]
	b	LBB54_16
LBB54_15:
	mov	w11, #0                         ; =0x0
	mov	w12, #32                        ; =0x20
LBB54_16:
	stp	w9, w11, [sp]
	stp	x10, x12, [sp, #8]
	str	x8, [sp, #24]
	mov	x1, sp
	mov	x0, x20
	bl	_pool_try_resize_same_base
	ldr	x26, [x24, _minyar_pool_last_steps@PAGEOFF]
	adrp	x25, _minyar_pool_max_steps@PAGE
	ldr	x8, [x25, _minyar_pool_max_steps@PAGEOFF]
	cmp	x26, x8
	csel	x8, x26, x8, hi
	cbnz	x0, LBB54_18
; %bb.17:
	add	x27, x22, #8
	str	x8, [x25, _minyar_pool_max_steps@PAGEOFF]
	mov	x0, x21
	bl	_minyar_pool_allocate
	mov	x22, x0
	ldr	x8, [x24, _minyar_pool_last_steps@PAGEOFF]
	add	x26, x8, x26
	cmp	x27, x21
	csel	x2, x27, x21, lo
	mov	x1, x20
	bl	_memcpy
	mov	x0, x20
	bl	_minyar_pool_deallocate
	mov	x0, x22
	ldr	x8, [x24, _minyar_pool_last_steps@PAGEOFF]
	ldr	x9, [x25, _minyar_pool_max_steps@PAGEOFF]
	add	x8, x26, x8
	cmp	x8, x9
	str	x8, [x24, _minyar_pool_last_steps@PAGEOFF]
	csel	x8, x8, x9, hi
LBB54_18:
	str	x8, [x25, _minyar_pool_max_steps@PAGEOFF]
	mov	x20, x19
	b	LBB54_21
LBB54_19:
	adrp	x8, _rc_bounded_last_work@PAGE
	str	xzr, [x8, _rc_bounded_last_work@PAGEOFF]
	cmn	x19, #8
	b.hs	LBB54_23
LBB54_20:
	add	x20, x19, #8
	mov	x0, x20
	bl	_minyar_pool_allocate
LBB54_21:
	str	x19, [x0], #8
	ldr	x8, [x23, _rc_bytes@PAGEOFF]
	add	x8, x8, x20
	str	x8, [x23, _rc_bytes@PAGEOFF]
	ldp	x29, x30, [sp, #112]            ; 16-byte Folded Reload
	ldp	x20, x19, [sp, #96]             ; 16-byte Folded Reload
	ldp	x22, x21, [sp, #80]             ; 16-byte Folded Reload
	ldp	x24, x23, [sp, #64]             ; 16-byte Folded Reload
	ldp	x26, x25, [sp, #48]             ; 16-byte Folded Reload
	ldp	x28, x27, [sp, #32]             ; 16-byte Folded Reload
	add	sp, sp, #128
	ret
LBB54_22:
	bl	_rc_reallocate_data.cold.3
LBB54_23:
	bl	_out_of_memory
LBB54_24:
	bl	_rc_reallocate_data.cold.2
LBB54_25:
	bl	_rc_reallocate_data.cold.1
	.loh AdrpLdr	Lloh151, Lloh152
	.loh AdrpAdd	Lloh153, Lloh154
	.loh AdrpAdd	Lloh155, Lloh156
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
	mov	x19, x0
	ldr	x8, [x0, #8]
	cmp	x8, #1
	b.lt	LBB55_4
; %bb.1:
	mov	x22, #0                         ; =0x0
	ldr	x9, [x19]
LBB55_2:                                ; =>This Inner Loop Header: Depth=1
	ldr	x10, [x9], #8
	ldr	x10, [x10, #8]
	eor	x11, x22, #0x7fffffffffffffff
	cmp	x10, x11
	b.gt	LBB55_26
; %bb.3:                                ;   in Loop: Header=BB55_2 Depth=1
	add	x22, x10, x22
	subs	x8, x8, #1
	b.ne	LBB55_2
	b	LBB55_5
LBB55_4:
	mov	x22, #0                         ; =0x0
LBB55_5:
	add	x23, x22, #1
	adrp	x24, _rc_pending_count@PAGE
	ldr	x8, [x24, _rc_pending_count@PAGEOFF]
	cbz	x8, LBB55_22
; %bb.6:
	mov	w0, #32                         ; =0x20
	bl	_minyar_rc_poll
	cmn	x23, #8
	b.hs	LBB55_23
LBB55_7:
	add	x21, x22, #9
	mov	x0, x21
	bl	_minyar_pool_allocate
	mov	x20, x0
	str	x23, [x20], #8
	adrp	x23, _rc_bytes@PAGE
	ldr	x8, [x23, _rc_bytes@PAGEOFF]
	add	x8, x8, x21
	str	x8, [x23, _rc_bytes@PAGEOFF]
	ldr	x8, [x19, #8]
	cmp	x8, #1
	b.lt	LBB55_20
; %bb.8:
	mov	x21, #0                         ; =0x0
	mov	x25, #0                         ; =0x0
	b	LBB55_11
LBB55_9:                                ;   in Loop: Header=BB55_11 Depth=1
	bl	_memcpy
LBB55_10:                               ;   in Loop: Header=BB55_11 Depth=1
	ldr	x8, [x26, #8]
	add	x25, x8, x25
	add	x21, x21, #1
	ldr	x8, [x19, #8]
	cmp	x21, x8
	b.ge	LBB55_20
LBB55_11:                               ; =>This Inner Loop Header: Depth=1
	ldr	x8, [x19]
	ldr	x26, [x8, x21, lsl #3]
	add	x0, x20, x25
	ldp	x1, x2, [x26]
	cmp	x2, #17
	b.hs	LBB55_9
; %bb.12:                               ;   in Loop: Header=BB55_11 Depth=1
	cmp	x2, #8
	b.lo	LBB55_14
; %bb.13:                               ;   in Loop: Header=BB55_11 Depth=1
	ldr	x8, [x1]
	add	x9, x1, x2
	ldur	x9, [x9, #-8]
	str	x8, [x0]
	add	x8, x0, x2
	stur	x9, [x8, #-8]
	b	LBB55_10
LBB55_14:                               ;   in Loop: Header=BB55_11 Depth=1
	cmp	x2, #4
	b.lo	LBB55_16
; %bb.15:                               ;   in Loop: Header=BB55_11 Depth=1
	ldr	w8, [x1]
	add	x9, x1, x2
	ldur	w9, [x9, #-4]
	str	w8, [x0]
	add	x8, x0, x2
	stur	w9, [x8, #-4]
	b	LBB55_10
LBB55_16:                               ;   in Loop: Header=BB55_11 Depth=1
	cmp	x2, #2
	b.lo	LBB55_18
; %bb.17:                               ;   in Loop: Header=BB55_11 Depth=1
	ldrh	w8, [x1]
	add	x9, x1, x2
	ldurh	w9, [x9, #-2]
	strh	w8, [x0]
	add	x8, x0, x2
	sturh	w9, [x8, #-2]
	b	LBB55_10
LBB55_18:                               ;   in Loop: Header=BB55_11 Depth=1
	cmp	x2, #1
	b.ne	LBB55_10
; %bb.19:                               ;   in Loop: Header=BB55_11 Depth=1
	ldrb	w8, [x1]
	strb	w8, [x0]
	b	LBB55_10
LBB55_20:
	strb	wzr, [x20, x22]
	ldr	x8, [x24, _rc_pending_count@PAGEOFF]
	cbz	x8, LBB55_24
; %bb.21:
	mov	w0, #32                         ; =0x20
	bl	_minyar_rc_poll
	b	LBB55_25
LBB55_22:
	adrp	x8, _rc_bounded_last_work@PAGE
	str	xzr, [x8, _rc_bounded_last_work@PAGEOFF]
	cmn	x23, #8
	b.lo	LBB55_7
LBB55_23:
	bl	_out_of_memory
LBB55_24:
	adrp	x8, _rc_bounded_last_work@PAGE
	str	xzr, [x8, _rc_bounded_last_work@PAGEOFF]
LBB55_25:
	mov	w0, #48                         ; =0x30
	bl	_minyar_pool_allocate
	mov	w8, #9                          ; =0x9
	str	x8, [x0]
	adrp	x8, _rc_object_count@PAGE
	ldr	x9, [x8, _rc_object_count@PAGEOFF]
	add	x9, x9, #1
	str	x9, [x8, _rc_object_count@PAGEOFF]
	ldr	x8, [x23, _rc_bytes@PAGEOFF]
	add	x8, x8, #48
	str	x8, [x23, _rc_bytes@PAGEOFF]
	mov	x8, #-1                         ; =0xffffffffffffffff
	stp	x22, x8, [x0, #16]
	stp	xzr, xzr, [x0, #32]
	str	x20, [x0, #8]!
	ldp	x29, x30, [sp, #64]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp, #48]             ; 16-byte Folded Reload
	ldp	x22, x21, [sp, #32]             ; 16-byte Folded Reload
	ldp	x24, x23, [sp, #16]             ; 16-byte Folded Reload
	ldp	x26, x25, [sp], #80             ; 16-byte Folded Reload
	ret
LBB55_26:
	bl	_join_too_large
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
	tbnz	x0, #63, LBB56_2
LBB56_1:
	ldp	x29, x30, [sp, #16]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp], #32             ; 16-byte Folded Reload
	ret
LBB56_2:
	mov	x0, x19
	bl	_build_text_index
	ldr	x0, [x19, #16]
	b	LBB56_1
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
	tbnz	x8, #63, LBB58_4
; %bb.1:
	cmp	x8, x1
	b.ls	LBB58_4
; %bb.2:
	ldr	x8, [x0, #24]
	cbnz	x8, LBB58_5
; %bb.3:
	ldr	x8, [x0]
	ldrb	w0, [x8, x1]
	ret
LBB58_4:
	b	_character_at_slowly
LBB58_5:
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
	tbnz	x1, #63, LBB59_7
; %bb.1:
	mov	x19, x1
	mov	x20, x0
	ldr	x8, [x0, #16]
	tbnz	x8, #63, LBB59_5
LBB59_2:
	cmp	x8, x19
	b.le	LBB59_8
; %bb.3:
	ldr	x8, [x20, #24]
	cbnz	x8, LBB59_6
; %bb.4:
	ldr	x8, [x20]
	ldrb	w0, [x8, x19]
	ldp	x29, x30, [sp, #16]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp], #32             ; 16-byte Folded Reload
	ret
LBB59_5:
	mov	x0, x20
	bl	_build_text_index
	ldr	x8, [x20, #16]
	b	LBB59_2
LBB59_6:
	mov	x0, x20
	mov	x1, x19
	ldp	x29, x30, [sp, #16]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp], #32             ; 16-byte Folded Reload
	b	_indexed_character_at
LBB59_7:
	bl	_negative_text_position
LBB59_8:
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
	b.gt	LBB60_2
; %bb.1:
	ldr	x8, [x20, #24]
	str	w10, [x8, x9, lsl #2]
	add	x9, x11, #2
	ldr	x10, [sp, #8]
	add	x10, x10, x19
	b	LBB60_3
LBB60_2:
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
	b.gt	LBB60_4
LBB60_3:
	str	w10, [x8, x9, lsl #2]
	b	LBB60_5
LBB60_4:
	str	x10, [x8, x9, lsl #3]
LBB60_5:
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
	mov	x19, x2
	mov	x21, x1
	mov	x20, x0
	ldr	x8, [x0, #16]
	tbnz	x8, #63, LBB61_27
; %bb.1:
	tbnz	x21, #63, LBB61_28
LBB61_2:
	subs	x24, x19, x21
	b.lt	LBB61_28
; %bb.3:
	ldr	x8, [x20, #16]
	cmp	x8, x19
	b.lt	LBB61_28
; %bb.4:
	ldr	x8, [x20, #24]
	cbz	x8, LBB61_6
; %bb.5:
	mov	x0, x20
	mov	x1, x21
	bl	_indexed_byte_offset
	mov	x21, x0
	mov	x0, x20
	mov	x1, x19
	bl	_indexed_byte_offset
	mov	x19, x0
LBB61_6:
	sub	x19, x19, x21
	ldr	x8, [x20, #32]
	cmp	x8, #0
	csel	x22, x20, x8, eq
	cbnz	x21, LBB61_11
; %bb.7:
	ldr	x8, [x20, #8]
	cmp	x19, x8
	b.ne	LBB61_11
; %bb.8:
	ldur	x8, [x20, #-8]
	cmp	x8, #8
	b.lo	LBB61_26
; %bb.9:
	cmn	x8, #8
	b.hs	LBB61_30
; %bb.10:
	add	x8, x8, #8
	stur	x8, [x20, #-8]
	b	LBB61_26
LBB61_11:
	ldr	x8, [x22, #8]
	lsl	x9, x19, #3
	cmp	x8, #1, lsl #12                 ; =4096
	ccmp	x9, x8, #2, gt
	b.lo	LBB61_14
; %bb.12:
	ldr	x8, [x20]
	add	x21, x8, x21
	cmp	x19, x24
	csinv	x20, x24, xzr, eq
Lloh157:
	adrp	x8, _rc_pending_count@PAGE
Lloh158:
	ldr	x8, [x8, _rc_pending_count@PAGEOFF]
	cbz	x8, LBB61_18
; %bb.13:
	mov	w0, #32                         ; =0x20
	bl	_minyar_rc_poll
	b	LBB61_19
LBB61_14:
	add	x25, x19, #1
	adrp	x26, _rc_pending_count@PAGE
	ldr	x8, [x26, _rc_pending_count@PAGEOFF]
	cbz	x8, LBB61_22
; %bb.15:
	mov	w0, #32                         ; =0x20
	bl	_minyar_rc_poll
	cmn	x25, #8
	b.hs	LBB61_23
LBB61_16:
	add	x23, x19, #9
	mov	x0, x23
	bl	_minyar_pool_allocate
	mov	x22, x0
	str	x25, [x22], #8
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
	csinv	x20, x24, xzr, eq
	ldr	x8, [x26, _rc_pending_count@PAGEOFF]
	cbz	x8, LBB61_24
; %bb.17:
	mov	w0, #32                         ; =0x20
	bl	_minyar_rc_poll
	b	LBB61_25
LBB61_18:
	adrp	x8, _rc_bounded_last_work@PAGE
	str	xzr, [x8, _rc_bounded_last_work@PAGEOFF]
LBB61_19:
	mov	w0, #48                         ; =0x30
	bl	_minyar_pool_allocate
	mov	w8, #9                          ; =0x9
	str	x8, [x0]
Lloh159:
	adrp	x8, _rc_object_count@PAGE
	ldr	x9, [x8, _rc_object_count@PAGEOFF]
	add	x9, x9, #1
	str	x9, [x8, _rc_object_count@PAGEOFF]
Lloh160:
	adrp	x8, _rc_bytes@PAGE
	ldr	x9, [x8, _rc_bytes@PAGEOFF]
	add	x9, x9, #48
	str	x9, [x8, _rc_bytes@PAGEOFF]
	stp	x19, x20, [x0, #16]
	stp	xzr, x22, [x0, #32]
	mov	x20, x0
	str	x21, [x20, #8]!
	ldur	x8, [x22, #-8]
	cmp	x8, #8
	b.lo	LBB61_26
; %bb.20:
	cmn	x8, #8
	b.hs	LBB61_29
; %bb.21:
	add	x8, x8, #8
	stur	x8, [x22, #-8]
	b	LBB61_26
LBB61_22:
	adrp	x8, _rc_bounded_last_work@PAGE
	str	xzr, [x8, _rc_bounded_last_work@PAGEOFF]
	cmn	x25, #8
	b.lo	LBB61_16
LBB61_23:
	bl	_out_of_memory
LBB61_24:
	adrp	x8, _rc_bounded_last_work@PAGE
	str	xzr, [x8, _rc_bounded_last_work@PAGEOFF]
LBB61_25:
	mov	w0, #48                         ; =0x30
	bl	_minyar_pool_allocate
	mov	w8, #9                          ; =0x9
	str	x8, [x0]
	adrp	x8, _rc_object_count@PAGE
	ldr	x9, [x8, _rc_object_count@PAGEOFF]
	add	x9, x9, #1
	str	x9, [x8, _rc_object_count@PAGEOFF]
	ldr	x8, [x25, _rc_bytes@PAGEOFF]
	add	x8, x8, #48
	str	x8, [x25, _rc_bytes@PAGEOFF]
	stp	x19, x20, [x0, #16]
	stp	xzr, xzr, [x0, #32]
	mov	x20, x0
	str	x22, [x20, #8]!
LBB61_26:
	mov	x0, x20
	ldp	x29, x30, [sp, #64]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp, #48]             ; 16-byte Folded Reload
	ldp	x22, x21, [sp, #32]             ; 16-byte Folded Reload
	ldp	x24, x23, [sp, #16]             ; 16-byte Folded Reload
	ldp	x26, x25, [sp], #80             ; 16-byte Folded Reload
	ret
LBB61_27:
	mov	x0, x20
	bl	_build_text_index
	tbz	x21, #63, LBB61_2
LBB61_28:
	bl	_slice_outside_text
LBB61_29:
	bl	_minyar_text_slice.cold.1
LBB61_30:
	bl	_minyar_text_slice.cold.2
	.loh AdrpLdr	Lloh157, Lloh158
	.loh AdrpAdrp	Lloh159, Lloh160
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
Lloh161:
	adrp	x0, l_.str.60@PAGE
Lloh162:
	add	x0, x0, l_.str.60@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh161, Lloh162
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
	b.gt	LBB63_2
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
	b	LBB63_3
LBB63_2:
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
LBB63_3:
	cmp	x10, x9
	cset	w11, ge
	cmp	x10, x19
	cset	w12, le
	tst	w11, w12
	csel	x11, x0, x23, ne
	csel	x12, x10, x9, ne
	subs	x13, x10, x19
	b.gt	LBB63_5
; %bb.4:
	mov	x23, x11
	mov	x9, x12
	b	LBB63_6
LBB63_5:
	and	x11, x19, #0x3f
	cmp	x13, x11
	b.le	LBB63_11
LBB63_6:
	subs	x24, x19, x9
	b.le	LBB63_10
; %bb.7:
	adrp	x25, _text_decode_count@PAGE
LBB63_8:                                ; =>This Inner Loop Header: Depth=1
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
	b.ne	LBB63_8
; %bb.9:
	ldr	x8, [x20, #8]
LBB63_10:
	mov	x0, x23
	b	LBB63_15
LBB63_11:
	adrp	x9, _text_decode_count@PAGE
	ldr	x11, [x9, _text_decode_count@PAGEOFF]
	ldr	x12, [x20]
	add	x11, x10, x11
	sub	x12, x12, #1
LBB63_12:                               ; =>This Inner Loop Header: Depth=1
	ldrb	w13, [x12, x0]
	sub	x0, x0, #1
	and	w13, w13, #0xc0
	cmp	w13, #128
	b.eq	LBB63_12
; %bb.13:                               ;   in Loop: Header=BB63_12 Depth=1
	sub	x10, x10, #1
	cmp	x10, x19
	b.gt	LBB63_12
; %bb.14:
	sub	x10, x11, x19
	str	x10, [x9, _text_decode_count@PAGEOFF]
LBB63_15:
	mov	w9, #-1                         ; =0xffffffff
	cmp	x8, x9
	b.gt	LBB63_17
; %bb.16:
	ldr	x8, [x20, #24]
	str	w19, [x8, x22, lsl #2]
	str	w0, [x8, x21, lsl #2]
	b	LBB63_20
LBB63_17:
	ldr	x8, [x20, #24]
	str	x19, [x8, x22, lsl #3]
	ldr	x9, [x20, #8]
	mov	w10, #-1                        ; =0xffffffff
	cmp	x9, x10
	b.gt	LBB63_19
; %bb.18:
	str	w0, [x8, x21, lsl #2]
	b	LBB63_20
LBB63_19:
	str	x0, [x8, x21, lsl #3]
LBB63_20:
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
	cbnz	x9, LBB64_3
; %bb.1:
Lloh163:
	adrp	x20, _minyar_integer_text.integer_cache@PAGE
Lloh164:
	add	x20, x20, _minyar_integer_text.integer_cache@PAGEOFF
	ldr	x0, [x20, x19, lsl #3]
	cbz	x0, LBB64_4
LBB64_2:
	ldp	x29, x30, [sp, #16]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp], #32             ; 16-byte Folded Reload
	ret
LBB64_3:
	mov	x0, x19
	ldp	x29, x30, [sp, #16]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp], #32             ; 16-byte Folded Reload
	b	_format_integer_text
LBB64_4:
	mov	x0, x19
	bl	_format_integer_text
	str	x0, [x20, x19, lsl #3]
	mov	w8, #1                          ; =0x1
	stur	x8, [x0, #-8]
	adrp	x8, _rc_immortal_object_count@PAGE
	ldr	x9, [x8, _rc_immortal_object_count@PAGEOFF]
	add	x9, x9, #1
	str	x9, [x8, _rc_immortal_object_count@PAGEOFF]
	b	LBB64_2
	.loh AdrpAdd	Lloh163, Lloh164
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
Lloh165:
	adrp	x8, ___stack_chk_guard@GOTPAGE
Lloh166:
	ldr	x8, [x8, ___stack_chk_guard@GOTPAGEOFF]
Lloh167:
	ldr	x8, [x8]
	str	x8, [sp, #40]
	add	x10, sp, #8
	add	x8, x10, #32
	cmp	x0, #0
	cneg	x9, x0, mi
	add	x19, x10, #31
	mov	w10, #10                        ; =0xa
LBB65_1:                                ; =>This Inner Loop Header: Depth=1
	udiv	x11, x9, x10
	msub	w12, w11, w10, w9
	orr	w12, w12, #0x30
	strb	w12, [x19], #-1
	cmp	x9, #9
	mov	x9, x11
	b.hi	LBB65_1
; %bb.2:
	tbnz	x0, #63, LBB65_4
; %bb.3:
	add	x19, x19, #1
	b	LBB65_5
LBB65_4:
	mov	w9, #45                         ; =0x2d
	strb	w9, [x19]
LBB65_5:
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
Lloh168:
	adrp	x9, ___stack_chk_guard@GOTPAGE
Lloh169:
	ldr	x9, [x9, ___stack_chk_guard@GOTPAGEOFF]
Lloh170:
	ldr	x9, [x9]
	cmp	x9, x8
	b.ne	LBB65_7
; %bb.6:
	ldp	x29, x30, [sp, #80]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp, #64]             ; 16-byte Folded Reload
	ldp	x22, x21, [sp, #48]             ; 16-byte Folded Reload
	add	sp, sp, #96
	ret
LBB65_7:
	bl	___stack_chk_fail
	.loh AdrpLdrGotLdr	Lloh165, Lloh166, Lloh167
	.loh AdrpLdrGotLdr	Lloh168, Lloh169, Lloh170
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_character_text          ; -- Begin function minyar_character_text
	.p2align	2
_minyar_character_text:                 ; @minyar_character_text
	.cfi_startproc
; %bb.0:
	cmp	w0, #127
	b.hi	LBB66_4
; %bb.1:
Lloh171:
	adrp	x8, _minyar_character_text.ascii_texts@PAGE
Lloh172:
	add	x8, x8, _minyar_character_text.ascii_texts@PAGEOFF
	mov	w9, #48                         ; =0x30
	umaddl	x8, w0, w9, x8
	ldr	x9, [x8, #16]
	cbz	x9, LBB66_3
; %bb.2:
	add	x0, x8, #8
	ret
LBB66_3:
	mov	w9, w0
Lloh173:
	adrp	x10, _minyar_character_text.ascii_bytes@PAGE
Lloh174:
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
LBB66_4:
	b	_encode_character_text
	.loh AdrpAdd	Lloh171, Lloh172
	.loh AdrpAdd	Lloh173, Lloh174
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
	b.eq	LBB67_9
; %bb.1:
	cmp	w0, #127
	b.hi	LBB67_3
; %bb.2:
	strb	w0, [sp, #12]
	mov	w19, #1                         ; =0x1
	b	LBB67_8
LBB67_3:
	cmp	w0, #2047
	b.hi	LBB67_5
; %bb.4:
	lsr	w8, w0, #6
	orr	w8, w8, #0xc0
	strb	w8, [sp, #12]
	mov	w8, #128                        ; =0x80
	bfxil	w8, w0, #0, #6
	strb	w8, [sp, #13]
	mov	w19, #2                         ; =0x2
	b	LBB67_8
LBB67_5:
	cbnz	w8, LBB67_7
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
	b	LBB67_8
LBB67_7:
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
LBB67_8:
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
LBB67_9:
Lloh175:
	adrp	x0, l_.str.61@PAGE
Lloh176:
	add	x0, x0, l_.str.61@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh175, Lloh176
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_boolean_text            ; -- Begin function minyar_boolean_text
	.p2align	2
_minyar_boolean_text:                   ; @minyar_boolean_text
	.cfi_startproc
; %bb.0:
Lloh177:
	adrp	x8, l_.str.7@PAGE
Lloh178:
	add	x8, x8, l_.str.7@PAGEOFF
Lloh179:
	adrp	x9, l_.str.6@PAGE
Lloh180:
	add	x9, x9, l_.str.6@PAGEOFF
	cmp	w0, #0
	csel	x0, x9, x8, ne
	b	_copy_c_text
	.loh AdrpAdd	Lloh179, Lloh180
	.loh AdrpAdd	Lloh177, Lloh178
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
	cbz	x8, LBB69_4
; %bb.1:
	mov	w0, #32                         ; =0x20
	bl	_minyar_rc_poll
	cmn	x22, #8
	b.hs	LBB69_5
LBB69_2:
	add	x23, x19, #9
	mov	x0, x23
	bl	_minyar_pool_allocate
	mov	x20, x0
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
	cbz	x8, LBB69_6
; %bb.3:
	mov	w0, #32                         ; =0x20
	bl	_minyar_rc_poll
	b	LBB69_7
LBB69_4:
	adrp	x8, _rc_bounded_last_work@PAGE
	str	xzr, [x8, _rc_bounded_last_work@PAGEOFF]
	cmn	x22, #8
	b.lo	LBB69_2
LBB69_5:
	bl	_out_of_memory
LBB69_6:
	adrp	x8, _rc_bounded_last_work@PAGE
	str	xzr, [x8, _rc_bounded_last_work@PAGEOFF]
LBB69_7:
	mov	w0, #48                         ; =0x30
	bl	_minyar_pool_allocate
	mov	w8, #9                          ; =0x9
	str	x8, [x0]
	adrp	x8, _rc_object_count@PAGE
	ldr	x9, [x8, _rc_object_count@PAGEOFF]
	add	x9, x9, #1
	str	x9, [x8, _rc_object_count@PAGEOFF]
	ldr	x8, [x24, _rc_bytes@PAGEOFF]
	add	x8, x8, #48
	str	x8, [x24, _rc_bytes@PAGEOFF]
	mov	x8, #-1                         ; =0xffffffffffffffff
	stp	x19, x8, [x0, #16]
	stp	xzr, xzr, [x0, #32]
	str	x20, [x0, #8]!
	ldp	x29, x30, [sp, #64]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp, #48]             ; 16-byte Folded Reload
	ldp	x22, x21, [sp, #32]             ; 16-byte Folded Reload
	ldp	x24, x23, [sp, #16]             ; 16-byte Folded Reload
	ldp	x26, x25, [sp], #80             ; 16-byte Folded Reload
	ret
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_initialize_arguments    ; -- Begin function minyar_initialize_arguments
	.p2align	2
_minyar_initialize_arguments:           ; @minyar_initialize_arguments
	.cfi_startproc
; %bb.0:
Lloh181:
	adrp	x8, _saved_argument_count@PAGE
	str	w0, [x8, _saved_argument_count@PAGEOFF]
Lloh182:
	adrp	x8, _saved_argument_values@PAGE
	str	x1, [x8, _saved_argument_values@PAGEOFF]
	mov	w0, #13                         ; =0xd
	mov	w1, #1                          ; =0x1
	b	_signal
	.loh AdrpAdrp	Lloh181, Lloh182
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_argument_count          ; -- Begin function minyar_argument_count
	.p2align	2
_minyar_argument_count:                 ; @minyar_argument_count
	.cfi_startproc
; %bb.0:
Lloh183:
	adrp	x8, _saved_argument_count@PAGE
Lloh184:
	ldr	w8, [x8, _saved_argument_count@PAGEOFF]
	sub	w9, w8, #1
	cmp	w8, #0
	csel	w8, w9, wzr, gt
	sxtw	x0, w8
	ret
	.loh AdrpLdr	Lloh183, Lloh184
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_argument                ; -- Begin function minyar_argument
	.p2align	2
_minyar_argument:                       ; @minyar_argument
	.cfi_startproc
; %bb.0:
	tbnz	x0, #63, LBB72_3
; %bb.1:
Lloh185:
	adrp	x8, _saved_argument_count@PAGE
Lloh186:
	ldr	w8, [x8, _saved_argument_count@PAGEOFF]
	sub	w9, w8, #1
	cmp	w8, #0
	csel	w8, w9, wzr, gt
	sxtw	x8, w8
	cmp	x8, x0
	b.le	LBB72_3
; %bb.2:
Lloh187:
	adrp	x8, _saved_argument_values@PAGE
Lloh188:
	ldr	x8, [x8, _saved_argument_values@PAGEOFF]
	add	x8, x8, x0, lsl #3
	ldr	x0, [x8, #8]
	b	_copy_c_text
LBB72_3:
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
	bl	_minyar_argument.cold.1
	.loh AdrpLdr	Lloh185, Lloh186
	.loh AdrpLdr	Lloh187, Lloh188
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
	mov	x19, x0
	ldr	x0, [x0]
	ldr	x20, [x19, #8]
	mov	w1, #0                          ; =0x0
	mov	x2, x20
	bl	_memchr
	cbnz	x0, LBB73_10
; %bb.1:
	add	x0, x20, #1
	bl	_minyar_pool_allocate
	mov	x20, x0
	ldp	x1, x2, [x19]
	bl	_memcpy
	ldr	x8, [x19, #8]
	strb	wzr, [x20, x8]
Lloh189:
	adrp	x1, l_.str.9@PAGE
Lloh190:
	add	x1, x1, l_.str.9@PAGEOFF
	mov	x0, x20
	bl	_fopen
	cbz	x0, LBB73_11
; %bb.2:
	mov	x22, x0
	bl	_text_file_length
	mov	x19, x0
	add	x24, x0, #1
	adrp	x25, _rc_pending_count@PAGE
	ldr	x8, [x25, _rc_pending_count@PAGEOFF]
	cbz	x8, LBB73_4
; %bb.3:
	mov	w0, #32                         ; =0x20
	bl	_minyar_rc_poll
	b	LBB73_5
LBB73_4:
	adrp	x8, _rc_bounded_last_work@PAGE
	str	xzr, [x8, _rc_bounded_last_work@PAGEOFF]
LBB73_5:
	add	x23, x19, #9
	mov	x0, x23
	bl	_minyar_pool_allocate
	mov	x21, x0
	str	x24, [x21], #8
	adrp	x24, _rc_bytes@PAGE
	ldr	x8, [x24, _rc_bytes@PAGEOFF]
	add	x8, x8, x23
	str	x8, [x24, _rc_bytes@PAGEOFF]
	mov	x0, x21
	mov	w1, #1                          ; =0x1
	mov	x2, x19
	mov	x3, x22
	bl	_fread
	cmp	x0, x19
	b.ne	LBB73_12
; %bb.6:
	mov	x0, x22
	bl	_fclose
	mov	x0, x20
	bl	_minyar_pool_deallocate
	strb	wzr, [x21, x19]
	ldr	x8, [x25, _rc_pending_count@PAGEOFF]
	cbz	x8, LBB73_8
; %bb.7:
	mov	w0, #32                         ; =0x20
	bl	_minyar_rc_poll
	b	LBB73_9
LBB73_8:
	adrp	x8, _rc_bounded_last_work@PAGE
	str	xzr, [x8, _rc_bounded_last_work@PAGEOFF]
LBB73_9:
	mov	w0, #48                         ; =0x30
	bl	_minyar_pool_allocate
	mov	w8, #9                          ; =0x9
	str	x8, [x0]
	adrp	x8, _rc_object_count@PAGE
	ldr	x9, [x8, _rc_object_count@PAGEOFF]
	add	x9, x9, #1
	str	x9, [x8, _rc_object_count@PAGEOFF]
	ldr	x8, [x24, _rc_bytes@PAGEOFF]
	add	x8, x8, #48
	str	x8, [x24, _rc_bytes@PAGEOFF]
	mov	x8, #-1                         ; =0xffffffffffffffff
	stp	x19, x8, [x0, #16]
	stp	xzr, xzr, [x0, #32]
	str	x21, [x0, #8]!
	ldp	x29, x30, [sp, #80]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp, #64]             ; 16-byte Folded Reload
	ldp	x22, x21, [sp, #48]             ; 16-byte Folded Reload
	ldp	x24, x23, [sp, #32]             ; 16-byte Folded Reload
	ldp	x26, x25, [sp, #16]             ; 16-byte Folded Reload
	add	sp, sp, #96
	ret
LBB73_10:
	bl	_minyar_read_text_file.cold.1
LBB73_11:
Lloh191:
	adrp	x8, ___stderrp@GOTPAGE
Lloh192:
	ldr	x8, [x8, ___stderrp@GOTPAGEOFF]
Lloh193:
	ldr	x0, [x8]
	str	x20, [sp]
Lloh194:
	adrp	x1, l_.str.10@PAGE
Lloh195:
	add	x1, x1, l_.str.10@PAGEOFF
	bl	_fprintf
	mov	x0, x20
	bl	_minyar_pool_deallocate
	mov	w0, #1                          ; =0x1
	bl	_exit
LBB73_12:
	bl	_minyar_read_text_file.cold.2
	.loh AdrpAdd	Lloh189, Lloh190
	.loh AdrpAdd	Lloh194, Lloh195
	.loh AdrpLdrGotLdr	Lloh191, Lloh192, Lloh193
	.cfi_endproc
                                        ; -- End function
	.p2align	2                               ; -- Begin function minyar_pool_deallocate
_minyar_pool_deallocate:                ; @minyar_pool_deallocate
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
	adrp	x11, _minyar_pool_last_steps@PAGE
	str	xzr, [x11, _minyar_pool_last_steps@PAGEOFF]
	cbz	x0, LBB74_19
; %bb.1:
Lloh196:
	adrp	x10, _minyar_pool@PAGE
Lloh197:
	add	x10, x10, _minyar_pool@PAGEOFF
	subs	x8, x0, x10
	b.lo	LBB74_20
; %bb.2:
	mov	w9, #16777216                   ; =0x1000000
	add	x9, x10, x9
	cmp	x0, x9
	b.hs	LBB74_20
; %bb.3:
	tst	x8, #0x1f
	b.ne	LBB74_20
; %bb.4:
	lsr	x12, x8, #5
Lloh198:
	adrp	x9, _minyar_pool_map@PAGE
Lloh199:
	add	x9, x9, _minyar_pool_map@PAGEOFF
	ldrsb	w13, [x9, x12]
	tbz	w13, #31, LBB74_21
; %bb.5:
	and	w0, w13, #0xff
	and	w15, w0, #0x7f
	sub	w17, w15, #1
	mov	x13, #-32                       ; =0xffffffffffffffe0
	lsl	x13, x13, x17
Lloh200:
	adrp	x14, _minyar_pool_used@PAGE
	ldr	x16, [x14, _minyar_pool_used@PAGEOFF]
	add	x13, x16, x13
	str	x13, [x14, _minyar_pool_used@PAGEOFF]
	strb	wzr, [x9, x12]
Lloh201:
	adrp	x12, _minyar_pool_max_order@PAGE
Lloh202:
	ldr	w16, [x12, _minyar_pool_max_order@PAGEOFF]
Lloh203:
	adrp	x12, _minyar_pool_mask@PAGE
	ldr	x13, [x12, _minyar_pool_mask@PAGEOFF]
Lloh204:
	adrp	x14, _minyar_pool_free@PAGE
Lloh205:
	add	x14, x14, _minyar_pool_free@PAGEOFF
	cmp	w17, w16
	b.hs	LBB74_13
; %bb.6:
	mov	x2, #0                          ; =0x0
	sub	w15, w16, w15
	add	x15, x15, #1
	add	x1, x14, x17, lsl #3
	and	x3, x0, #0x7f
	neg	w4, w16
	add	x3, x3, x4
	sub	x3, x3, #1
	mov	w4, #32                         ; =0x20
	mov	w5, #1                          ; =0x1
	mov	x6, #-1                         ; =0xffffffffffffffff
	b	LBB74_8
LBB74_7:                                ;   in Loop: Header=BB74_8 Depth=1
	ldr	x2, [x1, x2, lsl #3]
	lsl	x21, x5, x21
	cmp	x2, #0
	csinv	x2, x6, x21, ne
	and	x13, x13, x2
	strb	wzr, [x9, x20]
	bic	x8, x8, x19
	mov	x2, x7
	cmn	w3, w7
	b.eq	LBB74_15
LBB74_8:                                ; =>This Inner Loop Header: Depth=1
	add	x21, x17, x2
	lsl	x19, x4, x21
	eor	x22, x19, x8
	add	x7, x2, #1
	lsr	x20, x22, #5
	ldrb	w23, [x9, x20]
	add	x24, x21, #1
	cmp	x24, x23
	b.ne	LBB74_14
; %bb.9:                                ;   in Loop: Header=BB74_8 Depth=1
	add	x23, x10, x22
	ldp	x22, x23, [x23]
	cbz	x22, LBB74_11
; %bb.10:                               ;   in Loop: Header=BB74_8 Depth=1
	str	x23, [x22, #8]
	cbnz	x23, LBB74_12
	b	LBB74_7
LBB74_11:                               ;   in Loop: Header=BB74_8 Depth=1
	str	x23, [x1, x2, lsl #3]
	cbz	x23, LBB74_7
LBB74_12:                               ;   in Loop: Header=BB74_8 Depth=1
	str	x22, [x23]
	b	LBB74_7
LBB74_13:
	mov	x15, #0                         ; =0x0
	mov	x16, x17
	b	LBB74_16
LBB74_14:
	and	w15, w0, #0x7f
	add	w15, w15, w2
	sub	w16, w15, #1
	mov	x15, x7
LBB74_15:
	str	x15, [x11, _minyar_pool_last_steps@PAGEOFF]
LBB74_16:
	add	x11, x10, x8
	ldr	x17, [x14, w16, uxtw #3]
	mov	w10, w16
	stp	xzr, x17, [x11]
	cbz	x17, LBB74_18
; %bb.17:
	str	x11, [x17]
LBB74_18:
	str	x11, [x14, x10, lsl #3]
	mov	w11, #1                         ; =0x1
	lsl	x11, x11, x10
	orr	x11, x13, x11
	add	w10, w10, #1
	lsr	x8, x8, #5
	strb	w10, [x9, x8]
	str	x11, [x12, _minyar_pool_mask@PAGEOFF]
	adrp	x8, _minyar_pool_max_steps@PAGE
	ldr	x9, [x8, _minyar_pool_max_steps@PAGEOFF]
	cmp	x15, x9
	csel	x9, x15, x9, hi
	str	x9, [x8, _minyar_pool_max_steps@PAGEOFF]
LBB74_19:
	ldp	x29, x30, [sp, #48]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp, #32]             ; 16-byte Folded Reload
	ldp	x22, x21, [sp, #16]             ; 16-byte Folded Reload
	ldp	x24, x23, [sp], #64             ; 16-byte Folded Reload
	ret
LBB74_20:
	bl	_minyar_pool_deallocate.cold.2
LBB74_21:
	bl	_minyar_pool_deallocate.cold.1
	.loh AdrpAdd	Lloh196, Lloh197
	.loh AdrpAdd	Lloh198, Lloh199
	.loh AdrpAdd	Lloh204, Lloh205
	.loh AdrpAdrp	Lloh201, Lloh203
	.loh AdrpLdr	Lloh201, Lloh202
	.loh AdrpAdrp	Lloh200, Lloh204
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
	b.ne	LBB75_2
; %bb.1:
	mov	x0, x19
	bl	_ferror
	cbnz	w0, LBB75_7
LBB75_2:
	mov	x0, x19
	mov	x1, #0                          ; =0x0
	mov	w2, #2                          ; =0x2
	bl	_fseek
	cbnz	w0, LBB75_6
; %bb.3:
	mov	x0, x19
	bl	_ftell
	tbnz	x0, #63, LBB75_6
; %bb.4:
	mov	x20, x0
	mov	x0, x19
	mov	x1, #0                          ; =0x0
	mov	w2, #0                          ; =0x0
	bl	_fseek
	cbnz	w0, LBB75_6
; %bb.5:
	mov	x0, x20
	ldp	x29, x30, [sp, #16]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp], #32             ; 16-byte Folded Reload
	ret
LBB75_6:
	bl	_text_file_length.cold.2
LBB75_7:
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
	mov	x20, x0
	ldr	x0, [x0]
	ldr	x21, [x20, #8]
	mov	w1, #0                          ; =0x0
	mov	x2, x21
	bl	_memchr
	cbnz	x0, LBB76_6
; %bb.1:
	add	x0, x21, #1
	bl	_minyar_pool_allocate
	mov	x21, x0
	ldp	x1, x2, [x20]
	bl	_memcpy
	ldr	x8, [x20, #8]
	strb	wzr, [x21, x8]
Lloh206:
	adrp	x1, l_.str.12@PAGE
Lloh207:
	add	x1, x1, l_.str.12@PAGEOFF
	mov	x0, x21
	bl	_fopen
	mov	x20, x0
	mov	x0, x21
	bl	_minyar_pool_deallocate
	cbz	x20, LBB76_7
; %bb.2:
	ldp	x0, x2, [x19]
	mov	w1, #1                          ; =0x1
	mov	x3, x20
	bl	_fwrite
	ldr	x8, [x19, #8]
	cmp	x0, x8
	b.ne	LBB76_5
; %bb.3:
	mov	x0, x20
	bl	_fclose
	cbnz	w0, LBB76_5
; %bb.4:
	ldp	x29, x30, [sp, #32]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp, #16]             ; 16-byte Folded Reload
	ldp	x22, x21, [sp], #48             ; 16-byte Folded Reload
	ret
LBB76_5:
	bl	_minyar_write_text_file.cold.2
LBB76_6:
	bl	_minyar_write_text_file.cold.1
LBB76_7:
	bl	_minyar_write_text_file.cold.3
	.loh AdrpAdd	Lloh206, Lloh207
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
Lloh208:
	adrp	x8, ___stderrp@GOTPAGE
Lloh209:
	ldr	x8, [x8, ___stderrp@GOTPAGEOFF]
Lloh210:
	ldr	x1, [x8]
Lloh211:
	adrp	x0, l_.str.15@PAGE
Lloh212:
	add	x0, x0, l_.str.15@PAGEOFF
	bl	_fputs
	bl	_OUTLINED_FUNCTION_0
	.loh AdrpAdd	Lloh211, Lloh212
	.loh AdrpLdrGotLdr	Lloh208, Lloh209, Lloh210
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_check_integer_overflow  ; -- Begin function minyar_check_integer_overflow
	.p2align	2
_minyar_check_integer_overflow:         ; @minyar_check_integer_overflow
	.cfi_startproc
; %bb.0:
	cbnz	w0, LBB78_2
; %bb.1:
	ret
LBB78_2:
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
Lloh213:
	adrp	x8, l_.str.17@PAGE
Lloh214:
	add	x8, x8, l_.str.17@PAGEOFF
Lloh215:
	adrp	x9, l_.str.16@PAGE
Lloh216:
	add	x9, x9, l_.str.16@PAGEOFF
	cmp	x0, #0
	csel	x0, x9, x8, eq
	bl	_integer_division_stop
	.loh AdrpAdd	Lloh215, Lloh216
	.loh AdrpAdd	Lloh213, Lloh214
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
Lloh217:
	adrp	x20, ___stderrp@GOTPAGE
Lloh218:
	ldr	x20, [x20, ___stderrp@GOTPAGEOFF]
	ldr	x1, [x20]
Lloh219:
	adrp	x0, l_.str.4@PAGE
Lloh220:
	add	x0, x0, l_.str.4@PAGEOFF
	bl	_fputs
	ldr	x1, [x20]
	mov	x0, x19
	bl	_fputs
	ldr	x1, [x20]
	mov	w0, #10                         ; =0xa
	bl	_fputc
	bl	_OUTLINED_FUNCTION_0
	.loh AdrpAdd	Lloh219, Lloh220
	.loh AdrpLdrGot	Lloh217, Lloh218
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_check_integer_division  ; -- Begin function minyar_check_integer_division
	.p2align	2
_minyar_check_integer_division:         ; @minyar_check_integer_division
	.cfi_startproc
; %bb.0:
	cbz	x1, LBB81_4
; %bb.1:
	mov	x8, #-9223372036854775808       ; =0x8000000000000000
	cmp	x0, x8
	b.ne	LBB81_3
; %bb.2:
	cmn	x1, #1
	b.eq	LBB81_4
LBB81_3:
	ret
LBB81_4:
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
Lloh221:
	adrp	x8, ___stack_chk_guard@GOTPAGE
Lloh222:
	ldr	x8, [x8, ___stack_chk_guard@GOTPAGEOFF]
Lloh223:
	ldr	x8, [x8]
	stur	x8, [x29, #-8]
	add	x0, sp, #8
	bl	_format_float
	add	x0, sp, #8
	bl	_puts
	cmn	w0, #1
	b.eq	LBB82_4
; %bb.1:
Lloh224:
	adrp	x8, ___stdoutp@GOTPAGE
Lloh225:
	ldr	x8, [x8, ___stdoutp@GOTPAGEOFF]
Lloh226:
	ldr	x0, [x8]
	bl	_fflush
	cmn	w0, #1
	b.eq	LBB82_4
; %bb.2:
	ldur	x8, [x29, #-8]
Lloh227:
	adrp	x9, ___stack_chk_guard@GOTPAGE
Lloh228:
	ldr	x9, [x9, ___stack_chk_guard@GOTPAGEOFF]
Lloh229:
	ldr	x9, [x9]
	cmp	x9, x8
	b.ne	LBB82_5
; %bb.3:
	ldp	x29, x30, [sp, #64]             ; 16-byte Folded Reload
	add	sp, sp, #80
	ret
LBB82_4:
	bl	_output_error
LBB82_5:
	bl	___stack_chk_fail
	.loh AdrpLdrGotLdr	Lloh221, Lloh222, Lloh223
	.loh AdrpLdrGotLdr	Lloh224, Lloh225, Lloh226
	.loh AdrpLdrGotLdr	Lloh227, Lloh228, Lloh229
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
Lloh230:
	adrp	x8, ___stack_chk_guard@GOTPAGE
Lloh231:
	ldr	x8, [x8, ___stack_chk_guard@GOTPAGEOFF]
Lloh232:
	ldr	x8, [x8]
	stur	x8, [x29, #-72]
	fcmp	d0, d0
	b.vs	LBB83_73
; %bb.1:
	fmov	d8, d0
	fabs	d0, d0
	mov	x8, #9218868437227405312        ; =0x7ff0000000000000
	fmov	d1, x8
	fcmp	d0, d1
	b.eq	LBB83_4
; %bb.2:
	fcmp	d8, #0.0
	b.ne	LBB83_8
; %bb.3:
	fmov	x8, d8
Lloh233:
	adrp	x9, l_.str.67@PAGE
Lloh234:
	add	x9, x9, l_.str.67@PAGEOFF
Lloh235:
	adrp	x10, l_.str.68@PAGE
Lloh236:
	add	x10, x10, l_.str.68@PAGEOFF
	cmp	x8, #0
	csel	x2, x10, x9, eq
	b	LBB83_5
LBB83_4:
Lloh237:
	adrp	x8, l_.str.66@PAGE
Lloh238:
	add	x8, x8, l_.str.66@PAGEOFF
Lloh239:
	adrp	x9, l_.str.65@PAGE
Lloh240:
	add	x9, x9, l_.str.65@PAGEOFF
	fcmp	d8, #0.0
	csel	x2, x9, x8, mi
LBB83_5:
	mov	w1, #48                         ; =0x30
	bl	_snprintf
                                        ; kill: def $w0 killed $w0 def $x0
	sxtw	x0, w0
LBB83_6:
	ldur	x8, [x29, #-72]
Lloh241:
	adrp	x9, ___stack_chk_guard@GOTPAGE
Lloh242:
	ldr	x9, [x9, ___stack_chk_guard@GOTPAGEOFF]
Lloh243:
	ldr	x9, [x9]
	cmp	x9, x8
	b.ne	LBB83_74
; %bb.7:
	ldp	x29, x30, [sp, #160]            ; 16-byte Folded Reload
	ldp	x20, x19, [sp, #144]            ; 16-byte Folded Reload
	ldp	x22, x21, [sp, #128]            ; 16-byte Folded Reload
	ldp	x24, x23, [sp, #112]            ; 16-byte Folded Reload
	ldp	d9, d8, [sp, #96]               ; 16-byte Folded Reload
	add	sp, sp, #176
	ret
LBB83_8:
	mov	x8, #4845873199050653696        ; =0x4340000000000000
	fmov	d1, x8
	fcmp	d0, d1
	fcvtzs	d0, d8
	scvtf	d0, d0
	fccmp	d0, d8, #0, mi
	b.eq	LBB83_42
; %bb.9:
	mov	x20, x0
	fmov	x8, d8
	tst	x8, #0xfffffffffffff
	cset	w9, eq
	tst	x8, #0x7fe0000000000000
	csel	w21, wzr, w9, eq
	str	d8, [sp, #8]
	str	xzr, [sp]
Lloh244:
	adrp	x19, l_.str.70@PAGE
Lloh245:
	add	x19, x19, l_.str.70@PAGEOFF
	add	x0, sp, #48
	mov	w1, #40                         ; =0x28
	mov	x2, x19
	bl	_snprintf
	mov	w22, #1                         ; =0x1
	b	LBB83_11
LBB83_10:                               ;   in Loop: Header=BB83_11 Depth=1
	add	w23, w22, #1
	str	d8, [sp, #8]
	str	x22, [sp]
	add	x0, sp, #48
	mov	w1, #40                         ; =0x28
	mov	x2, x19
	bl	_snprintf
	mov	x22, x23
	cmp	w23, #17
	b.eq	LBB83_15
LBB83_11:                               ; =>This Inner Loop Header: Depth=1
	add	x0, sp, #48
	mov	x1, #0                          ; =0x0
	bl	_strtod
	fcmp	d0, d8
	b.eq	LBB83_15
; %bb.12:                               ;   in Loop: Header=BB83_11 Depth=1
	cbz	w21, LBB83_10
; %bb.13:                               ;   in Loop: Header=BB83_11 Depth=1
	add	x0, sp, #48
	fmov	d0, d8
	mov	w1, #1                          ; =0x1
	bl	_adjacent_float_decimal
	tbnz	w0, #0, LBB83_15
; %bb.14:                               ;   in Loop: Header=BB83_11 Depth=1
	add	x0, sp, #48
	fmov	d0, d8
	mov	w1, #-1                         ; =0xffffffff
	bl	_adjacent_float_decimal
	tbz	w0, #0, LBB83_10
LBB83_15:
	mov	x21, #0                         ; =0x0
	ldrb	w19, [sp, #48]
	cmp	w19, #45
	add	x8, sp, #48
	cinc	x8, x8, eq
	add	x0, x8, #1
	add	x8, sp, #24
	b	LBB83_17
LBB83_16:                               ;   in Loop: Header=BB83_17 Depth=1
	add	x0, x0, #1
LBB83_17:                               ; =>This Inner Loop Header: Depth=1
	ldurb	w9, [x0, #-1]
	cbz	w9, LBB83_21
; %bb.18:                               ;   in Loop: Header=BB83_17 Depth=1
	cmp	w9, #101
	b.eq	LBB83_21
; %bb.19:                               ;   in Loop: Header=BB83_17 Depth=1
	sub	w10, w9, #48
	cmp	w10, #9
	b.hi	LBB83_16
; %bb.20:                               ;   in Loop: Header=BB83_17 Depth=1
	strb	w9, [x8, x21]
	add	x21, x21, #1
	b	LBB83_16
LBB83_21:
	bl	_atoi
                                        ; kill: def $w0 killed $w0 def $x0
	cmp	x21, #0
	cset	w9, ne
	add	x10, sp, #24
	mov	x8, x20
LBB83_22:                               ; =>This Inner Loop Header: Depth=1
	mov	x11, x21
	cmp	x21, #2
	b.lo	LBB83_25
; %bb.23:                               ;   in Loop: Header=BB83_22 Depth=1
	sub	x21, x11, #1
	add	x12, x10, x11
	ldurb	w12, [x12, #-1]
	cmp	w12, #48
	b.eq	LBB83_22
; %bb.24:
	add	x9, x21, #1
LBB83_25:
	cmp	w19, #45
	b.ne	LBB83_27
; %bb.26:
	mov	w10, #45                        ; =0x2d
	strb	w10, [x8]
	mov	w10, #1                         ; =0x1
	b	LBB83_28
LBB83_27:
	mov	x10, #0                         ; =0x0
LBB83_28:
	add	w12, w0, #7
	cmp	w12, #27
	b.hi	LBB83_37
; %bb.29:
	tbnz	w0, #31, LBB83_56
; %bb.30:
	mov	x11, #0                         ; =0x0
	mov	w12, w0
	add	x12, x12, #1
	add	x13, x8, x10
	add	x14, sp, #24
	b	LBB83_34
LBB83_31:                               ;   in Loop: Header=BB83_34 Depth=1
	ldrb	w15, [x14, x11]
LBB83_32:                               ;   in Loop: Header=BB83_34 Depth=1
	strb	w15, [x13, x11]
LBB83_33:                               ;   in Loop: Header=BB83_34 Depth=1
	add	x11, x11, #1
	cmp	x12, x11
	b.eq	LBB83_43
LBB83_34:                               ; =>This Inner Loop Header: Depth=1
	add	x15, x10, x11
	cmp	x15, #46
	b.hi	LBB83_33
; %bb.35:                               ;   in Loop: Header=BB83_34 Depth=1
	cmp	x9, x11
	b.hi	LBB83_31
; %bb.36:                               ;   in Loop: Header=BB83_34 Depth=1
	mov	w15, #48                        ; =0x30
	b	LBB83_32
LBB83_37:
	ldrb	w12, [sp, #24]
	add	x13, x8, x10
	strb	w12, [x13]
	orr	x12, x10, #0x2
	mov	w14, #46                        ; =0x2e
	strb	w14, [x13, #1]
	cmp	x11, #2
	b.lo	LBB83_50
; %bb.38:
	mov	w10, #2                         ; =0x2
	cmp	x9, #2
	csel	x9, x9, x10, hi
	sub	x9, x9, #1
	add	x10, sp, #24
	add	x10, x10, #1
	b	LBB83_40
LBB83_39:                               ;   in Loop: Header=BB83_40 Depth=1
	add	x10, x10, #1
	mov	x12, x19
	subs	x9, x9, #1
	b.eq	LBB83_51
LBB83_40:                               ; =>This Inner Loop Header: Depth=1
	add	x19, x12, #1
	cmp	x19, #47
	b.hi	LBB83_39
; %bb.41:                               ;   in Loop: Header=BB83_40 Depth=1
	ldrb	w11, [x10]
	strb	w11, [x8, x12]
	b	LBB83_39
LBB83_42:
	fcvtzs	x8, d8
	str	x8, [sp]
Lloh246:
	adrp	x2, l_.str.69@PAGE
Lloh247:
	add	x2, x2, l_.str.69@PAGEOFF
	b	LBB83_5
LBB83_43:
	add	x13, x10, x11
	sub	x13, x13, #1
	cmp	x13, #46
	b.hs	LBB83_45
; %bb.44:
	add	x14, x8, x10
	mov	w15, #46                        ; =0x2e
	strb	w15, [x14, x11]
LBB83_45:
	subs	x9, x9, x12
	b.ls	LBB83_62
; %bb.46:
	mov	x13, #0                         ; =0x0
	add	x14, sp, #24
	add	x12, x14, x12
	add	x14, x8, x10
	add	x15, x10, x11
	b	LBB83_48
LBB83_47:                               ;   in Loop: Header=BB83_48 Depth=1
	add	x13, x13, #1
	cmp	x9, x13
	b.eq	LBB83_64
LBB83_48:                               ; =>This Inner Loop Header: Depth=1
	add	x16, x15, x13
	add	x16, x16, #2
	cmp	x16, #47
	b.hi	LBB83_47
; %bb.49:                               ;   in Loop: Header=BB83_48 Depth=1
	ldrb	w16, [x12, x13]
	add	x17, x14, x13
	add	x17, x17, x11
	strb	w16, [x17, #1]
	b	LBB83_47
LBB83_50:
	add	x19, x10, #3
	mov	w9, #48                         ; =0x30
	strb	w9, [x8, x12]
LBB83_51:
	str	x0, [sp]
Lloh248:
	adrp	x2, l_.str.71@PAGE
Lloh249:
	add	x2, x2, l_.str.71@PAGEOFF
	add	x21, sp, #16
	add	x0, sp, #16
	mov	w1, #8                          ; =0x8
	bl	_snprintf
	ldrb	w10, [sp, #16]
	cbz	w10, LBB83_61
; %bb.52:
	add	x9, x21, #1
	mov	x8, x20
	b	LBB83_54
LBB83_53:                               ;   in Loop: Header=BB83_54 Depth=1
	ldrb	w10, [x9], #1
	mov	x19, x0
	cbz	w10, LBB83_72
LBB83_54:                               ; =>This Inner Loop Header: Depth=1
	add	x0, x19, #1
	cmp	x0, #47
	b.hi	LBB83_53
; %bb.55:                               ;   in Loop: Header=BB83_54 Depth=1
	strb	w10, [x8, x19]
	b	LBB83_53
LBB83_56:
	mov	w11, #11824                     ; =0x2e30
	strh	w11, [x8, x10]
	orr	x11, x10, #0x2
	cmn	w0, #1
	b.eq	LBB83_66
; %bb.57:
	sub	w10, w10, w0
	add	w10, w10, #1
	mov	w12, #48                        ; =0x30
	b	LBB83_59
LBB83_58:                               ;   in Loop: Header=BB83_59 Depth=1
	add	x11, x11, #1
	cmp	x10, x11
	b.eq	LBB83_65
LBB83_59:                               ; =>This Inner Loop Header: Depth=1
	cmp	x11, #46
	b.hi	LBB83_58
; %bb.60:                               ;   in Loop: Header=BB83_59 Depth=1
	strb	w12, [x8, x11]
	b	LBB83_58
LBB83_61:
	mov	x0, x19
	mov	x8, x20
	b	LBB83_72
LBB83_62:
	add	x9, x10, x11
	add	x0, x9, #2
	cmp	x13, #44
	b.hi	LBB83_72
; %bb.63:
	add	x9, x8, x10
	add	x9, x9, x11
	mov	w10, #48                        ; =0x30
	strb	w10, [x9, #1]
	b	LBB83_72
LBB83_64:
	add	x9, x10, x11
	add	x9, x9, x13
	add	x0, x9, #1
	b	LBB83_72
LBB83_65:
	mov	x11, x10
LBB83_66:
	cbz	x9, LBB83_71
; %bb.67:
	add	x10, sp, #24
	b	LBB83_69
LBB83_68:                               ;   in Loop: Header=BB83_69 Depth=1
	add	x10, x10, #1
	mov	x11, x0
	subs	x9, x9, #1
	b.eq	LBB83_72
LBB83_69:                               ; =>This Inner Loop Header: Depth=1
	add	x0, x11, #1
	cmp	x0, #47
	b.hi	LBB83_68
; %bb.70:                               ;   in Loop: Header=BB83_69 Depth=1
	ldrb	w12, [x10]
	strb	w12, [x8, x11]
	b	LBB83_68
LBB83_71:
	mov	x0, x11
LBB83_72:
	mov	w9, #47                         ; =0x2f
	cmp	x0, #47
	csel	x9, x0, x9, lo
	strb	wzr, [x8, x9]
	b	LBB83_6
LBB83_73:
	mov	w8, #24910                      ; =0x614e
	movk	w8, #78, lsl #16
	str	w8, [x0]
	mov	w0, #3                          ; =0x3
	b	LBB83_6
LBB83_74:
	bl	___stack_chk_fail
	.loh AdrpLdrGotLdr	Lloh230, Lloh231, Lloh232
	.loh AdrpAdd	Lloh235, Lloh236
	.loh AdrpAdd	Lloh233, Lloh234
	.loh AdrpAdd	Lloh239, Lloh240
	.loh AdrpAdd	Lloh237, Lloh238
	.loh AdrpLdrGotLdr	Lloh241, Lloh242, Lloh243
	.loh AdrpAdd	Lloh244, Lloh245
	.loh AdrpAdd	Lloh246, Lloh247
	.loh AdrpAdd	Lloh248, Lloh249
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_float_text              ; -- Begin function minyar_float_text
	.p2align	2
_minyar_float_text:                     ; @minyar_float_text
	.cfi_startproc
; %bb.0:
	sub	sp, sp, #128
	stp	x24, x23, [sp, #64]             ; 16-byte Folded Spill
	stp	x22, x21, [sp, #80]             ; 16-byte Folded Spill
	stp	x20, x19, [sp, #96]             ; 16-byte Folded Spill
	stp	x29, x30, [sp, #112]            ; 16-byte Folded Spill
	add	x29, sp, #112
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
	.cfi_offset w19, -24
	.cfi_offset w20, -32
	.cfi_offset w21, -40
	.cfi_offset w22, -48
	.cfi_offset w23, -56
	.cfi_offset w24, -64
Lloh250:
	adrp	x8, ___stack_chk_guard@GOTPAGE
Lloh251:
	ldr	x8, [x8, ___stack_chk_guard@GOTPAGEOFF]
Lloh252:
	ldr	x8, [x8]
	str	x8, [sp, #56]
	add	x0, sp, #8
	bl	_format_float
	mov	x19, x0
	add	x21, x0, #1
	adrp	x24, _rc_pending_count@PAGE
	ldr	x8, [x24, _rc_pending_count@PAGEOFF]
	cbz	x8, LBB84_4
; %bb.1:
	mov	w0, #32                         ; =0x20
	bl	_minyar_rc_poll
	cmn	x21, #8
	b.hs	LBB84_5
LBB84_2:
	add	x22, x19, #9
	mov	x0, x22
	bl	_minyar_pool_allocate
	mov	x20, x0
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
	cbz	x8, LBB84_6
; %bb.3:
	mov	w0, #32                         ; =0x20
	bl	_minyar_rc_poll
	b	LBB84_7
LBB84_4:
	adrp	x8, _rc_bounded_last_work@PAGE
	str	xzr, [x8, _rc_bounded_last_work@PAGEOFF]
	cmn	x21, #8
	b.lo	LBB84_2
LBB84_5:
	bl	_out_of_memory
LBB84_6:
	adrp	x8, _rc_bounded_last_work@PAGE
	str	xzr, [x8, _rc_bounded_last_work@PAGEOFF]
LBB84_7:
	mov	w0, #48                         ; =0x30
	bl	_minyar_pool_allocate
	mov	w8, #9                          ; =0x9
	str	x8, [x0]
	adrp	x8, _rc_object_count@PAGE
	ldr	x9, [x8, _rc_object_count@PAGEOFF]
	add	x9, x9, #1
	str	x9, [x8, _rc_object_count@PAGEOFF]
	ldr	x8, [x23, _rc_bytes@PAGEOFF]
	add	x8, x8, #48
	str	x8, [x23, _rc_bytes@PAGEOFF]
	stp	x19, x19, [x0, #16]
	stp	xzr, xzr, [x0, #32]
	str	x20, [x0, #8]!
	ldr	x8, [sp, #56]
Lloh253:
	adrp	x9, ___stack_chk_guard@GOTPAGE
Lloh254:
	ldr	x9, [x9, ___stack_chk_guard@GOTPAGEOFF]
Lloh255:
	ldr	x9, [x9]
	cmp	x9, x8
	b.ne	LBB84_9
; %bb.8:
	ldp	x29, x30, [sp, #112]            ; 16-byte Folded Reload
	ldp	x20, x19, [sp, #96]             ; 16-byte Folded Reload
	ldp	x22, x21, [sp, #80]             ; 16-byte Folded Reload
	ldp	x24, x23, [sp, #64]             ; 16-byte Folded Reload
	add	sp, sp, #128
	ret
LBB84_9:
	bl	___stack_chk_fail
	.loh AdrpLdrGotLdr	Lloh250, Lloh251, Lloh252
	.loh AdrpLdrGotLdr	Lloh253, Lloh254, Lloh255
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
	b.pl	LBB85_2
; %bb.1:
	fcvtzs	x0, d0
	ret
LBB85_2:
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
	b.hi	LBB86_3
; %bb.1:
	and	x8, x0, #0x1ff800
	mov	w9, #55296                      ; =0xd800
	cmp	x8, x9
	b.eq	LBB86_3
; %bb.2:
                                        ; kill: def $w0 killed $w0 killed $x0
	ret
LBB86_3:
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
	b.eq	LBB87_2
; %bb.1:
	cmp	x0, #0
	cneg	x0, x0, mi
	ret
LBB87_2:
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
	b.gt	LBB88_2
; %bb.1:
	ret
LBB88_2:
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
	b.hi	LBB89_2
; %bb.1:
	ret
LBB89_2:
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
	b.hs	LBB90_2
; %bb.1:
	ret
LBB90_2:
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
	tbnz	x0, #63, LBB96_9
; %bb.1:
	mov	x19, x0
	mov	x8, #9223372036854775807        ; =0x7fffffffffffffff
	cmp	x0, x8
	b.eq	LBB96_10
; %bb.2:
	add	x21, x19, #1
	adrp	x24, _rc_pending_count@PAGE
	ldr	x8, [x24, _rc_pending_count@PAGEOFF]
	cbz	x8, LBB96_4
; %bb.3:
	mov	w0, #32                         ; =0x20
	bl	_minyar_rc_poll
	b	LBB96_5
LBB96_4:
	adrp	x8, _rc_bounded_last_work@PAGE
	str	xzr, [x8, _rc_bounded_last_work@PAGEOFF]
LBB96_5:
	add	x22, x19, #9
	mov	x0, x22
	bl	_minyar_pool_allocate
	mov	x20, x0
	str	x21, [x20], #8
	adrp	x23, _rc_bytes@PAGE
	ldr	x8, [x23, _rc_bytes@PAGEOFF]
	add	x8, x8, x22
	str	x8, [x23, _rc_bytes@PAGEOFF]
	mov	x0, x20
	mov	x1, x21
	bl	_bzero
	ldr	x8, [x24, _rc_pending_count@PAGEOFF]
	cbz	x8, LBB96_7
; %bb.6:
	mov	w0, #32                         ; =0x20
	bl	_minyar_rc_poll
	b	LBB96_8
LBB96_7:
	adrp	x8, _rc_bounded_last_work@PAGE
	str	xzr, [x8, _rc_bounded_last_work@PAGEOFF]
LBB96_8:
	mov	w0, #48                         ; =0x30
	bl	_minyar_pool_allocate
	mov	w8, #9                          ; =0x9
	str	x8, [x0]
	adrp	x8, _rc_object_count@PAGE
	ldr	x9, [x8, _rc_object_count@PAGEOFF]
	add	x9, x9, #1
	str	x9, [x8, _rc_object_count@PAGEOFF]
	ldr	x8, [x23, _rc_bytes@PAGEOFF]
	add	x8, x8, #48
	str	x8, [x23, _rc_bytes@PAGEOFF]
	stp	x19, x19, [x0, #16]
	stp	xzr, xzr, [x0, #32]
	str	x20, [x0, #8]!
	ldp	x29, x30, [sp, #48]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp, #32]             ; 16-byte Folded Reload
	ldp	x22, x21, [sp, #16]             ; 16-byte Folded Reload
	ldp	x24, x23, [sp], #64             ; 16-byte Folded Reload
	ret
LBB96_9:
	bl	_minyar_bytes_new.cold.2
LBB96_10:
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
	tbnz	x1, #63, LBB98_9
; %bb.1:
	mov	x19, x1
	mov	x20, x0
	ldr	x8, [x0, #8]
	cmp	x8, x1
	b.ge	LBB98_8
; %bb.2:
	lsr	x9, x19, #61
	cbnz	x9, LBB98_10
; %bb.3:
	ldr	x9, [x20, #16]
	cmp	x9, x19
	b.ge	LBB98_6
; %bb.4:
	lsl	x8, x9, #1
	mov	w10, #16                        ; =0x10
	cmp	x9, #16
	csel	x8, x10, x8, lt
	cmp	x8, x19
	csel	x21, x8, x19, gt
	mov	x8, #9223372036854775807        ; =0x7fffffffffffffff
	cmp	x21, x8
	b.hs	LBB98_11
; %bb.5:
	ldr	x0, [x20]
	add	x1, x21, #1
	bl	_rc_reallocate_data
	strb	wzr, [x0, x21]
	str	x0, [x20]
	str	x21, [x20, #16]
	ldr	x8, [x20, #8]
	b	LBB98_7
LBB98_6:
	ldr	x0, [x20]
LBB98_7:
	sub	x1, x19, x8
	add	x0, x0, x8
	bl	_bzero
LBB98_8:
	str	x19, [x20, #8]
	ldp	x29, x30, [sp, #32]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp, #16]             ; 16-byte Folded Reload
	ldp	x22, x21, [sp], #48             ; 16-byte Folded Reload
	ret
LBB98_9:
	bl	_minyar_bytes_resize.cold.3
LBB98_10:
	bl	_minyar_bytes_resize.cold.2
LBB98_11:
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
	tbz	x8, #63, LBB99_4
; %bb.1:
	ldr	x9, [x19, #16]
	ldr	x0, [x19]
	tbz	x9, #63, LBB99_3
; %bb.2:
	mov	w1, #17                         ; =0x11
	bl	_rc_reallocate_data
	strb	wzr, [x0, #16]
	str	x0, [x19]
	mov	w8, #16                         ; =0x10
	str	x8, [x19, #16]
	ldr	x8, [x19, #8]
LBB99_3:
	neg	x1, x8
	add	x0, x0, x8
	bl	_bzero
LBB99_4:
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
	b.ls	LBB100_2
; %bb.1:
	ldr	x8, [x0]
	ldrb	w0, [x8, x1]
	ret
LBB100_2:
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
	b.ne	LBB101_2
; %bb.1:
	stp	x0, x2, [sp]
Lloh256:
	adrp	x2, l_.str.72@PAGE
Lloh257:
	add	x2, x2, l_.str.72@PAGEOFF
	b	LBB101_3
LBB101_2:
	stp	x0, x2, [sp, #8]
	str	x1, [sp]
Lloh258:
	adrp	x2, l_.str.73@PAGE
Lloh259:
	add	x2, x2, l_.str.73@PAGEOFF
LBB101_3:
	add	x0, sp, #32
	mov	w1, #160                        ; =0xa0
	bl	_snprintf
	add	x0, sp, #32
	bl	_minyar_stop
	.loh AdrpAdd	Lloh256, Lloh257
	.loh AdrpAdd	Lloh258, Lloh259
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
	b.ls	LBB102_3
; %bb.1:
	cmp	x2, #256
	b.hs	LBB102_4
; %bb.2:
	ldr	x8, [x0]
	strb	w2, [x8, x1]
	ldp	x29, x30, [sp], #16             ; 16-byte Folded Reload
	ret
LBB102_3:
	mov	x0, x1
	mov	w1, #1                          ; =0x1
	mov	x2, x8
	bl	_bytes_position_stop
LBB102_4:
Lloh260:
	adrp	x1, l_.str.26@PAGE
Lloh261:
	add	x1, x1, l_.str.26@PAGEOFF
	mov	x0, x2
	bl	_bytes_value_stop
	.loh AdrpAdd	Lloh260, Lloh261
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
Lloh262:
	adrp	x2, l_.str.74@PAGE
Lloh263:
	add	x2, x2, l_.str.74@PAGEOFF
	add	x0, sp, #16
	mov	w1, #160                        ; =0xa0
	bl	_snprintf
	add	x0, sp, #16
	bl	_minyar_stop
	.loh AdrpAdd	Lloh262, Lloh263
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
	b.ne	LBB104_7
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
Lloh264:
	adrp	x1, l_.str.78@PAGE
Lloh265:
	add	x1, x1, l_.str.78@PAGEOFF
	mov	x0, x19
	bl	_bytes_value_stop
LBB104_8:
	bl	_minyar_bytes_add_int16.cold.2
LBB104_9:
	bl	_minyar_bytes_add_int16.cold.1
	.loh AdrpAdd	Lloh264, Lloh265
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
	tbnz	x1, #63, LBB105_4
; %bb.1:
	sub	x9, x8, #2
	cmp	x9, x1
	b.lt	LBB105_4
; %bb.2:
	cmp	x2, w2, sxth
	b.ne	LBB105_5
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
Lloh266:
	adrp	x1, l_.str.78@PAGE
Lloh267:
	add	x1, x1, l_.str.78@PAGEOFF
	mov	x0, x2
	bl	_bytes_value_stop
	.loh AdrpAdd	Lloh266, Lloh267
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_bytes_get_int16         ; -- Begin function minyar_bytes_get_int16
	.p2align	2
_minyar_bytes_get_int16:                ; @minyar_bytes_get_int16
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
	add	x8, x8, x1
	ldrb	w9, [x8]
	ldrb	w8, [x8, #1]
	lsl	x9, x9, #48
	orr	x8, x9, x8, lsl #56
	asr	x0, x8, #48
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
	b.hs	LBB107_7
; %bb.1:
	mov	x20, x0
	ldr	x8, [x0, #8]
	mov	x9, #2305843009213693950        ; =0x1ffffffffffffffe
	cmp	x8, x9
	b.ge	LBB107_8
; %bb.2:
	ldr	x10, [x20, #16]
	add	x9, x8, #2
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
	strh	w19, [x0, x8]
	ldr	x8, [x20, #8]
	add	x8, x8, #2
	str	x8, [x20, #8]
	ldp	x29, x30, [sp, #32]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp, #16]             ; 16-byte Folded Reload
	ldp	x22, x21, [sp], #48             ; 16-byte Folded Reload
	ret
LBB107_7:
Lloh268:
	adrp	x1, l_.str.76@PAGE
Lloh269:
	add	x1, x1, l_.str.76@PAGEOFF
	mov	x0, x19
	bl	_bytes_value_stop
LBB107_8:
	bl	_minyar_bytes_add_uint16.cold.2
LBB107_9:
	bl	_minyar_bytes_add_uint16.cold.1
	.loh AdrpAdd	Lloh268, Lloh269
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
	tbnz	x1, #63, LBB108_4
; %bb.1:
	sub	x9, x8, #2
	cmp	x9, x1
	b.lt	LBB108_4
; %bb.2:
	cmp	x2, #16, lsl #12                ; =65536
	b.hs	LBB108_5
; %bb.3:
	ldr	x8, [x0]
	strh	w2, [x8, x1]
	ldp	x29, x30, [sp], #16             ; 16-byte Folded Reload
	ret
LBB108_4:
	mov	x0, x1
	mov	w1, #2                          ; =0x2
	mov	x2, x8
	bl	_bytes_position_stop
LBB108_5:
Lloh270:
	adrp	x1, l_.str.76@PAGE
Lloh271:
	add	x1, x1, l_.str.76@PAGEOFF
	mov	x0, x2
	bl	_bytes_value_stop
	.loh AdrpAdd	Lloh270, Lloh271
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_bytes_get_uint16        ; -- Begin function minyar_bytes_get_uint16
	.p2align	2
_minyar_bytes_get_uint16:               ; @minyar_bytes_get_uint16
	.cfi_startproc
; %bb.0:
	ldr	x2, [x0, #8]
	tbnz	x1, #63, LBB109_3
; %bb.1:
	sub	x8, x2, #2
	cmp	x8, x1
	b.lt	LBB109_3
; %bb.2:
	ldr	x8, [x0]
	ldrh	w0, [x8, x1]
	ret
LBB109_3:
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
	b.ne	LBB110_7
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
Lloh272:
	adrp	x1, l_.str.79@PAGE
Lloh273:
	add	x1, x1, l_.str.79@PAGEOFF
	mov	x0, x19
	bl	_bytes_value_stop
LBB110_8:
	bl	_minyar_bytes_add_int32.cold.2
LBB110_9:
	bl	_minyar_bytes_add_int32.cold.1
	.loh AdrpAdd	Lloh272, Lloh273
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
	tbnz	x1, #63, LBB111_4
; %bb.1:
	sub	x9, x8, #4
	cmp	x9, x1
	b.lt	LBB111_4
; %bb.2:
	cmp	x2, w2, sxtw
	b.ne	LBB111_5
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
Lloh274:
	adrp	x1, l_.str.79@PAGE
Lloh275:
	add	x1, x1, l_.str.79@PAGEOFF
	mov	x0, x2
	bl	_bytes_value_stop
	.loh AdrpAdd	Lloh274, Lloh275
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_bytes_get_int32         ; -- Begin function minyar_bytes_get_int32
	.p2align	2
_minyar_bytes_get_int32:                ; @minyar_bytes_get_int32
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
	cbnz	x8, LBB113_7
; %bb.1:
	mov	x20, x0
	ldr	x8, [x0, #8]
	mov	x9, #2305843009213693948        ; =0x1ffffffffffffffc
	cmp	x8, x9
	b.ge	LBB113_8
; %bb.2:
	ldr	x10, [x20, #16]
	add	x9, x8, #4
	cmp	x9, x10
	b.le	LBB113_5
; %bb.3:
	lsl	x8, x10, #1
	mov	w11, #16                        ; =0x10
	cmp	x10, #16
	csel	x8, x11, x8, lt
	cmp	x8, x9
	csel	x21, x8, x9, gt
	mov	x8, #9223372036854775807        ; =0x7fffffffffffffff
	cmp	x21, x8
	b.hs	LBB113_9
; %bb.4:
	ldr	x0, [x20]
	add	x1, x21, #1
	bl	_rc_reallocate_data
	strb	wzr, [x0, x21]
	str	x0, [x20]
	str	x21, [x20, #16]
	ldr	x8, [x20, #8]
	b	LBB113_6
LBB113_5:
	ldr	x0, [x20]
LBB113_6:
	str	w19, [x0, x8]
	ldr	x8, [x20, #8]
	add	x8, x8, #4
	str	x8, [x20, #8]
	ldp	x29, x30, [sp, #32]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp, #16]             ; 16-byte Folded Reload
	ldp	x22, x21, [sp], #48             ; 16-byte Folded Reload
	ret
LBB113_7:
Lloh276:
	adrp	x1, l_.str.77@PAGE
Lloh277:
	add	x1, x1, l_.str.77@PAGEOFF
	mov	x0, x19
	bl	_bytes_value_stop
LBB113_8:
	bl	_minyar_bytes_add_uint32.cold.2
LBB113_9:
	bl	_minyar_bytes_add_uint32.cold.1
	.loh AdrpAdd	Lloh276, Lloh277
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
	tbnz	x1, #63, LBB114_4
; %bb.1:
	sub	x9, x8, #4
	cmp	x9, x1
	b.lt	LBB114_4
; %bb.2:
	lsr	x8, x2, #32
	cbnz	x8, LBB114_5
; %bb.3:
	ldr	x8, [x0]
	str	w2, [x8, x1]
	ldp	x29, x30, [sp], #16             ; 16-byte Folded Reload
	ret
LBB114_4:
	mov	x0, x1
	mov	w1, #4                          ; =0x4
	mov	x2, x8
	bl	_bytes_position_stop
LBB114_5:
Lloh278:
	adrp	x1, l_.str.77@PAGE
Lloh279:
	add	x1, x1, l_.str.77@PAGEOFF
	mov	x0, x2
	bl	_bytes_value_stop
	.loh AdrpAdd	Lloh278, Lloh279
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_bytes_get_uint32        ; -- Begin function minyar_bytes_get_uint32
	.p2align	2
_minyar_bytes_get_uint32:               ; @minyar_bytes_get_uint32
	.cfi_startproc
; %bb.0:
	ldr	x2, [x0, #8]
	tbnz	x1, #63, LBB115_3
; %bb.1:
	sub	x8, x2, #4
	cmp	x8, x1
	b.lt	LBB115_3
; %bb.2:
	ldr	x8, [x0]
	ldr	w0, [x8, x1]
	ret
LBB115_3:
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
	b.ge	LBB116_6
; %bb.1:
	mov	x20, x1
	mov	x19, x0
	ldr	x10, [x0, #16]
	add	x9, x8, #8
	cmp	x9, x10
	b.le	LBB116_4
; %bb.2:
	lsl	x8, x10, #1
	mov	w11, #16                        ; =0x10
	cmp	x10, #16
	csel	x8, x11, x8, lt
	cmp	x8, x9
	csel	x21, x8, x9, gt
	mov	x8, #9223372036854775807        ; =0x7fffffffffffffff
	cmp	x21, x8
	b.hs	LBB116_7
; %bb.3:
	ldr	x0, [x19]
	add	x1, x21, #1
	bl	_rc_reallocate_data
	strb	wzr, [x0, x21]
	str	x0, [x19]
	str	x21, [x19, #16]
	ldr	x8, [x19, #8]
	b	LBB116_5
LBB116_4:
	ldr	x0, [x19]
LBB116_5:
	str	x20, [x0, x8]
	ldr	x8, [x19, #8]
	add	x8, x8, #8
	str	x8, [x19, #8]
	ldp	x29, x30, [sp, #32]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp, #16]             ; 16-byte Folded Reload
	ldp	x22, x21, [sp], #48             ; 16-byte Folded Reload
	ret
LBB116_6:
	bl	_minyar_bytes_add_int64.cold.2
LBB116_7:
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
	tbnz	x1, #63, LBB117_3
; %bb.1:
	sub	x9, x2, #8
	cmp	x9, x1
	b.lt	LBB117_3
; %bb.2:
	ldr	x9, [x0]
	str	x8, [x9, x1]
	ret
LBB117_3:
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
	tbnz	x1, #63, LBB118_3
; %bb.1:
	sub	x8, x2, #8
	cmp	x8, x1
	b.lt	LBB118_3
; %bb.2:
	ldr	x8, [x0]
	ldr	x0, [x8, x1]
	ret
LBB118_3:
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
	b.hs	LBB119_7
; %bb.1:
	mov	x20, x0
	ldr	x8, [x0, #8]
	mov	x9, #2305843009213693951        ; =0x1fffffffffffffff
	cmp	x8, x9
	b.ge	LBB119_8
; %bb.2:
	ldr	x9, [x20, #16]
	cmp	x8, x9
	b.ge	LBB119_4
; %bb.3:
	ldr	x0, [x20]
	b	LBB119_6
LBB119_4:
	add	x10, x8, #1
	lsl	x11, x9, #1
	mov	w12, #16                        ; =0x10
	cmp	x9, #16
	csel	x9, x12, x11, lt
	cmp	x9, x10
	csinc	x21, x9, x8, gt
	mov	x8, #9223372036854775807        ; =0x7fffffffffffffff
	cmp	x21, x8
	b.hs	LBB119_9
; %bb.5:
	ldr	x0, [x20]
	add	x1, x21, #1
	bl	_rc_reallocate_data
	strb	wzr, [x0, x21]
	str	x0, [x20]
	str	x21, [x20, #16]
	ldr	x8, [x20, #8]
LBB119_6:
	add	x9, x8, #1
	str	x9, [x20, #8]
	strb	w19, [x0, x8]
	ldp	x29, x30, [sp, #32]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp, #16]             ; 16-byte Folded Reload
	ldp	x22, x21, [sp], #48             ; 16-byte Folded Reload
	ret
LBB119_7:
Lloh280:
	adrp	x1, l_.str.26@PAGE
Lloh281:
	add	x1, x1, l_.str.26@PAGEOFF
	mov	x0, x19
	bl	_bytes_value_stop
LBB119_8:
	bl	_minyar_bytes_add.cold.2
LBB119_9:
	bl	_minyar_bytes_add.cold.1
	.loh AdrpAdd	Lloh280, Lloh281
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
	b.ge	LBB120_6
; %bb.1:
	fmov	d8, d0
	mov	x19, x0
	ldr	x10, [x0, #16]
	add	x9, x8, #4
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
	fcvt	s0, d8
	str	s0, [x0, x8]
	ldr	x8, [x19, #8]
	add	x8, x8, #4
	str	x8, [x19, #8]
	ldp	x29, x30, [sp, #32]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp, #16]             ; 16-byte Folded Reload
	ldp	d9, d8, [sp], #48               ; 16-byte Folded Reload
	ret
LBB120_6:
	bl	_minyar_bytes_add_float32.cold.2
LBB120_7:
	bl	_minyar_bytes_add_float32.cold.1
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_bytes_set_float32       ; -- Begin function minyar_bytes_set_float32
	.p2align	2
_minyar_bytes_set_float32:              ; @minyar_bytes_set_float32
	.cfi_startproc
; %bb.0:
	ldr	x2, [x0, #8]
	tbnz	x1, #63, LBB121_3
; %bb.1:
	sub	x8, x2, #4
	cmp	x8, x1
	b.lt	LBB121_3
; %bb.2:
	ldr	x8, [x0]
	fcvt	s0, d0
	str	s0, [x8, x1]
	ret
LBB121_3:
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
	tbnz	x1, #63, LBB122_3
; %bb.1:
	sub	x8, x2, #4
	cmp	x8, x1
	b.lt	LBB122_3
; %bb.2:
	ldr	x8, [x0]
	ldr	s0, [x8, x1]
	fcvt	d0, s0
	ret
LBB122_3:
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
	b.ge	LBB123_6
; %bb.1:
	fmov	d8, d0
	mov	x19, x0
	ldr	x10, [x0, #16]
	add	x9, x8, #8
	cmp	x9, x10
	b.le	LBB123_4
; %bb.2:
	lsl	x8, x10, #1
	mov	w11, #16                        ; =0x10
	cmp	x10, #16
	csel	x8, x11, x8, lt
	cmp	x8, x9
	csel	x20, x8, x9, gt
	mov	x8, #9223372036854775807        ; =0x7fffffffffffffff
	cmp	x20, x8
	b.hs	LBB123_7
; %bb.3:
	ldr	x0, [x19]
	add	x1, x20, #1
	bl	_rc_reallocate_data
	strb	wzr, [x0, x20]
	str	x0, [x19]
	str	x20, [x19, #16]
	ldr	x8, [x19, #8]
	b	LBB123_5
LBB123_4:
	ldr	x0, [x19]
LBB123_5:
	str	d8, [x0, x8]
	ldr	x8, [x19, #8]
	add	x8, x8, #8
	str	x8, [x19, #8]
	ldp	x29, x30, [sp, #32]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp, #16]             ; 16-byte Folded Reload
	ldp	d9, d8, [sp], #48               ; 16-byte Folded Reload
	ret
LBB123_6:
	bl	_minyar_bytes_add_float64.cold.2
LBB123_7:
	bl	_minyar_bytes_add_float64.cold.1
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_bytes_set_float64       ; -- Begin function minyar_bytes_set_float64
	.p2align	2
_minyar_bytes_set_float64:              ; @minyar_bytes_set_float64
	.cfi_startproc
; %bb.0:
	ldr	x2, [x0, #8]
	tbnz	x1, #63, LBB124_3
; %bb.1:
	sub	x8, x2, #8
	cmp	x8, x1
	b.lt	LBB124_3
; %bb.2:
	ldr	x8, [x0]
	str	d0, [x8, x1]
	ret
LBB124_3:
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
	tbnz	x1, #63, LBB125_3
; %bb.1:
	sub	x8, x2, #8
	cmp	x8, x1
	b.lt	LBB125_3
; %bb.2:
	ldr	x8, [x0]
	ldr	d0, [x8, x1]
	ret
LBB125_3:
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
Lloh282:
	adrp	x8, ___stack_chk_guard@GOTPAGE
Lloh283:
	ldr	x8, [x8, ___stack_chk_guard@GOTPAGEOFF]
Lloh284:
	ldr	x8, [x8]
	stur	x8, [x29, #-40]
	ldr	x8, [x0, #8]
	tbnz	x1, #63, LBB126_5
; %bb.1:
	subs	x21, x2, x19
	b.lt	LBB126_5
; %bb.2:
	cmp	x8, x2
	b.lt	LBB126_5
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
Lloh285:
	adrp	x9, ___stack_chk_guard@GOTPAGE
Lloh286:
	ldr	x9, [x9, ___stack_chk_guard@GOTPAGEOFF]
Lloh287:
	ldr	x9, [x9]
	cmp	x9, x8
	b.ne	LBB126_6
; %bb.4:
	mov	x0, x22
	ldp	x29, x30, [sp, #224]            ; 16-byte Folded Reload
	ldp	x20, x19, [sp, #208]            ; 16-byte Folded Reload
	ldp	x22, x21, [sp, #192]            ; 16-byte Folded Reload
	add	sp, sp, #240
	ret
LBB126_5:
	stp	x2, x8, [sp, #8]
	str	x19, [sp]
Lloh288:
	adrp	x2, l_.str.27@PAGE
Lloh289:
	add	x2, x2, l_.str.27@PAGEOFF
	add	x0, sp, #24
	mov	w1, #160                        ; =0xa0
	bl	_snprintf
	add	x0, sp, #24
	bl	_minyar_stop
LBB126_6:
	bl	___stack_chk_fail
	.loh AdrpLdrGotLdr	Lloh282, Lloh283, Lloh284
	.loh AdrpLdrGotLdr	Lloh285, Lloh286, Lloh287
	.loh AdrpAdd	Lloh288, Lloh289
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
	b.lt	LBB127_6
; %bb.1:
	mov	x21, x1
	mov	x19, x0
	ldr	x10, [x0, #16]
	add	x9, x8, x20
	cmp	x9, x10
	b.le	LBB127_4
; %bb.2:
	lsl	x8, x10, #1
	mov	w11, #16                        ; =0x10
	cmp	x10, #16
	csel	x8, x11, x8, lt
	cmp	x8, x9
	csel	x22, x8, x9, gt
	mov	x8, #9223372036854775807        ; =0x7fffffffffffffff
	cmp	x22, x8
	b.hs	LBB127_7
; %bb.3:
	ldr	x0, [x19]
	add	x1, x22, #1
	bl	_rc_reallocate_data
	strb	wzr, [x0, x22]
	str	x0, [x19]
	str	x22, [x19, #16]
	ldr	x8, [x19, #8]
	b	LBB127_5
LBB127_4:
	ldr	x0, [x19]
LBB127_5:
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
LBB127_6:
	bl	_minyar_bytes_append.cold.2
LBB127_7:
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
	mov	x19, x0
	ldr	x0, [x0]
	ldr	x20, [x19, #8]
	mov	w1, #0                          ; =0x0
	mov	x2, x20
	bl	_memchr
	cbnz	x0, LBB128_4
; %bb.1:
	add	x0, x20, #1
	bl	_minyar_pool_allocate
	mov	x20, x0
	ldp	x1, x2, [x19]
	bl	_memcpy
	ldr	x8, [x19, #8]
	strb	wzr, [x20, x8]
Lloh290:
	adrp	x1, l_.str.9@PAGE
Lloh291:
	add	x1, x1, l_.str.9@PAGEOFF
	mov	x0, x20
	bl	_fopen
	cbz	x0, LBB128_5
; %bb.2:
	mov	x19, x0
	mov	x0, x20
	bl	_minyar_pool_deallocate
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
	b.ne	LBB128_6
; %bb.3:
	mov	x0, x19
	bl	_fclose
	mov	x0, x20
	ldp	x29, x30, [sp, #48]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp, #32]             ; 16-byte Folded Reload
	ldp	x22, x21, [sp, #16]             ; 16-byte Folded Reload
	add	sp, sp, #64
	ret
LBB128_4:
	bl	_minyar_read_bytes_file.cold.1
LBB128_5:
Lloh292:
	adrp	x8, ___stderrp@GOTPAGE
Lloh293:
	ldr	x8, [x8, ___stderrp@GOTPAGEOFF]
Lloh294:
	ldr	x0, [x8]
	str	x20, [sp]
Lloh295:
	adrp	x1, l_.str.10@PAGE
Lloh296:
	add	x1, x1, l_.str.10@PAGEOFF
	bl	_fprintf
	mov	w0, #1                          ; =0x1
	bl	_exit
LBB128_6:
	bl	_minyar_read_bytes_file.cold.2
	.loh AdrpAdd	Lloh290, Lloh291
	.loh AdrpAdd	Lloh295, Lloh296
	.loh AdrpLdrGotLdr	Lloh292, Lloh293, Lloh294
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
	mov	x20, x0
	ldr	x0, [x0]
	ldr	x21, [x20, #8]
	mov	w1, #0                          ; =0x0
	mov	x2, x21
	bl	_memchr
	cbnz	x0, LBB129_6
; %bb.1:
	add	x0, x21, #1
	bl	_minyar_pool_allocate
	mov	x21, x0
	ldp	x1, x2, [x20]
	bl	_memcpy
	ldr	x8, [x20, #8]
	strb	wzr, [x21, x8]
Lloh297:
	adrp	x1, l_.str.12@PAGE
Lloh298:
	add	x1, x1, l_.str.12@PAGEOFF
	mov	x0, x21
	bl	_fopen
	mov	x20, x0
	mov	x0, x21
	bl	_minyar_pool_deallocate
	cbz	x20, LBB129_7
; %bb.2:
	ldp	x0, x2, [x19]
	mov	w1, #1                          ; =0x1
	mov	x3, x20
	bl	_fwrite
	ldr	x8, [x19, #8]
	cmp	x0, x8
	b.ne	LBB129_5
; %bb.3:
	mov	x0, x20
	bl	_fclose
	cbnz	w0, LBB129_5
; %bb.4:
	ldp	x29, x30, [sp, #32]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp, #16]             ; 16-byte Folded Reload
	ldp	x22, x21, [sp], #48             ; 16-byte Folded Reload
	ret
LBB129_5:
	bl	_minyar_write_bytes_file.cold.2
LBB129_6:
	bl	_minyar_write_bytes_file.cold.1
LBB129_7:
	bl	_minyar_write_bytes_file.cold.3
	.loh AdrpAdd	Lloh297, Lloh298
	.cfi_endproc
                                        ; -- End function
	.globl	_minyar_file_exists             ; -- Begin function minyar_file_exists
	.p2align	2
_minyar_file_exists:                    ; @minyar_file_exists
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
	ldr	x20, [x19, #8]
	mov	w1, #0                          ; =0x0
	mov	x2, x20
	bl	_memchr
	cbnz	x0, LBB130_4
; %bb.1:
	add	x0, x20, #1
	bl	_minyar_pool_allocate
	mov	x20, x0
	ldp	x1, x2, [x19]
	bl	_memcpy
	ldr	x8, [x19, #8]
	strb	wzr, [x20, x8]
Lloh299:
	adrp	x1, l_.str.9@PAGE
Lloh300:
	add	x1, x1, l_.str.9@PAGEOFF
	mov	x0, x20
	bl	_fopen
	mov	x19, x0
	mov	x0, x20
	bl	_minyar_pool_deallocate
	cbz	x19, LBB130_3
; %bb.2:
	mov	x0, x19
	bl	_fclose
LBB130_3:
	cmp	x19, #0
	cset	w0, ne
	ldp	x29, x30, [sp, #16]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp], #32             ; 16-byte Folded Reload
	ret
LBB130_4:
	bl	_minyar_file_exists.cold.1
	.loh AdrpAdd	Lloh299, Lloh300
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
	tbnz	x1, #63, LBB131_7
; %bb.1:
	mov	x20, x1
	mov	x19, x0
	ldr	x22, [x0, #8]
	mov	x8, #2305843009213693951        ; =0x1fffffffffffffff
	sub	x8, x8, x22
	cmp	x8, x1
	b.lt	LBB131_8
; %bb.2:
	ldr	x9, [x19, #16]
	add	x8, x22, x20
	cmp	x8, x9
	b.le	LBB131_5
; %bb.3:
	lsl	x10, x9, #1
	mov	w11, #16                        ; =0x10
	cmp	x9, #16
	csel	x9, x11, x10, lt
	cmp	x9, x8
	csel	x22, x9, x8, gt
	mov	x8, #9223372036854775807        ; =0x7fffffffffffffff
	cmp	x22, x8
	b.hs	LBB131_9
; %bb.4:
	ldr	x0, [x19]
	add	x1, x22, #1
	bl	_rc_reallocate_data
	mov	x21, x0
	strb	wzr, [x0, x22]
	str	x0, [x19]
	str	x22, [x19, #16]
	ldr	x22, [x19, #8]
	b	LBB131_6
LBB131_5:
	ldr	x21, [x19]
LBB131_6:
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
LBB131_7:
	bl	_minyar_bytes_extend.cold.3
LBB131_8:
	bl	_minyar_bytes_extend.cold.2
LBB131_9:
	bl	_minyar_bytes_extend.cold.1
	.cfi_endproc
                                        ; -- End function
	.section	__TEXT,__literal16,16byte_literals
	.p2align	4, 0x0                          ; -- Begin function main
lCPI132_0:
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
	b.ne	LBB132_72
; %bb.1:
	mov	x21, x1
	ldr	x0, [x1, #8]
	mov	x1, #0                          ; =0x0
	mov	w2, #10                         ; =0xa
	bl	_strtoull
	mov	x27, x0
	ldr	x0, [x21, #16]
	mov	x1, #0                          ; =0x0
	mov	w2, #10                         ; =0xa
	bl	_strtoull
	mov	x20, x0
	ldr	x0, [x21, #24]
	mov	x1, #0                          ; =0x0
	mov	w2, #10                         ; =0xa
	bl	_strtoul
	mov	x24, x0
	ldr	x0, [x21, #32]
	mov	x1, #0                          ; =0x0
	mov	w2, #16                         ; =0x10
	bl	_strtoull
	mov	x25, x0
	ldr	x0, [x21, #40]
	mov	x1, #0                          ; =0x0
	mov	w2, #16                         ; =0x10
	bl	_strtoull
	mov	w8, #8193                       ; =0x2001
	cmp	x27, x8
	b.hi	LBB132_73
; %bb.2:
	sub	x8, x20, #256, lsl #12          ; =1048576
	sub	x8, x8, #1
	cmn	x8, #256, lsl #12               ; =1048576
	ccmp	w24, #3, #2, hs
	b.hs	LBB132_73
; %bb.3:
	mov	x26, x0
	cmp	w24, #2
	b.ne	LBB132_5
; %bb.4:
Lloh301:
	adrp	x0, l_.str.35@PAGE
Lloh302:
	add	x0, x0, l_.str.35@PAGEOFF
	bl	_copy_c_text
	mov	x28, x0
	b	LBB132_6
LBB132_5:
	mov	x28, #0                         ; =0x0
LBB132_6:
	adrp	x19, _rc_pending_count@PAGE
	ldr	x8, [x19, _rc_pending_count@PAGEOFF]
	adrp	x9, _rc_bounded_last_work@PAGE
	cbz	x8, LBB132_8
; %bb.7:
	mov	w0, #32                         ; =0x20
	bl	_minyar_rc_poll
	b	LBB132_9
LBB132_8:
	str	xzr, [x9, _rc_bounded_last_work@PAGEOFF]
LBB132_9:
	mov	w0, #32                         ; =0x20
	bl	_minyar_pool_allocate
	mov	x22, x0
	mov	w8, #10                         ; =0xa
	str	x8, [x0]
Lloh303:
	adrp	x10, _rc_object_count@PAGE
	ldr	x9, [x10, _rc_object_count@PAGEOFF]
	add	x9, x9, #1
	str	x9, [x10, _rc_object_count@PAGEOFF]
Lloh304:
	adrp	x10, _rc_bytes@PAGE
	ldr	x9, [x10, _rc_bytes@PAGEOFF]
	add	x9, x9, #32
	str	x9, [x10, _rc_bytes@PAGEOFF]
	mov	x23, x0
	str	xzr, [x23, #8]!
	stp	xzr, xzr, [x0, #16]
	cmp	w24, #2
	b.ne	LBB132_11
; %bb.10:
	mov	w8, #14                         ; =0xe
	str	x8, [x22]
LBB132_11:
	mov	x9, #31765                      ; =0x7c15
	movk	x9, #32586, lsl #16
	movk	x9, #31161, lsl #32
	movk	x9, #40503, lsl #48
	str	x20, [sp, #88]                  ; 8-byte Folded Spill
	str	x27, [sp, #56]                  ; 8-byte Folded Spill
	cbz	x27, LBB132_16
; %bb.12:
	mov	x20, x25
	mov	x21, x27
LBB132_13:                              ; =>This Inner Loop Header: Depth=1
	cmp	w24, #2
	csel	x1, x28, x20, eq
	mov	x0, x23
	mov	x27, x9
	bl	_minyar_list_add
	mov	x9, x27
	add	x20, x20, x27
	subs	x21, x21, #1
	b.ne	LBB132_13
; %bb.14:
	ldr	x8, [x22]
	cmp	x8, #8
	ldr	x20, [sp, #88]                  ; 8-byte Folded Reload
	b.lo	LBB132_17
; %bb.15:
	cmn	x8, #8
	b.hs	LBB132_83
LBB132_16:
	add	x8, x8, #8
	str	x8, [x22]
LBB132_17:
	str	x22, [sp, #48]                  ; 8-byte Folded Spill
	cmp	w24, #2
	mov	x8, #12816                      ; =0x3210
	movk	x8, #30292, lsl #16
	movk	x8, #47768, lsl #32
	movk	x8, #65244, lsl #48
	csel	x8, x28, x8, eq
	str	x8, [sp, #96]                   ; 8-byte Folded Spill
	ldr	x8, [x19, _rc_pending_count@PAGEOFF]
	cbz	x8, LBB132_19
LBB132_18:                              ; =>This Inner Loop Header: Depth=1
	mov	w0, #32                         ; =0x20
	bl	_minyar_rc_poll
	ldr	x8, [x19, _rc_pending_count@PAGEOFF]
	cbnz	x8, LBB132_18
LBB132_19:
	sub	x1, x29, #96
	mov	w0, #12                         ; =0xc
	bl	_clock_gettime
	cbnz	w0, LBB132_74
; %bb.20:
	str	x28, [sp, #104]                 ; 8-byte Folded Spill
	ldp	x9, x8, [x29, #-96]
	stp	x9, x8, [sp, #32]               ; 16-byte Folded Spill
	mov	x27, #0                         ; =0x0
	cbz	x20, LBB132_35
; %bb.21:
	mov	x21, #0                         ; =0x0
	cmp	w24, #2
	cset	w28, eq
	ldr	x8, [sp, #56]                   ; 8-byte Folded Reload
	add	x22, x8, #1
Lloh305:
	adrp	x8, lCPI132_0@PAGE
Lloh306:
	ldr	q0, [x8, lCPI132_0@PAGEOFF]
	str	q0, [sp, #64]                   ; 16-byte Folded Spill
	b	LBB132_24
LBB132_22:                              ;   in Loop: Header=BB132_24 Depth=1
	mov	w8, w0
	adrp	x9, _rc_bounded_last_work@PAGE
	str	x8, [x9, _rc_bounded_last_work@PAGEOFF]
LBB132_23:                              ;   in Loop: Header=BB132_24 Depth=1
	add	x8, x26, x21
	eor	x27, x8, x27
	add	x21, x21, #1
	ldr	x8, [sp, #88]                   ; 8-byte Folded Reload
	cmp	x21, x8
	b.eq	LBB132_35
LBB132_24:                              ; =>This Loop Header: Depth=1
                                        ;     Child Loop BB132_34 Depth 2
	cmp	w24, #1
	b.ne	LBB132_29
; %bb.25:                               ;   in Loop: Header=BB132_24 Depth=1
	ldr	x8, [x19, _rc_pending_count@PAGEOFF]
	cbz	x8, LBB132_27
; %bb.26:                               ;   in Loop: Header=BB132_24 Depth=1
	mov	w0, #32                         ; =0x20
	bl	_minyar_rc_poll
	b	LBB132_28
LBB132_27:                              ;   in Loop: Header=BB132_24 Depth=1
	adrp	x8, _rc_bounded_last_work@PAGE
	str	xzr, [x8, _rc_bounded_last_work@PAGEOFF]
LBB132_28:                              ;   in Loop: Header=BB132_24 Depth=1
	mov	w0, #1186                       ; =0x4a2
	bl	_minyar_pool_allocate
	mov	x20, x0
Lloh307:
	adrp	x9, _rc_object_count@PAGE
	ldr	x8, [x9, _rc_object_count@PAGEOFF]
	add	x8, x8, #1
	str	x8, [x9, _rc_object_count@PAGEOFF]
Lloh308:
	adrp	x9, _rc_bytes@PAGE
	ldr	x8, [x9, _rc_bytes@PAGEOFF]
	add	x8, x8, #1186
	str	x8, [x9, _rc_bytes@PAGEOFF]
	add	x0, x0, #16
	mov	w1, #1170                       ; =0x492
	bl	_bzero
	ldr	q0, [sp, #64]                   ; 16-byte Folded Reload
	str	q0, [x20], #8
	mov	x0, x20
	bl	_rc_drop
LBB132_29:                              ;   in Loop: Header=BB132_24 Depth=1
	mov	x0, x23
	ldr	x1, [sp, #96]                   ; 8-byte Folded Reload
	mov	x2, x28
	mov	x3, #0                          ; =0x0
	bl	_minyar_list_appended
	cmp	x0, x23
	b.eq	LBB132_68
; %bb.30:                               ;   in Loop: Header=BB132_24 Depth=1
	mov	x20, x0
	ldr	x8, [x0, #8]
	cmp	x8, x22
	b.ne	LBB132_68
; %bb.31:                               ;   in Loop: Header=BB132_24 Depth=1
	ldr	x0, [x20]
	mov	x1, x22
	ldr	x2, [sp, #104]                  ; 8-byte Folded Reload
	bl	_research_checksum
	cmp	x0, x26
	b.ne	LBB132_69
; %bb.32:                               ;   in Loop: Header=BB132_24 Depth=1
	mov	x0, x20
	bl	_rc_drop
	ldr	x8, [x19, _rc_pending_count@PAGEOFF]
	cbz	x8, LBB132_22
; %bb.33:                               ;   in Loop: Header=BB132_24 Depth=1
	mov	w8, #32                         ; =0x20
	sub	w8, w8, w0
	mov	x20, x0
	mov	x0, x8
	bl	_minyar_rc_poll
	adrp	x10, _rc_bounded_last_work@PAGE
	ldr	x8, [x10, _rc_bounded_last_work@PAGEOFF]
	ldr	x9, [x19, _rc_pending_count@PAGEOFF]
	add	x8, x8, w20, uxtw
	str	x8, [x10, _rc_bounded_last_work@PAGEOFF]
	cbz	x9, LBB132_23
LBB132_34:                              ;   Parent Loop BB132_24 Depth=1
                                        ; =>  This Inner Loop Header: Depth=2
	mov	w0, #32                         ; =0x20
	bl	_minyar_rc_poll
	ldr	x8, [x19, _rc_pending_count@PAGEOFF]
	cbnz	x8, LBB132_34
	b	LBB132_23
LBB132_35:
	sub	x1, x29, #96
	mov	w0, #12                         ; =0xc
	bl	_clock_gettime
	cbnz	w0, LBB132_75
; %bb.36:
	cmp	w24, #2
	cset	w2, eq
	ldp	x26, x22, [x29, #-96]
	mov	x0, x23
	ldr	x1, [sp, #96]                   ; 8-byte Folded Reload
	mov	x3, #0                          ; =0x0
	bl	_minyar_list_appended
	ldr	x9, [x0]
	ldr	x8, [x23]
	ldr	x28, [sp, #56]                  ; 8-byte Folded Reload
	cbz	x28, LBB132_38
; %bb.37:
	cmp	x9, x8
	b.eq	LBB132_76
LBB132_38:
	mov	x15, #31765                     ; =0x7c15
	movk	x15, #32586, lsl #16
	movk	x15, #31161, lsl #32
	movk	x15, #40503, lsl #48
	cbz	x28, LBB132_43
; %bb.39:
	mov	x10, x8
	mov	x11, x9
	mov	x12, x28
LBB132_40:                              ; =>This Inner Loop Header: Depth=1
	ldr	x13, [x10], #8
	cmp	w24, #2
	ldr	x14, [sp, #104]                 ; 8-byte Folded Reload
	csel	x14, x14, x25, eq
	cmp	x13, x14
	b.ne	LBB132_70
; %bb.41:                               ;   in Loop: Header=BB132_40 Depth=1
	ldr	x14, [x11]
	cmp	x14, x13
	b.ne	LBB132_71
; %bb.42:                               ;   in Loop: Header=BB132_40 Depth=1
	add	x11, x11, #8
	add	x25, x25, x15
	subs	x12, x12, #1
	b.ne	LBB132_40
LBB132_43:
	ldr	x10, [x9, x28, lsl #3]
	ldr	x11, [sp, #96]                  ; 8-byte Folded Reload
	cmp	x10, x11
	b.ne	LBB132_77
; %bb.44:
	adrp	x25, _rc_bounded_last_work@PAGE
	cbz	x28, LBB132_52
; %bb.45:
	ldr	x10, [x0, #8]
	cbz	x10, LBB132_82
; %bb.46:
	ldr	x21, [x8]
	ldur	x10, [x0, #-8]
	and	x10, x10, #0x7
	cmp	x10, #3
	b.ne	LBB132_50
; %bb.47:
	mov	x24, x0
	ldr	x0, [x9]
	str	xzr, [x9]
	bl	_rc_drop
	mov	x20, x0
	ldr	x8, [x19, _rc_pending_count@PAGEOFF]
	cbz	x8, LBB132_49
; %bb.48:
	mov	w8, #32                         ; =0x20
	sub	w0, w8, w20
	bl	_minyar_rc_poll
	ldr	x8, [x25, _rc_bounded_last_work@PAGEOFF]
LBB132_49:
	add	x8, x8, w20, uxtw
	str	x8, [x25, _rc_bounded_last_work@PAGEOFF]
	ldr	x8, [x23]
	mov	x0, x24
	b	LBB132_51
LBB132_50:
	str	xzr, [x9]
LBB132_51:
	ldr	x8, [x8]
	cmp	x8, x21
	b.ne	LBB132_81
LBB132_52:
	bl	_rc_drop
	mov	x20, x0
	ldr	x8, [x19, _rc_pending_count@PAGEOFF]
	cbz	x8, LBB132_54
; %bb.53:
	mov	w8, #32                         ; =0x20
	sub	w0, w8, w20
	bl	_minyar_rc_poll
	ldr	x8, [x25, _rc_bounded_last_work@PAGEOFF]
LBB132_54:
	add	x8, x8, w20, uxtw
	str	x8, [x25, _rc_bounded_last_work@PAGEOFF]
	mov	x0, x23
	bl	_rc_drop
	mov	x20, x0
	ldr	x8, [x19, _rc_pending_count@PAGEOFF]
	cbz	x8, LBB132_56
; %bb.55:
	mov	w8, #32                         ; =0x20
	sub	w0, w8, w20
	bl	_minyar_rc_poll
	ldr	x8, [x25, _rc_bounded_last_work@PAGEOFF]
LBB132_56:
	add	x8, x8, w20, uxtw
	str	x8, [x25, _rc_bounded_last_work@PAGEOFF]
	ldr	x8, [sp, #48]                   ; 8-byte Folded Reload
	ldr	x8, [x8, #16]
	cmp	x8, x28
	b.ne	LBB132_78
; %bb.57:
	mov	x0, x23
	bl	_rc_drop
	mov	x20, x0
	ldr	x8, [x19, _rc_pending_count@PAGEOFF]
	cbz	x8, LBB132_59
; %bb.58:
	mov	w8, #32                         ; =0x20
	sub	w0, w8, w20
	bl	_minyar_rc_poll
	ldr	x8, [x25, _rc_bounded_last_work@PAGEOFF]
LBB132_59:
	ldr	x0, [sp, #104]                  ; 8-byte Folded Reload
	add	x8, x8, w20, uxtw
	str	x8, [x25, _rc_bounded_last_work@PAGEOFF]
	cbz	x0, LBB132_64
; %bb.60:
	bl	_rc_drop
	mov	x20, x0
	ldr	x8, [x19, _rc_pending_count@PAGEOFF]
	cbz	x8, LBB132_62
; %bb.61:
	mov	w8, #32                         ; =0x20
	sub	w0, w8, w20
	bl	_minyar_rc_poll
	ldr	x8, [x25, _rc_bounded_last_work@PAGEOFF]
LBB132_62:
	add	x8, x8, w20, uxtw
	str	x8, [x25, _rc_bounded_last_work@PAGEOFF]
	b	LBB132_64
LBB132_63:                              ;   in Loop: Header=BB132_64 Depth=1
	mov	w0, #32                         ; =0x20
	bl	_minyar_rc_poll
LBB132_64:                              ; =>This Inner Loop Header: Depth=1
	ldr	x8, [x19, _rc_pending_count@PAGEOFF]
	cbnz	x8, LBB132_63
; %bb.65:
Lloh309:
	adrp	x8, _rc_object_count@PAGE
Lloh310:
	ldr	x8, [x8, _rc_object_count@PAGEOFF]
Lloh311:
	adrp	x9, _rc_bytes@PAGE
Lloh312:
	ldr	x9, [x9, _rc_bytes@PAGEOFF]
	orr	x8, x8, x9
	cbnz	x8, LBB132_79
; %bb.66:
Lloh313:
	adrp	x8, _minyar_pool_used@PAGE
Lloh314:
	ldr	x8, [x8, _minyar_pool_used@PAGEOFF]
	cbnz	x8, LBB132_80
; %bb.67:
	ldp	x8, x10, [sp, #32]              ; 16-byte Folded Reload
	sub	x8, x26, x8
	mov	w9, #51712                      ; =0xca00
	movk	w9, #15258, lsl #16
	sub	x10, x22, x10
	madd	x8, x8, x9, x10
	ldr	x9, [sp, #88]                   ; 8-byte Folded Reload
	stp	x27, x9, [sp, #8]
	str	x8, [sp]
Lloh315:
	adrp	x0, l_.str.46@PAGE
Lloh316:
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
LBB132_68:
	bl	_main.cold.5
LBB132_69:
	bl	_main.cold.4
LBB132_70:
	bl	_main.cold.7
LBB132_71:
	bl	_main.cold.8
LBB132_72:
	bl	_main.cold.1
LBB132_73:
	bl	_main.cold.16
LBB132_74:
	bl	_main.cold.3
LBB132_75:
	bl	_main.cold.6
LBB132_76:
	bl	_main.cold.15
LBB132_77:
	bl	_main.cold.9
LBB132_78:
	bl	_main.cold.11
LBB132_79:
	bl	_main.cold.13
LBB132_80:
	bl	_main.cold.12
LBB132_81:
	bl	_main.cold.10
LBB132_82:
	bl	_main.cold.14
LBB132_83:
	bl	_main.cold.2
	.loh AdrpAdd	Lloh301, Lloh302
	.loh AdrpAdrp	Lloh303, Lloh304
	.loh AdrpLdr	Lloh305, Lloh306
	.loh AdrpAdrp	Lloh307, Lloh308
	.loh AdrpLdr	Lloh311, Lloh312
	.loh AdrpLdr	Lloh309, Lloh310
	.loh AdrpLdr	Lloh313, Lloh314
	.loh AdrpAdd	Lloh315, Lloh316
	.cfi_endproc
                                        ; -- End function
	.p2align	2                               ; -- Begin function rc_bounded_enqueue
_rc_bounded_enqueue:                    ; @rc_bounded_enqueue
	.cfi_startproc
; %bb.0:
	ldr	x8, [x0]
	and	x9, x8, #0x7
	cmp	x9, #1
	b.eq	LBB133_8
; %bb.1:
	cmp	x9, #3
	b.ne	LBB133_3
; %bb.2:
	str	xzr, [x0, #24]
	b	LBB133_8
LBB133_3:
	ldr	x9, [x0, #8]
	cbz	x9, LBB133_8
; %bb.4:
	mov	x8, #0                          ; =0x0
	add	x9, x0, x9, lsl #3
	add	x9, x9, #16
LBB133_5:                               ; =>This Inner Loop Header: Depth=1
	ldrb	w10, [x9, x8]
	and	w10, w10, #0x1
	strb	w10, [x9, x8]
	cmp	x8, #8
	b.hi	LBB133_7
; %bb.6:                                ;   in Loop: Header=BB133_5 Depth=1
	add	x8, x8, #1
	ldr	x10, [x0, #8]
	cmp	x8, x10
	b.lo	LBB133_5
LBB133_7:
	ldr	x8, [x0]
LBB133_8:
	adrp	x9, _rc_bounded_recent_head@PAGE
	ldr	x10, [x9, _rc_bounded_recent_head@PAGEOFF]
	orr	x8, x8, x10
	str	x8, [x0]
	str	x0, [x9, _rc_bounded_recent_head@PAGEOFF]
	adrp	x8, _rc_bounded_recent_tail@PAGE
	ldr	x9, [x8, _rc_bounded_recent_tail@PAGEOFF]
	cbnz	x9, LBB133_10
; %bb.9:
	str	x0, [x8, _rc_bounded_recent_tail@PAGEOFF]
LBB133_10:
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
	cbz	x0, LBB134_2
; %bb.1:
	ldr	x8, [x0]
	b	LBB134_10
LBB134_2:
	adrp	x8, _rc_bounded_head@PAGE
	ldr	x0, [x8, _rc_bounded_head@PAGEOFF]
	str	x0, [x19, _rc_bounded_active@PAGEOFF]
	ldr	x9, [x0]
	and	x10, x9, #0xfffffffffffffff8
	str	x10, [x8, _rc_bounded_head@PAGEOFF]
	and	x8, x9, #0x7
	str	x8, [x0]
	cmp	x8, #1
	b.eq	LBB134_8
; %bb.3:
	cmp	x8, #3
	b.ne	LBB134_5
; %bb.4:
	ldr	x9, [x0, #24]
	b	LBB134_9
LBB134_5:
	ldr	x12, [x0, #8]
	cbz	x12, LBB134_8
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
LBB134_7:                               ; =>This Inner Loop Header: Depth=1
	ldrb	w13, [x11], #1
	lsr	x13, x13, #1
	lsl	x13, x13, x10
	orr	x9, x13, x9
	add	x10, x10, #7
	cmp	x12, x10
	b.ne	LBB134_7
	b	LBB134_9
LBB134_8:
	mov	x9, #0                          ; =0x0
LBB134_9:
	adrp	x10, _rc_bounded_cursor@PAGE
	str	x9, [x10, _rc_bounded_cursor@PAGEOFF]
LBB134_10:
	and	w1, w8, #0x7
	cmp	w1, #4
	b.eq	LBB134_14
; %bb.11:
	cmp	w1, #3
	b.ne	LBB134_17
; %bb.12:
	adrp	x9, _rc_bounded_cursor@PAGE
	ldr	x8, [x9, _rc_bounded_cursor@PAGEOFF]
	ldr	x10, [x0, #16]
	cmp	x8, x10
	b.hs	LBB134_17
; %bb.13:
	ldr	x10, [x0, #8]
	add	x11, x8, #1
	str	x11, [x9, _rc_bounded_cursor@PAGEOFF]
	b	LBB134_16
LBB134_14:
	adrp	x9, _rc_bounded_cursor@PAGE
	ldr	x8, [x9, _rc_bounded_cursor@PAGEOFF]
	ldr	x11, [x0, #8]
	cmp	x8, x11
	b.hs	LBB134_17
; %bb.15:
	add	x10, x0, #16
	add	x11, x10, x11, lsl #3
	add	x12, x8, #1
	str	x12, [x9, _rc_bounded_cursor@PAGEOFF]
	ldrb	w9, [x11, x8]
	tbz	w9, #0, LBB134_18
LBB134_16:
	ldr	x0, [x10, x8, lsl #3]
	ldp	x29, x30, [sp, #16]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp], #32             ; 16-byte Folded Reload
	b	_rc_drop
LBB134_17:
	bl	_rc_bounded_finish_object
	adrp	x8, _rc_pending_count@PAGE
	ldr	x9, [x8, _rc_pending_count@PAGEOFF]
	sub	x9, x9, #1
	str	x9, [x8, _rc_pending_count@PAGEOFF]
	str	xzr, [x19, _rc_bounded_active@PAGEOFF]
LBB134_18:
	ldp	x29, x30, [sp, #16]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp], #32             ; 16-byte Folded Reload
	ret
	.cfi_endproc
                                        ; -- End function
	.p2align	2                               ; -- Begin function pool_try_resize_same_base
_pool_try_resize_same_base:             ; @pool_try_resize_same_base
	.cfi_startproc
; %bb.0:
	stp	x20, x19, [sp, #-16]!           ; 16-byte Folded Spill
	.cfi_def_cfa_offset 16
	.cfi_offset w19, -8
	.cfi_offset w20, -16
	ldp	w9, w8, [x1]
	ldr	x10, [x1, #16]
	cmp	w8, w9
	b.ls	LBB135_6
; %bb.1:
	ldr	x11, [x1, #24]
	sub	x12, x10, #1
	tst	x12, x11
	b.ne	LBB135_5
; %bb.2:
	adrp	x12, _minyar_pool_last_steps@PAGE
	ldr	x13, [x12, _minyar_pool_last_steps@PAGEOFF]
	mov	w15, #32                        ; =0x20
	mov	x16, x9
Lloh317:
	adrp	x14, _minyar_pool_map@PAGE
Lloh318:
	add	x14, x14, _minyar_pool_map@PAGEOFF
LBB135_3:                               ; =>This Inner Loop Header: Depth=1
	cmp	x8, x16
	b.eq	LBB135_14
; %bb.4:                                ;   in Loop: Header=BB135_3 Depth=1
	lsl	x17, x15, x16
	add	x17, x17, x11
	lsr	x17, x17, #5
	ldrb	w17, [x14, x17]
	add	x16, x16, #1
	add	x13, x13, #1
	str	x13, [x12, _minyar_pool_last_steps@PAGEOFF]
	cmp	x16, x17
	b.eq	LBB135_3
LBB135_5:
	mov	x0, #0                          ; =0x0
	ldp	x20, x19, [sp], #16             ; 16-byte Folded Reload
	ret
LBB135_6:
	ldr	x11, [x1, #8]
	adrp	x12, _minyar_pool_used@PAGE
	ldr	x13, [x12, _minyar_pool_used@PAGEOFF]
	sub	x10, x10, x11
	add	x10, x10, x13
	str	x10, [x12, _minyar_pool_used@PAGEOFF]
Lloh319:
	adrp	x10, _minyar_pool_map@PAGE
Lloh320:
	add	x10, x10, _minyar_pool_map@PAGEOFF
	cmp	w9, w8
	b.ls	LBB135_12
; %bb.7:
	adrp	x11, _minyar_pool_last_steps@PAGE
	ldr	x12, [x11, _minyar_pool_last_steps@PAGEOFF]
	adrp	x13, _minyar_pool_mask@PAGE
	ldr	x14, [x13, _minyar_pool_mask@PAGEOFF]
	sub	x15, x9, #1
	sub	w16, w9, #1
	mov	w17, #32                        ; =0x20
Lloh321:
	adrp	x2, _minyar_pool_free@PAGE
Lloh322:
	add	x2, x2, _minyar_pool_free@PAGEOFF
	mov	w3, #1                          ; =0x1
Lloh323:
	adrp	x4, _minyar_pool@PAGE
Lloh324:
	add	x4, x4, _minyar_pool@PAGEOFF
	b	LBB135_9
LBB135_8:                               ;   in Loop: Header=BB135_9 Depth=1
	str	x5, [x2, x16, lsl #3]
	lsl	x6, x3, x16
	add	w7, w15, #1
	sub	x5, x5, x4
	lsr	x5, x5, #5
	strb	w7, [x10, x5]
	orr	x14, x14, x6
	add	x12, x12, #1
	sub	x15, x15, #1
	sub	x16, x16, #1
	sub	w9, w9, #1
	cmp	w8, w9
	b.hs	LBB135_11
LBB135_9:                               ; =>This Inner Loop Header: Depth=1
	lsl	x5, x17, x16
	ldr	x6, [x2, x16, lsl #3]
	add	x5, x0, x5
	stp	xzr, x6, [x5]
	cbz	x6, LBB135_8
; %bb.10:                               ;   in Loop: Header=BB135_9 Depth=1
	str	x5, [x6]
	b	LBB135_8
LBB135_11:
	str	w8, [x1]
	str	x14, [x13, _minyar_pool_mask@PAGEOFF]
	str	x12, [x11, _minyar_pool_last_steps@PAGEOFF]
LBB135_12:
	add	w8, w8, #1
	orr	w8, w8, #0x80
	ldr	x9, [x1, #24]
	lsr	x9, x9, #5
	strb	w8, [x10, x9]
LBB135_13:
	ldp	x20, x19, [sp], #16             ; 16-byte Folded Reload
	ret
LBB135_14:
Lloh325:
	adrp	x15, _minyar_pool@PAGE
Lloh326:
	add	x15, x15, _minyar_pool@PAGEOFF
	adrp	x16, _minyar_pool_mask@PAGE
	ldr	x17, [x16, _minyar_pool_mask@PAGEOFF]
	add	x2, x15, x11
	mov	w3, #32                         ; =0x20
Lloh327:
	adrp	x4, _minyar_pool_free@PAGE
Lloh328:
	add	x4, x4, _minyar_pool_free@PAGEOFF
	mov	w5, #1                          ; =0x1
	b	LBB135_16
LBB135_15:                              ;   in Loop: Header=BB135_16 Depth=1
	sub	x6, x6, x15
	lsr	x6, x6, #5
	strb	wzr, [x14, x6]
	add	x13, x13, #1
	add	x9, x9, #1
	cmp	x8, x9
	b.eq	LBB135_22
LBB135_16:                              ; =>This Inner Loop Header: Depth=1
	lsl	x6, x3, x9
	add	x6, x2, x6
	ldp	x7, x19, [x6]
	cbz	x7, LBB135_21
; %bb.17:                               ;   in Loop: Header=BB135_16 Depth=1
	str	x19, [x7, #8]
	cbz	x19, LBB135_19
LBB135_18:                              ;   in Loop: Header=BB135_16 Depth=1
	str	x7, [x19]
LBB135_19:                              ;   in Loop: Header=BB135_16 Depth=1
	ldr	x7, [x4, x9, lsl #3]
	cbnz	x7, LBB135_15
; %bb.20:                               ;   in Loop: Header=BB135_16 Depth=1
	lsl	x7, x5, x9
	bic	x17, x17, x7
	str	x17, [x16, _minyar_pool_mask@PAGEOFF]
	b	LBB135_15
LBB135_21:                              ;   in Loop: Header=BB135_16 Depth=1
	str	x19, [x4, x9, lsl #3]
	cbnz	x19, LBB135_18
	b	LBB135_19
LBB135_22:
	str	x13, [x12, _minyar_pool_last_steps@PAGEOFF]
	add	w8, w8, #1
	orr	w8, w8, #0x80
	lsr	x9, x11, #5
	strb	w8, [x14, x9]
	ldr	x8, [x1, #8]
Lloh329:
	adrp	x9, _minyar_pool_used@PAGE
	ldr	x11, [x9, _minyar_pool_used@PAGEOFF]
	sub	x8, x10, x8
	add	x8, x11, x8
	str	x8, [x9, _minyar_pool_used@PAGEOFF]
Lloh330:
	adrp	x9, _minyar_pool_high_water@PAGE
	ldr	x10, [x9, _minyar_pool_high_water@PAGEOFF]
	cmp	x8, x10
	b.ls	LBB135_13
; %bb.23:
	str	x8, [x9, _minyar_pool_high_water@PAGEOFF]
	ldp	x20, x19, [sp], #16             ; 16-byte Folded Reload
	ret
	.loh AdrpAdd	Lloh317, Lloh318
	.loh AdrpAdd	Lloh319, Lloh320
	.loh AdrpAdd	Lloh323, Lloh324
	.loh AdrpAdd	Lloh321, Lloh322
	.loh AdrpAdd	Lloh327, Lloh328
	.loh AdrpAdd	Lloh325, Lloh326
	.loh AdrpAdrp	Lloh329, Lloh330
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
Lloh331:
	adrp	x8, _rc_pending_count@PAGE
Lloh332:
	ldr	x8, [x8, _rc_pending_count@PAGEOFF]
	cbz	x8, LBB136_3
; %bb.1:
	mov	w0, #32                         ; =0x20
	bl	_minyar_rc_poll
	cmn	x20, #8
	b.hs	LBB136_4
LBB136_2:
	add	x20, x20, #8
	mov	x0, x20
	bl	_minyar_pool_allocate
	orr	w8, w19, #0x8
	str	x8, [x0], #8
Lloh333:
	adrp	x8, _rc_object_count@PAGE
	ldr	x9, [x8, _rc_object_count@PAGEOFF]
	add	x9, x9, #1
	str	x9, [x8, _rc_object_count@PAGEOFF]
Lloh334:
	adrp	x8, _rc_bytes@PAGE
	ldr	x9, [x8, _rc_bytes@PAGEOFF]
	add	x9, x9, x20
	str	x9, [x8, _rc_bytes@PAGEOFF]
	ldp	x29, x30, [sp, #16]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp], #32             ; 16-byte Folded Reload
	ret
LBB136_3:
	adrp	x8, _rc_bounded_last_work@PAGE
	str	xzr, [x8, _rc_bounded_last_work@PAGEOFF]
	cmn	x20, #8
	b.lo	LBB136_2
LBB136_4:
	bl	_out_of_memory
	.loh AdrpLdr	Lloh331, Lloh332
	.loh AdrpAdrp	Lloh333, Lloh334
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
Lloh335:
	adrp	x8, _rc_pending_count@PAGE
Lloh336:
	ldr	x8, [x8, _rc_pending_count@PAGEOFF]
	cbz	x8, LBB137_3
; %bb.1:
	mov	w0, #32                         ; =0x20
	bl	_minyar_rc_poll
	cmn	x19, #8
	b.hs	LBB137_4
LBB137_2:
	add	x20, x19, #8
	mov	x0, x20
	bl	_minyar_pool_allocate
	str	x19, [x0], #8
	adrp	x8, _rc_bytes@PAGE
	ldr	x9, [x8, _rc_bytes@PAGEOFF]
	add	x9, x9, x20
	str	x9, [x8, _rc_bytes@PAGEOFF]
	ldp	x29, x30, [sp, #16]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp], #32             ; 16-byte Folded Reload
	ret
LBB137_3:
	adrp	x8, _rc_bounded_last_work@PAGE
	str	xzr, [x8, _rc_bounded_last_work@PAGEOFF]
	cmn	x19, #8
	b.lo	LBB137_2
LBB137_4:
	bl	_out_of_memory
	.loh AdrpLdr	Lloh335, Lloh336
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
LBB138_1:                               ; =>This Inner Loop Header: Depth=1
	mov	x20, x9
	subs	x8, x8, #8
	b.lt	LBB138_3
; %bb.2:                                ;   in Loop: Header=BB138_1 Depth=1
	ldr	x9, [x19]
	ldr	x10, [x9, x20]
	add	x9, x20, #8
	and	x10, x10, #0x8080808080808080
	cbz	x10, LBB138_1
LBB138_3:
	cmp	x20, x21
	b.ge	LBB138_8
; %bb.4:
	ldr	x8, [x19]
LBB138_5:                               ; =>This Inner Loop Header: Depth=1
	ldrsb	w9, [x8, x20]
	tbnz	w9, #31, LBB138_8
; %bb.6:                                ;   in Loop: Header=BB138_5 Depth=1
	add	x20, x20, #1
	cmp	x21, x20
	b.ne	LBB138_5
; %bb.7:
	mov	x22, x21
	b	LBB138_13
LBB138_8:
	cmp	x20, x21
	b.ge	LBB138_11
; %bb.9:
	mov	x22, x20
LBB138_10:                              ; =>This Inner Loop Header: Depth=1
	ldr	x8, [x19]
	sub	x1, x21, x20
	add	x0, x8, x20
	bl	_OUTLINED_FUNCTION_1
	ldr	x8, [sp, #8]
	add	x22, x22, #1
	ldr	x21, [x19, #8]
	add	x20, x8, x20
	cmp	x20, x21
	b.lt	LBB138_10
	b	LBB138_12
LBB138_11:
	mov	x22, x20
LBB138_12:
	cmp	x22, x21
	b.ne	LBB138_14
LBB138_13:
	str	x22, [x19, #16]
	b	LBB138_32
LBB138_14:
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
	b.lt	LBB138_23
; %bb.15:
	mov	x23, #0                         ; =0x0
	mov	x22, #0                         ; =0x0
	mov	w24, #-1                        ; =0xffffffff
LBB138_16:                              ; =>This Inner Loop Header: Depth=1
	tst	x22, #0x3f
	b.ne	LBB138_20
; %bb.17:                               ;   in Loop: Header=BB138_16 Depth=1
	lsr	x9, x22, #6
	cmp	x21, x24
	b.gt	LBB138_19
; %bb.18:                               ;   in Loop: Header=BB138_16 Depth=1
	str	w23, [x20, x9, lsl #2]
	b	LBB138_20
LBB138_19:                              ;   in Loop: Header=BB138_16 Depth=1
	str	x23, [x20, x9, lsl #3]
	ldr	x8, [x19, #8]
LBB138_20:                              ;   in Loop: Header=BB138_16 Depth=1
	add	x22, x22, #1
	ldr	x9, [x19]
	sub	x1, x8, x23
	add	x0, x9, x23
	bl	_OUTLINED_FUNCTION_1
	ldr	x9, [sp, #8]
	ldr	x8, [x19, #8]
	add	x23, x9, x23
	cmp	x23, x8
	b.lt	LBB138_16
; %bb.21:
	tst	x22, #0x3f
	b.eq	LBB138_24
; %bb.22:
	lsr	x9, x22, #6
	b	LBB138_27
LBB138_23:
	mov	x23, #0                         ; =0x0
	mov	x22, #0                         ; =0x0
LBB138_24:
	lsr	x9, x22, #6
	mov	w10, #-1                        ; =0xffffffff
	cmp	x21, x10
	b.gt	LBB138_26
; %bb.25:
	str	w23, [x20, x9, lsl #2]
	b	LBB138_27
LBB138_26:
	str	x23, [x20, x9, lsl #3]
	ldr	x8, [x19, #8]
LBB138_27:
	stp	x22, x20, [x19, #16]
	add	x9, x9, #1
	mov	w10, #-1                        ; =0xffffffff
	cmp	x8, x10
	b.gt	LBB138_29
; %bb.28:
	str	wzr, [x20, x9, lsl #2]
	mov	w8, #64                         ; =0x40
	sdiv	x8, x22, x8
	add	x8, x8, #2
	b	LBB138_30
LBB138_29:
	str	xzr, [x20, x9, lsl #3]
	ldp	x9, x8, [x19, #8]
	mov	w10, #64                        ; =0x40
	sdiv	x8, x8, x10
	add	x8, x8, #2
	mov	w10, #-1                        ; =0xffffffff
	cmp	x9, x10
	b.gt	LBB138_31
LBB138_30:
	str	wzr, [x20, x8, lsl #2]
	b	LBB138_32
LBB138_31:
	str	xzr, [x20, x8, lsl #3]
LBB138_32:
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
	b.le	LBB139_28
; %bb.1:
	mov	x8, x0
	ldrsb	w9, [x0]
	and	w0, w9, #0xff
	tbnz	w9, #31, LBB139_3
; %bb.2:
	mov	w8, #1                          ; =0x1
	str	x8, [x2]
	ldp	x29, x30, [sp], #16             ; 16-byte Folded Reload
	ret
LBB139_3:
	cmp	x1, #1
	b.eq	LBB139_7
; %bb.4:
	sub	w9, w0, #194
	cmp	w9, #29
	b.hi	LBB139_7
; %bb.5:
	ldrb	w9, [x8, #1]
	and	w9, w9, #0xc0
	cmp	w9, #128
	b.ne	LBB139_7
; %bb.6:
	mov	w9, #2                          ; =0x2
	str	x9, [x2]
	ldrb	w8, [x8, #1]
	and	w8, w8, #0x3f
	bfi	w8, w0, #6, #5
	mov	x0, x8
	ldp	x29, x30, [sp], #16             ; 16-byte Folded Reload
	ret
LBB139_7:
	cmp	x1, #3
	b.lo	LBB139_16
; %bb.8:
	and	w9, w0, #0xf0
	cmp	w9, #224
	b.ne	LBB139_16
; %bb.9:
	ldrb	w9, [x8, #1]
	and	w10, w9, #0xc0
	cmp	w10, #128
	b.ne	LBB139_16
; %bb.10:
	ldrb	w10, [x8, #2]
	and	w10, w10, #0xc0
	cmp	w10, #128
	b.ne	LBB139_16
; %bb.11:
	cmp	w0, #224
	b.ne	LBB139_13
; %bb.12:
	cmp	w9, #160
	b.lo	LBB139_27
LBB139_13:
	cmp	w0, #237
	b.ne	LBB139_15
; %bb.14:
	cmp	w9, #159
	b.hi	LBB139_27
LBB139_15:
	mov	w9, #3                          ; =0x3
	str	x9, [x2]
	ubfiz	w0, w0, #12, #4
	ldrb	w9, [x8, #1]
	bfi	w0, w9, #6, #6
	ldrb	w8, [x8, #2]
	b	LBB139_26
LBB139_16:
	cmp	x1, #4
	b.lo	LBB139_27
; %bb.17:
	sub	w9, w0, #240
	cmp	w9, #4
	b.hi	LBB139_27
; %bb.18:
	ldrb	w9, [x8, #1]
	and	w10, w9, #0xc0
	cmp	w10, #128
	b.ne	LBB139_27
; %bb.19:
	ldrb	w10, [x8, #2]
	and	w10, w10, #0xc0
	cmp	w10, #128
	b.ne	LBB139_27
; %bb.20:
	ldrb	w10, [x8, #3]
	and	w10, w10, #0xc0
	cmp	w10, #128
	b.ne	LBB139_27
; %bb.21:
	cmp	w0, #240
	b.ne	LBB139_23
; %bb.22:
	cmp	w9, #144
	b.lo	LBB139_27
LBB139_23:
	cmp	w0, #244
	b.ne	LBB139_25
; %bb.24:
	cmp	w9, #143
	b.hi	LBB139_27
LBB139_25:
	mov	w9, #4                          ; =0x4
	str	x9, [x2]
	ubfiz	w0, w0, #18, #3
	ldrb	w9, [x8, #1]
	bfi	w0, w9, #12, #6
	ldrb	w9, [x8, #2]
	bfi	w0, w9, #6, #6
	ldrb	w8, [x8, #3]
LBB139_26:
	bfxil	w0, w8, #0, #6
	ldp	x29, x30, [sp], #16             ; 16-byte Folded Reload
	ret
LBB139_27:
	bl	_invalid_utf8
LBB139_28:
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
Lloh337:
	adrp	x0, l_.str.57@PAGE
Lloh338:
	add	x0, x0, l_.str.57@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh337, Lloh338
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
Lloh339:
	adrp	x0, l_.str.58@PAGE
Lloh340:
	add	x0, x0, l_.str.58@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh339, Lloh340
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
Lloh341:
	adrp	x0, l_.str.59@PAGE
Lloh342:
	add	x0, x0, l_.str.59@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh341, Lloh342
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
Lloh343:
	adrp	x8, ___stack_chk_guard@GOTPAGE
Lloh344:
	ldr	x8, [x8, ___stack_chk_guard@GOTPAGEOFF]
Lloh345:
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
	b.ls	LBB143_10
; %bb.1:
	mov	x10, x21
	mov	x9, x21
	b	LBB143_4
LBB143_2:                               ;   in Loop: Header=BB143_4 Depth=1
	strb	w10, [x9]
LBB143_3:                               ;   in Loop: Header=BB143_4 Depth=1
	mov	x10, x9
	cmp	x9, x23
	b.ls	LBB143_10
LBB143_4:                               ; =>This Inner Loop Header: Depth=1
	ldrsb	w11, [x9, #-1]!
	cmp	w11, #46
	b.eq	LBB143_3
; %bb.5:                                ;   in Loop: Header=BB143_4 Depth=1
	cmp	w20, #1
	b.lt	LBB143_8
; %bb.6:                                ;   in Loop: Header=BB143_4 Depth=1
	cmp	w11, #57
	b.lt	LBB143_15
; %bb.7:                                ;   in Loop: Header=BB143_4 Depth=1
	mov	w10, #48                        ; =0x30
	b	LBB143_2
LBB143_8:                               ;   in Loop: Header=BB143_4 Depth=1
	cmp	w11, #48
	b.gt	LBB143_16
; %bb.9:                                ;   in Loop: Header=BB143_4 Depth=1
	mov	w10, #57                        ; =0x39
	b	LBB143_2
LBB143_10:
	mov	w9, #49                         ; =0x31
	strb	w9, [x23]
	add	w8, w8, #1
LBB143_11:
	add	x9, sp, #16
	sub	x9, x9, x21
	str	x8, [sp]
Lloh346:
	adrp	x2, l_.str.71@PAGE
Lloh347:
	add	x2, x2, l_.str.71@PAGEOFF
	add	x1, x9, #40
	mov	x0, x21
	bl	_snprintf
	add	x0, sp, #16
	mov	x1, #0                          ; =0x0
	bl	_strtod
	fmov	d9, d0
	fcmp	d0, d8
	b.ne	LBB143_13
; %bb.12:
	add	x0, sp, #16
	bl	_strlen
	add	x1, sp, #16
	add	x2, x0, #1
	mov	x0, x19
	bl	_memcpy
LBB143_13:
	fcmp	d9, d8
	cset	w0, eq
	ldr	x8, [sp, #56]
Lloh348:
	adrp	x9, ___stack_chk_guard@GOTPAGE
Lloh349:
	ldr	x9, [x9, ___stack_chk_guard@GOTPAGEOFF]
Lloh350:
	ldr	x9, [x9]
	cmp	x9, x8
	b.ne	LBB143_23
; %bb.14:
	ldp	x29, x30, [sp, #128]            ; 16-byte Folded Reload
	ldp	x20, x19, [sp, #112]            ; 16-byte Folded Reload
	ldp	x22, x21, [sp, #96]             ; 16-byte Folded Reload
	ldp	x24, x23, [sp, #80]             ; 16-byte Folded Reload
	ldp	d9, d8, [sp, #64]               ; 16-byte Folded Reload
	add	sp, sp, #144
	ret
LBB143_15:
	mov	w9, #1                          ; =0x1
	b	LBB143_17
LBB143_16:
	mov	w9, #255                        ; =0xff
LBB143_17:
	add	w9, w11, w9
	sturb	w9, [x10, #-1]
	ldrb	w9, [x23]
	cmp	w9, #48
	b.ne	LBB143_11
; %bb.18:
	add	x9, sp, #16
	add	x9, x22, x9
	add	x9, x9, #1
	mov	w11, #48                        ; =0x30
	mov	w10, #57                        ; =0x39
	cmp	w11, #46
	b.eq	LBB143_20
LBB143_19:
	sturb	w10, [x9, #-1]
LBB143_20:                              ; =>This Inner Loop Header: Depth=1
	cmp	x9, x21
	b.hs	LBB143_22
; %bb.21:                               ;   in Loop: Header=BB143_20 Depth=1
	ldrb	w11, [x9], #1
	cmp	w11, #46
	b.ne	LBB143_19
	b	LBB143_20
LBB143_22:
	sub	w8, w8, #1
	b	LBB143_11
LBB143_23:
	bl	___stack_chk_fail
	.loh AdrpLdrGotLdr	Lloh343, Lloh344, Lloh345
	.loh AdrpAdd	Lloh346, Lloh347
	.loh AdrpLdrGotLdr	Lloh348, Lloh349, Lloh350
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
Lloh351:
	adrp	x0, l_.str@PAGE
Lloh352:
	add	x0, x0, l_.str@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh351, Lloh352
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
Lloh353:
	adrp	x0, l_.str.1@PAGE
Lloh354:
	add	x0, x0, l_.str.1@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh353, Lloh354
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
Lloh355:
	adrp	x0, l_.str.2@PAGE
Lloh356:
	add	x0, x0, l_.str.2@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh355, Lloh356
	.cfi_endproc
                                        ; -- End function
	.p2align	2                               ; -- Begin function minyar_rc_poll.cold.1
_minyar_rc_poll.cold.1:                 ; @minyar_rc_poll.cold.1
	.cfi_startproc
; %bb.0:
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
Lloh357:
	adrp	x0, l_.str.49@PAGE
Lloh358:
	add	x0, x0, l_.str.49@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh357, Lloh358
	.cfi_endproc
                                        ; -- End function
	.p2align	2                               ; -- Begin function minyar_rc_poll.cold.2
_minyar_rc_poll.cold.2:                 ; @minyar_rc_poll.cold.2
	.cfi_startproc
; %bb.0:
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
Lloh359:
	adrp	x0, l_.str.48@PAGE
Lloh360:
	add	x0, x0, l_.str.48@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh359, Lloh360
	.cfi_endproc
                                        ; -- End function
	.p2align	2                               ; -- Begin function minyar_rc_poll.cold.3
_minyar_rc_poll.cold.3:                 ; @minyar_rc_poll.cold.3
	.cfi_startproc
; %bb.0:
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
Lloh361:
	adrp	x0, l_.str.49@PAGE
Lloh362:
	add	x0, x0, l_.str.49@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh361, Lloh362
	.cfi_endproc
                                        ; -- End function
	.p2align	2                               ; -- Begin function minyar_rc_poll.cold.4
_minyar_rc_poll.cold.4:                 ; @minyar_rc_poll.cold.4
	.cfi_startproc
; %bb.0:
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
Lloh363:
	adrp	x0, l_.str.48@PAGE
Lloh364:
	add	x0, x0, l_.str.48@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh363, Lloh364
	.cfi_endproc
                                        ; -- End function
	.p2align	2                               ; -- Begin function minyar_rc_enter.cold.1
_minyar_rc_enter.cold.1:                ; @minyar_rc_enter.cold.1
	.cfi_startproc
; %bb.0:
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
Lloh365:
	adrp	x0, l_.str.49@PAGE
Lloh366:
	add	x0, x0, l_.str.49@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh365, Lloh366
	.cfi_endproc
                                        ; -- End function
	.p2align	2                               ; -- Begin function minyar_rc_enter.cold.2
_minyar_rc_enter.cold.2:                ; @minyar_rc_enter.cold.2
	.cfi_startproc
; %bb.0:
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
Lloh367:
	adrp	x0, l_.str.48@PAGE
Lloh368:
	add	x0, x0, l_.str.48@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh367, Lloh368
	.cfi_endproc
                                        ; -- End function
	.p2align	2                               ; -- Begin function minyar_rc_enter.cold.3
_minyar_rc_enter.cold.3:                ; @minyar_rc_enter.cold.3
	.cfi_startproc
; %bb.0:
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
Lloh369:
	adrp	x0, l_.str.49@PAGE
Lloh370:
	add	x0, x0, l_.str.49@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh369, Lloh370
	.cfi_endproc
                                        ; -- End function
	.p2align	2                               ; -- Begin function minyar_rc_enter.cold.4
_minyar_rc_enter.cold.4:                ; @minyar_rc_enter.cold.4
	.cfi_startproc
; %bb.0:
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
Lloh371:
	adrp	x0, l_.str.48@PAGE
Lloh372:
	add	x0, x0, l_.str.48@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh371, Lloh372
	.cfi_endproc
                                        ; -- End function
	.p2align	2                               ; -- Begin function minyar_rc_enter.cold.5
_minyar_rc_enter.cold.5:                ; @minyar_rc_enter.cold.5
	.cfi_startproc
; %bb.0:
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
Lloh373:
	adrp	x0, l_.str.50@PAGE
Lloh374:
	add	x0, x0, l_.str.50@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh373, Lloh374
	.cfi_endproc
                                        ; -- End function
	.p2align	2                               ; -- Begin function minyar_rc_enter.cold.6
_minyar_rc_enter.cold.6:                ; @minyar_rc_enter.cold.6
	.cfi_startproc
; %bb.0:
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
Lloh375:
	adrp	x0, l_.str.49@PAGE
Lloh376:
	add	x0, x0, l_.str.49@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh375, Lloh376
	.cfi_endproc
                                        ; -- End function
	.p2align	2                               ; -- Begin function minyar_rc_enter.cold.7
_minyar_rc_enter.cold.7:                ; @minyar_rc_enter.cold.7
	.cfi_startproc
; %bb.0:
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
Lloh377:
	adrp	x0, l_.str.48@PAGE
Lloh378:
	add	x0, x0, l_.str.48@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh377, Lloh378
	.cfi_endproc
                                        ; -- End function
	.p2align	2                               ; -- Begin function minyar_pool_allocate.cold.1
_minyar_pool_allocate.cold.1:           ; @minyar_pool_allocate.cold.1
	.cfi_startproc
; %bb.0:
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
Lloh379:
	adrp	x0, l_.str.50@PAGE
Lloh380:
	add	x0, x0, l_.str.50@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh379, Lloh380
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
Lloh381:
	adrp	x0, l_.str.2@PAGE
Lloh382:
	add	x0, x0, l_.str.2@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh381, Lloh382
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
Lloh383:
	adrp	x0, l_.str.2@PAGE
Lloh384:
	add	x0, x0, l_.str.2@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh383, Lloh384
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
Lloh385:
	adrp	x0, l_.str.2@PAGE
Lloh386:
	add	x0, x0, l_.str.2@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh385, Lloh386
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
Lloh387:
	adrp	x0, l_.str.2@PAGE
Lloh388:
	add	x0, x0, l_.str.2@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh387, Lloh388
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
Lloh389:
	adrp	x0, l_.str.3@PAGE
Lloh390:
	add	x0, x0, l_.str.3@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh389, Lloh390
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
Lloh391:
	adrp	x0, l_.str.53@PAGE
Lloh392:
	add	x0, x0, l_.str.53@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh391, Lloh392
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
Lloh393:
	adrp	x0, l_.str.53@PAGE
Lloh394:
	add	x0, x0, l_.str.53@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh393, Lloh394
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
Lloh395:
	adrp	x0, l_.str.2@PAGE
Lloh396:
	add	x0, x0, l_.str.2@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh395, Lloh396
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
Lloh397:
	adrp	x0, l_.str.2@PAGE
Lloh398:
	add	x0, x0, l_.str.2@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh397, Lloh398
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
Lloh399:
	adrp	x0, l_.str.61@PAGE
Lloh400:
	add	x0, x0, l_.str.61@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh399, Lloh400
	.cfi_endproc
                                        ; -- End function
	.p2align	2                               ; -- Begin function rc_reallocate_data.cold.1
_rc_reallocate_data.cold.1:             ; @rc_reallocate_data.cold.1
	.cfi_startproc
; %bb.0:
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
Lloh401:
	adrp	x0, l_.str.50@PAGE
Lloh402:
	add	x0, x0, l_.str.50@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh401, Lloh402
	.cfi_endproc
                                        ; -- End function
	.p2align	2                               ; -- Begin function rc_reallocate_data.cold.2
_rc_reallocate_data.cold.2:             ; @rc_reallocate_data.cold.2
	.cfi_startproc
; %bb.0:
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
Lloh403:
	adrp	x0, l_.str.49@PAGE
Lloh404:
	add	x0, x0, l_.str.49@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh403, Lloh404
	.cfi_endproc
                                        ; -- End function
	.p2align	2                               ; -- Begin function rc_reallocate_data.cold.3
_rc_reallocate_data.cold.3:             ; @rc_reallocate_data.cold.3
	.cfi_startproc
; %bb.0:
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
Lloh405:
	adrp	x0, l_.str.48@PAGE
Lloh406:
	add	x0, x0, l_.str.48@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh405, Lloh406
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
Lloh407:
	adrp	x0, l_.str.2@PAGE
Lloh408:
	add	x0, x0, l_.str.2@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh407, Lloh408
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
Lloh409:
	adrp	x0, l_.str.2@PAGE
Lloh410:
	add	x0, x0, l_.str.2@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh409, Lloh410
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
Lloh411:
	adrp	x0, l_.str.8@PAGE
Lloh412:
	add	x0, x0, l_.str.8@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh411, Lloh412
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
Lloh413:
	adrp	x0, l_.str.62@PAGE
Lloh414:
	add	x0, x0, l_.str.62@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh413, Lloh414
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
Lloh415:
	adrp	x0, l_.str.11@PAGE
Lloh416:
	add	x0, x0, l_.str.11@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh415, Lloh416
	.cfi_endproc
                                        ; -- End function
	.p2align	2                               ; -- Begin function minyar_pool_deallocate.cold.1
_minyar_pool_deallocate.cold.1:         ; @minyar_pool_deallocate.cold.1
	.cfi_startproc
; %bb.0:
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
Lloh417:
	adrp	x0, l_.str.49@PAGE
Lloh418:
	add	x0, x0, l_.str.49@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh417, Lloh418
	.cfi_endproc
                                        ; -- End function
	.p2align	2                               ; -- Begin function minyar_pool_deallocate.cold.2
_minyar_pool_deallocate.cold.2:         ; @minyar_pool_deallocate.cold.2
	.cfi_startproc
; %bb.0:
	stp	x29, x30, [sp, #-16]!           ; 16-byte Folded Spill
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
Lloh419:
	adrp	x0, l_.str.48@PAGE
Lloh420:
	add	x0, x0, l_.str.48@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh419, Lloh420
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
Lloh421:
	adrp	x0, l_.str.11@PAGE
Lloh422:
	add	x0, x0, l_.str.11@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh421, Lloh422
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
Lloh423:
	adrp	x0, l_.str.11@PAGE
Lloh424:
	add	x0, x0, l_.str.11@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh423, Lloh424
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
Lloh425:
	adrp	x0, l_.str.62@PAGE
Lloh426:
	add	x0, x0, l_.str.62@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh425, Lloh426
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
Lloh427:
	adrp	x0, l_.str.14@PAGE
Lloh428:
	add	x0, x0, l_.str.14@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh427, Lloh428
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
Lloh429:
	adrp	x0, l_.str.13@PAGE
Lloh430:
	add	x0, x0, l_.str.13@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh429, Lloh430
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
Lloh431:
	adrp	x8, l_.str.18@PAGE
Lloh432:
	add	x8, x8, l_.str.18@PAGEOFF
Lloh433:
	adrp	x9, l_.str.19@PAGE
Lloh434:
	add	x9, x9, l_.str.19@PAGEOFF
	fcmp	d0, d0
	csel	x0, x9, x8, vc
	bl	_minyar_stop
	.loh AdrpAdd	Lloh433, Lloh434
	.loh AdrpAdd	Lloh431, Lloh432
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
Lloh435:
	adrp	x0, l_.str.20@PAGE
Lloh436:
	add	x0, x0, l_.str.20@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh435, Lloh436
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
Lloh437:
	adrp	x0, l_.str.21@PAGE
Lloh438:
	add	x0, x0, l_.str.21@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh437, Lloh438
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
Lloh439:
	adrp	x0, l_.str.22@PAGE
Lloh440:
	add	x0, x0, l_.str.22@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh439, Lloh440
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
Lloh441:
	adrp	x0, l_.str.22@PAGE
Lloh442:
	add	x0, x0, l_.str.22@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh441, Lloh442
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
Lloh443:
	adrp	x0, l_.str.23@PAGE
Lloh444:
	add	x0, x0, l_.str.23@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh443, Lloh444
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
Lloh445:
	adrp	x0, l_.str.25@PAGE
Lloh446:
	add	x0, x0, l_.str.25@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh445, Lloh446
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
Lloh447:
	adrp	x0, l_.str.24@PAGE
Lloh448:
	add	x0, x0, l_.str.24@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh447, Lloh448
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
Lloh449:
	adrp	x0, l_.str.25@PAGE
Lloh450:
	add	x0, x0, l_.str.25@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh449, Lloh450
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
Lloh451:
	adrp	x0, l_.str.25@PAGE
Lloh452:
	add	x0, x0, l_.str.25@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh451, Lloh452
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
Lloh453:
	adrp	x0, l_.str.24@PAGE
Lloh454:
	add	x0, x0, l_.str.24@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh453, Lloh454
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
Lloh455:
	adrp	x0, l_.str.25@PAGE
Lloh456:
	add	x0, x0, l_.str.25@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh455, Lloh456
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
Lloh457:
	adrp	x0, l_.str.25@PAGE
Lloh458:
	add	x0, x0, l_.str.25@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh457, Lloh458
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
Lloh459:
	adrp	x0, l_.str.25@PAGE
Lloh460:
	add	x0, x0, l_.str.25@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh459, Lloh460
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
Lloh461:
	adrp	x0, l_.str.25@PAGE
Lloh462:
	add	x0, x0, l_.str.25@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh461, Lloh462
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
Lloh463:
	adrp	x0, l_.str.25@PAGE
Lloh464:
	add	x0, x0, l_.str.25@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh463, Lloh464
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
Lloh465:
	adrp	x0, l_.str.25@PAGE
Lloh466:
	add	x0, x0, l_.str.25@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh465, Lloh466
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
Lloh467:
	adrp	x0, l_.str.25@PAGE
Lloh468:
	add	x0, x0, l_.str.25@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh467, Lloh468
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
Lloh469:
	adrp	x0, l_.str.25@PAGE
Lloh470:
	add	x0, x0, l_.str.25@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh469, Lloh470
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
Lloh471:
	adrp	x0, l_.str.25@PAGE
Lloh472:
	add	x0, x0, l_.str.25@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh471, Lloh472
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
Lloh473:
	adrp	x0, l_.str.25@PAGE
Lloh474:
	add	x0, x0, l_.str.25@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh473, Lloh474
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
Lloh475:
	adrp	x0, l_.str.25@PAGE
Lloh476:
	add	x0, x0, l_.str.25@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh475, Lloh476
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
Lloh477:
	adrp	x0, l_.str.25@PAGE
Lloh478:
	add	x0, x0, l_.str.25@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh477, Lloh478
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
Lloh479:
	adrp	x0, l_.str.25@PAGE
Lloh480:
	add	x0, x0, l_.str.25@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh479, Lloh480
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
Lloh481:
	adrp	x0, l_.str.25@PAGE
Lloh482:
	add	x0, x0, l_.str.25@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh481, Lloh482
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
Lloh483:
	adrp	x0, l_.str.25@PAGE
Lloh484:
	add	x0, x0, l_.str.25@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh483, Lloh484
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
Lloh485:
	adrp	x0, l_.str.25@PAGE
Lloh486:
	add	x0, x0, l_.str.25@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh485, Lloh486
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
Lloh487:
	adrp	x0, l_.str.25@PAGE
Lloh488:
	add	x0, x0, l_.str.25@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh487, Lloh488
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
Lloh489:
	adrp	x0, l_.str.25@PAGE
Lloh490:
	add	x0, x0, l_.str.25@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh489, Lloh490
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
Lloh491:
	adrp	x0, l_.str.62@PAGE
Lloh492:
	add	x0, x0, l_.str.62@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh491, Lloh492
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
Lloh493:
	adrp	x0, l_.str.28@PAGE
Lloh494:
	add	x0, x0, l_.str.28@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh493, Lloh494
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
Lloh495:
	adrp	x0, l_.str.62@PAGE
Lloh496:
	add	x0, x0, l_.str.62@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh495, Lloh496
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
Lloh497:
	adrp	x0, l_.str.30@PAGE
Lloh498:
	add	x0, x0, l_.str.30@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh497, Lloh498
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
Lloh499:
	adrp	x0, l_.str.29@PAGE
Lloh500:
	add	x0, x0, l_.str.29@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh499, Lloh500
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
Lloh501:
	adrp	x0, l_.str.62@PAGE
Lloh502:
	add	x0, x0, l_.str.62@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh501, Lloh502
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
Lloh503:
	adrp	x0, l_.str.25@PAGE
Lloh504:
	add	x0, x0, l_.str.25@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh503, Lloh504
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
Lloh505:
	adrp	x0, l_.str.25@PAGE
Lloh506:
	add	x0, x0, l_.str.25@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh505, Lloh506
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
Lloh507:
	adrp	x0, l_.str.31@PAGE
Lloh508:
	add	x0, x0, l_.str.31@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh507, Lloh508
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
Lloh509:
	adrp	x0, l___func__.main@PAGE
Lloh510:
	add	x0, x0, l___func__.main@PAGEOFF
Lloh511:
	adrp	x1, l_.str.32@PAGE
Lloh512:
	add	x1, x1, l_.str.32@PAGEOFF
Lloh513:
	adrp	x3, l_.str.33@PAGE
Lloh514:
	add	x3, x3, l_.str.33@PAGEOFF
	mov	w2, #29                         ; =0x1d
	bl	___assert_rtn
	.loh AdrpAdd	Lloh513, Lloh514
	.loh AdrpAdd	Lloh511, Lloh512
	.loh AdrpAdd	Lloh509, Lloh510
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
Lloh515:
	adrp	x0, l_.str.2@PAGE
Lloh516:
	add	x0, x0, l_.str.2@PAGEOFF
	bl	_minyar_stop
	.loh AdrpAdd	Lloh515, Lloh516
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
Lloh517:
	adrp	x0, l___func__.cpu_nanoseconds@PAGE
Lloh518:
	add	x0, x0, l___func__.cpu_nanoseconds@PAGEOFF
Lloh519:
	adrp	x1, l_.str.32@PAGE
Lloh520:
	add	x1, x1, l_.str.32@PAGEOFF
Lloh521:
	adrp	x3, l_.str.80@PAGE
Lloh522:
	add	x3, x3, l_.str.80@PAGEOFF
	mov	w2, #24                         ; =0x18
	bl	___assert_rtn
	.loh AdrpAdd	Lloh521, Lloh522
	.loh AdrpAdd	Lloh519, Lloh520
	.loh AdrpAdd	Lloh517, Lloh518
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
Lloh523:
	adrp	x0, l___func__.main@PAGE
Lloh524:
	add	x0, x0, l___func__.main@PAGEOFF
Lloh525:
	adrp	x1, l_.str.32@PAGE
Lloh526:
	add	x1, x1, l_.str.32@PAGEOFF
Lloh527:
	adrp	x3, l_.str.37@PAGE
Lloh528:
	add	x3, x3, l_.str.37@PAGEOFF
	mov	w2, #71                         ; =0x47
	bl	___assert_rtn
	.loh AdrpAdd	Lloh527, Lloh528
	.loh AdrpAdd	Lloh525, Lloh526
	.loh AdrpAdd	Lloh523, Lloh524
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
Lloh529:
	adrp	x0, l___func__.main@PAGE
Lloh530:
	add	x0, x0, l___func__.main@PAGEOFF
Lloh531:
	adrp	x1, l_.str.32@PAGE
Lloh532:
	add	x1, x1, l_.str.32@PAGEOFF
Lloh533:
	adrp	x3, l_.str.36@PAGE
Lloh534:
	add	x3, x3, l_.str.36@PAGEOFF
	mov	w2, #69                         ; =0x45
	bl	___assert_rtn
	.loh AdrpAdd	Lloh533, Lloh534
	.loh AdrpAdd	Lloh531, Lloh532
	.loh AdrpAdd	Lloh529, Lloh530
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
Lloh535:
	adrp	x0, l___func__.cpu_nanoseconds@PAGE
Lloh536:
	add	x0, x0, l___func__.cpu_nanoseconds@PAGEOFF
Lloh537:
	adrp	x1, l_.str.32@PAGE
Lloh538:
	add	x1, x1, l_.str.32@PAGEOFF
Lloh539:
	adrp	x3, l_.str.80@PAGE
Lloh540:
	add	x3, x3, l_.str.80@PAGEOFF
	mov	w2, #24                         ; =0x18
	bl	___assert_rtn
	.loh AdrpAdd	Lloh539, Lloh540
	.loh AdrpAdd	Lloh537, Lloh538
	.loh AdrpAdd	Lloh535, Lloh536
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
Lloh541:
	adrp	x0, l___func__.main@PAGE
Lloh542:
	add	x0, x0, l___func__.main@PAGEOFF
Lloh543:
	adrp	x1, l_.str.32@PAGE
Lloh544:
	add	x1, x1, l_.str.32@PAGEOFF
Lloh545:
	adrp	x3, l_.str.39@PAGE
Lloh546:
	add	x3, x3, l_.str.39@PAGEOFF
	mov	w2, #83                         ; =0x53
	bl	___assert_rtn
	.loh AdrpAdd	Lloh545, Lloh546
	.loh AdrpAdd	Lloh543, Lloh544
	.loh AdrpAdd	Lloh541, Lloh542
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
Lloh547:
	adrp	x0, l___func__.main@PAGE
Lloh548:
	add	x0, x0, l___func__.main@PAGEOFF
Lloh549:
	adrp	x1, l_.str.32@PAGE
Lloh550:
	add	x1, x1, l_.str.32@PAGEOFF
Lloh551:
	adrp	x3, l_.str.40@PAGE
Lloh552:
	add	x3, x3, l_.str.40@PAGEOFF
	mov	w2, #84                         ; =0x54
	bl	___assert_rtn
	.loh AdrpAdd	Lloh551, Lloh552
	.loh AdrpAdd	Lloh549, Lloh550
	.loh AdrpAdd	Lloh547, Lloh548
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
Lloh553:
	adrp	x0, l___func__.main@PAGE
Lloh554:
	add	x0, x0, l___func__.main@PAGEOFF
Lloh555:
	adrp	x1, l_.str.32@PAGE
Lloh556:
	add	x1, x1, l_.str.32@PAGEOFF
Lloh557:
	adrp	x3, l_.str.41@PAGE
Lloh558:
	add	x3, x3, l_.str.41@PAGEOFF
	mov	w2, #86                         ; =0x56
	bl	___assert_rtn
	.loh AdrpAdd	Lloh557, Lloh558
	.loh AdrpAdd	Lloh555, Lloh556
	.loh AdrpAdd	Lloh553, Lloh554
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
Lloh559:
	adrp	x0, l___func__.main@PAGE
Lloh560:
	add	x0, x0, l___func__.main@PAGEOFF
Lloh561:
	adrp	x1, l_.str.32@PAGE
Lloh562:
	add	x1, x1, l_.str.32@PAGEOFF
Lloh563:
	adrp	x3, l_.str.42@PAGE
Lloh564:
	add	x3, x3, l_.str.42@PAGEOFF
	mov	w2, #90                         ; =0x5a
	bl	___assert_rtn
	.loh AdrpAdd	Lloh563, Lloh564
	.loh AdrpAdd	Lloh561, Lloh562
	.loh AdrpAdd	Lloh559, Lloh560
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
Lloh565:
	adrp	x0, l___func__.main@PAGE
Lloh566:
	add	x0, x0, l___func__.main@PAGEOFF
Lloh567:
	adrp	x1, l_.str.32@PAGE
Lloh568:
	add	x1, x1, l_.str.32@PAGEOFF
Lloh569:
	adrp	x3, l_.str.43@PAGE
Lloh570:
	add	x3, x3, l_.str.43@PAGEOFF
	mov	w2, #94                         ; =0x5e
	bl	___assert_rtn
	.loh AdrpAdd	Lloh569, Lloh570
	.loh AdrpAdd	Lloh567, Lloh568
	.loh AdrpAdd	Lloh565, Lloh566
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
Lloh571:
	adrp	x0, l___func__.main@PAGE
Lloh572:
	add	x0, x0, l___func__.main@PAGEOFF
Lloh573:
	adrp	x1, l_.str.32@PAGE
Lloh574:
	add	x1, x1, l_.str.32@PAGEOFF
Lloh575:
	adrp	x3, l_.str.45@PAGE
Lloh576:
	add	x3, x3, l_.str.45@PAGEOFF
	mov	w2, #101                        ; =0x65
	bl	___assert_rtn
	.loh AdrpAdd	Lloh575, Lloh576
	.loh AdrpAdd	Lloh573, Lloh574
	.loh AdrpAdd	Lloh571, Lloh572
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
Lloh577:
	adrp	x0, l___func__.main@PAGE
Lloh578:
	add	x0, x0, l___func__.main@PAGEOFF
Lloh579:
	adrp	x1, l_.str.32@PAGE
Lloh580:
	add	x1, x1, l_.str.32@PAGEOFF
Lloh581:
	adrp	x3, l_.str.44@PAGE
Lloh582:
	add	x3, x3, l_.str.44@PAGEOFF
	mov	w2, #99                         ; =0x63
	bl	___assert_rtn
	.loh AdrpAdd	Lloh581, Lloh582
	.loh AdrpAdd	Lloh579, Lloh580
	.loh AdrpAdd	Lloh577, Lloh578
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
Lloh583:
	adrp	x0, l___func__.main@PAGE
Lloh584:
	add	x0, x0, l___func__.main@PAGEOFF
Lloh585:
	adrp	x1, l_.str.32@PAGE
Lloh586:
	add	x1, x1, l_.str.32@PAGEOFF
Lloh587:
	adrp	x3, l_.str.38@PAGE
Lloh588:
	add	x3, x3, l_.str.38@PAGEOFF
	mov	w2, #79                         ; =0x4f
	bl	___assert_rtn
	.loh AdrpAdd	Lloh587, Lloh588
	.loh AdrpAdd	Lloh585, Lloh586
	.loh AdrpAdd	Lloh583, Lloh584
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
Lloh589:
	adrp	x0, l___func__.main@PAGE
Lloh590:
	add	x0, x0, l___func__.main@PAGEOFF
Lloh591:
	adrp	x1, l_.str.32@PAGE
Lloh592:
	add	x1, x1, l_.str.32@PAGEOFF
Lloh593:
	adrp	x3, l_.str.34@PAGE
Lloh594:
	add	x3, x3, l_.str.34@PAGEOFF
	mov	w2, #35                         ; =0x23
	bl	___assert_rtn
	.loh AdrpAdd	Lloh593, Lloh594
	.loh AdrpAdd	Lloh591, Lloh592
	.loh AdrpAdd	Lloh589, Lloh590
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

.zerofill __DATA,__bss,_minyar_pool,16777216,3 ; @minyar_pool
.zerofill __DATA,__bss,_minyar_pool_map,524288,0 ; @minyar_pool_map
.zerofill __DATA,__bss,_minyar_pool_max_order,4,2 ; @minyar_pool_max_order
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

.zerofill __DATA,__bss,_minyar_pool_used,8,3 ; @minyar_pool_used
l_.str.45:                              ; @.str.45
	.asciz	"!minyar_pool_used"

l_.str.46:                              ; @.str.46
	.asciz	"{\"kind\":\"result\",\"cpu_nanoseconds\":%llu,\"checksum\":\"%016llx\",\"repetitions\":%zu,\"recovered\":true}\n"

l_.str.47:                              ; @.str.47
	.asciz	"Minyar stopped: %s\n"

.zerofill __DATA,__bss,_minyar_pool_free,512,3 ; @minyar_pool_free
.zerofill __DATA,__bss,_minyar_pool_mask,8,3 ; @minyar_pool_mask
.zerofill __DATA,__bss,_rc_bounded_chunk_tail,8,3 ; @rc_bounded_chunk_tail
l_.str.48:                              ; @.str.48
	.asciz	"an invalid bounded-heap allocation was released."

l_.str.49:                              ; @.str.49
	.asciz	"a bounded-heap allocation was released twice."

l_.str.50:                              ; @.str.50
	.asciz	"the bounded heap is exhausted (including pending cleanup and fragmentation)."

.zerofill __DATA,__bss,_minyar_pool_last_steps,8,3 ; @minyar_pool_last_steps
.zerofill __DATA,__bss,_minyar_pool_max_steps,8,3 ; @minyar_pool_max_steps
.zerofill __DATA,__bss,_minyar_pool_allocation_count,8,3 ; @minyar_pool_allocation_count
.zerofill __DATA,__bss,_minyar_pool_high_water,8,3 ; @minyar_pool_high_water
l_.str.51:                              ; @.str.51
	.asciz	"the computer ran out of memory."

l_.str.52:                              ; @.str.52
	.asciz	"List position %lld is outside its length of %lld."

l_.str.53:                              ; @.str.53
	.asciz	"this record has too many fields."

l_.str.54:                              ; @.str.54
	.asciz	"standard output could not be written."

l_.str.55:                              ; @.str.55
	.asciz	"the joined Text would be too large."

l_.str.57:                              ; @.str.57
	.asciz	"a Text position was outside the Text."

l_.str.58:                              ; @.str.58
	.asciz	"Text contained invalid UTF-8."

l_.str.59:                              ; @.str.59
	.asciz	"a Text position cannot be negative."

.zerofill __DATA,__bss,_text_decode_count,8,3 ; @text_decode_count
l_.str.60:                              ; @.str.60
	.asciz	"a Text slice must stay within the Text and end after it starts."

l_.str.61:                              ; @.str.61
	.asciz	"this Character is not valid Unicode."

l_.str.62:                              ; @.str.62
	.asciz	"a file path cannot contain a zero byte."

l_.str.65:                              ; @.str.65
	.asciz	"-Infinity"

l_.str.66:                              ; @.str.66
	.asciz	"Infinity"

l_.str.67:                              ; @.str.67
	.asciz	"-0.0"

l_.str.68:                              ; @.str.68
	.asciz	"0.0"

l_.str.69:                              ; @.str.69
	.asciz	"%lld.0"

l_.str.70:                              ; @.str.70
	.asciz	"%.*e"

l_.str.71:                              ; @.str.71
	.asciz	"e%+d"

l_.str.72:                              ; @.str.72
	.asciz	"Bytes position %lld is outside its length of %lld."

l_.str.73:                              ; @.str.73
	.asciz	"a %lld-byte value at position %lld does not fit in Bytes of length %lld."

l_.str.74:                              ; @.str.74
	.asciz	"%lld does not fit in %s."

l_.str.76:                              ; @.str.76
	.asciz	"an unsigned 16-bit Integer"

l_.str.77:                              ; @.str.77
	.asciz	"an unsigned 32-bit Integer"

l_.str.78:                              ; @.str.78
	.asciz	"a signed 16-bit Integer"

l_.str.79:                              ; @.str.79
	.asciz	"a signed 32-bit Integer"

l___func__.cpu_nanoseconds:             ; @__func__.cpu_nanoseconds
	.asciz	"cpu_nanoseconds"

l_.str.80:                              ; @.str.80
	.asciz	"clock_gettime(CLOCK_PROCESS_CPUTIME_ID, &value) == 0"

	.section	__DATA,__mod_init_func,mod_init_funcs
	.p2align	3, 0x0
	.quad	_minyar_pool_initialize
.zerofill __DATA,__bss,__MergedGlobals,24,3 ; @_MergedGlobals
.subsections_via_symbols
