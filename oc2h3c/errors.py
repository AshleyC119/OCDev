"""Error types used by the translator."""


class InputError(Exception):
    """The input document cannot be processed at all."""


class MappingError(Exception):
    """A single mapping step failed; recorded in the report, translation continues."""
