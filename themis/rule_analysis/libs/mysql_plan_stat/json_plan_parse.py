# -*- coding: utf-8 -*-

"""
本文件中的函数用来解析json树，对mysql中的format=json的结果进行解析，方便
后面的处理
"""

true = True
false = False


def parse_dict(arg, level, parent_key, total_dict):
    """
    整理json树，将key以"/"划分
    示例：
        >>> example = {"first": {"query": "select", "update": {"a": "b"}}}
        >>> result = {}
        >>> parse_dict(example, 0, "", result)
        >>> result
        {
            '/first/update/a': [3, 0, 'b'],
            '/first/update': [2, 2, {'a': 'b'}],
            '/first': [1, 2, {'query': 'select', 'update': {'a': 'b'}}],
            '/first/query': [2, 0, 'select']
        }
    '/first/query': [2, 0, 'select'] 
    列表第一个元素代表key的深度
    第二个元素代表子元素类型，通过函数check_type判断
    第三个元素为子元素的值
    """

    if isinstance(arg, dict):
        level = level + 1
        for key, value in arg.items():
            temp_key = "/".join([parent_key, key])
            content_type = check_type(value)
            total_dict.update({temp_key: [level, content_type, value]})
            parse_dict(value, level, temp_key, total_dict)
    elif isinstance(arg, list):
        for index, value in enumerate(arg):
            list_temp_key = "/".join([parent_key, str(index)])
            content_type = check_type(value)
            total_dict.update({list_temp_key: [level, content_type, value]})
            parse_dict(value, level, list_temp_key, total_dict)
    else:
        pass


def get_all_parent(children):
    """
    """

    parent_dict = {}
    for value in children:
        parent_dict.update({value[0]: "/".join(value[0].split("/")[:-1])})
    return parent_dict


def get_direct_children(parent_key, parent_dict):
    """
    获取某个父key的直接子key
    """

    children_list = []
    for key, value in parent_dict.items():
        if value == parent_key:
            children_list.append(key)
    return children_list


def save_to_db(client, planitem):
    object_id = client.get_collection("planitem").insert(planitem)
    return object_id


def get_item_level(key):
    """
    获取key的深度，使用1_1_1这种形式表示
    """

    every_level = key.split("/")
    temp_str = ""
    for index, temp in enumerate(every_level):
        if "%" in temp:
            temp_str += "_" + str(int(temp.split("%")[1]) + 1)
        else:
            temp_str += "_1"
    return temp_str[3:]


def check_type(value):
    """
    判断json树中子元素的各种类型
    """
    
    if isinstance(value, str):
        content_type = 0
    elif isinstance(value, list):
        content_type = 1
    elif isinstance(value, dict):
        content_type = 2
    elif isinstance(value, tuple):
        content_type = 3
    elif isinstance(value, bool):
        content_type = 4
    elif isinstance(value, int):
        content_type = 5
    elif isinstance(value, float):
        content_type = 6
    else:
        content_type = None
    return content_type


def json_plan_item(client, checksum, data, v_schemas):
    """
    解析json树
    """
    
    total_dict = {}
    parse_dict(data, 0, "", total_dict)

    # 将整理后的结果取出key和深度，追加到一个列表，并根据深度进行逆序排列
    temp_list = []
    for key, value in total_dict.items():
        temp_list.append((key, value[0]))
    after_sort = sorted(temp_list, key=lambda t: t[1], reverse=1)

    # 获取子元素中类型为字典的所有元素的key
    # direct_children_list变量命名不合适
    key_list = total_dict.keys()
    direct_children_list = {}
    for value in after_sort:
        children_level = value[0] + "/"
        children_list = []
        for data1 in key_list:
            if children_level in data1:
                children_list.append(data1)
        temp_children_list = []
        for data2 in children_list:
            # 判断是否为字典
            if total_dict[data2][1] == 2:
                temp_children_list.append(data2)
        temp_children_list = list(set(temp_children_list))
        direct_children_list.update({value[0]: temp_children_list})
        children_list = []

    # 处理/first/update/a/0 /first/update/a/1这种情况
    add_list_level = {}
    for value in after_sort:
        temp_str = ""
        temp_level = value[0].split("/")
        for index, temp in enumerate(temp_level):
            try:
                int(temp)
                temp_str += "%" + temp
            except Exception:
                temp_str += "/" + temp
            add_list_level.update({value[0]: temp_str[1:]})

    # 初始化一个以子键为key，以父键为值的字典
    all_parent = get_all_parent(after_sort)

    save_object_id = {}
    mongo_dict = {}
    item_level = ""
    for value in after_sort:
        object_id_list = []
        if total_dict[value[0]][1] == 2:
            # 包含子元素
            if direct_children_list[value[0]]:
                # 获取某个key的直接子key
                # 如/a/b,/a/c是/a的直接子，/a/b/c/d不是/a的直接子
                temp_object_id = get_direct_children(value[0], all_parent)
                if temp_object_id:
                    for temp_object in temp_object_id:
                        # 如果子元素为字典
                        if total_dict[temp_object][1] == 2:
                            object_id_list.append(save_object_id[temp_object])
                        # 如果子元素为列表
                        elif total_dict[temp_object][1] == 1:
                            # 列表中嵌套了字典
                            if isinstance(total_dict[temp_object][2][0], dict):
                                obj_len = len(total_dict[temp_object][2])
                                for i in range(obj_len):
                                    temp_key = "/".join([temp_object, str(i)])
                                    # temp_key = temp_object + "/" + str(i)
                                    object_id_list.append(
                                        save_object_id[temp_key])
                item_level = get_item_level(add_list_level[value[0]])
                item_type = add_list_level[value[0]].\
                    split("/")[-1].split("%")[0]
                mongo_dict = total_dict[value[0]][2]
                new_mongo_dict = {}
                citem_type = ""
                for key, mongo_no_child in mongo_dict.items():
                    if isinstance(mongo_no_child, dict):
                        citem_type = key
                    elif isinstance(mongo_no_child, list) and isinstance(mongo_no_child[0], dict):
                        citem_type = key
                    else:
                        new_mongo_dict.update({key: mongo_no_child})
                # 生成最终结果，object_id_list为子元素列表
                new_mongo_dict.update({
                    "item_level": item_level,
                    "checksum": checksum,
                    "item_type": item_type,
                    "citem": object_id_list,
                    "citem_type": citem_type,
                    "schemas": v_schemas
                })
                object_id = client.insert("planitem", new_mongo_dict)
                save_object_id.update({value[0]: object_id})
                new_mongo_dict = {}
                mongo_dict = {}
            else:
                # 不包含子元素
                mongo_dict = total_dict[value[0]][2]
                item_level = get_item_level(add_list_level[value[0]])
                item_type = add_list_level[value[0]].\
                    split("/")[-1].split("%")[0]
                mongo_dict.update({
                    "item_level": item_level,
                    "checksum": checksum,
                    "item_type": item_type,
                    "schemas": v_schemas
                })
                object_id = client.insert("planitem", mongo_dict)
                save_object_id.update({value[0]: object_id})
                mongo_dict = {}
