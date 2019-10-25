# -*- coding: UTF-8 -*-
import re

jdbc_type = {
    'NUM': ['TINYINT', 'SMALLINT', 'INTEGER', 'BIGINT', 'BIT', 'DECIMAL', 'DOUBLE', 'FLOAT', 'NUMERIC'],
    'BOOLEAN': ['BOOLEAN'],
    'DATE': ['DATE', 'TIME', 'TIMESTAMP'],
    'STRING': ['CHAR', 'VARCHAR', 'NCHAR', 'NVARCHAR', 'LONGNVARCHAR', 'LONGVARCHAR'],
    'BINARY': ['BINARY', 'VARBINARY', 'LONGVARBINARY', 'BLOB'],
    'OTHER': ['ARRAY', 'CLOB', 'CURSOR', 'DATALINK', 'DATETIMEOFFSET', 'DISTINCT', 'JAVA_OBJECT', 'NCLOB',
              'NULL', 'OTHER', 'REAL', 'REF', 'ROWID', 'SQLXML', 'STRUCT', 'UNDEFINED']

}


def get_params(child):
    """
    Get SQL Params
    example: #{age,javaType=int,jdbcType=NUMERIC,typeHandler=MyTypeHandler}
    change: '#','$'
    :return:
    """
    p = re.compile('\S')
    # Remove empty info
    child_text = child.text if child.text else ''
    child_tail = child.tail if child.tail else ''
    child_text = child_text if p.search(child_text) else ''
    child_tail = child_tail if p.search(child_tail) else ''
    convert_string = child_text + child_tail

    params = {'#': [], '$': []}
    for change in ['#', '$']:
        tmp_params = []
        string_regex = '\\' + change + '\{.+?\}'
        pattern = re.compile(string_regex)
        match = pattern.findall(convert_string)
        # tmp_unique_params
        tmp_params += sorted(set(match), key=match.index)
        # get jdbcType、javaType
        for param in tmp_params:
            param_dict = dict()
            param_dict['full_name'] = param
            param = param.replace(change + '{', '').replace('}', '')
            param_dict['name'] = param.split(',')[0]
            m = re.search('(\s*jdbcType\s*=\s*)(?P<jdbc_type>\w+)?', param)
            param_dict['jdbc_type'] = m.group('jdbc_type').strip() if m else None
            m = re.search('(\s*javaType\s*=\s*)(?P<java_type>\w+)?', param)
            param_dict['java_type'] = m.group('java_type').strip() if m else None
            #  Replace SQL Params
            replace_params(param_dict)
            params[change].append(param_dict)
    return params


def replace_params(param):
    """
    Replace SQL Params
    :return:
    """
    param_jdbc_type = param['jdbc_type']
    if param_jdbc_type in jdbc_type['NUM']:
        param['mock_value'] = '?'
    elif param_jdbc_type in jdbc_type['BOOLEAN']:
        param['mock_value'] = '?'
    elif param_jdbc_type in jdbc_type['BINARY']:
        param['mock_value'] = '?'
    elif param_jdbc_type in jdbc_type['STRING']:
        param['mock_value'] = '?'
    else:
        param['mock_value'] = '?'
