"""Tests for Thoth error system."""

from thoth.errors import ErrorHandler, PipelineError, ServiceError, ThothError


def test_error_creation_and_properties() -> None:
    """Ensure errors store provided properties."""
    err = ThothError(
        error_code='E001',
        message='Test error',
        recoverable=True,
        context={'foo': 'bar'},
    )

    assert err.error_code == 'E001'
    assert err.message == 'Test error'
    assert err.recoverable is True
    assert err.context == {'foo': 'bar'}


def test_error_serialization() -> None:
    """Errors should serialize to dictionaries."""
    err = ServiceError('S001', 'Service failed')
    result = err.to_dict()

    assert result['error_code'] == 'S001'
    assert result['message'] == 'Service failed'
    assert result['recoverable'] is False
    assert result['context'] == {}


def test_error_handler_functionality() -> None:
    """ErrorHandler should record and serialize errors."""
    handler = ErrorHandler()
    err = PipelineError('P001', 'Pipeline issue', recoverable=True)

    is_recoverable = handler.handle(err)
    assert is_recoverable is True
    assert handler.errors == [err]

    serialized = handler.serialize_errors()
    assert serialized == [err.to_dict()]

    handler.clear()
    assert handler.errors == []
