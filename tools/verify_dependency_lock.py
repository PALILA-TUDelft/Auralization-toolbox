#!/usr/bin/env python3
"""Check that an ITA build tree used the dependency commits in
patches/ita/dependency-lock.json.

    python tools/verify_dependency_lock.py                 # default build dir
    python tools/verify_dependency_lock.py <ita-build-dir>

Reads <build-dir>/_deps/<name>-src for every locked git dependency that was
actually fetched (a dependency the configuration did not ask for is skipped)
and compares its HEAD to the locked commit. Exit status is 0 when nothing
drifted, 1 otherwise. Standard library only.
"""
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOCK = os.path.join(ROOT, "patches", "ita", "dependency-lock.json")


def default_build_dir():
    base = os.path.join(ROOT, "ITAGeometricalAcoustics", "out", "build")
    if sys.platform == "win32":
        name = "full-win-vs-msvc"
    elif sys.platform == "darwin":
        name = "full-mac-ninja-clang"
    else:
        name = "full-linux-ninja-gcc"
    return os.path.join(base, name)


def head(path):
    r = subprocess.run(["git", "-C", path, "rev-parse", "HEAD"], capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else None


def main():
    build = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else default_build_dir()
    deps = os.path.join(build, "_deps")
    if not os.path.isdir(deps):
        print("No _deps directory in %s - configure ITA first." % build)
        return 2
    lock = json.load(open(LOCK))
    ok = drift = missing = 0
    for name, want in sorted(lock.items()):
        src = os.path.join(deps, name + "-src")
        if not os.path.isdir(src):
            missing += 1          # not requested by this configuration
            continue
        got = head(src)
        if got == want["commit"]:
            ok += 1
        else:
            drift += 1
            print("DRIFT  %-16s locked %s  got %s" % (name, want["commit"][:12], (got or "?")[:12]))
    print("%d match, %d drifted, %d not fetched in this configuration." % (ok, drift, missing))
    return 1 if drift else 0


if __name__ == "__main__":
    sys.exit(main())
