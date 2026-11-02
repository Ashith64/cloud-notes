"""Tests for storage backends.

LocalStorage is tested with real filesystem writes.
S3Storage is tested with all boto3 calls mocked via unittest.mock.
"""
import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from app.storage.local import LocalStorage
from app.storage.s3 import S3Storage


# ---------------------------------------------------------------------------
# LocalStorage
# ---------------------------------------------------------------------------

@pytest.fixture()
def local():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield LocalStorage(base_path=tmpdir)


def test_local_put_get_text(local):
    local.put_text("notes/test.md", "# Hello")
    assert local.get_text("notes/test.md") == "# Hello"


def test_local_put_get_bytes(local):
    data = b"\x89PNG\r\n"
    local.put_bytes("attachments/img.png", data, "image/png")
    assert local.get_bytes("attachments/img.png") == data


def test_local_exists(local):
    assert not local.exists("nope.txt")
    local.put_text("nope.txt", "yes")
    assert local.exists("nope.txt")


def test_local_delete(local):
    local.put_text("del.txt", "bye")
    local.delete("del.txt")
    assert not local.exists("del.txt")


def test_local_delete_nonexistent_no_error(local):
    local.delete("ghost.txt")  # should not raise


def test_local_get_missing_raises(local):
    with pytest.raises(FileNotFoundError):
        local.get_text("missing.md")


def test_local_presigned_url_is_none(local):
    local.put_text("a.txt", "x")
    assert local.presigned_url_or_none("a.txt") is None


def test_local_health_check(local):
    assert local.health_check() is True


def test_local_traversal_rejected(local):
    with pytest.raises(ValueError):
        local.put_text("../../etc/passwd", "evil")


# ---------------------------------------------------------------------------
# S3Storage (mocked)
# ---------------------------------------------------------------------------

@pytest.fixture()
def mock_s3_client():
    """Patch boto3.client so S3Storage never touches the network."""
    with patch("app.storage.s3.boto3.client") as mock_boto:
        mock_client = MagicMock()
        mock_boto.return_value = mock_client
        yield mock_client


@pytest.fixture()
def s3(mock_s3_client):
    return S3Storage(bucket="test-bucket", region="us-east-1")


def test_s3_put_text(s3, mock_s3_client):
    s3.put_text("notes/n.md", "content")
    mock_s3_client.put_object.assert_called_once()
    call_kwargs = mock_s3_client.put_object.call_args.kwargs
    assert call_kwargs["Bucket"] == "test-bucket"
    assert call_kwargs["Key"] == "notes/n.md"
    assert call_kwargs["ServerSideEncryption"] == "AES256"
    assert b"content" in call_kwargs["Body"]


def test_s3_get_text(s3, mock_s3_client):
    mock_s3_client.get_object.return_value = {
        "Body": MagicMock(read=lambda: b"hello world")
    }
    result = s3.get_text("notes/n.md")
    assert result == "hello world"
    mock_s3_client.get_object.assert_called_once_with(Bucket="test-bucket", Key="notes/n.md")


def test_s3_put_bytes(s3, mock_s3_client):
    s3.put_bytes("attachments/a.png", b"\x89PNG", "image/png")
    call_kwargs = mock_s3_client.put_object.call_args.kwargs
    assert call_kwargs["ContentType"] == "image/png"
    assert call_kwargs["ServerSideEncryption"] == "AES256"


def test_s3_get_bytes(s3, mock_s3_client):
    mock_s3_client.get_object.return_value = {
        "Body": MagicMock(read=lambda: b"\x89PNG")
    }
    result = s3.get_bytes("attachments/a.png")
    assert result == b"\x89PNG"


def test_s3_exists_true(s3, mock_s3_client):
    mock_s3_client.head_object.return_value = {}
    assert s3.exists("some/key") is True


def test_s3_exists_false(s3, mock_s3_client):
    from botocore.exceptions import ClientError
    mock_s3_client.head_object.side_effect = ClientError(
        {"Error": {"Code": "404", "Message": "Not Found"}}, "HeadObject"
    )
    assert s3.exists("some/key") is False


def test_s3_delete(s3, mock_s3_client):
    s3.delete("some/key")
    mock_s3_client.delete_object.assert_called_once_with(Bucket="test-bucket", Key="some/key")


def test_s3_presigned_url(s3, mock_s3_client):
    mock_s3_client.generate_presigned_url.return_value = "https://s3.example.com/signed"
    url = s3.presigned_url_or_none("some/key", expires_in=300)
    assert url == "https://s3.example.com/signed"
    mock_s3_client.generate_presigned_url.assert_called_once_with(
        "get_object",
        Params={"Bucket": "test-bucket", "Key": "some/key"},
        ExpiresIn=300,
    )


def test_s3_health_check_ok(s3, mock_s3_client):
    mock_s3_client.head_bucket.return_value = {}
    assert s3.health_check() is True


def test_s3_health_check_fail(s3, mock_s3_client):
    from botocore.exceptions import ClientError
    mock_s3_client.head_bucket.side_effect = ClientError(
        {"Error": {"Code": "403", "Message": "Forbidden"}}, "HeadBucket"
    )
    assert s3.health_check() is False
