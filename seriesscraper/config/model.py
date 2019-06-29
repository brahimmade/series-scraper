from enum import Enum


class TvShowConfig:
    def __init__(self, name: str) -> None:
        self.name = name


class LanguageConfig(Enum):
    ENGLISH = 1
    GERMAN = 2
