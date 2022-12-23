/* Copyright (c) 2000, 2012, Oracle and/or its affiliates. All rights reserved.

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

/* Written by Sergei A. Golubchik, who has a shared copyright to this code */

/* some definitions for full-text indices */

/* #include "myisam.h" */

#ifndef _ft_global_h
#define _ft_global_h
#ifdef  __cplusplus
extern "C" {
#endif

#define HA_FT_MAXBYTELEN 254
#define HA_FT_MAXCHARLEN (HA_FT_MAXBYTELEN/3)

#define DEFAULT_FTB_SYNTAX "+ -><()~*:\"\"&|"

typedef struct st_ft_info FT_INFO;
struct _ft_vft
{
  int       (*read_next)(FT_INFO *, char *);
  float     (*find_relevance)(FT_INFO *, uchar *, uint);
  void      (*close_search)(FT_INFO *);
  float     (*get_relevance)(FT_INFO *);
  void      (*reinit_search)(FT_INFO *);
};

typedef struct st_ft_info_ext FT_INFO_EXT;
struct _ft_vft_ext
{
  uint      (*get_version)();        // Extended API version
  ulonglong (*get_flags)();
  ulonglong (*get_docid)(FT_INFO_EXT *);
  ulonglong (*count_matches)(FT_INFO_EXT *);
};

/* Flags for extended FT API */
#define FTS_ORDERED_RESULT                (LL(1) << 1)
#define FTS_DOCID_IN_RESULT               (LL(1) << 2)

#define FTS_DOC_ID_COL_NAME "FTS_DOC_ID"

#ifndef FT_CORE
struct st_ft_info
{
  struct _ft_vft *please; /* INTERCAL style :-) */
};

struct st_ft_info_ext
{
  struct _ft_vft     *please; /* INTERCAL style :-) */
  struct _ft_vft_ext *could_you;
};
#endif

#define FT_NL     0
#define FT_BOOL   1
#define FT_SORTED 2
#define FT_EXPAND 4   /* query expansion */

#ifdef  __cplusplus
}
#endif
#endif
