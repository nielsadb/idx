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


def write_cache():
    out_msg(f"storing cache in {get_cfg().cache_file}.")
    with open(get_cfg().cache_file, "wb") as fd:
        pickle.dump(get_cfg().cache, fd)


@app.command()
def index(do_stat: bool = False):
    root = Path(get_cfg().root).resolve()
    if not root.exists():
        fatal(f"{root} does not exist")
    out_msg(f"starting scan of {root}.")
    top = scan(root, do_stat)
    get_cfg().cache[root] = top
    write_cache()


@app.command()
def update(only: Optional[Path] = None, do_stat: bool = False):
    only = only.resolve() if only else None
    for root in get_cfg().cache.keys():
        if not only or root == only:
            out_msg(f"starting scan of {root}.")
            top = scan(root, do_stat)
            get_cfg().cache[root] = top
    write_cache()


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
def search(regexps: list[str], md: int = 1, ic: bool = True):
    name_cnd = []
    tags_cnd = []
    for r in regexps:
        if r.startswith("@"):
            tags_cnd.append(r[1:])
        else:
            name_cnd.append(re.compile(r, re.IGNORECASE if ic else 0))

    def search_top(top: Node, results):
        def visit(node: Node, depth):
            if not node.children and depth >= md:
                term = "/".join(node.path.relative_to(top.path).parts[md:])
                if all(r.search(term) for r in name_cnd):
                    lower_tags = set(tag.lower() for tag in node.tags)
                    if all(tag in lower_tags for tag in tags_cnd):
                        key = "".join(re.findall("\w", term.lower()))
                        results.append((key, term, node))
            return depth + 1

        top.walk(visit, 0)

    results = []
    for top in get_cfg().tops():
        search_top(top, results)
    print(f"[dim]{'-'*80}[/dim]")
    for (_, term, node) in sorted(results, key=operator.itemgetter(0)):

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

        tagstr = " ".join(map(format_tag, node.tags))
        link = f"file://{urllib.parse.quote(node.path.as_posix())}"
        print(f"[bold]*[/bold] [link={link}]{term}[/link] [dim]{tagstr}[/dim]")
    print(f"[dim]{len(results)} results[/dim]")


if __name__ == "__main__":
    app()
