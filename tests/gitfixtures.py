"""Git fixtures for the tool tests: throwaway remotes and checkouts laid out like this machine, and a runner that
stops a command's whole process tree on timeout."""
import os
import signal
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PROBE = REPO / "tools" / "os_probe.py"
RULE_OS = ("- Between sections answer the pull requests Impossible OS opened here. "
           "Take only branches named `impossible-os/...` that are not from a fork.\n")
RULE_BRAND = ("- Between sections answer the pull requests Impossible OS opened here. "
              "Take only branches named `impossible-os/...` or `impossible-brand/...` that are not from a fork.\n")
GIT_ENV = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.invalid", "GIT_COMMITTER_NAME": "t",
           "GIT_COMMITTER_EMAIL": "t@example.invalid", "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_NOSYSTEM": "1"}


def git(cwd, *args):
    code, out, err = run_tree(["git", "-C", str(cwd), *args], env={**os.environ, **GIT_ENV}, timeout=60)
    assert code == 0, f"git {' '.join(args)}: {err}"
    return out


def run_tree(argv, cwd=None, env=None, timeout=30):
    """Run a command in its own process group and kill the whole group if it outlives the timeout."""
    proc = subprocess.Popen(argv, cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                            start_new_session=True)
    try:
        out, err = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid, signal.SIGKILL)
        proc.communicate()
        raise
    return proc.returncode, out, err


def run_probe(root, *args, env=None, timeout=30):
    full = {**os.environ, **GIT_ENV, **(env or {})}
    full.pop("CONCLAVE_HAVE", None)
    code, out, _ = run_tree([sys.executable, str(root / "tools" / "os_probe.py"), *args], env=full, timeout=timeout)
    return code, out.strip()


def commit_files(work, files, message="c"):
    for name, text in files.items():
        path = work / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    git(work, "add", "-A")
    git(work, "commit", "-q", "-m", message)


def make_remote(base, remote, files):
    """A bare remote at <base>/remotes/<remote>.git seeded with files, and a work clone that pushes to it."""
    bare = base / "fx" / "deep" / "remotes" / f"{remote}.git"
    bare.parent.mkdir(parents=True, exist_ok=True)
    git(base, "init", "-q", "--bare", "-b", "main", str(bare))
    work = base / "fx" / "deep" / "work" / remote.replace("/", "_")
    git(base, "clone", "-q", str(bare), str(work))
    git(work, "checkout", "-q", "-b", "main")
    commit_files(work, files or {"README.md": "seed\n"})
    git(work, "push", "-q", "origin", "main")
    return bare, work


def clone(bare, dest):
    dest.parent.mkdir(parents=True, exist_ok=True)
    git(dest.parent, "clone", "-q", str(bare), str(dest))
    return dest
