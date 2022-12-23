/*
   Copyright (c) 2008, 2011, Oracle and/or its affiliates. All rights reserved.

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

#include "sql_priv.h"
#include "unireg.h"
#include "sp_head.h"
#include "event_parse_data.h"
#include "sql_time.h"                           // TIME_to_timestamp

/*
  Returns a new instance

  SYNOPSIS
    Event_parse_data::new_instance()

  RETURN VALUE
    Address or NULL in case of error

  NOTE
    Created on THD's mem_root
*/

Event_parse_data *
Event_parse_data::new_instance(THD *thd)
{
  return new (thd->mem_root) Event_parse_data;
}


/*
  Constructor

  SYNOPSIS
    Event_parse_data::Event_parse_data()
*/

Event_parse_data::Event_parse_data()
  :on_completion(Event_parse_data::ON_COMPLETION_DEFAULT),
  status(Event_parse_data::ENABLED), status_changed(false),
  do_not_create(FALSE), body_changed(FALSE),
  item_starts(NULL), item_ends(NULL), item_execute_at(NULL),
  starts_null(TRUE), ends_null(TRUE), execute_at_null(TRUE),
  item_expression(NULL), expression(0)
{
  DBUG_ENTER("Event_parse_data::Event_parse_data");

  /* Actually in the parser STARTS is always set */
  starts= ends= execute_at= 0;

  comment.str= NULL;
  comment.length= 0;

  DBUG_VOID_RETURN;
}