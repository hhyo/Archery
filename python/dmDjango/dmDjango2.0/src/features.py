from django.db.backends.base.features import BaseDatabaseFeatures
from django.db.utils import InterfaceError

try:
    import pytz
except ImportError:
    pytz = None


class DatabaseFeatures(BaseDatabaseFeatures):
    can_use_chunked_reads = True
    empty_fetchmany_value = []
    uses_savepoints = True
    has_select_for_update = True
    has_select_for_update_nowait = True
    can_return_id_from_insert = False
    allow_sliced_subqueries = False
    supports_subqueries_in_group_by = False
    supports_transactions = True
    supports_timezones = False
    has_zoneinfo_database = pytz is not None
    supports_bitwise_or = False
    has_native_duration_field = True
    can_defer_constraint_checks = True
    supports_partially_nullable_unique_constraints = False
    truncates_names = True
    has_bulk_insert = False
    supports_tablespaces = True
    supports_sequence_reset = False
    can_introspect_default = False  # Pending implementation by an interested person.
    can_introspect_max_length = False
    can_introspect_time_field = False
    atomic_transactions = False
    supports_combined_alters = False
    nulls_order_largest = True
    requires_literal_defaults = True
    closed_cursor_error_class = InterfaceError
    bare_select_suffix = " FROM DUAL"
    uppercases_column_names = True
    supports_select_for_update_with_limit = False

    def introspected_boolean_field_type(self, field=None, created_separately=False):    
        return super(DatabaseFeatures, self).introspected_boolean_field_type(field, created_separately)
