#!/usr/bin/env python3
"""Check module-body reuse, interfaces, and stable identities."""
from pathlib import Path
import os
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[1]
COMPILER=Path(os.environ.get('MINYAR_TEST_COMPILER',ROOT/'build/minyarc-modules')).resolve()
BASE=ROOT/'build/minyarc'


def run(command,success=True):
    result=subprocess.run(list(map(str,command)),capture_output=True,text=True,timeout=60)
    assert (result.returncode==0)==success,result.stderr
    return result


with tempfile.TemporaryDirectory(prefix='minyar-module-interface-') as temp:
    directory=Path(temp)
    empty=directory/'empty.state'; empty.write_text('')
    prior=directory/'prior.state'; prior.write_text('')
    next_state=directory/'next.state'; stats=directory/'stats.txt'
    cold=directory/'cold.ll'; warm=directory/'warm.ll'

    def compile(entry,*,expected=None,counts=None,update=True):
        result=run([COMPILER,entry,warm,'--module-state',prior,next_state,stats])
        fields=stats.read_text().split()
        measured=tuple(map(int,fields[:6]))
        table_reused=fields[6]=='true'
        state=next_state.read_bytes()
        if update and state: prior.write_bytes(state)
        run([COMPILER,entry,cold,'--module-state',empty,next_state,stats])
        assert cold.read_bytes()==warm.read_bytes(),'clean and reused module LLVM differ'
        if counts is not None: assert measured==counts,(entry,measured,counts)
        if expected is not None:
            binary=directory/'program'
            run(['clang','-O0','-Wno-override-module',warm,ROOT/'build/minyar-runtime.o','-o',binary])
            assert run([binary]).stdout==expected
            # Also compare native behavior with the unmodified production path.
            run([BASE,entry,directory/'base.ll'])
            run(['clang','-O0','-Wno-override-module',directory/'base.ll',ROOT/'build/minyar-runtime.o','-o',directory/'base'])
            assert run([directory/'base']).stdout==expected
        return measured,table_reused

    for case,expected in [('basic','Hello, Ada\n42\nAda\n'),('diamond','42\n'),('explicit-main','42\n'),('windows-path','42\n')]:
        prior.write_text('')
        entry=ROOT/f'tests/modules/{case}/main.min'
        first,_=compile(entry,expected=expected)
        second,table=compile(entry,expected=expected)
        assert second==(first[1],0,0,first[1],0,0),second
        assert table

    # A private record returned through an exported function is part of its
    # interface closure, even though callers cannot directly name that record.
    prior.write_text('')
    leaf=directory/'leaf.min'; library=directory/'library.min'; entry=directory/'main.min'
    leaf_source='''record Hidden { value: Integer, label: Text }
public function make(): Hidden { return Hidden { value: 40, label: "λ\\n@.text.123" } }
'''
    library_source='''use "./leaf.min" as leaf
public function answer(): Integer { return leaf.make().value }
public function label(): Text { return leaf.make().label }
function secret(): Integer { return 5 }
'''
    main='''use "./library.min" as library
function main() {
    print(library.answer() + 2)
    print(library.label())
}
'''
    leaf.write_text(leaf_source); library.write_text(library_source); entry.write_text(main)
    compile(entry,expected='42\nλ\n@.text.123\n',counts=(0,3,3,0,5,0))
    compile(entry,counts=(3,0,0,3,0,0))
    library.write_text(library_source.replace('return 5', 'return 6'))
    counts,table=compile(entry,expected='42\nλ\n@.text.123\n',counts=(2,1,1,2,3,0))
    assert table
    entry.write_text(main.replace('    print(library.answer()', '    let moved = "entry literal"\n    print(library.answer()'))
    counts,table=compile(entry,expected='42\nλ\n@.text.123\n',counts=(2,1,1,2,1,0))
    assert table
    before=leaf.stat()
    leaf.write_text(leaf_source.replace('value: 40','value: 41'))
    os.utime(leaf,ns=(before.st_atime_ns,before.st_mtime_ns))
    counts,table=compile(entry,expected='43\nλ\n@.text.123\n',counts=(2,1,1,2,1,0))
    assert table
    # Changing a hidden record's layout invalidates its direct consumer; the
    # entry only sees Integer/Text and therefore remains reusable.
    leaf.write_text(leaf_source.replace('value: Integer, label: Text','label: Text, value: Integer'))
    counts,table=compile(entry,expected='42\nλ\n@.text.123\n',counts=(1,2,2,2,4,0))
    assert not table

    # Recursively exported private type closure also crosses an intermediate
    # function: a third-module field-layout edit must invalidate the entry.
    library.write_text('use "./leaf.min" as leaf\npublic function get(): leaf.Hidden { return leaf.make() }\n')
    # Directly naming the private type in a signature is correctly rejected.
    failure=run([COMPILER,entry,warm,'--module-state',prior,next_state,stats],success=False)
    assert 'private to its module' in failure.stderr
    public_leaf=leaf_source.replace('record Hidden','public record Hidden')
    leaf.write_text(public_leaf)
    entry.write_text('use "./library.min" as library\nprint(library.get().value)\n')
    compile(entry,expected='40\n')
    leaf.write_text(public_leaf.replace('value: Integer, label: Text','label: Text, value: Integer'))
    counts,_=compile(entry,expected='40\n')
    assert counts[0]==0 and counts[1]==3,counts

    # Public -> private visibility must invalidate a constructor even when
    # the record remains present in the type closure through another export.
    # Restore the layout first so visibility is the only interface change.
    leaf.write_text(public_leaf)
    entry.write_text('use "./leaf.min" as leaf\nlet value = leaf.Hidden { value: 7, label: "x" }\nprint(value.value)\n')
    compile(entry,expected='7\n')
    leaf.write_text(leaf_source)
    saved=prior.read_bytes()
    failure=run([COMPILER,entry,warm,'--module-state',prior,next_state,stats],success=False)
    assert 'private to its module' in failure.stderr,failure.stderr
    assert prior.read_bytes()==saved

    # Adding/reordering unrelated imports cannot rename existing code/type
    # identities. An extra earlier record also moves in-memory numeric IDs.
    leaf.write_text(public_leaf)
    unused=directory/'unused.min'
    unused.write_text('public record Earlier { value: Integer }\npublic function extra(): Integer { return 3 }\n')
    base_main='use "./leaf.min" as leaf\nprint(leaf.make().value)\n'
    entry.write_text(base_main);compile(entry,expected='40\n')
    entry.write_text('use "./unused.min" as unused\n'+base_main)
    counts,table=compile(entry,expected='40\n')
    assert counts[:2]==(1,2) and not table,counts
    entry.write_text(base_main+'use "./unused.min" as unused\n')
    counts,table=compile(entry,expected='40\n')
    assert counts[:2]==(2,1),counts
    entry.write_text(base_main)
    counts,_=compile(entry,expected='40\n')
    assert counts[:2]==(1,1),counts

    # A cached import still has to exist, and changed cycles/top-level code
    # are never hidden by the artifact.
    for source,diagnostic in [
        ('use "./main.min" as main\n'+public_leaf,'module import cycle'),
        (public_leaf+'\nprint(1)\n','executable top-level statements'),
        (public_leaf.replace('return Hidden','return missing'),'expected'),
    ]:
        leaf.write_text(source)
        failure=run([COMPILER,entry,warm,'--module-state',prior,next_state,stats],success=False)
        if diagnostic!='expected': assert diagnostic in failure.stderr,failure.stderr
    leaf.unlink()
    assert 'could not be opened' in run([COMPILER,entry,warm,'--module-state',prior,next_state,stats],success=False).stderr

    # Diagnostics after long omitted bodies retain original source lines.
    leaf.write_text(public_leaf)
    bad='function longBody(): Integer {\n'+'    let x = 1\n'*20+'    return 1\n}\n\npublic function bad(value: Missing): Integer { return 0 }\n'
    library.write_text(bad)
    entry.write_text('use "./library.min" as library\nprint(1)\n')
    expected_line=str(bad[:bad.index('public function bad')].count('\n')+1)
    failure=run([COMPILER,entry,warm,'--module-state',prior,next_state,stats],success=False)
    assert f'{library}:{expected_line}, column ' in failure.stderr,failure.stderr

    # Unicode, quotes and separators in paths must remain injective identities.
    odd=directory/'space λ "quote" | part'; odd.mkdir()
    (odd/'lib.min').write_text('public function answer(): Integer { return 42 }\n')
    (odd/'main.min').write_text('use "./lib.min" as lib\nprint(lib.answer())\n')
    prior.write_text('')
    compile(odd/'main.min',expected='42\n')
    compile(odd/'main.min',expected='42\n',counts=(2,0,0,2,0,0))

    # Explicit terminators after generic field types must survive interface
    # normalization even where a literal newline would not produce a token.
    declarations=directory/'declarations.min'
    declarations.write_text('record Node { children: List<Node>; values: List<Integer>; }\n')
    prior.write_text('')
    compile(declarations,counts=(0,1,1,0,0,1))
    compile(declarations,counts=(1,0,0,1,0,0))

    # Recursive type closure terminates and retains nominal identity even
    # when a new unrelated record shifts every in-memory record index.
    tree=directory/'tree.min'
    tree_source='''public record Node { value: Integer, children: List<Node> }
public function make(): Node {
    let child = Node { value: 2, children: [] }
    return Node { value: 40, children: [child] }
}
public function total(node: Node): Integer {
    let value = node.value
    let i = 0
    while i < node.children.length {
        value = value + total(node.children[i])
        i = i + 1
    }
    return value
}
'''
    tree.write_text(tree_source)
    tree_main='use "./tree.min" as tree\nprint(tree.total(tree.make()))\n'
    entry.write_text(tree_main);prior.write_text('')
    compile(entry,expected='42\n')
    compile(entry,expected='42\n',counts=(2,0,0,2,0,0))
    entry.write_text('use "./unused.min" as unused\n'+tree_main)
    counts,_=compile(entry,expected='42\n')
    assert counts[:2]==(1,2),counts
    tree.write_text(tree_source.replace('value: Integer, children: List<Node>','children: List<Node>, value: Integer'))
    counts,_=compile(entry,expected='42\n')
    assert counts[:2]==(1,2),counts

    for fixture in sorted((ROOT/'examples').glob('*.min')):
        prior.write_text('')
        first,_=compile(fixture)
        counts,table=compile(fixture)
        assert counts==(first[1],0,0,first[1],0,0),counts
        assert table

print('module interfaces: native equivalence, actual body bypass, stable identities, typed private closures, invalidation and source diagnostics verified')
