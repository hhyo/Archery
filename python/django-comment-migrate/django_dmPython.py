from django_comment_migrate.backends.base import BaseCommentMigration
from django_comment_migrate.utils import get_field_comment, get_table_comment


class CommentMigration(BaseCommentMigration):
    comment_sql = "COMMENT ON COLUMN "
    table_comment_sql = "COMMENT ON TABLE "

    def comments_sql(self):
        results = []
        comments_sql = self._get_fields_comments_sql()
        if comments_sql:
            results.extend(comments_sql)
        table_comment = get_table_comment(self.model)
        if table_comment:
            results.append(
                (
                    self.table_comment_sql+self.db_table+" IS "+"'"+table_comment+"'",
                    [table_comment],
                )
            )

        return results

    def _get_fields_comments_sql(self):
        comments_sql = []
        for field in self.model._meta.local_fields:
            comment = get_field_comment(field)
            if comment:
                comment_sql = "COMMENT ON COLUMN "+self.db_table+"."+field.column+" IS "+"'"+comment+"'"
                comments_sql.append((comment_sql, [comment]))
        return comments_sql
