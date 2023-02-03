import re
import sys
import typer
import pickle
import pretty_errors
import urllib.parse
import operator

from typing import Optional
from pathlib import Path
from dixpy import Node, scan
from junk import is_junk
from dataclasses import dataclass
from rich import print

### Cached indices ###################################

app = typer.Typer()


@dataclass
class Config:
    root: Optional[Path]
    cache_file: Path
    cache: dict[Path, Node]
    verbose: bool

    def tops(self):
        if self.root:
            if self.root in self.cache:
                yield self.cache[self.root]
            else:
                fatal(f"{self.root} has not been indexed yet.")
        else:
            yield from self.cache.values()


def _make_cfg_singleton():
    _cfg: list[Config] = [None]

    def set_cfg(cfg: Config):
        _cfg[0] = cfg

    def get_cfg() -> Config:
        return _cfg[0]

    return set_cfg, get_cfg


set_sfg, get_cfg = _make_cfg_singleton()


def out_msg(str: str, verbose: bool = None):
    if verbose == None:
        verbose = get_cfg().verbose
    if verbose:
        print(str)


def fatal(str: str):
    out_msg(str, True)
    exit(1)


DEFAULT_CACHE_FILE = Path.home() / ".idx_cache.pickle"


@app.callback()
def load(
    root: Optional[Path] = None,
    cache_file: Path = DEFAULT_CACHE_FILE,
    verbose: bool = False,
):
    if cache_file.exists():
        out_msg(f"loading cache from {cache_file}.", verbose)
        with open(cache_file, "rb") as fd:
            cache = pickle.load(fd)
    else:
        out_msg(f"cache file {cache_file} not found.", verbose)
        cache = {}
    if root and root not in cache:
        out_msg(f"{root} not found in cache.", verbose)
    set_sfg(Config(root, cache_file, cache, verbose))


def write_cache(out_file: Path):
    out_msg(f"storing cache in {out_file}.")
    with open(out_file, "wb") as fd:
        pickle.dump(get_cfg().cache, fd)


@app.command()
def index():
    root = Path(get_cfg().root).resolve()
    if not root.exists():
        fatal(f"{root} does not exist")
    out_msg(f"starting scan of {root}.")
    top = scan(root)
    get_cfg().cache[root] = top
    write_cache(get_cfg().cache_file)


@app.command()
def rescan(only: Optional[Path] = None):
    only = only.resolve() if only else None
    for root in get_cfg().cache.keys():
        if not only or root == only:
            out_msg(f"starting scan of {root}.")
            top = scan(root)
            get_cfg().cache[root] = top
    write_cache(get_cfg().cache_file)


@app.command()
def dump(file_name: Path):
    write_cache(file_name)


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
def simulate_update(older_dump: Path):
    with open(older_dump, "rb") as fd:
        older: dict[Path, Node] = pickle.load(fd)
    current = get_cfg().cache


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
    mindepth: int = 0,
    ignorecase: bool = True,
    datesort: bool = True,
    includejunk: bool = False,
):
    def format_tag(tag):
        match tag:
            case "Red":
                return "🔴"
            case "Green":
                return "🟢"
            case "Blue":
                return "🔵"
            case "Purple":
                return "🟣"
            case _:
                return "@" + tag

    @dataclass
    class Result:
        node: Node
        top: Node

        def parts(self):
            return self.node.path.relative_to(self.top.path).parts

        def term(self):
            return "/".join(self.parts())

    name_cnd = []
    tags_cnd = []
    for r in regexps:
        if r.startswith("@"):
            tags_cnd.append(r[1:])
        else:
            name_cnd.append(re.compile(r, re.IGNORECASE if ignorecase else 0))

    def search_top(top: Node, results: list[Result]):
        def visit(node: Node, depth):
            if (
                not node.children
                and depth >= mindepth
                and (includejunk or not is_junk(node))
            ):
                result = Result(node, top)
                if all(r.search(result.term()) for r in name_cnd):
                    lower_tags = set(tag.lower() for tag in node.tags)
                    if all(tag in lower_tags for tag in tags_cnd):
                        results.append(result)
            return depth + 1

        top.walk(visit, 0)

    results: list[Result] = []
    for top in get_cfg().tops():
        search_top(top, results)

    def sort_key(result: Result):
        if datesort:
            if m := re.search("\.(\d\d)\.(\d\d)\.(\d\d)\.", result.term()):
                return "".join(m[0]) + result.term()
            return ".00.00.00." + result.term()
        else:
            return "".join(re.findall("\w", result.term()))

    print(f"[dim]{'-'*80}[/dim]")
    for result in sorted(results, key=sort_key):
        tagstr = " ".join(map(format_tag, result.node.tags))
        tagsep = " " if result.node.tags else ""
        dirstr = "/".join(result.parts()[:-1])
        dirsep = "/" if dirstr else ""
        link = f"file://{urllib.parse.quote(result.node.path.as_posix())}"
        topl = result.top.path.parts[-1][0]
        print(
            f"[dim]-[/dim][link={link}][dim]{dirstr}{dirsep}[/dim]{result.parts()[-1]}[/link] [dim]{tagstr}[/dim]{tagsep}[purple]{topl}[/purple]"
        )

    print(f"[dim]{len(results)} results[/dim]")


if __name__ == "__main__":
    app()
