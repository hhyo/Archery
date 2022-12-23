/* Copyright (c) 2008, 2011, Oracle and/or its affiliates. All rights reserved.

   This program is free software; you can redistribute it and/or modify
   it under the terms of the GNU General Public License as published by
   the Free Software Foundation; version 2 of the License.

   This program is distributed in the hope that it will be useful,
   but WITHOUT ANY WARRANTY; without even the implied warranty of
   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
   GNU General Public License for more details.

   You should have received a copy of the GNU General Public License
   along with this program; if not, write to the Free Software
   Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA 02110-1301  USA */

#include "sql_priv.h"
#include "sp_head.h"
#include "sp_pcontext.h"
#include "sql_signal.h"

/*
  The parser accepts any error code (desired)
  The runtime internally supports any error code (desired)
  The client server protocol is limited to 16 bits error codes (restriction)
  Enforcing the 65535 limit in the runtime until the protocol can change.
*/
#define MAX_MYSQL_ERRNO UINT_MAX16

const LEX_STRING Diag_condition_item_names[]=
{
  { C_STRING_WITH_LEN("CLASS_ORIGIN") },
  { C_STRING_WITH_LEN("SUBCLASS_ORIGIN") },
  { C_STRING_WITH_LEN("CONSTRAINT_CATALOG") },
  { C_STRING_WITH_LEN("CONSTRAINT_SCHEMA") },
  { C_STRING_WITH_LEN("CONSTRAINT_NAME") },
  { C_STRING_WITH_LEN("CATALOG_NAME") },
  { C_STRING_WITH_LEN("SCHEMA_NAME") },
  { C_STRING_WITH_LEN("TABLE_NAME") },
  { C_STRING_WITH_LEN("COLUMN_NAME") },
  { C_STRING_WITH_LEN("CURSOR_NAME") },
  { C_STRING_WITH_LEN("MESSAGE_TEXT") },
  { C_STRING_WITH_LEN("MYSQL_ERRNO") },

  { C_STRING_WITH_LEN("CONDITION_IDENTIFIER") },
  { C_STRING_WITH_LEN("CONDITION_NUMBER") },
  { C_STRING_WITH_LEN("CONNECTION_NAME") },
  { C_STRING_WITH_LEN("MESSAGE_LENGTH") },
  { C_STRING_WITH_LEN("MESSAGE_OCTET_LENGTH") },
  { C_STRING_WITH_LEN("PARAMETER_MODE") },
  { C_STRING_WITH_LEN("PARAMETER_NAME") },
  { C_STRING_WITH_LEN("PARAMETER_ORDINAL_POSITION") },
  { C_STRING_WITH_LEN("RETURNED_SQLSTATE") },
  { C_STRING_WITH_LEN("ROUTINE_CATALOG") },
  { C_STRING_WITH_LEN("ROUTINE_NAME") },
  { C_STRING_WITH_LEN("ROUTINE_SCHEMA") },
  { C_STRING_WITH_LEN("SERVER_NAME") },
  { C_STRING_WITH_LEN("SPECIFIC_NAME") },
  { C_STRING_WITH_LEN("TRIGGER_CATALOG") },
  { C_STRING_WITH_LEN("TRIGGER_NAME") },
  { C_STRING_WITH_LEN("TRIGGER_SCHEMA") }
};

const LEX_STRING Diag_statement_item_names[]=
{
  { C_STRING_WITH_LEN("NUMBER") },
  { C_STRING_WITH_LEN("MORE") },
  { C_STRING_WITH_LEN("COMMAND_FUNCTION") },
  { C_STRING_WITH_LEN("COMMAND_FUNCTION_CODE") },
  { C_STRING_WITH_LEN("DYNAMIC_FUNCTION") },
  { C_STRING_WITH_LEN("DYNAMIC_FUNCTION_CODE") },
  { C_STRING_WITH_LEN("ROW_COUNT") },
  { C_STRING_WITH_LEN("TRANSACTIONS_COMMITTED") },
  { C_STRING_WITH_LEN("TRANSACTIONS_ROLLED_BACK") },
  { C_STRING_WITH_LEN("TRANSACTION_ACTIVE") }
};


Set_signal_information::Set_signal_information(
  const Set_signal_information& set)
{
  memcpy(m_item, set.m_item, sizeof(m_item));
}

void Set_signal_information::clear()
{
  memset(m_item, 0, sizeof(m_item));
}