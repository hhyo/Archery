#ifndef SQL_PARSER_INDEX_INCLUDED
#define SQL_PARSER_INDEX_INCLUDED


#include "string"
using std::string;

struct Field_Description{

    Item_field * field_name;
    Item_func::Functype operator_type;
    int cardinality;
    const char * field_print;

    Field_Description(Item_field * field, int card_value,Item_func::Functype type,const char * field_ptr){
	field_name = field;
	operator_type = type;
	cardinality = card_value;
	field_print = field_ptr;
    }

    Field_Description(Item_field * field){
	field_name = field;
	operator_type = Item_func::UNKNOWN_FUNC;
	cardinality = 0;
	field_print = NULL;
    }

};


struct INDEX_FIELD{
    Field_Description * index_field;

    INDEX_FIELD * next_field;

    INDEX_FIELD(Field_Description * field){
	index_field = field;
	next_field = NULL;
    }

};


struct JOIN_CONDITION{
    List<Item_field> join_fields;
    TABLE_LIST * join_table;

    JOIN_CONDITION(TABLE_LIST * table){
	join_table = table;
    }

    List<Item_field> * get_join_field(){
	if (join_fields.elements == 0){
	    join_fields.empty();
	}
	return &join_fields;
    }

};


struct POSSBILE_INDEX{
    string index_name;
    longlong cardinality;
    List<char> index_columns;

    POSSBILE_INDEX(char * indexname){

	index_name = string(indexname);
	cardinality = 0;
    }

    List<char> * get_index_columns(){
	if (index_columns.elements  == 0){
	    index_columns.empty();
	}
	return &index_columns;
    }
};





#endif

