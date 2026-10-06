	.section	__TEXT,__text,regular,pure_instructions
	.build_version macos, 26, 0	sdk_version 26, 2
	.globl	_research_checksum              ; -- Begin function research_checksum
	.p2align	2
_research_checksum:                     ; @research_checksum
	.cfi_startproc
; %bb.0:
	mov	x8, x0
	mov	x0, #8997                       ; =0x2325
	movk	x0, #33826, lsl #16
	movk	x0, #40164, lsl #32
	movk	x0, #52210, lsl #48
	cbz	x1, LBB0_3
; %bb.1:
	mov	x9, #435                        ; =0x1b3
	movk	x9, #256, lsl #32
LBB0_2:                                 ; =>This Inner Loop Header: Depth=1
	ldr	x10, [x8], #8
	cmp	x10, x2
	cset	w11, eq
	cmp	x2, #0
	csel	x10, x10, x11, eq
	eor	x10, x10, x0
	mul	x0, x10, x9
	subs	x1, x1, #1
	b.ne	LBB0_2
LBB0_3:
	ret
	.cfi_endproc
                                        ; -- End function
.subsections_via_symbols
