
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '8ae6f01e5d2c'
down_revision: Union[str, Sequence[str], None] = '0773d9637766'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None



def upgrade() -> None:

    op.execute(
        """
        INSERT INTO roles (code, name)
        VALUES
            ('ADMIN', 'Admin'),
            ('ENGINEER', 'Engineer'),
            ('VIEWER', 'Viewer')
        ON CONFLICT (code) DO NOTHING;
        """
    )


def downgrade() -> None:

    op.execute(
        """
        DELETE FROM roles
        WHERE code IN ('ADMIN', 'ENGINEER', 'VIEWER');
        """
    )
