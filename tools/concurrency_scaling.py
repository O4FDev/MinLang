#!/usr/bin/env python3
"""Freeze and run the shared FrozenBytes scaling qualification on eight CPUs."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import random
import re
import resource
import shutil
import statistics
import subprocess
import sys
import time

WIDTHS = (1, 2, 4, 8)
ROUNDS = 40
WARMUPS = 3
ORDER_SEED = 20261012
BOOTSTRAP_SEED = 424242
BOOTSTRAPS = 20000
ROOT = Path(__file__).resolve().parents[1]
WORKLOAD = ROOT / "benchmarks/concurrency/frozen-lcg.min"
WORKLOAD_SHA256 = "6b6f61b85c92b491375172b57781b282dec16f59351e8b85ca8216ab834a97f3"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def oracle() -> str:
    factor = pow(48271, 4096, 2147483647)
    total = sum(((block * 104729 + 20261012) % 2147483647) * factor % 2147483647
                for block in range(131072))
    return str(total) + "\n"


def schedule(rounds: int, seed: int) -> list[list[int]]:
    generator = random.Random(seed)
    result = []
    for _ in range(rounds):
        order = list(WIDTHS)
        generator.shuffle(order)
        result.append(order)
    return result


def cpu_ticks() -> dict[int, list[int]]:
    result = {}
    for line in Path("/proc/stat").read_text().splitlines():
        name, *fields = line.split()
        if name.startswith("cpu") and name[3:].isdigit():
            # guest/guest_nice already belong to user/nice; do not double count.
            result[int(name[3:])] = [int(v) for v in fields[:8]]
    return result


def cpu_activity(before: dict[int, list[int]], after: dict[int, list[int]],
                 cpus: list[int], child_seconds: float = 0) -> dict[str, float]:
    ticks = [sum(after[cpu][i] - before[cpu][i] for cpu in cpus) for i in range(8)]
    total = sum(ticks)
    if total <= 0:
        raise RuntimeError("CPU accounting interval is too short")
    busy = total - ticks[3] - ticks[4] - ticks[7]
    child_ticks = child_seconds * os.sysconf("SC_CLK_TCK")
    return {"other_busy_fraction": max(0, busy - child_ticks) / total,
            "steal_fraction": ticks[7] / total}


def quiet(activity: dict[str, float]) -> bool:
    return activity["other_busy_fraction"] <= .02 and activity["steal_fraction"] <= .005


def bootstrap_interval(values: list[float]) -> tuple[float, float]:
    if len(values) != ROUNDS:
        raise ValueError("all 40 paired rounds are required")
    generator = random.Random(BOOTSTRAP_SEED)
    estimates = sorted(statistics.median(generator.choices(values, k=len(values)))
                       for _ in range(BOOTSTRAPS))
    return (estimates[math.floor(.025 * (BOOTSTRAPS - 1))],
            estimates[math.ceil(.975 * (BOOTSTRAPS - 1))])


def write_new(path: Path, value: object) -> None:
    with path.open("x") as stream:
        json.dump(value, stream, indent=2)
        stream.write("\n")


def resource_identity(membership: str | None = None, root: Path = Path('/sys/fs/cgroup')) -> dict:
    if membership is None:
        membership = Path('/proc/self/cgroup').read_text()
    groups = []
    for line in membership.splitlines():
        hierarchy, controllers, location = line.split(':', 2)
        relative = Path(location)
        if not relative.is_absolute() or '..' in relative.parts:
            raise RuntimeError('invalid CPU cgroup membership')
        parts = list(relative.parts[1:])
        canonical_parts = list(parts)
        if parts and re.fullmatch(r'session-[0-9]+\.scope', parts[-1]):
            canonical_parts[-1] = 'session.scope'
        if controllers and not {'cpu', 'cpuset'}.intersection(controllers.split(',')):
            groups.append({'hierarchy': hierarchy, 'controllers': controllers,
                           'path': '/' + '/'.join(canonical_parts)})
            continue
        base = root if not controllers else root / controllers
        limits = []
        for depth in range(len(parts) + 1):
            directory = base.joinpath(*parts[:depth])
            values = {}
            for name in ('cpu.max', 'cpu.max.burst', 'cpu.weight', 'cpu.cfs_quota_us', 'cpu.cfs_period_us',
                         'cpuset.cpus', 'cpuset.cpus.effective'):
                try:
                    values[name] = {'availability': 'exposed', 'value': (directory / name).read_text()}
                except FileNotFoundError:
                    values[name] = {'availability': 'not exposed in guest'}
                except OSError as error:
                    values[name] = {'availability': 'unreadable', 'errno': error.errno}
            limits.append({'path': '/' + '/'.join(canonical_parts[:depth]), 'values': values})
        groups.append({'hierarchy': hierarchy, 'controllers': controllers,
                       'path': '/' + '/'.join(canonical_parts), 'ancestors': limits})
    return {'version': 2, 'cpu_count': os.cpu_count(),
            'affinity': sorted(os.sched_getaffinity(0)), 'groups': groups}


def resource_snapshot() -> dict:
    membership = Path('/proc/self/cgroup').read_text()
    paths = []
    for line in membership.splitlines():
        _, controllers, location = line.split(':', 2)
        if controllers and not {'cpu', 'cpuset'}.intersection(controllers.split(',')):
            continue
        base = Path('/sys/fs/cgroup') if not controllers else Path('/sys/fs/cgroup') / controllers
        parts = Path(location).parts[1:]
        paths.extend(str(base.joinpath(*parts[:depth])) for depth in range(len(parts) + 1))
    return {'raw_membership': membership, 'raw_ancestor_paths': paths,
            'identity': resource_identity(membership)}


def register(arguments: argparse.Namespace) -> None:
    if sys.platform != "linux":
        raise RuntimeError("qualification requires the admitted Linux Boat host")
    cpus = sorted(os.sched_getaffinity(0))
    if digest(WORKLOAD) != WORKLOAD_SHA256:
        raise RuntimeError("original frozen workload changed")
    if len(cpus) != 8:
        raise RuntimeError(f"exactly eight available CPUs required, found {cpus}")
    executable = arguments.executable.resolve(strict=True)
    lowered = arguments.lowered_llvm.resolve(strict=True)
    llvm = lowered.read_text()
    if '; minyar-thread-runtime: 1' not in llvm or not all(
            ('@' + symbol) in llvm for symbol in ('minyar_thread_spawn', 'minyar_frozen_bytes_take')):
        raise RuntimeError('lowered program must use the checked managed thread/shared-value API')
    clang = Path(shutil.which(arguments.clang) or arguments.clang).resolve(strict=True)
    quota = {}
    for name in ("/sys/fs/cgroup/cpu.max", "/sys/fs/cgroup/cpu/cpu.cfs_quota_us",
                 "/sys/fs/cgroup/cpu/cpu.cfs_period_us", "/proc/self/cgroup"):
        path = Path(name)
        quota[name] = path.read_text() if path.exists() else "not exposed in guest"
    protocol = {
        "frozen_at_unix_ns": time.time_ns(), "executable": str(executable),
        "executable_sha256": digest(executable), "workload_sha256": digest(WORKLOAD),
        "lowered_llvm": str(lowered), "lowered_llvm_sha256": digest(lowered),
        "sampler_sha256": digest(Path(__file__)), "expected_stdout": oracle(),
        "source_shas": {"candidate": arguments.candidate_sha,
                        "compiler": arguments.compiler_sha, "runtime": arguments.runtime_sha},
        "build_flags": arguments.build_flags, "memory_profile": arguments.memory_profile,
        "python": sys.version, "toolchain": subprocess.check_output(
            [arguments.clang, "--version"], text=True),
        "clang_path": str(clang), "clang_sha256": digest(clang), "kernel": list(os.uname()),
        "guest_topology": subprocess.check_output(["lscpu", "-J"], text=True),
        "affinity": cpus, "quota": quota, "resource_identity": resource_identity(),
        "resource_snapshot": resource_snapshot(),
        "work": {"blocks": 131072, "dependent_steps_per_block": 4096,
                 "seed": 20261012, "input_bytes": 1048576,
                 "kernel": "x = x * 48271 % 2147483647; sum final x per block"},
        "timing": "whole executable wall time: input creation, publication, launch, work, join, output",
        "warmup_order": schedule(WARMUPS, ORDER_SEED + 1),
        "paired_order": schedule(ROUNDS, ORDER_SEED),
        "estimator": "median of 40 within-round T1/Tn ratios",
        "interval": {"method": "paired percentile bootstrap of median ratios",
                     "replicates": BOOTSTRAPS, "seed": BOOTSTRAP_SEED,
                     "bounds": "floor(.025*(B-1)), ceil(.975*(B-1))"},
        "quiet": {"preflight_seconds": 5, "other_busy_fraction_max": .02,
                  "steal_fraction_max": .005, "no_post_result_sample_exclusion": True},
        "gates": {"median_eight_min": 7.2, "lower_95_eight_min": 6.4},
    }
    if arguments.control_executable:
        control = arguments.control_executable.resolve(strict=True)
        protocol['single_thread_control'] = {'executable': str(control),
            'sha256': digest(control), 'source_sha': arguments.control_sha,
            'upper_95_ratio_max': 1.01}
    protocol["protocol_sha256"] = hashlib.sha256(canonical(protocol)).hexdigest()
    write_new(arguments.protocol, protocol)
    print(f"frozen {arguments.protocol}; no timed qualification has run")


def observe_control(protocol):
    before = cpu_ticks()
    usage = resource.getrusage(resource.RUSAGE_CHILDREN)
    started = time.perf_counter_ns()
    completed = subprocess.run([protocol['single_thread_control']['executable'], '1'],
                               capture_output=True, text=True, timeout=120)
    seconds = (time.perf_counter_ns() - started) / 1e9
    after = resource.getrusage(resource.RUSAGE_CHILDREN)
    cpu = after.ru_utime + after.ru_stime - usage.ru_utime - usage.ru_stime
    sample = {'seconds': seconds, 'child_cpu_seconds': cpu,
              'activity': cpu_activity(before, cpu_ticks(), protocol['affinity'], cpu),
              'returncode': completed.returncode, 'stdout': completed.stdout,
              'stderr': completed.stderr}
    if (completed.returncode, completed.stdout, completed.stderr) != (0, protocol['expected_stdout'], ''):
        raise RuntimeError('incorrect original single-thread control result')
    return sample


def run(arguments: argparse.Namespace) -> None:
    protocol = json.loads(arguments.protocol.read_text())
    seal = protocol.pop("protocol_sha256")
    if hashlib.sha256(canonical(protocol)).hexdigest() != seal:
        raise RuntimeError("frozen protocol changed")
    for path, key in ((Path(protocol["executable"]), "executable_sha256"),
                      (WORKLOAD, "workload_sha256"), (Path(__file__), "sampler_sha256"),
                      (Path(protocol['lowered_llvm']), 'lowered_llvm_sha256'),
                      (Path(protocol['clang_path']), 'clang_sha256')):
        if digest(path) != protocol[key]:
            raise RuntimeError(f"frozen artifact changed: {path}")
    if sorted(os.sched_getaffinity(0)) != protocol["affinity"]:
        raise RuntimeError("affinity changed since registration")
    if sys.version != protocol['python'] or list(os.uname()) != protocol['kernel']:
        raise RuntimeError('Python or kernel changed since registration')
    if subprocess.check_output(['lscpu', '-J'], text=True) != protocol['guest_topology']:
        raise RuntimeError('CPU topology changed since registration')
    for name, expected in protocol['quota'].items():
        if name == '/proc/self/cgroup' and 'resource_identity' in protocol:
            continue
        path = Path(name)
        if (path.read_text() if path.exists() else 'not exposed in guest') != expected:
            raise RuntimeError('CPU quota/cgroup configuration changed since registration')
    resources = resource_snapshot() if 'resource_identity' in protocol else None
    if resources and resources['identity'] != protocol['resource_identity']:
        raise RuntimeError('CPU cgroup ancestry, limits or availability changed since registration')
    if protocol["paired_order"] != schedule(ROUNDS, ORDER_SEED):
        raise RuntimeError("paired order or sample count changed")
    if protocol["warmup_order"] != schedule(WARMUPS, ORDER_SEED + 1):
        raise RuntimeError("warmup order changed")
    if protocol["workload_sha256"] != WORKLOAD_SHA256:
        raise RuntimeError("original frozen workload changed")
    if protocol['gates'] != {'median_eight_min': 7.2, 'lower_95_eight_min': 6.4}:
        raise RuntimeError('original scaling gates changed')
    control = protocol.get('single_thread_control')
    if control and (digest(Path(control['executable'])) != control['sha256'] or
                    control['upper_95_ratio_max'] != 1.01):
        raise RuntimeError('single-thread control or original CPU gate changed')
    item = getattr(arguments, 'item', None)
    rounds = [(phase, index, order)
              for phase, orders in (("warmup", protocol["warmup_order"]),
                                    ("paired", protocol["paired_order"]))
              for index, order in enumerate(orders)]
    resumed = item is not None and item > 0
    if resumed:
        result = json.loads(arguments.results.read_text())
        if result["protocol_sha256"] != seal or "failure" in result or result["qualified"]:
            raise RuntimeError("cannot resume a different, failed or completed campaign")
        expected = [(phase, index, width) for phase, index, order in rounds[:item] for width in order]
        actual = [(s['phase'], s['round'], s['threads']) for s in result['samples']]
        if actual != expected or len(result['preflights']) != item:
            raise RuntimeError("items must run exactly once in the original order")
        if control and len(result['single_thread_pairs']) != item:
            raise RuntimeError('single-thread pairs must be retained in original order')
    else:
        result = {"protocol_sha256": seal, "started_unix_ns": time.time_ns(),
                  "samples": [], "preflights": [], "single_thread_pairs": [], "qualified": False}
    if resources:
        result.setdefault('resource_snapshots', []).append(resources)
    checks = []
    for attempt in range(10):
        before = cpu_ticks()
        time.sleep(5)
        activity = cpu_activity(before, cpu_ticks(), protocol["affinity"])
        checks.append(activity)
        if quiet(activity):
            break
        if attempt < 9:
            time.sleep(30)
    result.setdefault('preflight_waits', []).append({'item': item, 'checks': checks})
    result['preflights'].append(activity)
    if not resumed: result['preflight'] = activity
    # Retain failed and interrupted runs; never overwrite or filter their samples.
    with arguments.results.open("r+" if resumed else "x") as stream:
        def save() -> None:
            stream.seek(0)
            json.dump(result, stream, indent=2)
            stream.write("\n")
            stream.truncate()
            stream.flush()
        save()
        if not quiet(activity):
            result['failure'] = 'host failed frozen quiet criterion'
            save()
            raise RuntimeError("host failed frozen quiet criterion; retained unqualified run")
        try:
            selected = rounds if item is None else rounds[item:item + 1]
            for phase, round_index, order in selected:
                for width in order:
                    control_sample = None
                    if control and width == 1 and round_index % 2 == 0:
                        control_sample = observe_control(protocol)
                    before = cpu_ticks()
                    usage = resource.getrusage(resource.RUSAGE_CHILDREN)
                    started = time.perf_counter_ns()
                    completed = subprocess.run([protocol["executable"], str(width)],
                                               capture_output=True, text=True, timeout=120)
                    seconds = (time.perf_counter_ns() - started) / 1e9
                    after_usage = resource.getrusage(resource.RUSAGE_CHILDREN)
                    child_seconds = (after_usage.ru_utime + after_usage.ru_stime -
                                     usage.ru_utime - usage.ru_stime)
                    activity = cpu_activity(before, cpu_ticks(), protocol["affinity"], child_seconds)
                    sample = {"phase": phase, "round": round_index, "threads": width,
                              "seconds": seconds, "child_cpu_seconds": child_seconds,
                              "activity": activity, "returncode": completed.returncode,
                              "stdout": completed.stdout, "stderr": completed.stderr}
                    result["samples"].append(sample)
                    save()
                    if (completed.returncode, completed.stdout, completed.stderr) != (
                            0, protocol["expected_stdout"], ""):
                        raise RuntimeError("incorrect workload result; retained unqualified run")
                    if control and width == 1:
                        if control_sample is None: control_sample = observe_control(protocol)
                        result['single_thread_pairs'].append({'phase': phase, 'round': round_index,
                            'candidate': sample, 'control': control_sample})
                        save()
            if item is not None and item < len(rounds) - 1:
                result['last_item'] = item
                save()
                print(f"item {item} retained; campaign incomplete")
                return
            ratios = {width: [] for width in WIDTHS}
            for round_index in range(ROUNDS):
                paired = {s["threads"]: s["seconds"] for s in result["samples"]
                          if s["phase"] == "paired" and s["round"] == round_index}
                for width in WIDTHS:
                    ratios[width].append(paired[1] / paired[width])
            result["scaling"] = {width: {"median": statistics.median(values),
                                        "interval_95": bootstrap_interval(values)}
                                 for width, values in ratios.items()}
            eight = result["scaling"][8]
            result["quiet_all_samples"] = (all(quiet(s["activity"]) for s in result["samples"])
                                           and all(quiet(a) for a in result['preflights']))
            result["qualified"] = (result["quiet_all_samples"] and eight["median"] >= 7.2
                                   and eight["interval_95"][0] >= 6.4)
            if control:
                pairs = [p for p in result['single_thread_pairs'] if p['phase'] == 'paired']
                cpu_ratios = [p['candidate']['child_cpu_seconds'] / p['control']['child_cpu_seconds']
                              for p in pairs]
                interval = bootstrap_interval(cpu_ratios)
                clean = all(quiet(p['control']['activity']) for p in result['single_thread_pairs'])
                result['single_thread_cpu'] = {'ratios': cpu_ratios,
                    'median': statistics.median(cpu_ratios), 'interval_95': interval,
                    'qualified': clean and interval[1] <= 1.01}
                result['qualified'] = result['qualified'] and result['single_thread_cpu']['qualified']
        except BaseException as error:
            result["failure"] = str(error)
            save()
            raise
        result["finished_unix_ns"] = time.time_ns()
        save()
    print(json.dumps({"qualified": result["qualified"], "scaling": result["scaling"]}, indent=2))
    if not result["qualified"]:
        raise SystemExit("frozen scaling gate failed; diagnose without changing thresholds")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    freeze = commands.add_parser("register")
    freeze.add_argument("executable", type=Path)
    freeze.add_argument("protocol", type=Path)
    freeze.add_argument('--lowered-llvm', type=Path, required=True)
    for name in ("candidate-sha", "compiler-sha", "runtime-sha", "build-flags"):
        freeze.add_argument("--" + name, required=True)
    freeze.add_argument("--memory-profile", choices=("system", "eager"), required=True)
    freeze.add_argument("--clang", default="clang")
    freeze.add_argument('--control-executable', type=Path)
    freeze.add_argument('--control-sha')
    campaign = commands.add_parser("run")
    campaign.add_argument("protocol", type=Path)
    campaign.add_argument("results", type=Path)
    campaign.add_argument('--item', type=int, choices=range(WARMUPS + ROUNDS))
    arguments = parser.parse_args()
    if arguments.command == 'register' and arguments.control_executable and not arguments.control_sha:
        parser.error('--control-sha is required with --control-executable')
    (register if arguments.command == "register" else run)(arguments)


if __name__ == "__main__":
    main()
