class TableMetadataUnavailableError(Exception):
    def __init__(self, table):
        Exception.__init__(self,"Unable to find metadata for table {0}".format(table))


class BinLogNotEnabled(Exception):
    def __init__(self):
        Exception.__init__(self, "MySQL binary logging is not enabled.")
