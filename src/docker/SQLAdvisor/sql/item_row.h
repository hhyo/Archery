#ifndef ITEM_ROW_INCLUDED
#define ITEM_ROW_INCLUDED

/* Copyright (c) 2002, 2011, Oracle and/or its affiliates. All rights reserved.

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

class Item_row: public Item
{
  Item **items;
  table_map used_tables_cache, not_null_tables_cache;
  uint arg_count;
  bool const_item_cache;
  bool with_null;
public:
  Item_row(List<Item> &);
  Item_row(Item *head, List<Item> &tail);
  Item_row(Item_row *item):
    Item(),
    items(item->items),
    used_tables_cache(item->used_tables_cache),
    not_null_tables_cache(0),
    arg_count(item->arg_count),
    const_item_cache(item->const_item_cache),
    with_null(0)
  {}

  enum Type type() const { return ROW_ITEM; };
  void illegal_method_call(const char *);
  bool is_null() { return null_value; }
  double val_real()
  {
    illegal_method_call((const char*)"val");
    return 0;
  };
  longlong val_int()
  {
    illegal_method_call((const char*)"val_int");
    return 0;
  };
  String *val_str(String *)
  {
    illegal_method_call((const char*)"val_str");
    return 0;
  };
  my_decimal *val_decimal(my_decimal *)
  {
    illegal_method_call((const char*)"val_decimal");
    return 0;
  };


  table_map used_tables() const { return used_tables_cache; };
  bool const_item() const { return const_item_cache; };
  enum Item_result result_type() const { return ROW_RESULT; }
  table_map not_null_tables() const { return not_null_tables_cache; }
  virtual void print(String *str, enum_query_type query_type);

  bool walk(Item_processor processor, bool walk_subquery, uchar *arg);

  uint cols() { return arg_count; }
  Item* element_index(uint i) { return items[i]; }
  Item** addr(uint i) { return items + i; }
  bool check_cols(uint c);
  bool null_inside() { return with_null; };
  void bring_value();
};

#endif /* ITEM_ROW_INCLUDED */
