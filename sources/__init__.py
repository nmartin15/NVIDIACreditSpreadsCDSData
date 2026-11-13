"""Data sources. Each public function returns a DataFrame or raises SourceUnavailable."""


class SourceUnavailable(Exception):
    """A feed is missing, refused, or came back in an unexpected shape."""
