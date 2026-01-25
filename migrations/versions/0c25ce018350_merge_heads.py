"""merge heads

Revision ID: 0c25ce018350
Revises: c1d2e3f4a5b6, c3d4e5f6a7b8
Create Date: 2026-01-17 17:04:12.988965

"""
from alembic import op
import sqlalchemy as sa


revision = '0c25ce018350'
down_revision = ('c1d2e3f4a5b6', 'c3d4e5f6a7b8')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
