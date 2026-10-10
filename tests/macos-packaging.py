#!/usr/bin/env python3
"""Exercise bundle installation and preservation across packaging failures."""
from pathlib import Path
import os
import plistlib
import runpy
import shutil
from unittest.mock import patch
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
if sys.platform != 'darwin':
    print('macOS packaging tests skipped')
    sys.exit(0)

with tempfile.TemporaryDirectory(prefix='minyar-packaging-') as directory:
    temp = Path(directory)
    binary = temp / 'hello'
    subprocess.run(['clang','-x','c','-','-o',str(binary)], input='int main(void) { return 0; }',text=True,check=True)
    app = temp / 'App & Unicode é.app'
    def package(output=app, identifier='org.minyar.packaging', env=None):
        return subprocess.run([sys.executable,str(ROOT/'scripts/macos-app.py'), '--binary',str(binary),
                               '--output',str(output),'--identifier',identifier],
                              env=env, text=True,capture_output=True,timeout=30)
    result = package(); assert result.returncode == 0,result.stderr
    info = plistlib.loads((app/'Contents/Info.plist').read_bytes())
    assert info['CFBundleDisplayName'] == app.stem
    assert info['CFBundleExecutable'] == 'application'
    subprocess.run(['codesign','--verify','--strict',str(app)],check=True)
    # The unsigned replacement is never installed if signing or verification fails.
    before = {str(p.relative_to(app)):p.read_bytes() for p in app.rglob('*') if p.is_file()}
    fake = temp/'tools'; fake.mkdir()
    signer = fake/'codesign'; signer.write_text('#!/bin/sh\necho "injected signing failure" >&2\nexit 1\n'); signer.chmod(0o755)
    result = package(env=dict(os.environ,PATH=str(fake)+os.pathsep+os.environ['PATH']))
    assert result.returncode != 0 and 'injected signing failure' in result.stderr,result
    after = {str(p.relative_to(app)):p.read_bytes() for p in app.rglob('*') if p.is_file()}
    assert before == after
    implementation = runpy.run_path(str(ROOT/'scripts/macos-app.py'))['package']
    real_replace = os.replace
    def fail_install(source, destination):
        if Path(source).name == app.name and Path(destination) == app:
            raise OSError('injected installation failure')
        return real_replace(source, destination)
    with patch('os.replace', side_effect=fail_install):
        try:
            implementation(binary, app, 'org.minyar.replacement')
        except OSError as error:
            assert 'injected installation failure' in str(error)
        else:
            raise AssertionError('installation failure was not propagated')
    assert before == {str(p.relative_to(app)):p.read_bytes() for p in app.rglob('*') if p.is_file()}
    assert not list(temp.glob('.minyar-app-*'))
    def fail_install_and_rollback(source, destination):
        if Path(destination) == app:
            raise OSError('injected installation and rollback failure')
        return real_replace(source, destination)
    with patch('os.replace', side_effect=fail_install_and_rollback):
        try:
            implementation(binary, app, 'org.minyar.replacement')
        except OSError as error:
            assert 'previous app preserved at' in str(error)
        else:
            raise AssertionError('rollback failure was not propagated')
    preserved = list(temp.glob('.minyar-app-*/previous.app'))
    assert len(preserved) == 1
    assert before == {str(p.relative_to(preserved[0])):p.read_bytes()
                      for p in preserved[0].rglob('*') if p.is_file()}
    real_replace(preserved[0], app)
    shutil.rmtree(preserved[0].parent)
    lock = app.with_name(app.name+'.minyar-lock'); lock.touch()
    result = package(); assert result.returncode != 0 and 'locked' in result.stderr
    assert lock.exists(); lock.unlink()
    alias = temp/'Alias.app'; alias.symlink_to(app,target_is_directory=True)
    result = package(alias); assert result.returncode != 0 and 'refusing to replace' in result.stderr
    assert alias.is_symlink()
    foreign = temp/'Foreign.app'; foreign.mkdir(); (foreign/'keep').write_text('untouched')
    result = package(foreign); assert result.returncode != 0 and 'refusing to replace' in result.stderr
    assert (foreign/'keep').read_text() == 'untouched'
    result = package(identifier='invalid/id'); assert result.returncode != 0 and 'bundle ID' in result.stderr
    result = package(identifier='org.minyar.updated'); assert result.returncode == 0,result.stderr
    assert plistlib.loads((app/'Contents/Info.plist').read_bytes())['CFBundleIdentifier'] == 'org.minyar.updated'
    subprocess.run(['codesign','--verify','--strict',str(app)],check=True)
    # Icons and resources are copied into the bundle and covered by its signature.
    icon = temp/'Icon.icns'
    subprocess.run(['sips','-s','format','icns','/System/Library/CoreServices/CoreTypes.bundle/Contents/Resources/GenericApplicationIcon.icns',
                    '--out',str(icon)],check=True,capture_output=True)
    resources = temp/'resources'; (resources/'fonts').mkdir(parents=True); (resources/'fonts/Note.txt').write_text('bundled é')
    def package_with(*extra):
        return subprocess.run([sys.executable,str(ROOT/'scripts/macos-app.py'),'--binary',str(binary),'--output',str(app),
                               '--identifier','org.minyar.resources',*extra],text=True,capture_output=True,timeout=30)
    result = package_with('--icon',str(icon),'--resources',str(resources)); assert result.returncode == 0,result.stderr
    assert plistlib.loads((app/'Contents/Info.plist').read_bytes())['CFBundleIconFile'] == 'Icon.icns'
    assert (app/'Contents/Resources/Icon.icns').read_bytes() == icon.read_bytes()
    assert (app/'Contents/Resources/fonts/Note.txt').read_text() == 'bundled é'
    subprocess.run(['codesign','--verify','--strict',str(app)],check=True)
    (temp/'icon.png').write_bytes(b'png')
    result = package_with('--icon',str(temp/'icon.png')); assert result.returncode != 0 and '.icns' in result.stderr
    (resources/'Icon.icns').write_bytes(b'clash')
    result = package_with('--icon',str(icon),'--resources',str(resources)); assert result.returncode != 0 and 'would replace' in result.stderr
    assert (app/'Contents/Resources/fonts/Note.txt').read_text() == 'bundled é'
print('macOS bundle replacement, signing failure, locks, symlinks, icons, resources and Unicode metadata verified')
