/* Copyright (c) 2003, 2013, Oracle and/or its affiliates. All rights reserved.

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
  @file

  @brief
  This file defines all spatial functions
*/

#include "sql_priv.h"
/*
  It is necessary to include set_var.h instead of item.h because there
  are dependencies on include order for set_var.h and item.h. This
  will be resolved later.
*/
#include "sql_class.h"                          // THD, set_var.h: THD
#include "set_var.h"
#ifdef HAVE_SPATIAL
#include <m_ctype.h>

/*
  Functions for spatial relations
*/

const char *Item_func_spatial_mbr_rel::func_name() const 
{ 
  switch (spatial_rel) {
    case SP_CONTAINS_FUNC:
      return "mbrcontains";
    case SP_WITHIN_FUNC:
      return "mbrwithin";
    case SP_EQUALS_FUNC:
      return "mbrequals";
    case SP_DISJOINT_FUNC:
      return "mbrdisjoint";
    case SP_INTERSECTS_FUNC:
      return "mbrintersects";
    case SP_TOUCHES_FUNC:
      return "mbrtouches";
    case SP_CROSSES_FUNC:
      return "mbrcrosses";
    case SP_OVERLAPS_FUNC:
      return "mbroverlaps";
    default:
      DBUG_ASSERT(0);  // Should never happened
      return "mbrsp_unknown"; 
  }
}


Item_func_spatial_rel::Item_func_spatial_rel(Item *a,Item *b,
                                             enum Functype sp_rel) :
    Item_bool_func2(a,b)
{
  spatial_rel = sp_rel;
}


Item_func_spatial_rel::~Item_func_spatial_rel()
{
}


const char *Item_func_spatial_rel::func_name() const 
{ 
  switch (spatial_rel) {
    case SP_CONTAINS_FUNC:
      return "st_contains";
    case SP_WITHIN_FUNC:
      return "st_within";
    case SP_EQUALS_FUNC:
      return "st_equals";
    case SP_DISJOINT_FUNC:
      return "st_disjoint";
    case SP_INTERSECTS_FUNC:
      return "st_intersects";
    case SP_TOUCHES_FUNC:
      return "st_touches";
    case SP_CROSSES_FUNC:
      return "st_crosses";
    case SP_OVERLAPS_FUNC:
      return "st_overlaps";
    default:
      DBUG_ASSERT(0);  // Should never happened
      return "sp_unknown"; 
  }
}

#define GIS_ZERO 0.00000000001

Item_func_spatial_operation::~Item_func_spatial_operation()
{
}


const char *Item_func_spatial_operation::func_name() const
{
  switch (spatial_op) {
    case Item_func_spatial_operation::op_intersection:
      return "st_intersection";
    case Item_func_spatial_operation::op_difference:
      return "st_difference";
    case Item_func_spatial_operation::op_union:
      return "st_union";
    case Item_func_spatial_operation::op_symdifference:
      return "st_symdifference";
    default:
      DBUG_ASSERT(0);  // Should never happen
      return "sp_unknown";
  }
}
#endif /*HAVE_SPATIAL*/
