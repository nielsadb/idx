import re
import typer
import pickle
import pretty_errors
import urllib.parse

from typing import Optional
from pathlib import Path
from dixpy import Node, scan
from dataclasses import dataclass
from rich import print
import idx_lib
from idx_lib import get_cfg

### Cached indices ###################################

app = typer.Typer()


DEFAULT_CACHE_FILE = Path.home() / ".idx_cache.pickle"


@app.callback()
def load(
    root: Optional[Path] = None,
    cache_file: Path = DEFAULT_CACHE_FILE,
    verbose: bool = False,
):
    def out_msg(str: str):
        if verbose:
            print(str)

    idx_lib.load(cache_file, root, out_msg)


@app.command()
def index():
    root = Path(get_cfg().root).resolve()
    if not root.exists():
        get_cfg.out_msg(f"{root} does not exist")
        exit(1)
    get_cfg().out_msg(f"starting scan of {root}.")
    top = scan(root)
    get_cfg().cache[root] = top
    get_cfg().write_cache()


@app.command()
def rescan(only: Optional[Path] = None):
    only = only.resolve() if only else None
    for root in get_cfg().cache.keys():
        if not only or root == only:
            get_cfg().out_msg(f"starting scan of {root}.")
            top = scan(root)
            get_cfg().cache[root] = top
    get_cfg().write_cache()


@app.command()
def dump(file_name: Path):
    get_cfg().write_cache(file_name)


# --- 2023-01-19 20:21:30
# python idx.py --verbose rescan --do-stat
#   1.49s user
#   3.57s system
#   2% cpu
#   2:52.89 total
# --- 2023-01-19 20:34:34
# python idx.py --verbose rescan --do-stat
#   1.60s user
#   3.69s system
#   2% cpu
#   3:16.22 total


@app.command()
def show():
    def visit(node: Node, indent: int):
        tags = ", ".join(node.tags)
        print(f"{indent*'  '}{node.path.name} {f'[{tags}]' if tags else ''}")
        return indent + 1

    for top in get_cfg().tops():
        top.walk(visit, 0)


@app.command()
def cached():
    for root in get_cfg().cache.keys():
        print(f"* {root}")


@app.command()
def search(
    regexps: list[str],
    *,
    min_depth: int = 0,
    ignore_case: bool = True,
    date_sort: bool = True,
    include_junk: bool = False,
    show_dir: bool = False,
    compact_dir: bool = False,
):
    count = 0
    print(f"[dim]{'-'*80}[/dim]")
    for result in idx_lib.search(
        regexps,
        min_depth=min_depth,
        ignore_case=ignore_case,
        date_sort=date_sort,
        include_junk=include_junk,
    ):
        count += 1
        tagstr = " ".join(map(idx_lib.format_tag, result.node.tags))
        tagsep = " " if result.node.tags else ""
        if show_dir:
            if compact_dir:
                dirstr = "/".join(p[0] for p in result.parts()[:-1])
            else:
                dirstr = "/".join(result.parts()[:-1])
        else:
            dirstr = ""
        dirsep = "/" if dirstr else ""
        link = f"file://{urllib.parse.quote(result.node.path.as_posix())}"
        topl = result.top.path.parts[-1][0]
        print(
            f"[dim]-[/dim][link={link}][dim]{dirstr}{dirsep}[/dim]{result.parts()[-1]}[/link] [dim]{tagstr}[/dim]{tagsep}[purple]{topl}[/purple]"
        )

    print(f"[dim]{count} results[/dim]")


if __name__ == "__main__":
    app()
