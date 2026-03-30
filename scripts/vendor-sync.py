# ruff: noqa: T201
import argparse
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List, Optional, Sequence


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _require_safe_dest(dest: Path) -> None:
    resolved = dest.resolve()
    if resolved == Path("/"):
        raise ValueError("拒绝危险目标路径: `--dest=/`")
    if not resolved.exists():
        raise ValueError("目标目录不存在: {!r}".format(str(resolved)))
    if not resolved.is_dir():
        raise ValueError("目标必须是目录: {!r}".format(str(resolved)))


def _run_rsync(args: Sequence[str]) -> None:
    if shutil.which("rsync") is None:
        raise RuntimeError("未找到 `rsync`（必需）。请先安装 `rsync` 后重试。")
    completed = subprocess.run(list(args), check=False)
    if completed.returncode in (0, 141):
        # `141 = 128 + SIGPIPE`。常见于用户将输出管道到 `head`/`less` 后提前退出。
        return
    raise subprocess.CalledProcessError(completed.returncode, list(args))


def _rsync_mirror_dir(*, src_dir: Path, dest_dir: Path, dry_run: bool) -> None:
    src = str(src_dir.resolve()) + "/"
    dest = str(dest_dir.resolve()) + "/"
    cmd: List[str] = [
        "rsync",
        "-a",
        "--delete",
        "--exclude",
        "__pycache__/",
        "--exclude",
        "*.pyc",
        "--exclude",
        "*.pyo",
        "--exclude",
        "*.egg-info/",
    ]
    if dry_run:
        cmd.append("--dry-run")
        cmd.append("--itemize-changes")
    cmd.extend([src, dest])
    _run_rsync(cmd)


def _rsync_copy_file(*, src_path: Path, dest_dir: Path, dry_run: bool) -> None:
    src = str(src_path.resolve())
    dest = str(dest_dir.resolve()) + "/"
    cmd: List[str] = ["rsync", "-a"]
    if dry_run:
        cmd.append("--dry-run")
        cmd.append("--itemize-changes")
    cmd.extend([src, dest])
    _run_rsync(cmd)


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="将仓库的 README.md 与 src/scalim 镜像同步到目标 vendors 目录(基于 rsync).")
    p.add_argument("--dest", required=True, help="目标 vendors 根目录(脚本会同步到 <dest>/scalim/).")
    p.add_argument("--apply", action="store_true", help="执行实际同步(会写入目标目录). 默认仅 dry-run 预览.")
    p.add_argument("--dry-run", action="store_true", help="仅预览变更，不写入目标目录。")
    return p.parse_args(list(argv or sys.argv[1:]))


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parse_args(argv)
    root = _repo_root()
    dest_root = Path(str(args.dest)).expanduser()
    dry_run = bool(args.dry_run) or not bool(args.apply)

    try:
        _require_safe_dest(dest_root)
    except Exception as exc:
        print("错误: {}".format(exc), file=sys.stderr)
        return 2

    target_pkg_dir = dest_root.resolve() / "scalim"
    if not dry_run:
        target_pkg_dir.mkdir(parents=True, exist_ok=True)

    print("repo_root:", str(root))
    print("dest_root:", str(dest_root.resolve()))
    print("dest_pkg:", str(target_pkg_dir))
    print("模式:", "预览(`dry-run`)" if dry_run else "执行(`apply`)")
    print("")

    src_pkg = root / "src" / "scalim"
    if not src_pkg.exists():
        print("错误: `src/scalim` 不存在: {!r}".format(str(src_pkg)), file=sys.stderr)
        return 2
    _rsync_mirror_dir(src_dir=src_pkg, dest_dir=target_pkg_dir, dry_run=dry_run)

    readme = root / "README.md"
    if readme.exists():
        _rsync_copy_file(src_path=readme, dest_dir=target_pkg_dir, dry_run=dry_run)
    else:
        print("警告: 未找到 `README.md`，已跳过同步。", file=sys.stderr)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except BrokenPipeError:
        try:
            sys.stdout.close()
        except Exception:
            pass
        raise SystemExit(0)
