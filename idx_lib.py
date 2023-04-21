from dataclasses import dataclass
from pathlib import Path
import pickle
import re
from typing import Callable, Generator, Optional

from dixpy import Node


@dataclass
class Config:
    root: Optional[Path]
    cache_file: Path
    cache: dict[Path, Node]
    out_msg: Callable[[str], None]

    def tops(self):
        if self.root:
            assert self.root in self.cache, f"{self.root} has not been indexed yet."
            yield self.cache[self.root]
        else:
            yield from self.cache.values()

    def write_cache(self, out_file: Optional[Path] = None):
        out_file = out_file or self.cache_file
        with open(out_file, "wb") as fd:
            pickle.dump(self.cache, fd)


def _make_cfg_singleton():
    _cfg: list[Config] = [None]

    def set_cfg(cfg: Config):
        _cfg[0] = cfg

    def get_cfg() -> Config:
        return _cfg[0]

    return set_cfg, get_cfg


_set_sfg, get_cfg = _make_cfg_singleton()


def _ignore(_: str):
    pass


def load(
    cache_file: Path,
    root: Optional[Path] = None,
    out_msg: Callable[[str], None] = _ignore,
):
    if cache_file.exists():
        out_msg(f"loading cache from {cache_file}.")
        with open(cache_file, "rb") as fd:
            cache = pickle.load(fd)
    else:
        out_msg(f"cache file {cache_file} not found.")
        cache = {}
    if root and root not in cache:
        out_msg(f"{root} not found in cache.")
    _set_sfg(Config(root, cache_file, cache, out_msg))


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


JUNK_PATTERNS = [
    r"\.jpg$",
    r"\.jpeg$",
    r"\.exe$",
    r"\.txt$",
    r"\.nfo$",
    r"\.url$",
    r"^\.DS_Store$",
    r"^Samples$",
    r"^Covers$",
    r"^Subs$",
]
JUNK_REGEXPS = [re.compile(pattern) for pattern in JUNK_PATTERNS]


def is_junk(node: Node):
    name = node.path.name
    return any(pattern.search(name) for pattern in JUNK_REGEXPS)


def search(
    regexps: list[str],
    *,
    min_depth: int = 0,
    ignore_case: bool = True,
    date_sort: bool = True,
    include_junk: bool = False,
) -> Generator[Result, None, None]:
    name_cnd = []
    tags_cnd = []
    for r in regexps:
        if r.startswith("@"):
            tags_cnd.append(r[1:])
        else:
            name_cnd.append(re.compile(r, re.IGNORECASE if ignore_case else 0))

    def search_top(top: Node, results: list[Result]):
        def visit(node: Node, depth):
            if (
                not node.children
                and depth >= min_depth
                and (include_junk or not is_junk(node))
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
        if date_sort:
            if m := re.search("\.(\d\d)\.(\d\d)\.(\d\d)\.", result.term()):
                return "".join(m[0]) + result.term()
            return ".00.00.00." + result.term()
        else:
            return "".join(re.findall("\w", result.term()))

    return sorted(results, key=sort_key)
