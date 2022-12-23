FILE(REMOVE_RECURSE
  "CMakeFiles/GenServerSource"
  "sql_yacc.cc"
  "sql_yacc.h"
  "lex_hash.h"
)

# Per-language clean rules from dependency scanning.
FOREACH(lang)
  INCLUDE(CMakeFiles/GenServerSource.dir/cmake_clean_${lang}.cmake OPTIONAL)
ENDFOREACH(lang)
