declare void @minyar_stack_enter()
declare void @minyar_stack_leave()
declare void @minyar_rc_enter(i64)
declare void @minyar_rc_leave()
declare void @minyar_rc_step()
declare void @minyar_rc_keep(ptr)
declare ptr @minyar_list_new()
declare void @minyar_list_add(ptr, i64)
define void @component() {
1.5:
  call void @minyar_stack_enter()
  call void @minyar_rc_enter(i64 0)
  %owner = call ptr @minyar_list_new()
  call void @minyar_list_add(ptr %owner, i64 7)
  call void @minyar_rc_keep(ptr %owner)
  call void @minyar_rc_step()
  call void @minyar_rc_leave()
  call void @minyar_stack_leave()
  ret void
}
