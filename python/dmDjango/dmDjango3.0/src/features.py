from django.db.backends.base.features import BaseDatabaseFeatures
from django.db.utils import InterfaceError

try:
    import pytz
except ImportError:
    pytz = None


class DatabaseFeatures(BaseDatabaseFeatures):
    can_use_chunked_reads = True
    empty_fetchmany_value = []
    interprets_empty_strings_as_nulls = False
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
    can_defer_constraint_checks = False
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
    
    supports_primitives_in_json_field = False
    supports_json_field_contains = False
    
    supports_partial_indexes = False
    supports_json_field = False
    
    supports_ignore_conflicts = False
    supports_boolean_expr_in_select_clause = False
    
    supports_deferrable_unique_constraints = False
    allows_multiple_constraints_on_same_fields = False
    supports_nullable_unique_constraints = False
    has_case_insensitive_like = False
    supports_index_on_text_field = False
    
    ignores_table_name_case = False
    can_introspect_autofield = True
    
    supports_paramstyle_pyformat = False
    
    time_cast_precision = 0
    
    can_introspect_small_integer_field = True
    introspected_small_auto_field_type = 'AutoField'
    
    can_create_inline_fk = False
    
    allows_auto_pk_0 = False
    
    supports_explaining_query_execution = False
    
    allow_sliced_subqueries_with_in = False
    
    dmDjango = True

