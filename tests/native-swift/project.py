#!/usr/bin/env python3
"""Target-based source selection, independent of the host SDK/compiler."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('native_project', ROOT / 'scripts/native_project.py')
project = importlib.util.module_from_spec(spec)
spec.loader.exec_module(project)


class ProjectTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()

    def file(self, name):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('')
        return path

    def test_target_overrides_and_shared_fallback(self):
        paths = [self.file(name) for name in ['Toolbar.min', 'Toolbar.mac.min',
                 'Toolbar.windows.min', 'Counter.min', 'MacOnly.mac.min']]
        for target, expected in [('mac', {'Toolbar.mac.min', 'Counter.min', 'MacOnly.mac.min'}),
                                 ('windows', {'Toolbar.windows.min', 'Counter.min'}),
                                 ('linux', {'Toolbar.min', 'Counter.min'})]:
            self.assertEqual({p.name for p in project.select_variants(paths, target)}, expected)

    def test_project_entry_and_feature_folders(self):
        entry = self.file('app.min')
        component = self.file('notes/Editor.min')
        helper = self.file('notes/storage.min')
        self.file('notes/Editor.windows.min')
        for argument in [self.root, entry]:
            selected, root = project.resolve_sources([argument], 'mac')
            self.assertEqual(root, self.root)
            self.assertEqual(selected, [entry, component, helper])

    def test_generated_hidden_and_vendor_directories_are_excluded(self):
        entry = self.file('app.min')
        for name in ['build/bad.min', 'dist/bad.min', '.cache/bad.min',
                     'target/bad.min', 'node_modules/bad.min', 'Other.app/bad.min',
                     'Library.framework/bad.swift', '.hidden.min']:
            self.file(name)
        self.assertEqual(project.resolve_sources([self.root], 'mac')[0], [entry])

    def test_platform_specific_entry(self):
        entry = self.file('app.mac.min')
        self.assertEqual(project.resolve_sources([self.root], 'mac')[0], [entry])
        with self.assertRaisesRegex(ValueError, 'requires app.min'):
            project.resolve_sources([self.root], 'windows')

    def test_nested_apps_establish_independent_boundaries(self):
        outer = self.file('app.min')
        shared = self.file('outer/Screen.min')
        inner = self.file('tools/editor/app.min')
        inner_view = self.file('tools/editor/Screen.min')
        # Even an app whose entry targets another platform owns its subtree.
        self.file('tools/windows/app.windows.min')
        self.file('tools/windows/Screen.min')
        self.assertEqual(project.resolve_sources([self.root], 'mac')[0], [outer, shared])
        self.assertEqual(project.resolve_sources([inner], 'mac')[0], [inner, inner_view])

    def test_workspace_with_sibling_apps_requires_an_app_selection(self):
        first = self.file('apps/first/app.min')
        second = self.file('apps/second/app.min')
        with self.assertRaisesRegex(ValueError, 'select an individual app'):
            project.resolve_sources([self.root], 'mac')
        self.assertEqual(project.resolve_sources([first.parent], 'mac')[0], [first])
        self.assertEqual(project.resolve_sources([second.parent], 'mac')[0], [second])

    def test_explicit_sources_do_not_discover_neighbors(self):
        main = self.file('main.min')
        helper = self.file('helper.min')
        self.file('unrelated.min')
        self.assertEqual(project.resolve_sources([main, helper], 'mac'), ([main, helper], None))

    def test_missing_entry_and_duplicate_inputs(self):
        main = self.file('main.min')
        with self.assertRaisesRegex(ValueError, 'requires app.min'):
            project.resolve_sources([self.root], 'mac')
        with self.assertRaisesRegex(ValueError, 'duplicate source'):
            project.resolve_sources([main, main], 'mac')

    def test_source_symlinks_are_rejected(self):
        self.file('app.min')
        source = self.file('real.min')
        (self.root / 'alias.min').symlink_to(source)
        with self.assertRaisesRegex(ValueError, 'symbolic link'):
            project.resolve_sources([self.root], 'mac')

    def test_invalid_or_empty_target_selection(self):
        source = self.file('Only.windows.min')
        with self.assertRaisesRegex(ValueError, 'no sources'):
            project.resolve_sources([source], 'mac')
        with self.assertRaisesRegex(ValueError, 'unknown target'):
            project.resolve_sources([source], 'unknown')


if __name__ == '__main__':
    unittest.main()
