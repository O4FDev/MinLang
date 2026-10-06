require 'json'
require 'digest'
base = 'research/2026-10-memory/evidence/local-cleanup-certifier-implementation-review'
decl = <<~IR
  declare void @minyar_stack_enter()
  declare void @minyar_stack_leave()
  declare void @minyar_rc_enter(i64)
  declare void @minyar_rc_leave()
  declare void @minyar_rc_step()
  declare void @minyar_rc_keep(ptr)
  declare ptr @minyar_list_new()
  declare void @minyar_list_add(ptr, i64)
IR
getter = <<~IR
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
IR
root = <<~IR
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
IR
cases = {'same-target-getter' => [decl + getter + root, 'component', 'rejected', 'Both branch outcomes reach raw slot; position 1 is not less than inferred length 1. Allocated capacity is 2.'],
'numeric-ssa-alias' => [decl + root.sub("  %value = call i64 @read(ptr %owner, i64 1)\n", "    %0 = add i64 0, 1\n    %00 = add i64 0, 2\n"), 'component', 'rejected', 'Numeric identifiers 0 and 00 name the same unnamed SSA ID in LLVM; checker treats different strings.'],
'float-block-label' => [decl + root.sub("  %value = call i64 @read(ptr %owner, i64 1)\n", '').sub("entry:", "1.5:"), 'component', 'rejected', 'Unquoted float token is not an LLVM basic block identifier.']}
real = File.read(base + '/inputs/application.ll')
loopy = real.sub('br i1 %value.3, label %for.body.1, label %for.end.3', 'br i1 %value.3, label %for.body.1, label %for.body.1')
start = loopy.index("for.end.3:\n", loopy.index('define i64 @.minyar.fn.minyar_module_1_pick'))
finish = loopy.index("\n}", start)
loopy = loopy[0...start] + loopy[finish..-1]
cases['same-target-loop'] = [loopy, '.minyar.fn.minyar_module_1_snow', 'rejected', 'Removed fallback return tail; duplicate true/false loop-body target is cyclic on false as well. Loop condition rule independently requires false successor outside natural loop.']
cases['actual-control'] = [real, '.minyar.fn.minyar_module_1_snow', 'conditional_component_certificate', 'Single fresh review control; expected W4, V2, F2, 13 definitions, 225 instructions, 29 blocks, loopmax2.']
manifest = cases.map do |name, (ir, entry, expected, reason)|
  path = base + '/' + name + '.ll'
  File.write(path, ir)
  {name: name, path: path, entry: entry, expected_status: expected, reason: reason, sha256: Digest::SHA256.hexdigest(ir)}
end
File.write(base + '/probe-manifest.json', JSON.pretty_generate(manifest) + "\n")
