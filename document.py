"""Document module"""

import time
from collections import namedtuple
from dataclasses import dataclass
from typing import List

import sublime

from ..constant import VIEW_SELECTOR


def is_valid_document(view: sublime.View) -> bool:
    """check if view is valid document"""
    return bool(view.file_name()) and view.match_selector(0, VIEW_SELECTOR)


LANGUAGE_MAP = {
    "source.c": "c",
    "source.c++": "cpp",
    "source.c#": "csharp",
    "source.clojure": "clojure",
    "source.css": "css",
    "source.d": "d",
    "source.erlang": "erlang",
    "source.go": "go",
    "source.groovy": "groovy",
    "source.graphviz": "dot",
    "source.haskell": "haskell",
    "source.java": "java",
    "source.js": "javascript",
    "source.jsx": "javascriptreact",
    "source.json": "json",
    "source.jsonl": "jsonl",
    "source.jsonc": "jsonc",
    "source.julia": "julia",
    "source.kotlin": "kotlin",
    "source.lisp": "lisp",
    "source.lua": "lua",
    "source.makefile": "makefile",
    "source.matlab": "matlab",
    "source.ocaml": "ocaml",
    "source.objc": "objective-c",
    "source.objcpp": "objective-cpp",
    "source.pascal": "pascal",
    "source.perl": "perl",
    "source.php": "php",
    "source.python": "python",
    "source.r": "r",
    "source.raku": "raku",
    "source.ruby": "ruby",
    "source.rust": "rust",
    "source.scala": "scala",
    "source.shell": "shellscript",
    "source.sql": "sql",
    "source.swift": "swift",
    "source.ts": "typescript",
    "source.tsx": "typescriptreact",
    "source.vbnet": "vb",
    "source.elixir": "elixir",
    "source.fsharp": "fsharp",
    "source.dart": "dart",
    "source.scss": "scss",
    "source.less": "less",
    "source.sass": "scss",
    "source.vue": "vue",
    "source.angular": "angular",
    "source.svelte": "svelte",
    "source.nim": "nim",
    "source.zig": "zig",
    "source.hlsl": "hlsl",
    "source.shaderlab": "shaderlab",
    "source.wat": "wat",
    "source.powershell": "powershell",
    "source.handlebars": "handlebars",
    "source.jade": "pug",
    "source.tex": "tex",
    "source.bibtex": "bibtex",
    "source.dockerfile": "dockerfile",
    "source.dotenv": "dotenv",
    "source.ignore": "ignore",
    "source.ini": "ini",
    "source.properties": "properties",
    "source.log": "log",
    "source.search-result": "search-result",
    "source.snippets": "snippets",
    "text.html.basic": "html",
    "text.html.markdown": "markdown",
    "text.html.latex": "latex",
    "text.xml": "xml",
    "text.xsl": "xsl",
    "text.plain": "plaintext",
    "text.git-commit": "git-commit",
    "text.git-rebase": "git-rebase",
    "text.diff": "diff",
    "text.restructuredtext": "restructuredtext",
    "text.razor": "razor",
    "text.instructions": "instructions",
    "text.prompt": "prompt",
    "text.skill": "skill",
}


def get_language_id(view: sublime.View) -> str:
    """"""
    lang_selector = view.scope_name(0).split()[0]
    return LANGUAGE_MAP[lang_selector]


RowColumn = namedtuple("RowColumn", ["row", "column"])


@dataclass
class TextChange:
    start: RowColumn
    end: RowColumn
    text: str
    length: int

    __slots__ = ("start", "end", "text", "length")


class Document:

    def __init__(self, view: sublime.View):
        self.view = view
        self.file_name = self.view.file_name()
        self.language_id = get_language_id(view)
        self.diagnostics: List[dict] = []

    def window(self) -> sublime.Window:
        return self.view.window()

    @property
    def version(self) -> int:
        return self.view.change_count()

    @property
    def text(self):
        # wait until complete loaded
        while self.view.is_loading():
            time.sleep(0.5)

        return self.view.substr(sublime.Region(0, self.view.size()))
