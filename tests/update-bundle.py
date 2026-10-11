#!/usr/bin/env python3
"""Production bundle encoder roundtrips through the signed owned launch gate."""
import importlib.util
import os
from pathlib import Path
import struct
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location('update_bundle',ROOT/'scripts/update-bundle.py')
bundle=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(bundle)

class Packager(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.lab=Path(self.temp.name)
        self.root=self.lab/'root';self.root.mkdir()
        (self.root/'App.app/Contents/MacOS').mkdir(parents=True)
        (self.root/'App.app/Contents/MacOS/main').write_bytes(b'\x7fELFowned')
        (self.root/'App.app/Contents/Resources').mkdir()
        (self.root/'App.app/Contents/Resources/resource with spaces').write_bytes(b'full resource')
        (self.root/'empty').mkdir()
        self.output=self.lab/'Tolum.pkg'
        self.main='App.app/Contents/MacOS/main'
    def tearDown(self):self.temp.cleanup()

    def test_complete_tree_modes_empty_directories_and_deterministic_output(self):
        first=bundle.prepare(self.root,self.output,self.main)
        data=self.output.read_bytes()
        self.assertEqual(data[:16],b'MINYAR-BUNDLE-1\n')
        self.assertEqual(first['sha256'],__import__('hashlib').sha256(data).hexdigest())
        again=self.lab/'again.pkg'
        self.assertEqual(bundle.prepare(self.root,again,self.main),first)
        self.assertEqual(again.read_bytes(),data)
        at=16;size=struct.unpack_from('>I',data,at)[0];at+=4
        self.assertEqual(data[at:at+size].decode(),self.main);at+=size
        count=struct.unpack_from('>I',data,at)[0];at+=4
        entries={}
        for _ in range(count):
            kind,mode,length,size=struct.unpack_from('>BBIQ',data,at);at+=14
            path=data[at:at+length].decode();at+=length
            entries[path]=(kind,mode,data[at:at+size]);at+=size
        self.assertEqual(at,len(data))
        self.assertEqual(entries['empty'],(ord('D'),0,b''))
        self.assertEqual(entries[self.main][1],1)
        self.assertEqual(entries['App.app/Contents/Resources/resource with spaces'][2],b'full resource')

    def test_failed_final_tree_check_closes_temporary_before_cleanup(self):
        # Windows refuses unlink of an open NamedTemporaryFile. Enforce that
        # API ordering on every host while retaining the original tree error.
        self.output.write_bytes(b'previous artifact')
        factory=bundle.tempfile.NamedTemporaryFile
        unlink=Path.unlink
        commit=bundle.os.fsync
        opened=[]
        def temporary(*args,**kwargs):
            stream=factory(*args,**kwargs);opened.append(stream);return stream
        def remove(path,*args,**kwargs):
            if path.name.startswith('.minyar-bundle-'):
                self.assertTrue(opened[-1].closed,'cleanup must close its temporary first')
            return unlink(path,*args,**kwargs)
        def change_tree(fd):
            commit(fd)
            (self.root/'late unsigned resource').write_bytes(b'not in the index')
        with patch.object(bundle.tempfile,'NamedTemporaryFile',side_effect=temporary), \
             patch.object(bundle.os,'fsync',side_effect=change_tree), \
             patch.object(Path,'unlink',remove):
            with self.assertRaisesRegex(ValueError,'tree changed'):
                bundle.prepare(self.root,self.output,self.main)
        self.assertEqual(self.output.read_bytes(),b'previous artifact')
        self.assertTrue(opened[0].closed)
        self.assertEqual(list(self.lab.glob('.minyar-bundle-*')),[])

    def test_index_must_stay_exact_even_when_directory_metadata_is_unchanged(self):
        # Some providers report fixed directory sizes/creation times. Model
        # that metadata contract while changing the real directory listing.
        # This is a semantic test, not Windows execution evidence.
        self.output.write_bytes(b'previous artifact')
        original=self.root.lstat()
        lstat=Path.lstat;commit=bundle.os.fsync
        changed=False
        def stable_root(path,*args,**kwargs):
            return original if path==self.root else lstat(path,*args,**kwargs)
        def change_tree(fd):
            nonlocal changed
            commit(fd)
            if not changed:
                (self.root/'late unsigned resource').write_bytes(b'not in the index')
                changed=True
        with patch.object(Path,'lstat',stable_root), \
             patch.object(bundle.os,'fsync',side_effect=change_tree):
            with self.assertRaisesRegex(ValueError,'tree changed'):
                bundle.prepare(self.root,self.output,self.main)
        self.assertEqual(self.output.read_bytes(),b'previous artifact')
        self.assertEqual(list(self.lab.glob('.minyar-bundle-*')),[])

    def test_directory_index_hint_can_change_without_changing_the_bundle(self):
        # Actual Windows R8 changed only empty-directory attributes from
        # 0x10000010 to 0x10 after enumeration. Reproduce that metadata
        # contract on other hosts, without calling it Windows verification.
        empty=self.root/'empty';lstat=Path.lstat;calls=0
        info=empty.lstat()
        def observed(path,*args,**kwargs):
            nonlocal calls
            current=lstat(path,*args,**kwargs)
            if path==empty:
                calls+=1
                values={name:getattr(info,name) for name in
                    ('st_dev','st_ino','st_mode','st_size','st_mtime_ns','st_ctime_ns','st_nlink')}
                values['st_file_attributes']=0x10 | (0x10000000 if calls==1 else 0)
                return SimpleNamespace(**values)
            return current
        with patch.object(Path,'lstat',observed):
            first=bundle.prepare(self.root,self.output,self.main)
        second=bundle.prepare(self.root,self.lab/'again.pkg',self.main)
        self.assertEqual(first,second)
        self.assertEqual(self.output.read_bytes(),(self.lab/'again.pkg').read_bytes())

    def test_directory_security_attributes_and_identity_still_fail_closed(self):
        empty=self.root/'empty';lstat=Path.lstat;info=empty.lstat()
        for changed in [{'st_file_attributes':0x410},{'st_file_attributes':0x11},
                        {'st_mode':info.st_mode ^ 0o200},{'st_ino':info.st_ino+1}]:
            calls=0
            def observed(path,*args,**kwargs):
                nonlocal calls
                current=lstat(path,*args,**kwargs)
                if path==empty:
                    calls+=1
                    values={name:getattr(info,name) for name in
                        ('st_dev','st_ino','st_mode','st_size','st_mtime_ns','st_ctime_ns','st_nlink')}
                    values['st_file_attributes']=0x10
                    if calls>1:values.update(changed)
                    return SimpleNamespace(**values)
                return current
            self.output.write_bytes(b'previous artifact')
            with self.subTest(changed=changed),patch.object(Path,'lstat',observed):
                with self.assertRaises(ValueError):
                    bundle.prepare(self.root,self.output,self.main)
            self.assertEqual(self.output.read_bytes(),b'previous artifact')
            self.assertEqual(list(self.lab.glob('.minyar-bundle-*')),[])

    def test_ambiguous_names_bad_entrypoints_and_embedded_output_refused(self):
        for name in ['../escape','/absolute','NUL','missing','App.app/Contents/Resources/resource with spaces']:
            with self.subTest(main=name),self.assertRaises((ValueError,OSError)):
                bundle.prepare(self.root,self.output,name)
        self.assertFalse(self.output.exists())
        (self.root/'Case').write_bytes(b'one');(self.root/'case').write_bytes(b'two')
        # Case-insensitive filesystems present the same inode twice or a single
        # path; native package parser still tests signed duplicate spellings.
        if len([p for p in self.root.iterdir() if p.name in ('Case','case')])==2:
            with self.assertRaises(ValueError):bundle.prepare(self.root,self.output,self.main)
        with self.assertRaises(ValueError):bundle.prepare(self.root,self.root/'embedded.pkg',self.main)

    def test_symlinks_hardlinks_and_special_files_fail_without_replacing_output(self):
        self.output.write_bytes(b'previous artifact')
        external=self.lab/'outside';external.write_bytes(b'external')
        # POSIX actual link cases; Windows link/reparse provider is tested in the
        # native launch suite and must never substitute a copied file fixture.
        if os.name!='nt':
            linked=self.root/'escape';linked.symlink_to(external)
            with self.assertRaises(ValueError):bundle.prepare(self.root,self.output,self.main)
            linked.unlink()
            os.link(external,linked)
            with self.assertRaises(ValueError):bundle.prepare(self.root,self.output,self.main)
            linked.unlink()
            os.mkfifo(linked)
            with self.assertRaises(ValueError):bundle.prepare(self.root,self.output,self.main)
            linked.unlink()
        with self.assertRaises(ValueError):bundle.safe_path('NUL.txt')
        self.assertEqual(self.output.read_bytes(),b'previous artifact')

    def test_internal_framework_aliases_are_refused_without_dereferencing(self):
        if os.name=='nt':self.skipTest('actual POSIX framework symlink layout')
        framework=self.root/'App.app/Contents/Frameworks/Foo.framework'
        (framework/'Versions/A/Resources').mkdir(parents=True)
        (framework/'Versions/A/Foo').write_bytes(b'nested signed code')
        (framework/'Versions/A/Resources/data').write_bytes(b'nested signed resource')
        (framework/'Versions/Current').symlink_to('A',target_is_directory=True)
        (framework/'Foo').symlink_to('Versions/Current/Foo')
        (framework/'Resources').symlink_to('Versions/Current/Resources',target_is_directory=True)
        self.output.write_bytes(b'previous artifact')
        with self.assertRaisesRegex(ValueError,'links'):
            bundle.prepare(self.root,self.output,self.main)
        self.assertEqual(os.readlink(framework/'Versions/Current'),'A')
        self.assertEqual((framework/'Versions/A/Foo').read_bytes(),b'nested signed code')
        self.assertEqual(self.output.read_bytes(),b'previous artifact')

    def test_unsupported_attribute_policy_covers_root_directories_and_files(self):
        # A policy unit test, not a claim of macOS xattr/signing validation.
        # The final tree cannot silently omit unsupported attributes anywhere.
        for node in [self.root,self.root/'App.app',self.root/self.main]:
            for attribute in ['com.apple.cs.CodeDirectory','com.apple.ResourceFork']:
                self.output.write_bytes(b'previous artifact')
                with self.subTest(node=node,attribute=attribute):
                    with patch.object(bundle.os,'listxattr',
                        side_effect=lambda path,**_: [attribute] if Path(path)==node else [],create=True):
                        with self.assertRaisesRegex(ValueError,'unsupported'):
                            bundle.prepare(self.root,self.output,self.main)
                    self.assertEqual(self.output.read_bytes(),b'previous artifact')

if __name__=='__main__':unittest.main()
