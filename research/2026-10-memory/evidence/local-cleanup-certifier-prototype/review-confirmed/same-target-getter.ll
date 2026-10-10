declare void @minyar_stack_enter()
declare void @minyar_stack_leave()
declare void @minyar_rc_enter(i64)
declare void @minyar_rc_leave()
declare void @minyar_rc_step()
declare void @minyar_rc_keep(ptr)
declare ptr @minyar_list_new()
declare void @minyar_list_add(ptr, i64)
define i64 @read(ptr %list, i64 %position) {
entry:
  %length.pointer = getelementptr {ptr,i64,i64}, ptr %list, i32 0, i32 1
  %length = load i64, ptr %length.pointer
  %valid = icmp ult i64 %position, %length
  br i1 %valid, label %good, label %good
good:
  %backing = load ptr, ptr %list
  %slot = getelementptr i64, ptr %backing, i64 %position
  %word = load i64, ptr %slot
  ret i64 %word
}
define void @component() {
entry:
  call void @minyar_stack_enter()
  call void @minyar_rc_enter(i64 0)
  %owner = call ptr @minyar_list_new()
  call void @minyar_list_add(ptr %owner, i64 7)
  call void @minyar_rc_keep(ptr %owner)
  %value = call i64 @read(ptr %owner, i64 1)
  call void @minyar_rc_step()
  call void @minyar_rc_leave()
  call void @minyar_stack_leave()
  ret void
}
