FILE(REMOVE_RECURSE
  "CMakeFiles/GenError"
  "../include/mysqld_error.h"
  "../sql/share/english/errmsg.sys"
)

# Per-language clean rules from dependency scanning.
FOREACH(lang)
  INCLUDE(CMakeFiles/GenError.dir/cmake_clean_${lang}.cmake OPTIONAL)
ENDFOREACH(lang)
