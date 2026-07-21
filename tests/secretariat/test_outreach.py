import sqlite3

from src.secretariat.outreach import read_outreach


def test_outreach_projection_uses_campaign_outcomes_without_fabricating_opens(tmp_path) -> None:
    database = tmp_path / "outreach.db"
    connection = sqlite3.connect(database)
    connection.executescript(
        """
        CREATE TABLE email_campaigns (
            campaign TEXT, variant TEXT, sent_at DATETIME, replied_at DATETIME,
            converted_at DATETIME, unsubscribed_at DATETIME, status TEXT
        );
        CREATE TABLE leads (
            reply_classification TEXT, reply_account TEXT, reply_date DATETIME
        );
        INSERT INTO email_campaigns VALUES
            ('launch', 'a', datetime('now'), datetime('now'), NULL, NULL, 'replied'),
            ('launch', 'a', datetime('now'), NULL, NULL, NULL, 'sent'),
            ('launch', 'b', datetime('now'), NULL, datetime('now'), NULL, 'sent');
        INSERT INTO leads VALUES
            ('human_reply', NULL, datetime('now')),
            ('REGISTRATION', 'registration', datetime('now'));
        """
    )
    connection.commit()
    connection.close()

    result = read_outreach(str(database))

    assert result.available is True
    assert result.sent == 3
    assert result.replied == 1
    assert result.human_replies == 1
    assert result.registrations == 1
    assert result.converted == 1
    assert result.reply_rate == 33.33
    assert [variant.variant for variant in result.variants] == ["a", "b"]
    assert len(result.daily) == 90
    assert result.daily[-1].sent == 3
    assert result.daily[-1].replied == 1


def test_outreach_projection_fails_closed_when_database_is_missing(tmp_path) -> None:
    result = read_outreach(str(tmp_path / "missing.db"))

    assert result.available is False
    assert result.sent == 0
    assert result.variants == []
