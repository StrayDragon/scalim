from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple

from scalim import _project_constants
from scalim.cli import yaml_dsl as yaml_dsl_cli


class CliDocsError(RuntimeError):
    pass


TokenPath = Tuple[str, ...]


@dataclass
class CommandRecording:
    parsers: Dict[TokenPath, argparse.ArgumentParser] = field(default_factory=dict)
    helps: Dict[TokenPath, str] = field(default_factory=dict)


class RecordingSubparsers:
    def __init__(self, action: Any, *, recording: CommandRecording, prefix: TokenPath) -> None:
        self.action = action
        self.recording = recording
        self.prefix = prefix

    def add_parser(self, name: str, *args: Any, **kwargs: Any) -> argparse.ArgumentParser:
        parser = self.action.add_parser(name, *args, **kwargs)
        token_path: TokenPath = (*self.prefix, name)

        # Ensure nested `add_subparsers()` calls continue recording.
        if isinstance(parser, RecordingArgumentParser):
            parser.recording = self.recording
            parser.recording_prefix = token_path

        help_text = str(kwargs.get("help") or "")
        if help_text:
            self.recording.helps[token_path] = help_text
        self.recording.parsers[token_path] = parser
        return parser


class RecordingArgumentParser(argparse.ArgumentParser):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.recording = CommandRecording()
        self.recording_prefix: TokenPath = ()

    def add_subparsers(self, **kwargs: Any) -> RecordingSubparsers:
        # Ensure all child parsers are also RecordingArgumentParser.
        if "parser_class" not in kwargs:
            kwargs["parser_class"] = RecordingArgumentParser
        action = super().add_subparsers(**kwargs)
        return RecordingSubparsers(action, recording=self.recording, prefix=self.recording_prefix)


def build_yaml_dsl_command_docs() -> List[Dict[str, Any]]:
    root_parser = RecordingArgumentParser(prog=_project_constants.CLI_NAME, description="Scalim CLI")
    root_subparsers = root_parser.add_subparsers(dest="command")
    yaml_dsl_cli.register(root_subparsers)

    command_tokens = [
        ("yaml-dsl", "validate"),
        ("yaml-dsl", "schema", "validate"),
        ("yaml-dsl", "schema", "show"),
        ("yaml-dsl", "schema", "path"),
    ]
    docs = []
    for tokens in command_tokens:
        parser = root_parser.recording.parsers.get(tokens)
        if parser is None:
            message = "CLI 解析器中缺少子命令: {}".format(" ".join(tokens))
            raise CliDocsError(message)
        help_text = root_parser.recording.helps.get(tokens, "") or ""
        docs.append(
            {
                "tokens": tokens,
                "help": help_text or parser.description or "",
                "usage": parser.format_usage().strip().replace("usage: ", "", 1),
                "help_full": parser.format_help().rstrip(),
            }
        )
    return docs
