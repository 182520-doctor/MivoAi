"""Domain and integration exceptions translated to HTTP errors by the API layer."""


class AppServerError(RuntimeError):
    """The local Codex App Server rejected a request or became unavailable."""


class ConversationNotFoundError(LookupError):
    """A requested conversation identifier does not exist in local persistence."""


class ConversationBusyError(RuntimeError):
    """A second turn was submitted while the same conversation was active."""


class DuplicateSubmissionError(RuntimeError):
    """A client message ID was already accepted and must not be replayed."""


class ProviderConfigurationError(ValueError):
    """A provider or model selection is invalid for the requested capability."""
