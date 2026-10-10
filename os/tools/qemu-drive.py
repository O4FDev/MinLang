#!/usr/bin/env python3
"""Drive a headless Minyar OS in QEMU through QMP: type, click, screenshot.

usage: qemu-drive.py SCRIPT_JSON   (screenshots go to /tmp/mos-shots)
SCRIPT is a list of steps: ["wait", seconds] | ["type", text] | ["key", qcode]
| ["click", x, y] | ["move", x, y] | ["sweep", x0, y0, x1, y1, seconds]
| ["scroll", amount] | ["shot", name] | ["window", name]

MOS_ARCH selects the build to boot, x86_64 (the default) or arm64; MOS_IMAGE
and, for arm64, MOS_KERNEL override the files from build/os/$MOS_ARCH.

With MOS_ATTACH set to a QMP socket (os/tools/show.sh opens
/tmp/minyar-visible-qmp.sock), the script drives that running QEMU instead of
starting a headless one. ["window", name] saves what the visible QEMU window
shows on the host, through `screencapture -l $MOS_WINDOW` (a window number).
"""
import json, os, socket, subprocess, sys, tempfile, time

ARCH = os.environ.get('MOS_ARCH', 'x86_64')
BUILD = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'build', 'os', ARCH)
IMG = os.environ.get('MOS_IMAGE', os.path.join(BUILD, 'minyar-os.img'))
KERNEL = os.environ.get('MOS_KERNEL', os.path.join(BUILD, 'kernel.elf'))


def qemu_command(path, serial):
    """The headless QEMU for MOS_ARCH, as os/Makefile runs it."""
    common = ['-m', '1G', '-display', 'none', '-serial', f'file:{serial}', '-qmp', f'unix:{path},server,nowait',
              '-netdev', 'user,id=net0', '-device', 'e1000,netdev=net0']
    if ARCH == 'arm64':
        accel = 'hvf' if sys.platform == 'darwin' and os.uname().machine == 'arm64' else 'tcg'
        extra = os.environ.get('MOS_QEMU', f'-smp 4 -accel {accel} -cpu {"host" if accel != "tcg" else "max"}').split()
        return ['qemu-system-aarch64', '-M', 'virt', *common, '-kernel', KERNEL, '-device', 'bochs-display',
                '-drive', f'if=none,id=disk,file={IMG},format=raw,snapshot=on',
                '-device', 'virtio-blk-pci,drive=disk,disable-legacy=on',
                '-device', 'virtio-keyboard-pci,disable-legacy=on', '-device', 'virtio-tablet-pci,disable-legacy=on',
                '-device', 'virtio-rng-pci,disable-legacy=on', *extra]
    extra = os.environ.get('MOS_QEMU', '-smp 4 -accel tcg,thread=multi').split()
    return ['qemu-system-x86_64', '-cpu', 'max', '-vga', 'std', *common, '-drive', f'file={IMG},format=raw,if=ide',
            '-device', 'isa-debug-exit,iobase=0xf4,iosize=0x04', *extra]
OUT = os.environ.get('MOS_OUT', '/tmp/mos-shots')


class QMP:
    """A bounded, framed QMP connection; events may precede a split reply."""
    def __init__(self, path, timeout=10):
        self.socket = socket.socket(socket.AF_UNIX)
        self.socket.settimeout(timeout)
        self.sequence = 0
        self.reader = None
        try:
            self.socket.connect(path)
            self.reader = self.socket.makefile('rb')
            if 'QMP' not in self.read():
                raise RuntimeError('QMP greeting missing')
            self.command('qmp_capabilities')
        except BaseException:
            self.close()
            raise

    def read(self):
        line = self.reader.readline()
        if not line:
            raise EOFError('QEMU closed the QMP connection')
        return json.loads(line)

    def command(self, command, **arguments):
        self.sequence += 1
        message = {'execute': command, 'id': self.sequence}
        if arguments:
            message['arguments'] = arguments
        self.socket.sendall((json.dumps(message) + '\n').encode())
        deadline = time.monotonic() + 10
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError(f'QMP timed out: {command}')
            self.socket.settimeout(remaining)
            reply = self.read()
            if reply.get('id') != self.sequence:
                continue
            if 'error' in reply:
                raise RuntimeError(f'QMP {command}: {reply["error"]}')
            return reply

    def close(self):
        if self.reader:
            self.reader.close()
        self.socket.close()

KEYS = {' ': 'spc', '.': 'dot', ',': 'comma', '?': ('shift', 'slash'), '/': 'slash', "'": 'apostrophe',
        '-': 'minus', '!': ('shift', '1'), ':': ('shift', 'semicolon'), ';': 'semicolon', '$': ('shift', '4'),
        '"': ('shift', 'apostrophe'), '(': ('shift', '9'), ')': ('shift', '0'), '&': ('shift', '7'), '\n': 'ret'}


def qmp(sock, command, **arguments):
    return sock.command(command, **arguments)


def keys_for(character):
    if character in KEYS:
        value = KEYS[character]
        return list(value) if isinstance(value, tuple) else [value]
    if character.isupper():
        return ['shift', character.lower()]
    return [character]


def main():
    steps = json.loads(open(sys.argv[1]).read())
    os.makedirs(OUT, exist_ok=True)
    attach = os.environ.get('MOS_ATTACH')
    temporary = tempfile.TemporaryDirectory(prefix='mos-') if not attach else None
    path = attach or os.path.join(temporary.name, 'qmp.sock')
    serial = os.environ.get('MOS_SERIAL', '/tmp/mos-drive-serial.txt')
    qemu = None
    sock = None
    if not attach:
        qemu = subprocess.Popen(qemu_command(path, serial))
    try:
        for _ in range(100):
            if os.path.exists(path):
                break
            time.sleep(0.05)
        sock = QMP(path)
        for step in steps:
            kind = step[0]
            print(json.dumps({'wall': time.time(), 'step': step}), flush=True)
            if kind == 'wait':
                time.sleep(step[1])
            elif kind == 'type':
                for character in step[1]:
                    keys = [{'type': 'qcode', 'data': key} for key in keys_for(character)]
                    qmp(sock, 'send-key', keys=keys, **{'hold-time': 30})
                    time.sleep(0.03)
            elif kind == 'key':
                keys = step[1] if isinstance(step[1], list) else [step[1]]
                qmp(sock, 'send-key', keys=[{'type': 'qcode', 'data': key} for key in keys], **{'hold-time': 30})
                time.sleep(0.04)
            elif kind in ('move', 'click'):
                x = int(step[1] * 32767 / 1720)
                y = int(step[2] * 32767 / 1080)
                qmp(sock, 'input-send-event', events=[{'type': 'abs', 'data': {'axis': 'x', 'value': x}},
                                                      {'type': 'abs', 'data': {'axis': 'y', 'value': y}}])
                if kind == 'click':
                    time.sleep(0.08)
                    qmp(sock, 'input-send-event', events=[{'type': 'btn', 'data': {'down': True, 'button': 'left'}}])
                    time.sleep(0.08)
                    qmp(sock, 'input-send-event', events=[{'type': 'btn', 'data': {'down': False, 'button': 'left'}}])
            elif kind == 'sweep':
                # ["sweep", x0, y0, x1, y1, seconds]: continuous movement at 200 Hz.
                x0, y0, x1, y1, seconds = step[1:6]
                count = max(int(seconds * 200), 1)
                started = time.monotonic()
                for index in range(count + 1):
                    t = index / count
                    x = int((x0 + (x1 - x0) * t) * 32767 / 1720)
                    y = int((y0 + (y1 - y0) * t) * 32767 / 1080)
                    qmp(sock, 'input-send-event', events=[{'type': 'abs', 'data': {'axis': 'x', 'value': x}},
                                                          {'type': 'abs', 'data': {'axis': 'y', 'value': y}}])
                    # Include QMP round-trip time in the 200 Hz period. A
                    # fixed sleep after each command used to run at ~130 Hz.
                    if index < count:
                        time.sleep(max(0, started + seconds * (index + 1) / count - time.monotonic()))
                print(json.dumps({'sweep_events': count + 1, 'elapsed': time.monotonic() - started}), flush=True)
            elif kind == 'scroll':
                button = 'wheel-down' if step[1] > 0 else 'wheel-up'
                for _ in range(abs(step[1])):
                    qmp(sock, 'input-send-event', events=[{'type': 'btn', 'data': {'down': True, 'button': button}}])
                    qmp(sock, 'input-send-event', events=[{'type': 'btn', 'data': {'down': False, 'button': button}}])
            elif kind == 'shot':
                qmp(sock, 'screendump', filename=f'{OUT}/{step[1]}.ppm')
            elif kind == 'window':
                subprocess.run(['screencapture', '-x', '-o', '-l', os.environ['MOS_WINDOW'], f'{OUT}/{step[1]}.png'], check=True)
            else:
                raise ValueError(f'Unknown test step: {kind}')
            sys.stdout.flush()
    finally:
        if sock:
            sock.close()
        if qemu:
            qemu.kill()
            qemu.wait()
        if temporary:
            temporary.cleanup()
    if not attach:
        print(open(serial).read()[-3000:])


if __name__ == '__main__':
    main()
