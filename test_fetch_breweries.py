import csv
import io
import sys
from unittest.mock import MagicMock, call, mock_open, patch

import pytest
import requests

import fetch_breweries
from fetch_breweries import fetch_all_breweries, save_to_csv


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_response(data, status_code=200):
    """Build a mock requests.Response whose .json() returns *data*."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = data
    resp.raise_for_status.return_value = None
    return resp


BREWERY = {"id": "1", "name": "Acme Brewing", "city": "Portland", "state": "Oregon"}


# ---------------------------------------------------------------------------
# fetch_all_breweries – happy path
# ---------------------------------------------------------------------------

class TestFetchAllBreweriesPagination:
    """Pagination and data-accumulation behaviour."""

    @patch("fetch_breweries.time.sleep")
    @patch("fetch_breweries.requests.get")
    def test_single_partial_page_returns_data(self, mock_get, mock_sleep):
        """When the API returns fewer items than PER_PAGE the loop stops."""
        data = [BREWERY]
        mock_get.return_value = make_response(data)

        result = fetch_all_breweries()

        assert result == data
        mock_get.assert_called_once()

    @patch("fetch_breweries.time.sleep")
    @patch("fetch_breweries.requests.get")
    def test_empty_first_page_returns_empty_list(self, mock_get, mock_sleep):
        """An empty first-page response returns an empty list immediately."""
        mock_get.return_value = make_response([])

        result = fetch_all_breweries()

        assert result == []
        mock_get.assert_called_once()

    @patch("fetch_breweries.time.sleep")
    @patch("fetch_breweries.requests.get")
    def test_multiple_full_pages_then_partial(self, mock_get, mock_sleep):
        """Two full pages followed by a partial page accumulates all items."""
        full_page = [{"id": str(i)} for i in range(fetch_breweries.PER_PAGE)]
        partial_page = [{"id": "x"}]

        mock_get.side_effect = [
            make_response(full_page),
            make_response(full_page),
            make_response(partial_page),
        ]

        result = fetch_all_breweries()

        assert len(result) == fetch_breweries.PER_PAGE * 2 + 1
        assert mock_get.call_count == 3

    @patch("fetch_breweries.time.sleep")
    @patch("fetch_breweries.requests.get")
    def test_full_page_followed_by_empty_page_stops(self, mock_get, mock_sleep):
        """A full page followed by an empty page stops pagination."""
        full_page = [{"id": str(i)} for i in range(fetch_breweries.PER_PAGE)]

        mock_get.side_effect = [
            make_response(full_page),
            make_response([]),
        ]

        result = fetch_all_breweries()

        assert len(result) == fetch_breweries.PER_PAGE
        assert mock_get.call_count == 2

    @patch("fetch_breweries.time.sleep")
    @patch("fetch_breweries.requests.get")
    def test_correct_query_params_sent(self, mock_get, mock_sleep):
        """Each request includes the expected per_page and page parameters."""
        full_page = [{"id": str(i)} for i in range(fetch_breweries.PER_PAGE)]
        partial_page = [{"id": "z"}]

        mock_get.side_effect = [
            make_response(full_page),
            make_response(partial_page),
        ]

        fetch_all_breweries()

        first_call_params = mock_get.call_args_list[0].kwargs["params"]
        second_call_params = mock_get.call_args_list[1].kwargs["params"]

        assert first_call_params == {"per_page": fetch_breweries.PER_PAGE, "page": 1}
        assert second_call_params == {"per_page": fetch_breweries.PER_PAGE, "page": 2}

    @patch("fetch_breweries.time.sleep")
    @patch("fetch_breweries.requests.get")
    def test_timeout_kwarg_passed_to_requests(self, mock_get, mock_sleep):
        """requests.get is always called with the configured TIMEOUT."""
        mock_get.return_value = make_response([BREWERY])

        fetch_all_breweries()

        _, kwargs = mock_get.call_args
        assert kwargs["timeout"] == fetch_breweries.TIMEOUT

    @patch("fetch_breweries.time.sleep")
    @patch("fetch_breweries.requests.get")
    def test_politeness_sleep_between_pages(self, mock_get, mock_sleep):
        """time.sleep(0.2) is called once between pages."""
        full_page = [{"id": str(i)} for i in range(fetch_breweries.PER_PAGE)]
        partial_page = [{"id": "z"}]

        mock_get.side_effect = [
            make_response(full_page),
            make_response(partial_page),
        ]

        fetch_all_breweries()

        # sleep(0.2) only after a full page (before fetching the next page)
        assert call(0.2) in mock_sleep.call_args_list

    @patch("fetch_breweries.time.sleep")
    @patch("fetch_breweries.requests.get")
    def test_no_politeness_sleep_on_single_page(self, mock_get, mock_sleep):
        """time.sleep(0.2) is NOT called when there is only one page."""
        mock_get.return_value = make_response([BREWERY])

        fetch_all_breweries()

        assert call(0.2) not in mock_sleep.call_args_list


# ---------------------------------------------------------------------------
# fetch_all_breweries – retry / error handling
# ---------------------------------------------------------------------------

class TestFetchAllBreweriesRetry:
    """Timeout retry and error propagation behaviour."""

    @patch("fetch_breweries.time.sleep")
    @patch("fetch_breweries.requests.get")
    def test_timeout_retries_then_succeeds(self, mock_get, mock_sleep):
        """A transient timeout is retried and eventual success is returned."""
        mock_get.side_effect = [
            requests.exceptions.Timeout(),
            make_response([BREWERY]),
        ]

        result = fetch_all_breweries()

        assert result == [BREWERY]
        assert mock_get.call_count == 2

    @patch("fetch_breweries.time.sleep")
    @patch("fetch_breweries.requests.get")
    def test_timeout_retry_sleep_exponential_backoff(self, mock_get, mock_sleep):
        """time.sleep is called with 2**attempt on each timeout retry."""
        partial_page = [{"id": "z"}]
        mock_get.side_effect = [
            requests.exceptions.Timeout(),
            requests.exceptions.Timeout(),
            make_response(partial_page),
        ]

        fetch_all_breweries()

        # attempt=1 → sleep(2), attempt=2 → sleep(4)
        assert call(2) in mock_sleep.call_args_list
        assert call(4) in mock_sleep.call_args_list

    @patch("fetch_breweries.time.sleep")
    @patch("fetch_breweries.requests.get")
    def test_timeout_exhausts_max_retries_raises(self, mock_get, mock_sleep):
        """After MAX_RETRIES timeouts the Timeout exception propagates."""
        mock_get.side_effect = requests.exceptions.Timeout()

        with pytest.raises(requests.exceptions.Timeout):
            fetch_all_breweries()

        assert mock_get.call_count == fetch_breweries.MAX_RETRIES

    @patch("fetch_breweries.time.sleep")
    @patch("fetch_breweries.requests.get")
    def test_non_timeout_request_exception_raises_system_exit(self, mock_get, mock_sleep):
        """A non-timeout RequestException is wrapped in SystemExit."""
        mock_get.side_effect = requests.exceptions.ConnectionError("no route")

        with pytest.raises(SystemExit) as exc_info:
            fetch_all_breweries()

        assert "Request failed" in str(exc_info.value)

    @patch("fetch_breweries.time.sleep")
    @patch("fetch_breweries.requests.get")
    def test_http_error_raises_system_exit(self, mock_get, mock_sleep):
        """An HTTP error status (raise_for_status) raises SystemExit."""
        bad_resp = MagicMock()
        bad_resp.raise_for_status.side_effect = requests.exceptions.HTTPError("404")
        mock_get.return_value = bad_resp

        with pytest.raises(SystemExit) as exc_info:
            fetch_all_breweries()

        assert "Request failed" in str(exc_info.value)

    @patch("fetch_breweries.time.sleep")
    @patch("fetch_breweries.requests.get")
    def test_timeout_on_second_page_retries_correctly(self, mock_get, mock_sleep):
        """Timeout retries work correctly when they happen on later pages."""
        full_page = [{"id": str(i)} for i in range(fetch_breweries.PER_PAGE)]
        partial_page = [{"id": "z"}]

        mock_get.side_effect = [
            make_response(full_page),          # page 1: OK
            requests.exceptions.Timeout(),     # page 2: timeout attempt 1
            make_response(partial_page),       # page 2: OK on retry
        ]

        result = fetch_all_breweries()

        assert len(result) == fetch_breweries.PER_PAGE + 1
        assert mock_get.call_count == 3

    @patch("fetch_breweries.time.sleep")
    @patch("fetch_breweries.requests.get")
    def test_system_exit_message_includes_page_number(self, mock_get, mock_sleep):
        """SystemExit message references the page that failed."""
        mock_get.side_effect = requests.exceptions.ConnectionError("boom")

        with pytest.raises(SystemExit) as exc_info:
            fetch_all_breweries()

        assert "page 1" in str(exc_info.value).lower()


# ---------------------------------------------------------------------------
# save_to_csv
# ---------------------------------------------------------------------------

class TestSaveToCsv:
    """CSV writing behaviour."""

    def test_empty_list_prints_message_and_does_not_write(self, capsys, tmp_path):
        """Empty input prints a notice and creates no file."""
        filepath = tmp_path / "out.csv"

        save_to_csv([], str(filepath))

        captured = capsys.readouterr()
        assert "No data to save" in captured.out
        assert not filepath.exists()

    def test_single_brewery_written_correctly(self, tmp_path):
        """A single brewery produces a valid CSV with header and one row."""
        filepath = tmp_path / "out.csv"
        brewery = {"id": "1", "name": "Acme", "city": "Portland"}

        save_to_csv([brewery], str(filepath))

        with open(filepath, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        assert len(rows) == 1
        assert rows[0]["id"] == "1"
        assert rows[0]["name"] == "Acme"
        assert rows[0]["city"] == "Portland"

    def test_multiple_breweries_all_written(self, tmp_path):
        """All rows are written when multiple breweries are provided."""
        filepath = tmp_path / "out.csv"
        breweries = [
            {"id": "1", "name": "Alpha"},
            {"id": "2", "name": "Beta"},
            {"id": "3", "name": "Gamma"},
        ]

        save_to_csv(breweries, str(filepath))

        with open(filepath, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        assert len(rows) == 3
        assert [r["name"] for r in rows] == ["Alpha", "Beta", "Gamma"]

    def test_fieldnames_are_sorted(self, tmp_path):
        """Column headers are the sorted union of all row keys."""
        filepath = tmp_path / "out.csv"
        breweries = [
            {"z_field": "1", "a_field": "2"},
            {"m_field": "3", "a_field": "4"},
        ]

        save_to_csv(breweries, str(filepath))

        with open(filepath, newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            header = next(reader)

        assert header == sorted({"z_field", "a_field", "m_field"})

    def test_sparse_rows_with_different_keys(self, tmp_path):
        """Rows with different key sets are written with empty values for absent keys."""
        filepath = tmp_path / "out.csv"
        breweries = [
            {"id": "1", "name": "Alpha"},
            {"id": "2", "website": "http://beta.com"},
        ]

        save_to_csv(breweries, str(filepath))

        with open(filepath, newline="", encoding="utf-8") as f:
            content = f.read()

        # Both id, name, and website should appear in the header
        assert "id" in content
        assert "name" in content
        assert "website" in content

    def test_success_message_printed(self, capsys, tmp_path):
        """A success message mentioning the count and filepath is printed."""
        filepath = tmp_path / "out.csv"
        breweries = [{"id": "1", "name": "Acme"}]

        save_to_csv(breweries, str(filepath))

        captured = capsys.readouterr()
        assert "1" in captured.out
        assert str(filepath) in captured.out

    def test_csv_written_with_utf8_encoding(self, tmp_path):
        """Non-ASCII characters in brewery names are preserved correctly."""
        filepath = tmp_path / "out.csv"
        breweries = [{"id": "1", "name": "Brasserie Ångström"}]

        save_to_csv(breweries, str(filepath))

        with open(filepath, newline="", encoding="utf-8") as f:
            content = f.read()

        assert "Ångström" in content

    def test_output_is_valid_csv(self, tmp_path):
        """The output file is parseable by csv.DictReader without errors."""
        filepath = tmp_path / "out.csv"
        breweries = [
            {"id": "1", "name": "Has, Comma", "city": "Portland"},
            {"id": "2", "name": 'Has "Quotes"', "city": "Denver"},
        ]

        save_to_csv(breweries, str(filepath))

        with open(filepath, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        assert len(rows) == 2
        assert rows[0]["name"] == "Has, Comma"
        assert rows[1]["name"] == 'Has "Quotes"'