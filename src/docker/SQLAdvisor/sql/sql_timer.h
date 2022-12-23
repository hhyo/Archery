/* Copyright (c) 2012, Twitter, Inc. All rights reserved.

   This program is free software; you can redistribute it and/or modify
   it under the terms of the GNU General Public License as published by
   the Free Software Foundation; version 2 of the License.

   This program is distributed in the hope that it will be useful,
   but WITHOUT ANY WARRANTY; without even the implied warranty of
   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
   GNU General Public License for more details.

   You should have received a copy of the GNU General Public License along
   with this program; if not, write to the Free Software Foundation, Inc.,
   51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA. */

#ifndef SQL_TIMER_INCLUDED
#define SQL_TIMER_INCLUDED

class THD;
struct st_thd_timer;
typedef struct st_thd_timer thd_timer_t;

#ifdef HAVE_MY_TIMER

thd_timer_t *thd_timer_set(THD *, thd_timer_t *, unsigned long);
thd_timer_t *thd_timer_reset(thd_timer_t *);
void thd_timer_end(thd_timer_t *);

#else

static inline thd_timer_t *
thd_timer_set(THD *, thd_timer_t *, unsigned long)
{
  return NULL;
}

static inline thd_timer_t *
thd_timer_reset(thd_timer_t *)
{
  return NULL;
}

static inline void
thd_timer_end(thd_timer_t *)
{
}

#endif

#endif /* SQL_TIMER_INCLUDED */
