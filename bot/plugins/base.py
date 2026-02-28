from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine


@dataclass
class Command:
    name: str
    handler: Callable[..., Coroutine]
    help_text: str
    required_role: str = "user"
    plugin: str = ""


@dataclass
class CommandContext:
    sender: str
    hostmask: str
    channel: str
    args: list[str]
    reply: Callable[[str], Coroutine]


class Plugin(ABC):
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def register_commands(self) -> list[Command]: ...

    async def on_load(self) -> None:
        pass

    async def on_unload(self) -> None:
        pass
