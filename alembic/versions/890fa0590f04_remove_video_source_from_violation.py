"""remove video_source from violation

Revision ID: 890fa0590f04
Revises: d0c68ef3417f
Create Date: 2025-05-12 16:51:44.012730

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = '890fa0590f04'
down_revision: Union[str, None] = 'd0c68ef3417f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('violations', 'video_source')
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('violations', sa.Column('video_source', mysql.VARCHAR(length=256), nullable=True))
    # ### end Alembic commands ###
