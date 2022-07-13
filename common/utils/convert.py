from django.db.models import Func


class Convert(Func):
    """
    Description: 支持mysql的convert(field using gbk)语法，从而支持汉字排序
    Usage:       queryset.order_by(Convert('name', 'gbk').asc())
    Reference:   https://stackoverflow.com/questions/38517743/django-how-to-make-a-query-with-order-by-convert-name-using-gbk-asc
    """

    def __init__(self, expression, transcoding_name, **extra):
        super(Convert, self).__init__(
            expression=expression, transcoding_name=transcoding_name, **extra
        )

    def as_mysql(self, compiler, connection):
        self.function = "CONVERT"
        self.template = "%(function)s(%(expression)s USING  %(transcoding_name)s)"
        return super(Convert, self).as_sql(compiler, connection)
