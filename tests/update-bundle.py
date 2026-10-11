#!/usr/bin/env python3
"""Production bundle encoder roundtrips through the signed owned launch gate."""
import importlib.util
import os
from pathlib import Path
import struct
import tempfile
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
