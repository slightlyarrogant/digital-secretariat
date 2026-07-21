"""Read-only campaign outcome projection from the KRS outreach database."""

import os
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from src.secretariat.schemas import (
    CampaignVariantSummary,
    OutreachSummary,
    OutreachVolumePoint,
)

_WINDOW_DAYS = 90


def _rate(numerator: int, denominator: int) -> float | None:
    if denominator == 0:
        return None
    return round(numerator * 100 / denominator, 2)


def unavailable_outreach() -> OutreachSummary:
    return OutreachSummary(
        available=False,
        window_days=_WINDOW_DAYS,
        sent=0,
        replied=0,
        human_replies=0,
        registrations=0,
        converted=0,
        unsubscribed=0,
        failed=0,
        reply_rate=None,
        conversion_rate=None,
        variants=[],
    )


def read_outreach(path: str | None = None) -> OutreachSummary:
    database_path = path or os.getenv("SECRETARIAT_OUTREACH_DB", "").strip()
    if not database_path or not Path(database_path).is_file():
        return unavailable_outreach()

    try:
        connection = sqlite3.connect(
            f"file:{database_path}?mode=ro",
            uri=True,
            timeout=5,
        )
        connection.row_factory = sqlite3.Row
        cutoff = f"datetime('now', '-{_WINDOW_DAYS} days')"
        totals = connection.execute(
            f"""
            SELECT COUNT(sent_at) AS sent,
                   COUNT(replied_at) AS replied,
                   COUNT(converted_at) AS converted,
                   COUNT(unsubscribed_at) AS unsubscribed,
                   COUNT(*) FILTER (WHERE status = 'failed') AS failed
            FROM email_campaigns
            WHERE sent_at >= {cutoff}
            """
        ).fetchone()
        outcomes = connection.execute(
            f"""
            SELECT COUNT(*) FILTER (WHERE reply_classification = 'human_reply') AS human_replies,
                   COUNT(*) FILTER (WHERE reply_account = 'registration') AS registrations
            FROM leads
            WHERE reply_date >= {cutoff}
            """
        ).fetchone()
        variant_rows = connection.execute(
            f"""
            SELECT campaign, variant, COUNT(sent_at) AS sent,
                   COUNT(replied_at) AS replied,
                   COUNT(converted_at) AS converted,
                   COUNT(unsubscribed_at) AS unsubscribed
            FROM email_campaigns
            WHERE sent_at >= {cutoff}
            GROUP BY campaign, variant
            ORDER BY sent DESC, campaign, variant
            """
        ).fetchall()
        daily_rows = connection.execute(
            f"""
            SELECT day, SUM(sent) AS sent, SUM(replied) AS replied
            FROM (
                SELECT date(sent_at) AS day, COUNT(*) AS sent, 0 AS replied
                FROM email_campaigns
                WHERE sent_at >= {cutoff}
                GROUP BY 1
                UNION ALL
                SELECT date(replied_at) AS day, 0 AS sent, COUNT(*) AS replied
                FROM email_campaigns
                WHERE replied_at >= {cutoff}
                GROUP BY 1
            )
            GROUP BY day
            ORDER BY day
            """
        ).fetchall()
    except sqlite3.Error:
        return unavailable_outreach()
    finally:
        if "connection" in locals():
            connection.close()

    sent = int(totals["sent"] or 0)
    replied = int(totals["replied"] or 0)
    converted = int(totals["converted"] or 0)
    variants = [
        CampaignVariantSummary(
            campaign=str(row["campaign"]),
            variant=row["variant"],
            sent=int(row["sent"] or 0),
            replied=int(row["replied"] or 0),
            converted=int(row["converted"] or 0),
            unsubscribed=int(row["unsubscribed"] or 0),
            reply_rate=_rate(int(row["replied"] or 0), int(row["sent"] or 0)),
            conversion_rate=_rate(int(row["converted"] or 0), int(row["sent"] or 0)),
        )
        for row in variant_rows
    ]
    last_day = datetime.now(ZoneInfo("Europe/Warsaw")).date()
    first_day = last_day - timedelta(days=_WINDOW_DAYS - 1)
    daily_values = {str(row["day"]): dict(row) for row in daily_rows}
    daily = [
        OutreachVolumePoint(
            day=day,
            sent=int(daily_values.get(day.isoformat(), {}).get("sent", 0) or 0),
            replied=int(daily_values.get(day.isoformat(), {}).get("replied", 0) or 0),
        )
        for day in (first_day + timedelta(days=offset) for offset in range(_WINDOW_DAYS))
    ]
    return OutreachSummary(
        available=True,
        window_days=_WINDOW_DAYS,
        sent=sent,
        replied=replied,
        human_replies=int(outcomes["human_replies"] or 0),
        registrations=int(outcomes["registrations"] or 0),
        converted=converted,
        unsubscribed=int(totals["unsubscribed"] or 0),
        failed=int(totals["failed"] or 0),
        reply_rate=_rate(replied, sent),
        conversion_rate=_rate(converted, sent),
        variants=variants,
        daily=daily,
    )
