
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '26f41b1a4a80'
down_revision: Union[str, Sequence[str], None] = '8ae6f01e5d2c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:

    op.create_table('login_attempts',
    sa.Column('id', sa.BigInteger(), sa.Identity(always=False), nullable=False),
    sa.Column('email', sa.String(length=255), nullable=False),
    sa.Column('ip_address', sa.String(length=45), nullable=False),
    sa.Column('attempted_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_login_attempts_email_time', 'login_attempts', ['email', 'attempted_at'], unique=False)
    op.create_index('ix_login_attempts_ip_time', 'login_attempts', ['ip_address', 'attempted_at'], unique=False)

def downgrade() -> None:

    op.drop_index('ix_login_attempts_ip_time', table_name='login_attempts')
    op.drop_index('ix_login_attempts_email_time', table_name='login_attempts')
    op.drop_table('login_attempts')
