#ifndef _SQL_QUERY_STRIPC_COMMENTS_H_
#define _SQL_QUERY_STRIPC_COMMENTS_H_
#ifdef HAVE_QUERY_CACHE

// implemented in sql_cache.cc
class QueryStripComments
{
private:
  QueryStripComments(const QueryStripComments&);
  QueryStripComments& operator=(const QueryStripComments&);
public:
  QueryStripComments();
  ~QueryStripComments();
  void set(const char* a_query, uint a_query_length, uint a_additional_length);
  
  char* query()        { return buffer; }
  uint  query_length() { return length; }
private:
  void cleanup();
private:
  char* buffer;
  uint  length /*query length, not buffer length*/;
  uint  buffer_length;
};
class QueryStripComments_Backup
{
public:
  QueryStripComments_Backup(THD* a_thd,QueryStripComments* qsc);
  ~QueryStripComments_Backup();
private:
  THD*  thd;
  char* query;
  uint  length;
};

#endif // HAVE_QUERY_CACHE
#endif // _SQL_QUERY_STRIPC_COMMENTS_H_
