from dataclasses import dataclass


@dataclass
class JdLink:
    autostart: bool
    links: str
    packageName: str
    destinationFolder: str
    extractPassword: str = None
    priority: str = 'DEFAULT'
    downloadPassword: str = None
    overwritePackagizerRules: bool = True
