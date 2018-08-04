# -*- coding: utf-8 -*-"

import MySQLdb


def f_user_get(**kwargs):
    l_db_dbinfo = kwargs["v_dbinfo"]
    l_sqltext = kwargs["sqltext"]
    ip = l_db_dbinfo[0]
    port = l_db_dbinfo[1]
    username = l_db_dbinfo[3]
    passwd = l_db_dbinfo[4]
    conn = MySQLdb.connect(
        host=ip, port=int(port), user=username, passwd=passwd)
    cursor = conn.cursor()
    cursor.execute(l_sqltext)
    userlist = cursor.fetchall()
    cursor.close()
    conn.close()
    return userlist


if __name__ == "__main__":
    v_dbinfo = ["127.0.0.1", 3306, "mysql", "root", "1234567890"]
    v_sqltext = """select user,host from mysql.user"""
    arg = {
        "v_dbinfo": v_dbinfo,
        "sqltext": v_sqltext
    }
    print(f_user_get(**arg))
