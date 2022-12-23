#define MYSQL_SERVER

#include <algorithm>
#include <limits>
#include <locale.h>
#include "sql/mysqld.h"
#include "sql/sql_class.h"
#include "sql/sql_lex.h"
#include "sql/sql_parse_index.h"
#include "sql/item.h"
#include "sql/table.h"
#include "mysql.h"
#include "glib.h"
#include "set"
#include "queue"
#include "map"
#include "string"

#define OFFSET 100000
#define RAND_ROWS 10000
#define CARDINALITY_LEVEL 30
#define SQL_COUNT 100
#define CHUNK_SIZE 10000
#define DBNAME "information_schema"
#define GROUT_NAME "sqladvisor"
#define SEP ';'
#define EXPLAIN_ROWS 8
#define INDEX_NON_UNIQUE 1
#define INDEX_KEY_NAME 2
#define INDEX_SEQ 3
#define INDEX_COLUMN_NAME 4
#define INDEX_CARDINALITY 6
#define SHOW_ROWS 4
#define AFFECT_ROWS 0

using std::set;
using std::queue;
using std::map;
using std::string;
using std::numeric_limits;

typedef struct _ConnectionOptions {
    //connection options
    char *configfile;
    char *username;
    char *password;
    int port;
    char *host;
    char *dbname;
    char **query;
    int verbose;
} ConnectionOptions;

struct compare {
    bool operator ()(string s1, string s2) {
        return s1 > s2;
    } ///自定义一个仿函数
};

typedef std::set<string, compare> _SET_C;

int ICP_VERSION = 1;
int TABLE_ELEMENT;
int STEP_CNT = 1; //整个过程中的第几步
TABLE_LIST * DRIVED_TABLE;
st_select_lex * current_lex;
set<TABLE_LIST *> TABLE_DRIVERD;
ConnectionOptions options;


void ConnectionOptionsInit(ConnectionOptions *options);
void ConnectionOptionsFree(ConnectionOptions *options);
void print_index();
void print_sql(char * sql);
void final_table_drived();
void mysql_sql_parse_admin();
void mysql_sql_parse(Item * item);
void finish_with_error(MYSQL *con);
void table_index_add_condition_field();
void mysql_sql_parse_join(Item *join_condition);
void mysql_sql_parse_join(TABLE_LIST *join_table);
void find_join_elements_new(TABLE_LIST *join_table);
void mysql_sql_parse_index(Field_Description *field_desp);
void mysql_sql_parse_group_order_add(TABLE_LIST *table,
        SQL_I_List<ORDER> order_list);
void mysql_sql_parse_field(Item_field *field,
        Item_func::Functype func_item_type, const char * field_print);

uint find_join_elements(TABLE_LIST *join_table);
uint get_join_table_result_set(TABLE_LIST *table);
int mysql_sql_parse_field_cardinality(Item_field *field,
        const char * field_print);
int mysql_sql_parse_field_cardinality_new(Item_field *field,
        const char * field_print);

TABLE_LIST * mysql_sql_parse_group();
TABLE_LIST * mysql_sql_parse_order();
TABLE_LIST * find_table(Item_field * field);
TABLE_LIST * find_table(const char *table_name);
TABLE_LIST * find_table_by_field(const char * field_name);


bool sql_execute(LEX *lex);
bool is_like_pre(char * field_ptr);
bool is_not_tmp_table(TABLE_LIST * table);
bool isPrimary(const char *field_name, char *table_name);
bool is_this_table(const char * field_name, char * table_name);
POSSBILE_INDEX * find_best_index(char *tablename, char *dbname,
        const char *field_name);
_SET_C get_key_name(const char * field_name, char * table_name,
        int seq_in_index);

void ConnectionOptionsInit(ConnectionOptions *options) {
    if (options == NULL) {
        return;
    }
    options->configfile = NULL;
    options->username = NULL;
    options->password = NULL;
    options->port = 3306;
    options->host = NULL;
    options->dbname = NULL;
    options->verbose = 0;
}

void ConnectionOptionsFree(ConnectionOptions *options) {
    if (options == NULL) {
        return;
    }
    if (options->configfile != NULL) {
        g_free(options->configfile);
    }
    if (options->username != NULL) {
        g_free(options->username);
    }
    if (options->password != NULL) {
        g_free(options->password);
    }
    if (options->host != NULL) {
        g_free(options->host);
    }
    if (options->dbname != NULL) {
        g_free(options->dbname);
    }
    g_strfreev(options->query);
}

void mysql_sql_parse_join(TABLE_LIST *join_table) {
    List_iterator<TABLE_LIST> li_join_list(join_table->nested_join->join_list);
    TABLE_LIST * table_right = li_join_list++;
    TABLE_LIST * table_left = li_join_list++;
    List_iterator<String> using_fields(*join_table->join_using_fields);
    String *using_field;
    while ((using_field = using_fields++)) {
        if (options.verbose)
            sql_print_information("第%d步：开始解析join using条件:%s \n", STEP_CNT++,
                    using_field->ptr());
        Item_field * field_cond_left = new Item_field(NULL, NULL,
                table_left->table_name, using_field->ptr());
        Item_field * field_cond_right = new Item_field(NULL, NULL,
                table_right->table_name, using_field->ptr());

        JOIN_CONDITION * right_table_join = new JOIN_CONDITION(table_left);
        JOIN_CONDITION * left_table_join = new JOIN_CONDITION(table_right);

        right_table_join->get_join_field()->push_back(field_cond_left);
        left_table_join->get_join_field()->push_back(field_cond_right);

        table_right->get_join_condition()->push_back(right_table_join);
        table_left->get_join_condition()->push_back(left_table_join);
    }
}

void mysql_sql_parse_join(Item *join_condition) {
    Item::Type type = join_condition->type();
    if (type == Item::FUNC_ITEM) {
        Item_func *join_func = (Item_func*) join_condition;
        if (join_func->argument_count() == 2) {
            Item **item_begin = join_func->arguments();
            Item **item_end = (join_func->arguments())
                    + join_func->argument_count() - 1;
            if ((*item_begin)->type() == Item::FIELD_ITEM
                    && (*item_end)->type() == Item::FIELD_ITEM) {
                if (options.verbose)
                    sql_print_information("第%d步：开始解析join on条件:%s=%s \n",
                            STEP_CNT++,
                            ((Item_field *) (*item_begin))->full_name(),
                            ((Item_field *) (*item_end))->full_name());

                TABLE_LIST * item_begin_table = find_table(
                        ((Item_field *) (*item_begin))->table_name);
                TABLE_LIST * item_end_table = find_table(
                        ((Item_field *) (*item_end))->table_name);
		if (item_begin_table && item_end_table){
		    JOIN_CONDITION * begin_join = new JOIN_CONDITION(item_end_table);
		    JOIN_CONDITION * end_join = new JOIN_CONDITION(item_begin_table);

                    begin_join->get_join_field()->push_back((Item_field *) (*item_end));
		    end_join->get_join_field()->push_back((Item_field *) (*item_begin));

		    item_begin_table->get_join_condition()->push_back(begin_join);
		    item_end_table->get_join_condition()->push_back(end_join);
		}
            }
        }
    } else if (type == Item::COND_ITEM) {
        mysql_sql_parse(join_condition); //当join条件中包含xx = ? 这种情况
    }
}

void find_join_elements_new(TABLE_LIST *join_table) {
    if (join_table->nested_join != NULL) {
        List_iterator<TABLE_LIST> li_join_list(
                join_table->nested_join->join_list);
        TABLE_LIST * table_right = li_join_list++;
        TABLE_LIST * table_left = li_join_list++;
	if ( ! is_not_tmp_table(table_right) || ! is_not_tmp_table(table_left))	{
	    return; //临时表不做处理
	}

        //当join条件是using on时,join条件存在nest_join_table中
        if (join_table->join_using_fields != NULL
                && join_table->is_natural_join) {
            if (join_table->nested_join->join_list.elements == 2) {
                mysql_sql_parse_join(join_table);
            }
        }
        //right join会转换成left join. 所以不判断right join
        if (table_right->outer_join == JOIN_TYPE_LEFT || table_right->straight
                || table_left->outer_join == JOIN_TYPE_LEFT
                || table_left->straight) {
            //当左节点是叶子节点,右节点是非叶子节点时,即使是left join, 也是以右节点为驱动表
            if (table_right->nested_join != NULL
                    && table_left->nested_join == NULL) {
                find_join_elements_new(table_right);
                if (table_left->join_cond())
                    mysql_sql_parse_join(table_left->join_cond());
            } else {
                find_join_elements_new(table_left);
                if (table_right->join_cond())
                    mysql_sql_parse_join(table_right->join_cond());
            }
        } else {
            find_join_elements_new(table_right);
            find_join_elements_new(table_left);
        }
    } else {
        //获取join条件,nest_join_table会为空,条件只保存在叶子节点中。如果左右都是叶子节点,一般只会存在右节点中
        if (join_table->join_cond()) {
            mysql_sql_parse_join(join_table->join_cond());
        }
        if (TABLE_DRIVERD.count(join_table) == 0) {
            TABLE_DRIVERD.insert(join_table);
        }
    }
}

bool sql_execute(LEX *lex) {
    enum_sql_command command_type = lex->sql_command;
    if (command_type == SQLCOM_INSERT) {
        return false;
    } else {
        return true;
    }

}

void print_sql(char * sql) {
    if (options.verbose)
        sql_print_information("%s \n", sql);
}

uint get_join_table_result_set(TABLE_LIST *table) {
    MYSQL *con = mysql_init(NULL);
    if (con == NULL) {
        finish_with_error(con);
    }

    if (mysql_real_connect(con, options.host, options.username,
            options.password, options.dbname, options.port, NULL, 0) == NULL) {
        finish_with_error(con);
    }

    mysql_query(con, "set names utf8");

    uint result_set_count;
    GString *cardinality_sql = g_string_new(NULL);
    if (table->index_field_head != NULL) {
        if (table->index_field_head->index_field->field_name->table_name
                == NULL) {
            g_string_sprintf(cardinality_sql,
                    "explain select * from %s where %s", table->table_name,
                    table->index_field_head->index_field->field_print);
        } else {
            g_string_sprintf(cardinality_sql,
                    "explain select * from %s as %s where %s",
                    table->table_name,
                    table->index_field_head->index_field->field_name->table_name,
                    table->index_field_head->index_field->field_print);
        }
    } else {
        g_string_sprintf(cardinality_sql, "explain select * from %s",
                table->table_name);
    }

    print_sql(cardinality_sql->str);

    if (mysql_query(con, cardinality_sql->str)) {
        finish_with_error(con);
    }

    MYSQL_RES *result = mysql_store_result(con);
    if (result == NULL) {
        finish_with_error(con);
    }

    int num_fields = mysql_num_fields(result);

    MYSQL_ROW row;

    if ((row = mysql_fetch_row(result))) {
        result_set_count = atoi(row[EXPLAIN_ROWS]);
    }
    g_string_free(cardinality_sql, TRUE);
    mysql_free_result(result);
    mysql_close(con);
    return result_set_count;
}

void final_table_drived() {
    if (options.verbose)
        sql_print_information("第%d步：开始选择驱动表,一共有%d个候选驱动表 \n", STEP_CNT++,
                TABLE_DRIVERD.size());
    int small_result_set = numeric_limits<int>::max();
    if (!TABLE_DRIVERD.empty()) {
        set<TABLE_LIST *>::iterator drived_it;
        for (drived_it = TABLE_DRIVERD.begin();
                drived_it != TABLE_DRIVERD.end(); drived_it++) {
            int result_set = get_join_table_result_set(*drived_it);
            if (options.verbose)
                sql_print_information("第%d步：候选驱动表%s的结果集行数为:%d \n", STEP_CNT++,
                        (*drived_it)->table_name, result_set);
            if (result_set < small_result_set) {
                DRIVED_TABLE = *drived_it;
                small_result_set = result_set;
            }
        }
	if (DRIVED_TABLE != NULL) {
	    DRIVED_TABLE->is_table_driverd = true;
	    if (options.verbose)
		sql_print_information("第%d步：选择表%s为驱动表 \n", STEP_CNT++,DRIVED_TABLE->table_name);
	} else {
	    sql_print_information("第%d步：侯选驱动表个数:%d,但无法确定驱动表 \n", STEP_CNT++,TABLE_DRIVERD.size());
	    exit(-1);
	}
    }	
}

void table_index_add_condition_field() {
    set<TABLE_LIST *> deployed_table_set;
    queue<TABLE_LIST *> to_deployed_table_queue;
    to_deployed_table_queue.push(DRIVED_TABLE);
    deployed_table_set.insert(DRIVED_TABLE);
    TABLE_LIST * deploy_table;
    while (!to_deployed_table_queue.empty()) {
        deploy_table = to_deployed_table_queue.front();
        to_deployed_table_queue.pop();

        List<JOIN_CONDITION> * cond_list = deploy_table->get_join_condition();
        List_iterator<JOIN_CONDITION> cond_li(*cond_list);
        JOIN_CONDITION *join_cond;
        while ((join_cond = cond_li++)) {
            TABLE_LIST * deploy_table = join_cond->join_table;
            if (deployed_table_set.count(deploy_table) > 0) {
                continue;
            }
            List_iterator<Item_field> field_li(*(join_cond->get_join_field()));
            Item_field *join_field;
            while ((join_field = field_li++)) {
                Field_Description * join_field_desc = new Field_Description(
                        join_field);
                INDEX_FIELD * index_head = new INDEX_FIELD(join_field_desc);
                INDEX_FIELD * head = deploy_table->index_field_head;
                if (head == NULL) {
                    deploy_table->index_field_head = index_head;
                } else {
                    index_head->next_field = head;
                    deploy_table->index_field_head = index_head;
                }
            }
            deployed_table_set.insert(deploy_table);
            to_deployed_table_queue.push(deploy_table);
        }
    }
}

void finish_with_error(MYSQL *con) {
    if (options.verbose)
        sql_print_information("第%d步：SQLAdvisor结束！错误日志:%s \n", STEP_CNT++,
                mysql_error(con));
    if (con != NULL)
        mysql_close(con);
    exit(-1);
}

POSSBILE_INDEX * find_best_index(char *tablename, char *dbname,
        const char *field_name) {
    MYSQL *con = mysql_init(NULL);
    if (con == NULL || dbname == NULL || tablename == NULL) {
        finish_with_error(con);
    }

    if (mysql_real_connect(con, options.host, options.username,
            options.password, dbname, options.port, NULL, 0) == NULL) {
        finish_with_error(con);
    }

    mysql_query(con, "set names utf8");
    GString *table_indexes = g_string_new(NULL);
    g_string_sprintf(table_indexes, "show index from %s", tablename);
    print_sql(table_indexes->str);

    if (mysql_query(con, table_indexes->str)) {
        finish_with_error(con);
    }

    MYSQL_RES *result = mysql_store_result(con);
    if (result == NULL) {
        finish_with_error(con);
    }
    g_string_free(table_indexes, TRUE);

    map<string, POSSBILE_INDEX *> possible_index_map;

    MYSQL_ROW row;

    char * index_name = NULL;

    while ((row = mysql_fetch_row(result))) {
        if (strcasecmp(row[INDEX_KEY_NAME], "PRIMARY") == 0) {
            if(index_name) free(index_name);
            index_name = strdup("PRIMARY");
        } else if (atoi(row[INDEX_NON_UNIQUE]) == 0) {
	    if (index_name == NULL || strcasecmp(index_name, "PRIMARY") != 0)
            if(index_name) free(index_name);
		    index_name = strdup(row[INDEX_KEY_NAME]);
        } else if (atoi(row[INDEX_SEQ]) == 1
                && strcasecmp(row[INDEX_COLUMN_NAME], field_name) == 0) {
			//if(index_name) free(index_name);
            // index_name = strdup(row[INDEX_KEY_NAME]);
            continue;
        }

        map<string, POSSBILE_INDEX *>::iterator l_it = possible_index_map.find(
                string(row[INDEX_KEY_NAME]));
        if (l_it == possible_index_map.end()) {
            POSSBILE_INDEX * poss_index = new POSSBILE_INDEX(
                    strdup(row[INDEX_KEY_NAME]));
            poss_index->cardinality =
                    row[INDEX_CARDINALITY] == NULL ?
                            1 : atoi(row[INDEX_CARDINALITY]); //row[INDEX_CARDINALITY]是cardinality,有的时候cardinality列显示的是NULL
            poss_index->get_index_columns()->push_back(
                    strdup(row[INDEX_COLUMN_NAME])); // 后面会对result进行释放,所以需要strdup
            possible_index_map[string(strdup(row[INDEX_KEY_NAME]))] =
                    poss_index;
        } else {
            POSSBILE_INDEX * poss_index = l_it->second;
            poss_index->cardinality = poss_index->cardinality
                    * (row[INDEX_CARDINALITY] == NULL ?
                            1 : atoi(row[INDEX_CARDINALITY]));
            poss_index->get_index_columns()->push_back(
                    strdup(row[INDEX_COLUMN_NAME]));
        }
    }
    mysql_free_result(result);
    mysql_close(con);

    POSSBILE_INDEX * best_index = NULL;
    if (index_name == NULL) {
        map<string, POSSBILE_INDEX *>::iterator iter;
        for (iter = possible_index_map.begin();
                iter != possible_index_map.end(); iter++) {
            POSSBILE_INDEX * poss_index = iter->second;
            if (best_index == NULL) {
                best_index = poss_index;
            } else {
                best_index =
                        best_index->cardinality > poss_index->cardinality ?
                                best_index : poss_index;
            }
        }
    } else {
        map<string, POSSBILE_INDEX *>::iterator lit = possible_index_map.find(
                string(index_name));
        best_index = lit->second;
    }
    if (best_index == NULL) {
        if (options.verbose)
            sql_print_information("第%d步：SQLAdvisor结束！表中没有任何索引 \n", STEP_CNT++);
        if(index_name) free(index_name);
        exit(-1);
    }
    if(index_name) free(index_name);
    return best_index;
}

int mysql_sql_parse_field_cardinality_new(Item_field *field,
        const char * field_print) {
    char *dbname, *tablename;
    TABLE_LIST * table = find_table(field);
    if (table) {
	tablename = table->table_name;
        dbname = table->db;
    } else
        return 0;
   
    POSSBILE_INDEX * best_index = find_best_index(tablename, dbname,
            field->full_name());

    MYSQL *con = mysql_init(NULL);
    if (con == NULL || dbname == NULL || tablename == NULL) {
        finish_with_error(con);
    }
 
    if (mysql_real_connect(con, options.host, options.username,
            options.password, dbname, options.port, NULL, 0) == NULL) {
        finish_with_error(con);
    }

    mysql_query(con, "set names utf8"); //指定字符集,确保能够执行含中文的SQL
    GString *table_count_sql = g_string_new(NULL);
    ulonglong table_count;
    g_string_sprintf(table_count_sql, "show table status like '%s'", tablename);
    print_sql(table_count_sql->str);
    if (mysql_query(con, table_count_sql->str)) {
        finish_with_error(con);
    } 

    g_string_free(table_count_sql, TRUE);

    MYSQL_RES *result = mysql_store_result(con);
    if (result == NULL) {
        finish_with_error(con);
    }

    int num_fields = mysql_num_fields(result);

    MYSQL_ROW row;

    if ((row = mysql_fetch_row(result))) {
        table_count = atoi(row[SHOW_ROWS]);
    }

    uint offset = (table_count / 2) > OFFSET ? OFFSET : (table_count / 2);
    uint rand_rows =
            (table_count / 2) > RAND_ROWS ? RAND_ROWS : (table_count / 2);

    GString *order_sql = g_string_new(NULL);
    char * index_column = NULL;
    int index_columns_size = best_index->get_index_columns()->elements;
    List_iterator<char> index_column_li(*(best_index->get_index_columns()));
    while ((index_column = index_column_li++)) {
        g_string_append(order_sql, index_column);
        g_string_append(order_sql, " DESC");
        index_columns_size--;
        if (index_columns_size > 0) {
            g_string_append(order_sql, ",");
        }
        index_column = NULL;
    }

    uint cardinality = 0;
    GString *cardinality_sql = g_string_new(NULL);
    const char * orig_table_name =
            field->table_name == NULL ? tablename : field->table_name;

    g_string_sprintf(cardinality_sql,
            "select count(*) from ( select `%s` from `%s` FORCE INDEX( %s ) order by %s limit %d) `%s` where %s ",
            field->field_name, tablename, best_index->index_name.c_str(),
            order_sql->str, rand_rows, orig_table_name, field_print);

    print_sql(cardinality_sql->str);
    if (mysql_query(con, cardinality_sql->str)) {
        finish_with_error(con);
    }

    result = mysql_store_result(con);
    if (result == NULL) {
        finish_with_error(con);
    }

    num_fields = mysql_num_fields(result);

    if ((row = mysql_fetch_row(result))) {
        cardinality =
                atoi(row[AFFECT_ROWS]) == 0 ?
                        rand_rows : rand_rows / atoi(row[AFFECT_ROWS]);
    }
    mysql_free_result(result);
    mysql_close(con);
    if (options.verbose)
        sql_print_information(
                "第%d步：表%s的行数:%d,limit行数:%d,得到where条件中%s的选择度:%d \n", STEP_CNT++,
                tablename, table_count, rand_rows, field_print, cardinality);

    g_string_free(order_sql, TRUE);
    g_string_free(cardinality_sql, TRUE);
    return cardinality;
}

TABLE_LIST * find_table(const char *table_name) {
    SQL_I_List<TABLE_LIST> table_list = current_lex->table_list;
    TABLE_LIST *table = table_list.first;
    while (table != NULL) {
	if (is_not_tmp_table(table)){
	    if (strcasecmp(table->table_name, table_name) == 0 || strcasecmp(table->alias, table_name) == 0) {
		return table;
	    }
	}
        table = table->next_local;
    }
    return NULL;
}

//增加这个函数的目的是因为有的时候field本身table_name的值为空,一般这种情况为where column xxx ,而table_name不为空的情况则是where tbname.column xxxxx
TABLE_LIST * find_table(Item_field * field) {
    if (field->table_name == NULL && field->db_name == NULL) {
        if (current_lex->table_list.elements > 1) {
            return find_table_by_field(field->field_name);
        } else {
            if(is_not_tmp_table(current_lex->table_list.first)){
		return current_lex->table_list.first;
	    }else{
		return NULL;
	    }
        }
    } else {
        return find_table(field->table_name);
    }
}

//当SQL中有多个表,但是字段中没有表名,则进行查找看这个字段是哪一个表的。如果一个字段同时存在于多个表,则返回NULL
TABLE_LIST * find_table_by_field(const char * field_name) {
    if (options.verbose)
        sql_print_information("第%d步：开始解析字段%s是哪一张表 \n", STEP_CNT++, field_name);
    SQL_I_List<TABLE_LIST> table_list = current_lex->table_list;
    TABLE_LIST *table = table_list.first;
    bool has_table = false;
    TABLE_LIST * this_table = NULL;
    while (table != NULL) {
        if (!has_table && is_this_table(field_name, table->table_name)) {
            this_table = table;
            has_table = true;
        } else if (has_table && is_this_table(field_name, table->table_name)) {
            if (options.verbose)
                sql_print_information("第%d步：字段%s存在多个表中 \n", STEP_CNT++,
                        field_name);
            return NULL;
        }
        table = table->next_local;
    }
    if (options.verbose && this_table)
        sql_print_information("第%d步：确定字段%s在表%s中 \n", STEP_CNT++, field_name,
                this_table->table_name);
    else if (options.verbose && !this_table)
        sql_print_information("第%d步：字段%s不存在任何一张表中 \n", STEP_CNT++, field_name);
    return this_table;
}

bool is_this_table(const char * field_name, char * table_name) {
    MYSQL *con = mysql_init(NULL);
    if (con == NULL || table_name == NULL || field_name == NULL) {
        finish_with_error(con);
    }

    if (mysql_real_connect(con, options.host, options.username,
            options.password, DBNAME, options.port, NULL, 0) == NULL) {
        finish_with_error(con);
    }
    mysql_query(con, "set names utf8"); //指定字符集,确保能够执行含中文的SQL

    GString *table_count_sql = g_string_new(NULL);
    ulonglong table_count;
    g_string_sprintf(table_count_sql,
            "select count(*) from columns where TABLE_NAME = '%s' and COLUMN_NAME = '%s'",
            table_name, field_name);

    print_sql(table_count_sql->str);

    if (mysql_query(con, table_count_sql->str)) {
        finish_with_error(con);
    }

    MYSQL_RES *result = mysql_store_result(con);
    if (result == NULL) {
        finish_with_error(con);
    }

    int num_fields = mysql_num_fields(result);

    MYSQL_ROW row;

    if ((row = mysql_fetch_row(result))) {
        table_count = atoi(row[AFFECT_ROWS]);
    }
    g_string_free(table_count_sql, TRUE);
    mysql_free_result(result);
    mysql_close(con);

    if (table_count == 0)
        return false;
    else
        return true;
}

void mysql_sql_parse_index(Field_Description *field_desp) {
    INDEX_FIELD * field_index = new INDEX_FIELD(field_desp);
    TABLE_LIST * table = find_table(field_desp->field_name);
    if (table->index_field_head == NULL) {
        table->index_field_head = field_index;
    } else {
        INDEX_FIELD *index = table->index_field_head;
        INDEX_FIELD *prev = NULL;
        while (index != NULL) {
            if (strcasecmp(index->index_field->field_name->field_name,
                    field_index->index_field->field_name->field_name) == 0)
                break; //如果已存在相同字段,则直接退出
            if (index->index_field->operator_type == Item_func::EQ_FUNC) {
                if (field_desp->operator_type == Item_func::EQ_FUNC
                        && index->index_field->cardinality
                                < field_desp->cardinality) {
                    if (prev == NULL)
                        table->index_field_head = field_index;
                    else
                        prev->next_field = field_index;
                    field_index->next_field = index;
                    break;
                } else if (index->next_field == NULL) {
                    index->next_field = field_index;
                    break;
                }
            } else {
                if (field_desp->operator_type == Item_func::EQ_FUNC) {
                    if (prev == NULL)
                        table->index_field_head = field_index;
                    else
                        prev->next_field = field_index;
                    field_index->next_field = index;
                    break;
                } else if (index->index_field->cardinality
                        < field_desp->cardinality) {
                    prev->next_field = field_index;
                    if (ICP_VERSION == 1)
                        field_index->next_field = index;
                    break;
                }
            }
            prev = index;
            index = index->next_field;
        }
    }
}

void mysql_sql_parse_field(Item_field *field,
        Item_func::Functype func_item_type, const char * field_print) {
//    int cardinality = mysql_sql_parse_field_cardinality(field,field_print);
    int cardinality = mysql_sql_parse_field_cardinality_new(field, field_print);
    if (cardinality > CARDINALITY_LEVEL) {
        Field_Description * field_desp = new Field_Description(field,
                cardinality, func_item_type, field_print);
        mysql_sql_parse_index(field_desp);
    }
}

//如果SQL中有group by, 判断group by 的条件是哪一张表的。当group by 来自于多张表,则不做处理。只有当group by 的条件都来自于同一张表,或者这张表是驱动表则将返回这张表,否则返回NULL
TABLE_LIST* mysql_sql_parse_group() {
    TABLE_LIST * table = NULL;
    bool is_only_one_table = true;
    SQL_I_List<ORDER> group_list = current_lex->group_list;
    if (group_list.elements > 0) {
        if (options.verbose)
            sql_print_information("第%d步：开始解析group by 条件 \n", STEP_CNT++);
        ORDER *order_field = group_list.first;
        while (order_field != NULL) {
            if (order_field->item_ptr->type() == Item::FIELD_ITEM) {
                TABLE_LIST * tbname2 = find_table(
                        (Item_field *) (order_field->item_ptr));
                if (tbname2 == NULL) {
                    is_only_one_table = false;
                    break;
                } else {
                    if (table == NULL) {
                        table = tbname2;
                    } else if (table->table_name != tbname2->table_name) {
                        is_only_one_table = false;
                        break;
                    }
                }
            }
            order_field = order_field->next;
        }

        if (is_only_one_table) {
            if (TABLE_ELEMENT == 1 || table->is_table_driverd) {
                return table;
            }
        }
    }
    return NULL;
}

//同理,同时判断order by 表是否相同,还要判断升降序是否一致
TABLE_LIST* mysql_sql_parse_order() {
    TABLE_LIST * table = NULL;
    ORDER::enum_order dire;
    bool is_only_one_table = true;
    SQL_I_List<ORDER> order_list = current_lex->order_list;
    int order_elemnts = order_list.elements;
    int order_elment_i = 0;
    if (order_elemnts > 0) {
        if (options.verbose)
            sql_print_information("第%d步：开始解析order by 条件 \n", STEP_CNT++);
        ORDER *order_field = order_list.first;
        while (order_field != NULL) {
            order_elment_i++;
            if (order_field->item_ptr->type() == Item::FIELD_ITEM) {
                TABLE_LIST * tbname2 = find_table((Item_field *) (order_field->item_ptr));
		if (tbname2 == NULL) {
		    is_only_one_table = false;
		    break;
		}
                if (isPrimary(((Item_field *) (order_field->item_ptr))->field_name,tbname2->table_name)) {
                    if (order_elment_i == order_elemnts) //当order by c1,c2...中包含主键时,只有当主键在最后位置则忽略,否则无法使用order by索引
                        break;
                    else if (options.verbose)
                        sql_print_information("第%d步：字段%s是主键同时不在order by列表末尾,放弃处理order by条件 \n",STEP_CNT++,((Item_field *) (order_field->item_ptr))->field_name);
                    return NULL;
                }
                ORDER::enum_order dire2 = order_field->direction;
                if (table == NULL) {
                    table = tbname2;
                    dire = dire2;
                } else if (table->table_name != tbname2->table_name || dire != dire2) {
                    is_only_one_table = false;
                    break;
                }
	    }
            order_field = order_field->next;
        }

        if (is_only_one_table && table) {
            if (TABLE_ELEMENT == 1 || table->is_table_driverd) {
                return table;
            }
        }
    }
    return NULL;
}

void mysql_sql_parse_group_order_add(TABLE_LIST *table,
        SQL_I_List<ORDER> order_list) {
    INDEX_FIELD * index_head = NULL;
    INDEX_FIELD * index_prev = NULL;
    ORDER * order_field = order_list.first;
    while (order_field != NULL) {
        if (order_field->item_ptr->type() == Item::FIELD_ITEM) {
            if (isPrimary(((Item_field *) (order_field->item_ptr))->field_name,
                    table->table_name)) {
                if (options.verbose)
                    sql_print_information("第%d步：字段%s是主键并且在列表末尾,忽略不添加 \n",
                            STEP_CNT++,
                            ((Item_field *) (order_field->item_ptr))->field_name);
                break; //当字段是主键时,则一定是在order by| group by  列表末尾,直接忽略。
            }
            Field_Description * field_index = new Field_Description(
                    (Item_field *) order_field->item_ptr);
            INDEX_FIELD * index_field = new INDEX_FIELD(field_index);
            if (index_head == NULL) {
                index_head = index_field;
                index_prev = index_head;
            } else {
                index_prev->next_field = index_field;
                index_prev = index_prev->next_field;
            }
        }
        order_field = order_field->next;
    }
    if (index_head != NULL) {
        INDEX_FIELD *index = table->index_field_head;
        if (index == NULL
                || index->index_field->operator_type != Item_func::EQ_FUNC) {
            table->index_field_head = index_head;
        } else {
            INDEX_FIELD *PREV = NULL;
            while (index != NULL) {
                if (strcasecmp(index->index_field->field_name->field_name,
                        index_head->index_field->field_name->field_name) == 0) { //如果存在跟order by条件中相同字段,则直接将order by挂在后面。
                    if (PREV == NULL) {
                        table->index_field_head = index_head;
                    } else {
                        PREV->next_field = index_head;
                    }
                    break;
                }
                if (index->index_field->operator_type == Item_func::EQ_FUNC) {
                    if (index->next_field == NULL) {
                        index->next_field = index_head;
                        break;
                    } else {
                        PREV = index;
                        index = index->next_field;
                    }
                } else {
                    if (PREV == NULL) {
                        table->index_field_head = index_head;
                    } else {
                        PREV->next_field = index_head;
                    }
//		    index_prev->next_field = index; // Do not think about ICP
//		    index = NULL;
                    break;
                }
            }
        }
    }
}

void print_index() {
    SQL_I_List<TABLE_LIST> table_list = current_lex->table_list;
    TABLE_LIST *table = table_list.first;
    while (table != NULL) {
	if( ! is_not_tmp_table(table)){
	    table = table->next_local;
	    continue;
	}
        GString *create_index_sql = g_string_new(NULL);
        GString *index_field = g_string_new(NULL);
        GString *index_name = g_string_new(NULL);
        _SET_C s3;
        int seq_in_index = 1;
        bool is_repeat_index = true;
        INDEX_FIELD * index = table->index_field_head;

        //如果索引列首列是主键，则直接跳过
        if (index != NULL
                && isPrimary(index->index_field->field_name->field_name,
                        table->table_name)) {
            if (options.verbose)
                sql_print_information("第%d步：表%s 经过运算得到的索引列首列是主键,直接放弃,没有优化建议 \n",
                        STEP_CNT++, table->table_name);
            table = table->next_local;
            continue;
        }
        while (index != NULL) {
            //如果索引列表中含有主键，则直接跳过不处理
            if (!isPrimary(index->index_field->field_name->field_name,
                    table->table_name)) {
                if (index->next_field == NULL) {
                    g_string_append(index_field,
                            index->index_field->field_name->field_name);
                    g_string_append(index_name,
                            index->index_field->field_name->field_name);
                } else {
                    g_string_append(index_field,
                            index->index_field->field_name->field_name);
                    g_string_append(index_name,
                            index->index_field->field_name->field_name);
                    g_string_append(index_field, ",");
                    g_string_append(index_name, "_");
                }
                if (is_repeat_index) {
                    _SET_C s2 = get_key_name(
                            index->index_field->field_name->field_name,
                            table->table_name, seq_in_index);
                    if (seq_in_index == 1) {
                        s3 = s2;
                    } else {
                        string str[table_list.elements];
                        string *end = std::set_intersection(s3.begin(),
                                s3.end(), s2.begin(), s2.end(), str, compare());
                        if (str == end) {
                            s3.clear();
                            is_repeat_index = false;
                        } else {
                            s3.clear();
                            string *first = str;
                            while (first < end) {
                                s3.insert(*first);
                                first++;
                            }
                        }
                    }
                    seq_in_index++;
                }
            }

            if (index->index_field->operator_type == Item_func::EQ_FUNC
                    || index->index_field->operator_type
                            == Item_func::UNKNOWN_FUNC || ICP_VERSION == 1) {
                index = index->next_field;
                continue;
            } else {
                break;
            }
        }
        if (table->index_field_head != NULL) {
            if (s3.size() == 0) {
                if (options.verbose)
                    sql_print_information("第%d步：开始输出表%s索引优化建议: \n", STEP_CNT++,
                            table->table_name);
                g_string_sprintf(create_index_sql,
                        "alter table %s add index idx_%s(%s)",
                        table->table_name, index_name->str, index_field->str);
                sql_print_information("Create_Index_SQL：%s \n",
                        create_index_sql->str);
            } else if (options.verbose) {
                sql_print_information("第%d步：索引(%s)已存在 \n", STEP_CNT++,
                        index_field->str);
            }
        } else {
            if (options.verbose)
                sql_print_information("第%d步：表%s 的SQL太逆天,没有优化建议 \n", STEP_CNT++,
                        table->table_name);
        }
        table = table->next_local;
	g_string_free (create_index_sql, TRUE);
	g_string_free (index_field, TRUE);
	g_string_free (index_name, TRUE);
    }
}

_SET_C get_key_name(const char *field_name, char *table_name,
        int seq_in_index) {
    if (options.verbose)
        sql_print_information(
                "第%d步：开始验证表中是否已存在相关索引。表名:%s, 字段名:%s, 在索引中的位置:%d \n", STEP_CNT++,
                table_name, field_name, seq_in_index);
    MYSQL *conn = mysql_init(NULL);
    if (conn == NULL || table_name == NULL || field_name == NULL) {
        finish_with_error(conn);
    }
    if (mysql_real_connect(conn, options.host, options.username,
            options.password, options.dbname, options.port, NULL, 0) == NULL) {
        finish_with_error(conn);
    }
    mysql_query(conn, "set names utf8");
    GString *table_exist_index_sql = g_string_new(NULL);
    g_string_sprintf(table_exist_index_sql,
            "show index from %s where Column_name ='%s' and Seq_in_index =%d",
            table_name, field_name, seq_in_index);
    print_sql(table_exist_index_sql->str);
    if (mysql_query(conn, table_exist_index_sql->str)) {
        finish_with_error(conn);
    }
    MYSQL_RES *result = mysql_store_result(conn);
    if (result == NULL) {
        finish_with_error(conn);
    }
    MYSQL_ROW row;
    _SET_C s_key;
    int num_fields = mysql_num_fields(result);
    while ((row = mysql_fetch_row(result))) {
        s_key.insert(strdup(row[INDEX_KEY_NAME]));
    }
    g_string_free(table_exist_index_sql, TRUE);
    mysql_free_result(result);
    mysql_close(conn);
    return s_key;
}

bool isPrimary(const char *field_name, char *table_name) {
    if (options.verbose)
        sql_print_information("第%d步：开始验证 字段%s是不是主键。表名:%s \n", STEP_CNT++,
                field_name, table_name);
    MYSQL *conn = mysql_init(NULL);
    if (conn == NULL || table_name == NULL || field_name == NULL) {
        finish_with_error(conn);
    }
    if (mysql_real_connect(conn, options.host, options.username,
            options.password, options.dbname, options.port, NULL, 0) == NULL) {
        finish_with_error(conn);
    }
    mysql_query(conn, "set names utf8");
    GString *table_exist_index_sql = g_string_new(NULL);
    g_string_sprintf(table_exist_index_sql,
            "show index from %s where Key_name = 'PRIMARY' and Column_name ='%s' and Seq_in_index = 1",
            table_name, field_name);
    print_sql(table_exist_index_sql->str);
    if (mysql_query(conn, table_exist_index_sql->str)) {
        finish_with_error(conn);
    }
    MYSQL_RES *result = mysql_store_result(conn);
    if (result == NULL) {
        finish_with_error(conn);
    }
    bool is_primary = false;
    if (mysql_num_rows(result) > 0) {
        if (options.verbose)
            sql_print_information("第%d步：字段%s是主键。表名:%s \n", STEP_CNT++,
                    field_name, table_name);
        is_primary = true;
    } else {
        if (options.verbose)
            sql_print_information("第%d步：字段%s不是主键。表名:%s \n", STEP_CNT++,
                    field_name, table_name);
    }
    g_string_free(table_exist_index_sql, TRUE);
    mysql_free_result(result);
    mysql_close(conn);
    return is_primary;
}

bool is_like_pre(char * field_ptr) {
    bool meet_space = false;
    char *substr = strdup(" LIKE");
    char *s = strcasestr(field_ptr, substr);
    if (s != NULL) {
        int i;
        for (i = 0; i < strlen(s); i++) {
            if (!meet_space) {
                if (s[i] == ' ' && i > 0) {
                    meet_space = true;
                }
            } else {
                if (s[i] != ' ') {
                    return s[i + 1] == '%' ? true : false;
                }
            }
        }
    }
    if(substr) free(substr);
    return false;
}

bool is_not_tmp_table(TABLE_LIST * table){
    if (strcasecmp(table->db,"") == 0 && strcasecmp(table->table_name,"*") == 0){
	if (options.verbose){
	    sql_print_information("第%d步：表%s 是临时表,不进行处理 \n", STEP_CNT++, table->table_name);
	}
	return false;
    }
    else
	return true;
}

void mysql_sql_parse(Item *item_where) {
    const Item::Type item_where_type = item_where->type();
    switch (item_where_type) {
    case Item::FUNC_ITEM: {
        Item_func *item_func = (Item_func*) item_where;
        if (item_func->argument_count() > 0) {
            Item **item_end = (item_func->arguments())
                    + item_func->argument_count() - 1;
            if (item_func->argument_count() == 2
                    && (*(item_func->arguments()))->type() == Item::FIELD_ITEM
                    && (*item_end)->type() == Item::FIELD_ITEM) {
                mysql_sql_parse_join(item_where);
            } else {
                String * field_print = new (thd->mem_root) String();
                item_func->print(field_print, QT_ORDINARY);
                for (Item **child = item_func->arguments(); child <= item_end;
                        child++) {
                    if ((*child)->type() == Item::FIELD_ITEM) {
                        if (options.verbose)
                            sql_print_information("第%d步：开始解析where中的条件:%s \n",
                                    STEP_CNT++, field_print->c_ptr_safe());
                        if (item_func->functype() == Item_func::LIKE_FUNC
                                && is_like_pre(field_print->c_ptr_safe())) {
                            if (options.verbose)
                                sql_print_information(
                                        "第%d步：条件%s 是like前缀匹配,跳过不分析. \n",
                                        STEP_CNT++, field_print->c_ptr_safe());
                            continue;
                        }
                        mysql_sql_parse_field(((Item_field *) (*child)),
                                item_func->functype(),
                                field_print->c_ptr_safe());
                    }
                }
            }
        }
        break;
    }
    case Item::COND_ITEM: {
        Item_cond *item_cond = (Item_cond*) item_where;
        switch (item_cond->functype()) {
        case Item_func::COND_AND_FUNC: {
            List_iterator<Item> li_item_cond(*item_cond->argument_list());
            Item *item_abc;
            while ((item_abc = li_item_cond++)) {
                mysql_sql_parse(item_abc);
            }
            break;
        }
        case Item_func::COND_OR_FUNC: {
            break;
        }
        default: {
            break;
        }
        }
        break;
    }
    case Item::SUBSELECT_ITEM: {
        Item_cond *item_cond = (Item_cond*) item_where;
        break;
    }
    default: {
        break;
    }
    }
}

void mysql_sql_parse_admin(st_select_lex * current_lex) {
    SQL_I_List<TABLE_LIST> table_list = current_lex->table_list;
    TABLE_ELEMENT = table_list.elements;
    TABLE_LIST *table_name = table_list.first;

    if (TABLE_ELEMENT == 1) {
	if (is_not_tmp_table(table_name)){
	    DRIVED_TABLE = table_name;
	    table_name->is_table_driverd = true;
	}
    } else {
        List_iterator<TABLE_LIST> top_join_list(current_lex->top_join_list);
        TABLE_LIST *top_table;
        while ((top_table = top_join_list++)) {
            if (top_table->nested_join != NULL) {
                //		find_join_elements(top_table);
                find_join_elements_new(top_table);
            } else {
                if (TABLE_DRIVERD.count(top_table) == 0) {
                    TABLE_DRIVERD.insert(top_table);
                }
            }
        }
	if (!TABLE_DRIVERD.empty()) {
	    final_table_drived();
	}
    }
    if (mysql_sql_parse_group()) {
        if (options.verbose)
            sql_print_information("第%d步：开始添加group by 字段 \n", STEP_CNT++);
        mysql_sql_parse_group_order_add(DRIVED_TABLE, current_lex->group_list);
    } else if (mysql_sql_parse_order()) {
        if (options.verbose)
            sql_print_information("第%d步：开始添加order by 字段 \n", STEP_CNT++);
        mysql_sql_parse_group_order_add(DRIVED_TABLE, current_lex->order_list);
    }
    if (TABLE_ELEMENT > 1 && DRIVED_TABLE)
        table_index_add_condition_field();
    print_index();
}

static GOptionEntry entries[] = { { "defaults-file", 'f', 0,
        G_OPTION_ARG_STRING, &(options.configfile), "sqls file", NULL }, {
        "username", 'u', 0, G_OPTION_ARG_STRING, &(options.username),
        "username", NULL }, { "password", 'p', 0, G_OPTION_ARG_STRING,
        &(options.password), "password", NULL }, { "port", 'P', 0,
        G_OPTION_ARG_INT, &(options.port), "port", NULL }, { "host", 'h', 0,
        G_OPTION_ARG_STRING, &(options.host), "host", NULL }, { "dbname", 'd',
        0, G_OPTION_ARG_STRING, &(options.dbname), "database name", NULL }, {
        "sqls", 'q', 0, G_OPTION_ARG_STRING_ARRAY, &(options.query), "sqls",
        NULL }, { "verbose", 'v', 0, G_OPTION_ARG_INT, &(options.verbose),
        "1:output logs 0:output nothing", NULL }, { NULL } };
int g_option_keyfile_parse(GKeyFile *keyfile, const char *ini_group_name,
        GOptionEntry *entries) {
    GError *gerr = NULL;
    GOptionEntry *entry = NULL;
    int ret = 0;
    int i = 0, j = 0;
    if (keyfile == NULL) {
        return ret;
    }
    if (!g_key_file_has_group(keyfile, ini_group_name)) {
        return ret;
    }
    for (i = 0; entries[i].long_name; i++) {
        char *arg_string = NULL;
        char **arg_string_array = NULL;
        int arg_int = 0;
        gsize len = 0;
        entry = &(entries[i]);
        switch (entry->arg) {
        case G_OPTION_ARG_STRING: {
			g_clear_error(&gerr);
            if (entry->arg_data == NULL
                    || *(gchar **) (entry->arg_data) != NULL) {
                break;
            }
            arg_string = g_key_file_get_string(keyfile, ini_group_name,
                    entry->long_name, &gerr);
            if (!gerr) {
                *(gchar **) (entry->arg_data) = g_strchomp(arg_string);
            }
            break;
        }
        case G_OPTION_ARG_INT: {
			g_clear_error(&gerr);
            arg_int = g_key_file_get_integer(keyfile, ini_group_name,
                    entry->long_name, &gerr);
            if (!gerr) {
                *(gint *) (entry->arg_data) = arg_int;
            }
            break;
        }
        case G_OPTION_ARG_STRING_ARRAY: {
			g_clear_error(&gerr);
            if (entry->arg_data == NULL
                    || *(gchar **) (entry->arg_data) != NULL) {
                break;
            }
            arg_string_array = g_key_file_get_string_list(keyfile,
                    ini_group_name, entry->long_name, &len, &gerr);
            if (!gerr) {
                for (j = 0; arg_string_array[j]; j++) {
                    arg_string_array[j] = g_strstrip(arg_string_array[j]);
                }
                *(gchar ***) (entry->arg_data) = arg_string_array;
            }
            break;
        }
        default: {
            sql_print_error("the option can not be handled.\n");
            break;
        }
        }
    }
	ret = 1;
    return ret;
}

int main(int argc, char **argv) {

    LEX *sql_lex;
    String *lex_string = NULL;
    GKeyFile *keyfile = NULL;
    GError *error = NULL;
    GOptionContext *context = NULL;
    char *query = NULL;
    char *sqlparse_path = strdup("/usr/local/sqlparser");
    int i = 0;
    char *lc = NULL;
    if (mysqld_init(sqlparse_path)) {
        sql_print_error("加载sqlparser模块有错 \n");
        if(sqlparse_path) free(sqlparse_path);
        return -1;
    }
    if(sqlparse_path) free(sqlparse_path);

    lc = setlocale(LC_ALL, "");
    if (NULL == lc) {
        sql_print_error("setlocale 有错 \n");
        if(sqlparse_path) free(sqlparse_path);
        return -1;
    }

    ConnectionOptionsInit(&options);
    context = g_option_context_new("sqladvisor");
    g_option_context_add_main_entries(context, entries, NULL);
    g_option_context_set_summary(context, "SQL Advisor Summary");
    if (!g_option_context_parse(context, &argc, &argv, &error)) {
        sql_print_error("option parsing failed:%s\n", error->message);
        exit(1);
    }
    g_option_context_free(context);
    if (options.configfile != NULL) {
        //load config file
        keyfile = g_key_file_new();
        g_key_file_set_list_separator(keyfile, SEP);
        if (g_key_file_load_from_file(keyfile, options.configfile,
                G_KEY_FILE_NONE, &error) == FALSE) {
            g_key_file_free(keyfile);
            sql_print_error("load config file failed:%s\n", error->message);
        }
        if (g_option_keyfile_parse(keyfile, GROUT_NAME, entries) < 0) {
            g_key_file_free(keyfile);
            sql_print_error("read config file failed:%s\n", error->message);
        }
    }

    if (options.username == NULL || options.password == NULL
            || options.host == NULL || options.dbname == NULL
            || options.query[0] == NULL) {
        mysqld_cleanup();
        return -1;
    }
    while ((query = options.query[i]) != NULL) {
        sql_lex = sql_parser(query, options.dbname);

        if (sql_lex == NULL) {
            sql_print_error("sqlparser 解析出错,返回值lex为空 \n");
            continue;
        }

        current_lex = &sql_lex->select_lex;
        while (current_lex != NULL) {
            lex_string = new (thd->mem_root) String();
            current_lex->print(thd, lex_string, QT_ORDINARY);
            if (options.verbose) {
                sql_print_information("第%d步: 对SQL解析优化之后得到的SQL:%s \n",
                        STEP_CNT++, lex_string->ptr());
            }

            if (current_lex->where) {
                mysql_sql_parse(current_lex->where);
            }
            if (current_lex->table_list.elements >= 1) { //有可能SQL解析出来之后，生成的解析树是错的，则elements = 0
                mysql_sql_parse_admin(current_lex);
            }
            current_lex = current_lex->next_select();
        }
        if (lex_string != NULL) {
            delete lex_string;
        }
        if (options.verbose) {
            sql_print_information("第%d步: SQLAdvisor结束! \n", STEP_CNT++);
        }
        i++;
        STEP_CNT = 1;
    }

    sql_parser_cleanup();
    mysqld_cleanup();
    ConnectionOptionsFree(&options);
    return 0;
}
