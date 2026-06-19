"""
Tests for data_cleaning.py — scoped to the `unused_function` added in this PR.

The module runs side-effectful code at import time (pd.read_csv, os.system, file
writes), so pandas, numpy, and os.system are patched before the module is loaded.
"""

import sys
import importlib
import unittest
from io import StringIO
from unittest.mock import MagicMock, patch, call


# ---------------------------------------------------------------------------
# Patch heavy dependencies before data_cleaning is imported so that the
# module-level statements (read_csv, clean, analyze, export) do not attempt
# real file I/O or system calls.
# ---------------------------------------------------------------------------

def _make_mock_dataframe():
    """Return a MagicMock that quacks like a minimal pandas DataFrame."""
    df = MagicMock()
    df.shape = (10, 3)
    df.columns = ["brewery_type", "latitude", "longitude", "state"]
    df.copy.return_value = df
    df.__len__ = lambda self: 10
    df.head.return_value = df
    df.drop_duplicates.return_value = df
    df.__getitem__ = MagicMock(return_value=MagicMock())
    df.unique.return_value = []
    return df


_mock_df = _make_mock_dataframe()

_mock_pd = MagicMock()
_mock_pd.read_csv.return_value = _mock_df
_mock_pd.DataFrame = MagicMock

_mock_np = MagicMock()
_mock_np.nan = float("nan")

# Install the mocks into sys.modules so that `import pandas as pd` inside
# data_cleaning picks them up.
sys.modules.setdefault("pandas", _mock_pd)
sys.modules.setdefault("numpy", _mock_np)

# Also patch os.system so the `export` call in module scope does not spawn
# shell commands.
_os_system_patcher = patch("os.system", return_value=0)
_os_system_patcher.start()

# Now it is safe to import (or reload) data_cleaning.
if "data_cleaning" in sys.modules:
    importlib.reload(sys.modules["data_cleaning"])
    import data_cleaning
else:
    import data_cleaning

_os_system_patcher.stop()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestUnusedFunction(unittest.TestCase):
    """Unit tests for data_cleaning.unused_function (added in this PR)."""

    def test_prints_expected_message(self):
        """unused_function should print the exact string it contains."""
        with patch("builtins.print") as mock_print:
            data_cleaning.unused_function()
        mock_print.assert_called_once_with("This function is never called")

    def test_returns_none(self):
        """unused_function has no explicit return, so it must return None."""
        with patch("builtins.print"):
            result = data_cleaning.unused_function()
        self.assertIsNone(result)

    def test_print_called_exactly_once(self):
        """Only a single print call should be made during execution."""
        with patch("builtins.print") as mock_print:
            data_cleaning.unused_function()
        self.assertEqual(mock_print.call_count, 1)

    def test_printed_message_content(self):
        """Verify the exact text sent to stdout via a real StringIO capture."""
        with patch("sys.stdout", new_callable=StringIO) as fake_out:
            data_cleaning.unused_function()
        self.assertEqual(fake_out.getvalue(), "This function is never called\n")

    def test_raises_typeerror_when_called_with_positional_arg(self):
        """unused_function accepts no parameters; passing one must raise TypeError."""
        with self.assertRaises(TypeError):
            data_cleaning.unused_function("unexpected_argument")

    def test_raises_typeerror_when_called_with_keyword_arg(self):
        """unused_function accepts no parameters; passing a keyword arg must raise TypeError."""
        with self.assertRaises(TypeError):
            data_cleaning.unused_function(msg="hello")

    def test_callable(self):
        """unused_function should be a callable defined in the module."""
        self.assertTrue(callable(data_cleaning.unused_function))

    def test_idempotent_multiple_calls(self):
        """Calling unused_function multiple times should always print the same message."""
        outputs = []
        for _ in range(3):
            with patch("sys.stdout", new_callable=StringIO) as fake_out:
                data_cleaning.unused_function()
            outputs.append(fake_out.getvalue())
        self.assertEqual(outputs, ["This function is never called\n"] * 3)

    def test_print_called_with_string_not_bytes(self):
        """The argument passed to print must be a plain str, not bytes or other type."""
        with patch("builtins.print") as mock_print:
            data_cleaning.unused_function()
        printed_arg = mock_print.call_args[0][0]
        self.assertIsInstance(printed_arg, str)

    def test_no_side_effects_on_module_state(self):
        """Calling unused_function should not alter any module-level attribute."""
        before = dict(vars(data_cleaning))
        with patch("builtins.print"):
            data_cleaning.unused_function()
        after = dict(vars(data_cleaning))
        # Filter out dunder attributes that Python may update automatically
        def public(d):
            return {k: v for k, v in d.items() if not k.startswith("__")}
        self.assertEqual(public(before), public(after))


if __name__ == "__main__":
    unittest.main()
