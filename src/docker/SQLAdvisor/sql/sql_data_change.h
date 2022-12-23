#ifndef SQL_DATA_CHANGE_INCLUDED
#define SQL_DATA_CHANGE_INCLUDED
/* Copyright (c) 2000, 2013, Oracle and/or its affiliates. All rights reserved.

   This program is free software; you can redistribute it and/or modify
   it under the terms of the GNU General Public License as published by
   the Free Software Foundation; version 2 of the License.

   This program is distributed in the hope that it will be useful,
   but WITHOUT ANY WARRANTY; without even the implied warranty of
   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
   GNU General Public License for more details.

   You should have received a copy of the GNU General Public License
   along with this program; if not, write to the Free Software Foundation,
   51 Franklin Street, Suite 500, Boston, MA 02110-1335 USA */

/**
  @file sql_data_change.h

  Contains classes representing SQL-data change statements. The
  actual implementions of the functionality are found in files
  sql_{insert, update}.{h,cc} 
*/

#include "sql_list.h"
#include "my_base.h"
#include "my_bitmap.h"
#include "table.h"

enum enum_duplicates { DUP_ERROR, DUP_REPLACE, DUP_UPDATE };

/**
   This class encapsulates a data change operation. There are three such
   operations.

   -# Insert statements, i.e. INSERT INTO .. VALUES

   -# Update statements. UPDATE <table> SET ...

   -# Delete statements. Currently this class is not used for delete statements
      and thus has not yet been adapted to handle it.

   @todo Rename this class.

  The COPY_INFO structure is used by INSERT/REPLACE code.
  The schema of the row counting by the INSERT/INSERT ... ON DUPLICATE KEY
  UPDATE code:
    If a row is inserted then the copied variable is incremented.
    If a row is updated by the INSERT ... ON DUPLICATE KEY UPDATE and the
      new data differs from the old one then the copied and the updated
      variables are incremented.
    The touched variable is incremented if a row was touched by the update part
      of the INSERT ... ON DUPLICATE KEY UPDATE no matter whether the row
      was actually changed or not.
*/
class COPY_INFO: public Sql_alloc
{
public:
  class Statistics
  {
  public:
    Statistics() :
      records(0), deleted(0), updated(0), copied(0), error_count(0), touched(0)
    {}

    ha_rows records; /**< Number of processed records */
    ha_rows deleted; /**< Number of deleted records */
    ha_rows updated; /**< Number of updated records */
    ha_rows copied;  /**< Number of copied records */
    ha_rows error_count;
    ha_rows touched; /* Number of touched records */
  };

  enum operation_type { INSERT_OPERATION, UPDATE_OPERATION };

private:
  COPY_INFO(const COPY_INFO &other);            ///< undefined
  void operator=(COPY_INFO &);                  ///< undefined

  /// Describes the data change operation that this object represents.
  const operation_type m_optype;

  /**
     List of columns of the target table which the statement will explicitely
     fill; and thus we must not set a function default for them.
     NULL means "empty list".
  */
  List<Item> *m_changed_columns;

  /**
     A second list of columns like m_changed_columns. See the constructor
     specific of LOAD DATA INFILE, below.
  */
  List<Item> *m_changed_columns2;


  /** Whether this object must manage function defaults */
  const bool m_manage_defaults;
  /** Bitmap: bit is set if we should set column #i to its function default */
  MY_BITMAP *m_function_default_columns;

protected:

  /**
     Policy for handling insertion of duplicate values. Protected for legacy
     reasons.

     @see Delayable_insert_operation::set_dup_and_ignore()
  */
  enum enum_duplicates handle_duplicates;

  /**
     Policy for whether certain errors should be ignored. Protected for legacy
     reasons.

     @see Delayable_insert_operation::set_dup_and_ignore()
  */
  bool ignore;

  /**
     The column bitmap which has been cached for this data change operation.
     @see COPY_INFO::get_function_default_columns()

     @return The cached bitmap, or NULL if no bitmap was cached.
   */
  MY_BITMAP *get_cached_bitmap() const { return m_function_default_columns; }

public:
  Statistics stats;
  int escape_char, last_errno;
  /** Values for UPDATE; needed by write_record() if INSERT with DUP_UPDATE */
  List<Item> *update_values;

  /**
     Initializes this data change operation as an SQL @c INSERT (with all
     possible syntaxes and variants).

     @param optype           The data change operation type.
     @param inserted_columns List of columns of the target table which
                             the statement will explicitely fill; COPY_INFO
                             must not set a function default for them. NULL
                             means "empty list".
     @param manage_defaults  Whether this object should manage function
                             defaults.
     @param duplicate_handling The policy for handling duplicates.
     @param ignore_errors    Whether certain ignorable errors should be
                             ignored. A proper documentation has never existed
                             for this member, so the following has been
                             compiled by examining how clients actually use
                             the member.

     - Ignore non-fatal errors, except duplicate key error, during this insert
       operation (this constructor can only construct an insert operation).
     - If the insert operation spawns an update operation (as in ON DUPLICATE
       KEY UPDATE), tell the layer below
       (fill_record_n_invoke_before_triggers) to 'ignore errors'. (More
       detailed documentation is not available).
     - Let @i v be a view for which WITH CHECK OPTION applies. This can happen
       either if @i v is defined with WITH ... CHECK OPTION, or if @i v is
       being inserted into by a cascaded insert and an outer view is defined
       with "WITH CASCADED CHECK OPTION".
       If the insert operation on @i v spawns an update operation (as in ON
       DUPLICATE KEY UPDATE) for a certain row, and hence the @i v is being
       updated, ignore whether the WHERE clause was true for this row or
       not. I.e. if ignore is true, WITH CHECK OPTION can be ignored.
     - If the insert operation spawns an update operation (as in ON DUPLICATE
       KEY UPDATE) that fails, ignore this error.
  */
  COPY_INFO(operation_type optype,
            List<Item> *inserted_columns,
            bool manage_defaults,
            enum_duplicates duplicate_handling,
            bool ignore_errors) :
    m_optype(optype),
    m_changed_columns(inserted_columns),
    m_changed_columns2(NULL),
    m_manage_defaults(manage_defaults),
    m_function_default_columns(NULL),
    handle_duplicates(duplicate_handling),
    ignore(ignore_errors),
    stats(),
    escape_char(0),
    last_errno(0),
    update_values(NULL)
  {
    DBUG_ASSERT(optype == INSERT_OPERATION);
  }

  /**
     Initializes this data change operation as an SQL @c LOAD @c DATA @c
     INFILE.
     Note that this statement has its inserted columns spread over two
     lists:
@verbatim
     LOAD DATA INFILE a_file
     INTO TABLE a_table (col1, col2)   < first list (col1, col2)
     SET col3=val;                     < second list (col3)
@endverbatim

     @param optype            The data change operation type.
     @param inserted_columns List of columns of the target table which
                             the statement will explicitely fill; COPY_INFO
                             must not set a function default for them. NULL
                             means "empty list".
     @param inserted_columns2 A second list like inserted_columns
     @param manage_defaults   Whether this object should manage function
                              defaults.
     @param ignore_duplicates   Whether duplicate rows are ignored.
     @param duplicates_handling How to handle duplicates.
     @param escape_character    The escape character.
  */
  COPY_INFO(operation_type optype,
            List<Item> *inserted_columns,
            List<Item> *inserted_columns2,
            bool manage_defaults,
            enum_duplicates duplicates_handling,
            bool ignore_duplicates,
            int escape_character) :
    m_optype(optype),
    m_changed_columns(inserted_columns),
    m_changed_columns2(inserted_columns2),
    m_manage_defaults(manage_defaults),
    m_function_default_columns(NULL),
    handle_duplicates(duplicates_handling),
    ignore(ignore_duplicates),
    stats(),
    escape_char(escape_character),
    last_errno(0),
    update_values(NULL)
  {
    DBUG_ASSERT(optype == INSERT_OPERATION);
  }

  /**
     Initializes this data change operation as an SQL @c UPDATE (multi- or
     not).

     @param fields  The column objects that are to be updated.
     @param values  The values to be assigned to the fields.
     @note that UPDATE always lists columns, so non-listed columns may need a
     default thus m_manage_defaults is always true.
  */
  COPY_INFO(operation_type optype, List<Item> *fields, List<Item> *values) :
    m_optype(optype),
    m_changed_columns(fields),
    m_changed_columns2(NULL),
    m_manage_defaults(true),
    m_function_default_columns(NULL),
    handle_duplicates(DUP_ERROR),
    ignore(false),
    stats(),
    escape_char(0),
    last_errno(0),
    update_values(values)
  {
    DBUG_ASSERT(optype == UPDATE_OPERATION);
  }

  operation_type get_operation_type() const { return m_optype; }

  List<Item> *get_changed_columns() const { return m_changed_columns; }

  const List<Item> *get_changed_columns2() const { return m_changed_columns2; }

  bool get_manage_defaults() const { return m_manage_defaults; }

  enum_duplicates get_duplicate_handling() const { return handle_duplicates; }

  bool get_ignore_errors() const { return ignore; }

  /**
    True if any of the columns set in the bitmap have default functions
    that may set the column.
  */
  bool function_defaults_apply_on_columns(MY_BITMAP *map)
  {
    DBUG_ASSERT(m_function_default_columns != NULL);
    return bitmap_is_overlapping(m_function_default_columns, map);
  }

  /**
     This class allocates its memory in a MEM_ROOT, so there's nothing to
     delete.
  */
  virtual ~COPY_INFO() {}
};


#endif // SQL_DATA_CHANGE_INCLUDED
