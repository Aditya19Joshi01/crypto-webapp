"""
Auto-generated Alembic script template.
"""
from alembic import op
import sqlalchemy as sa

revision = '<%= revision %>'
down_revision = <%= repr(down_revision) %>
branch_labels = None
depends_on = None


def upgrade():
<% for stmt in upgrade_ops -%>
    <%= stmt %>
<% endfor -%>


def downgrade():
<% for stmt in downgrade_ops -%>
    <%= stmt %>
<% endfor -%>
