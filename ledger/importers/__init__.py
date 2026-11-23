from .base import ImportFileError, ParsedRow, read_table
from .generic import GenericImporter

# Bank-specific importers go first once they exist; the generic one is the fallback.
IMPORTERS = [GenericImporter()]


def detect(header: list[str]):
    for importer in IMPORTERS:
        if importer.matches(header):
            return importer
    raise ImportFileError(
        "Could not recognise the columns in this file: " + ", ".join(h for h in header if h)
    )


__all__ = ["IMPORTERS", "ImportFileError", "ParsedRow", "detect", "read_table"]
