"""Tests for TickTick MCP filter tools and helpers.

These tests verify:
1. CJK characters are preserved (not Unicode-escaped) in JSON output
2. ZoneInfo timezone handling works correctly (no pytz .localize())
3. PeriodFilter field ordering applies tz to date validators

Tests mock config.py's argparse to avoid conflicts with pytest CLI args.
"""
import datetime
import json
import sys
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest


# Patch argparse before any src imports to prevent config.py from
# stealing pytest's CLI arguments
@pytest.fixture(autouse=True)
def _patch_argparse():
    """Prevent config.py argparse from consuming pytest args."""
    with patch(
        "sys.argv",
        ["ticktick-mcp", "--dotenv-dir", "~/.config/ticktick-mcp"],
    ):
        yield


def _import_format_response():
    from src.ticktick_mcp.helpers import format_response
    return format_response


def _import_period_filter():
    from src.ticktick_mcp.tools.filter_tools import PeriodFilter
    return PeriodFilter


class TestFormatResponseCJK:
    """Bug 1: json.dumps must use ensure_ascii=False for CJK characters."""

    def test_format_response_preserves_cjk(self):
        format_response = _import_format_response()
        result = format_response({"title": "旅人無限卡 副卡"})
        assert "旅人無限卡" in result, (
            f"CJK characters were Unicode-escaped: {result!r}"
        )

    def test_format_response_preserves_mixed_cjk_ascii(self):
        format_response = _import_format_response()
        result = format_response({"title": "HSBC 旅人無限卡", "status": "done"})
        assert "旅人無限卡" in result
        assert "HSBC" in result

    def test_format_response_list_preserves_cjk(self):
        format_response = _import_format_response()
        tasks = [
            {"title": "台灣既有客戶 價格調整"},
            {"title": "電力系統新產品學習知識"},
        ]
        result = format_response(tasks)
        assert "台灣既有客戶" in result
        assert "電力系統" in result


class TestPeriodFilterLocalize:
    """Bug 2: ZoneInfo doesn't have .localize() — must use .replace(tzinfo=)."""

    def test_parse_task_date_naive_with_tz(self):
        """A date-only string should produce a tz-aware datetime, not None."""
        PeriodFilter = _import_period_filter()
        pf = PeriodFilter(
            tz=ZoneInfo("Asia/Taipei"),
            start_date=None,
            end_date=None,
        )
        result = pf._parse_task_date("2026-02-05")
        assert result is not None, (
            "_parse_task_date returned None — likely ZoneInfo.localize() AttributeError"
        )
        assert result.tzinfo is not None, "Result should be timezone-aware"
        assert result.date() == datetime.date(2026, 2, 5)

    def test_parse_task_date_naive_datetime_with_tz(self):
        """A naive datetime string (no offset) should get tz applied."""
        PeriodFilter = _import_period_filter()
        pf = PeriodFilter(
            tz=ZoneInfo("Asia/Taipei"),
            start_date=None,
            end_date=None,
        )
        result = pf._parse_task_date("2026-02-05T10:30:00")
        assert result is not None
        assert result.tzinfo is not None

    def test_parse_task_date_ticktick_format(self):
        """Standard TickTick timestamp (+0000 offset) should parse correctly."""
        PeriodFilter = _import_period_filter()
        pf = PeriodFilter(
            tz=ZoneInfo("Asia/Taipei"),
            start_date=None,
            end_date=None,
        )
        result = pf._parse_task_date("2026-02-10T03:44:31.000+0000")
        assert result is not None
        assert result.date() == datetime.date(2026, 2, 10)


class TestPeriodFilterFieldOrder:
    """Bug 3: tz field must be validated before start_date/end_date."""

    def test_tz_applied_to_start_date(self):
        """When tz is provided, start_date should be timezone-aware."""
        PeriodFilter = _import_period_filter()
        pf = PeriodFilter(
            tz=ZoneInfo("Asia/Taipei"),
            start_date="2026-02-01",
            end_date="2026-02-10",
        )
        assert pf.start_date is not None
        assert pf.start_date.tzinfo is not None, (
            "start_date has no timezone — tz field ordering bug"
        )

    def test_tz_applied_to_end_date(self):
        """When tz is provided, end_date should be timezone-aware."""
        PeriodFilter = _import_period_filter()
        pf = PeriodFilter(
            tz=ZoneInfo("Asia/Taipei"),
            start_date="2026-02-01",
            end_date="2026-02-10",
        )
        assert pf.end_date is not None
        assert pf.end_date.tzinfo is not None, (
            "end_date has no timezone — tz field ordering bug"
        )


class TestContainsIntegration:
    """Integration: PeriodFilter.contains() should work with real TickTick data."""

    def test_contains_completed_task_timestamp(self):
        """A TickTick completedTime should match a date range filter."""
        PeriodFilter = _import_period_filter()
        pf = PeriodFilter(
            tz=ZoneInfo("Asia/Taipei"),
            start_date="2026-02-01",
            end_date="2026-02-11",
        )
        assert pf.contains("2026-02-10T03:44:31.000+0000") is True

    def test_contains_excludes_out_of_range(self):
        """A task completed outside the range should not match."""
        PeriodFilter = _import_period_filter()
        pf = PeriodFilter(
            tz=ZoneInfo("Asia/Taipei"),
            start_date="2026-02-01",
            end_date="2026-02-05",
        )
        assert pf.contains("2026-02-10T03:44:31.000+0000") is False

    def test_cjk_task_searchable_in_filter_result(self):
        """End-to-end: filtered task JSON should be greppable for CJK titles."""
        format_response = _import_format_response()
        tasks = [{"title": "旅人無限卡 副卡", "completedTime": "2026-02-10T03:44:31.000+0000"}]
        result = format_response(tasks)
        assert "旅人無限卡" in result, (
            f"CJK title not searchable in output: {result[:200]!r}"
        )
