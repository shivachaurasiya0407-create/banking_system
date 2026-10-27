"""Normalize stored customer-facing display text to uppercase.

Revision ID: 0007_uppercase_display_text
Revises: 0006_staff_device_sessions
"""
from alembic import op

revision = "0007_uppercase_display_text"
down_revision = "0006_staff_device_sessions"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        UPDATE customers
        SET first_name = upper(first_name),
            last_name = upper(last_name),
            country = upper(country),
            state = upper(state),
            address_line1 = upper(address_line1),
            address_city = upper(address_city)
        """
    )
    op.execute("UPDATE staff_users SET full_name = upper(full_name)")
    op.execute("UPDATE branches SET name = upper(name)")
    op.execute("UPDATE ledger_transactions SET memo = upper(memo)")
    op.execute("UPDATE loans SET memo = upper(memo)")
    op.execute(
        """
        UPDATE audit_events
        SET metadata = jsonb_set(
            metadata::jsonb,
            '{memo}',
            to_jsonb(upper(metadata::jsonb ->> 'memo')),
            false
        )::json
        WHERE jsonb_typeof(metadata::jsonb -> 'memo') = 'string'
        """
    )
    op.execute(
        """
        UPDATE audit_events
        SET metadata = jsonb_set(
            metadata::jsonb,
            '{reason}',
            to_jsonb(upper(metadata::jsonb ->> 'reason')),
            false
        )::json
        WHERE jsonb_typeof(metadata::jsonb -> 'reason') = 'string'
        """
    )


def downgrade():
    pass
