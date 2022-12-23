/* Copyright (c) 2008, 2010, Oracle and/or its affiliates. All rights reserved.

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

#ifndef SQL_SIGNAL_H
#define SQL_SIGNAL_H

/**
  Sql_cmd_common_signal represents the common properties of the
  SIGNAL and RESIGNAL statements.
*/
class Sql_cmd_common_signal : public Sql_cmd
{
protected:
  /**
    Constructor.
    @param cond the condition signaled if any, or NULL.
    @param set collection of signal condition item assignments.
  */
  Sql_cmd_common_signal(const sp_condition_value *cond,
                        const Set_signal_information& set)
    : Sql_cmd(),
      m_cond(cond),
      m_set_signal_information(set)
  {}

  virtual ~Sql_cmd_common_signal()
  {}


  /**
    The condition to signal or resignal.
    This member is optional and can be NULL (RESIGNAL).
  */
  const sp_condition_value *m_cond;

  /**
    Collection of 'SET item = value' assignments in the
    SIGNAL/RESIGNAL statement.
  */
  Set_signal_information m_set_signal_information;
};

/**
  Sql_cmd_signal represents a SIGNAL statement.
*/
class Sql_cmd_signal : public Sql_cmd_common_signal
{
public:
  /**
    Constructor, used to represent a SIGNAL statement.
    @param cond the SQL condition to signal (required).
    @param set the collection of signal informations to signal.
  */
  Sql_cmd_signal(const sp_condition_value *cond,
                 const Set_signal_information& set)
    : Sql_cmd_common_signal(cond, set)
  {}

  virtual ~Sql_cmd_signal()
  {}

  virtual enum_sql_command sql_command_code() const
  {
    return SQLCOM_SIGNAL;
  }
};

/**
  Sql_cmd_resignal represents a RESIGNAL statement.
*/
class Sql_cmd_resignal : public Sql_cmd_common_signal
{
public:
  /**
    Constructor, used to represent a RESIGNAL statement.
    @param cond the SQL condition to resignal (optional, may be NULL).
    @param set the collection of signal informations to resignal.
  */
  Sql_cmd_resignal(const sp_condition_value *cond,
                   const Set_signal_information& set)
    : Sql_cmd_common_signal(cond, set)
  {}

  virtual ~Sql_cmd_resignal()
  {}

  virtual enum_sql_command sql_command_code() const
  {
    return SQLCOM_RESIGNAL;
  }
};

#endif

