#ifndef ITEM_GEOFUNC_INCLUDED
#define ITEM_GEOFUNC_INCLUDED

/* Copyright (c) 2000, 2011, Oracle and/or its affiliates. All rights reserved.

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


/* This file defines all spatial functions */

#ifdef HAVE_SPATIAL


class Item_geometry_func: public Item_str_func
{
public:
  Item_geometry_func() :Item_str_func() {}
  Item_geometry_func(Item *a) :Item_str_func(a) {}
  Item_geometry_func(Item *a,Item *b) :Item_str_func(a,b) {}
  Item_geometry_func(Item *a,Item *b,Item *c) :Item_str_func(a,b,c) {}
  Item_geometry_func(List<Item> &list) :Item_str_func(list) {}
  enum_field_types field_type() const  { return MYSQL_TYPE_GEOMETRY; };
  String *val_str(String *) {return NULL;}
};

class Item_func_geometry_from_text: public Item_geometry_func
{
public:
  Item_func_geometry_from_text(Item *a) :Item_geometry_func(a) {}
  Item_func_geometry_from_text(Item *a, Item *srid) :Item_geometry_func(a, srid) {}
  const char *func_name() const { return "st_geometryfromtext"; }

};

class Item_func_geometry_from_wkb: public Item_geometry_func
{
  String tmp_value;
public:
  Item_func_geometry_from_wkb(Item *a): Item_geometry_func(a) {}
  Item_func_geometry_from_wkb(Item *a, Item *srid): Item_geometry_func(a, srid) {}
  const char *func_name() const { return "st_geometryfromwkb"; }
};

class Item_func_as_wkt: public Item_str_ascii_func
{
public:
  Item_func_as_wkt(Item *a): Item_str_ascii_func(a) {}
  const char *func_name() const { return "st_astext"; }
  String *val_str_ascii(String *) {return NULL;}
};

class Item_func_as_wkb: public Item_geometry_func
{
public:
  Item_func_as_wkb(Item *a): Item_geometry_func(a) {}
  const char *func_name() const { return "st_aswkb"; }
  enum_field_types field_type() const  { return MYSQL_TYPE_BLOB; }
};

class Item_func_geometry_type: public Item_str_ascii_func
{
public:
  Item_func_geometry_type(Item *a): Item_str_ascii_func(a) {}
  const char *func_name() const { return "st_geometrytype"; }
  String *val_str_ascii(String *) { return NULL; }
};

class Item_func_centroid: public Item_geometry_func
{
public:
  Item_func_centroid(Item *a): Item_geometry_func(a) {}
  const char *func_name() const { return "st_centroid"; }
};

class Item_func_envelope: public Item_geometry_func
{
public:
  Item_func_envelope(Item *a): Item_geometry_func(a) {}
  const char *func_name() const { return "st_envelope"; }
};

class Item_func_point: public Item_geometry_func
{
public:
  Item_func_point(Item *a, Item *b): Item_geometry_func(a, b) {}
  Item_func_point(Item *a, Item *b, Item *srid): Item_geometry_func(a, b, srid) {}
  const char *func_name() const { return "st_point"; }
};

class Item_func_spatial_decomp: public Item_geometry_func
{
  enum Functype decomp_func;
public:
  Item_func_spatial_decomp(Item *a, Item_func::Functype ft) :
  	Item_geometry_func(a) { decomp_func = ft; }
  const char *func_name() const 
  { 
    switch (decomp_func)
    {
      case SP_STARTPOINT:
        return "st_startpoint";
      case SP_ENDPOINT:
        return "st_endpoint";
      case SP_EXTERIORRING:
        return "st_exteriorring";
      default:
	DBUG_ASSERT(0);  // Should never happened
        return "spatial_decomp_unknown"; 
    }
  }
};

class Item_func_spatial_decomp_n: public Item_geometry_func
{
  enum Functype decomp_func_n;
public:
  Item_func_spatial_decomp_n(Item *a, Item *b, Item_func::Functype ft):
  	Item_geometry_func(a, b) { decomp_func_n = ft; }
  const char *func_name() const 
  { 
    switch (decomp_func_n)
    {
      case SP_POINTN:
        return "st_pointn";
      case SP_GEOMETRYN:
        return "st_geometryn";
      case SP_INTERIORRINGN:
        return "st_interiorringn";
      default:
	DBUG_ASSERT(0);  // Should never happened
        return "spatial_decomp_n_unknown"; 
    }
  }
};

class Item_func_spatial_collection: public Item_geometry_func
{
  String tmp_value;
  enum Geometry::wkbType coll_type; 
  enum Geometry::wkbType item_type;
public:
  Item_func_spatial_collection(
     List<Item> &list, enum Geometry::wkbType ct, enum Geometry::wkbType it):
  Item_geometry_func(list)
  {
    coll_type=ct;
    item_type=it;
  }
  const char *func_name() const { return "st_multipoint"; }
};


/*
  Spatial relations
*/

class Item_func_spatial_mbr_rel: public Item_bool_func2
{
  enum Functype spatial_rel;
public:
  Item_func_spatial_mbr_rel(Item *a,Item *b, enum Functype sp_rel) :
    Item_bool_func2(a,b) { spatial_rel = sp_rel; }
  longlong val_int() {return 0;}
  enum Functype functype() const 
  { 
    return spatial_rel;
  }
  enum Functype rev_functype() const
  {
    switch (spatial_rel)
    {
      case SP_CONTAINS_FUNC:
        return SP_WITHIN_FUNC;
      case SP_WITHIN_FUNC:
        return SP_CONTAINS_FUNC;
      default:
        return spatial_rel;
    }
  }

  const char *func_name() const;
  virtual inline void print(String *str, enum_query_type query_type)
  {
    Item_func::print(str, query_type);
  }
  bool is_null() { (void) val_int(); return null_value; }
};


class Item_func_spatial_rel: public Item_bool_func2
{
  enum Functype spatial_rel;
  String tmp_value1,tmp_value2;
public:
  Item_func_spatial_rel(Item *a,Item *b, enum Functype sp_rel);
  virtual ~Item_func_spatial_rel();
  longlong val_int() {return 0;}
  enum Functype functype() const 
  { 
    return spatial_rel;
  }
  enum Functype rev_functype() const
  {
    switch (spatial_rel)
    {
      case SP_CONTAINS_FUNC:
        return SP_WITHIN_FUNC;
      case SP_WITHIN_FUNC:
        return SP_CONTAINS_FUNC;
      default:
        return spatial_rel;
    }
  }

  const char *func_name() const;
  virtual inline void print(String *str, enum_query_type query_type)
  {
    Item_func::print(str, query_type);
  }

  bool is_null() { (void) val_int(); return null_value; }
};


/*
  Spatial operations
*/

class Item_func_spatial_operation: public Item_geometry_func
{
public:
  enum op_type
  {
    op_shape= 0,
    op_not= 0x80000000,
    op_union= 0x10000000,
    op_intersection= 0x20000000,
    op_symdifference= 0x30000000,
    op_difference= 0x40000000,
    op_backdifference= 0x50000000,
    op_any= 0x7000000
  };
  op_type spatial_op;
  String tmp_value1,tmp_value2;
public:
  Item_func_spatial_operation(Item *a,Item *b, op_type sp_op):
    Item_geometry_func(a, b), spatial_op(sp_op)
  {}
  virtual ~Item_func_spatial_operation();
  String *val_str(String *) {return NULL;}
  const char *func_name() const;
  virtual inline void print(String *str, enum_query_type query_type)
  {
    Item_func::print(str, query_type);
  }
};


class Item_func_buffer: public Item_geometry_func
{
protected:
  String tmp_value;

public:
  Item_func_buffer(Item *obj, Item *distance):
    Item_geometry_func(obj, distance) {}
  const char *func_name() const { return "st_buffer"; }
  String *val_str(String *) {return NULL;}
};


class Item_func_isempty: public Item_bool_func
{
public:
  Item_func_isempty(Item *a): Item_bool_func(a) {}
  longlong val_int() {return 0;}
  optimize_type select_optimize() const { return OPTIMIZE_NONE; }
  const char *func_name() const { return "st_isempty"; }
};

class Item_func_issimple: public Item_bool_func
{
  String tmp;
public:
  Item_func_issimple(Item *a): Item_bool_func(a) {}
  longlong val_int() {return 0;}
  optimize_type select_optimize() const { return OPTIMIZE_NONE; }
  const char *func_name() const { return "st_issimple"; }
};

class Item_func_isclosed: public Item_bool_func
{
public:
  Item_func_isclosed(Item *a): Item_bool_func(a) {}
  longlong val_int() {return 0;}
  optimize_type select_optimize() const { return OPTIMIZE_NONE; }
  const char *func_name() const { return "st_isclosed"; }
};

class Item_func_dimension: public Item_int_func
{
  String value;
public:
  Item_func_dimension(Item *a): Item_int_func(a) {}
  longlong val_int() {return 0;}
  const char *func_name() const { return "st_dimension"; }
};

class Item_func_x: public Item_real_func
{
  String value;
public:
  Item_func_x(Item *a): Item_real_func(a) {}
  double val_real() {return 0.0;}
  const char *func_name() const { return "st_x"; }
};


class Item_func_y: public Item_real_func
{
  String value;
public:
  Item_func_y(Item *a): Item_real_func(a) {}
  double val_real() {return 0.0;}
  const char *func_name() const { return "st_y"; }
};


class Item_func_numgeometries: public Item_int_func
{
  String value;
public:
  Item_func_numgeometries(Item *a): Item_int_func(a) {}
  longlong val_int() {return 0;};
  const char *func_name() const { return "st_numgeometries"; }
};


class Item_func_numinteriorring: public Item_int_func
{
  String value;
public:
  Item_func_numinteriorring(Item *a): Item_int_func(a) {}
  longlong val_int() {return 0;}
  const char *func_name() const { return "st_numinteriorrings"; }
};


class Item_func_numpoints: public Item_int_func
{
  String value;
public:
  Item_func_numpoints(Item *a): Item_int_func(a) {}
  longlong val_int() {return 0;}
  const char *func_name() const { return "st_numpoints"; }
};


class Item_func_area: public Item_real_func
{
  String value;
public:
  Item_func_area(Item *a): Item_real_func(a) {}
  double val_real() {return 0.0;}
  const char *func_name() const { return "st_area"; }
};


class Item_func_glength: public Item_real_func
{
  String value;
public:
  Item_func_glength(Item *a): Item_real_func(a) {}
  double val_real() {return 0.0;}
  const char *func_name() const { return "st_length"; }
};


class Item_func_srid: public Item_int_func
{
  String value;
public:
  Item_func_srid(Item *a): Item_int_func(a) {}
  longlong val_int() {return 0;}
  const char *func_name() const { return "srid"; }
};


class Item_func_distance: public Item_real_func
{
  String tmp_value1;
  String tmp_value2;
public:
  Item_func_distance(Item *a, Item *b): Item_real_func(a, b) {}
  double val_real() {return 0.0;}
  const char *func_name() const { return "st_distance"; }
};


#ifndef DBUG_OFF
class Item_func_gis_debug: public Item_int_func
{
public:
  Item_func_gis_debug(Item *a) :Item_int_func(a) { null_value= false; }
  const char *func_name() const  { return "st_gis_debug"; }
  longlong val_int() {return 0;}
};
#endif


#define GEOM_NEW(thd, obj_constructor) new (thd->mem_root) obj_constructor

#else /*HAVE_SPATIAL*/

#define GEOM_NEW(thd, obj_constructor) NULL

#endif /*HAVE_SPATIAL*/
#endif /*ITEM_GEOFUNC_INCLUDED*/

