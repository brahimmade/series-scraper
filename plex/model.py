from dataclasses import dataclass


@dataclass
class PlexEpisode:
    TYPE: str
    grandparentTitle: str
    seasonEpisode: str
