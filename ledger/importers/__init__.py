from .base import ImportFileError, ParsedRow, read_table
from .generic import FIELDS, GenericImporter, MappedImporter

# Bank-specific importers go first once they exist; the generic one is the fallback.
IMPORTERS = [GenericImporter()]


class UnknownColumns(ImportFileError):
    """No importer recognises the header. The user can map the columns instead."""

    def __init__(self, header: list[str]):
        self.header = header
        super().__init__(
            "Could not recognise the columns in this file: " + ", ".join(h for h in header if h)
        )


def detect(header: list[str]):
    for importer in IMPORTERS:
        if importer.matches(header):
            return importer
    raise UnknownColumns(header)


__all__ = [
    "FIELDS",
    "IMPORTERS",
    "ImportFileError",
    "MappedImporter",
    "ParsedRow",
    "UnknownColumns",
    "detect",
    "read_table",
]
