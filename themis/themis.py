# -*- coding: utf-8 -*-

import re

from django.db import connection

from sql.models import Instance
from themis.rule_analysis.db.db_operat import DbOperat
from themis.rule_analysis.db.mongo_operat import MongoOperat
from themis.rule_analysis.libs.mysql_plan_stat.plan_stat import MysqlPlanOrStat
from themis.rule_analysis.review_result.rule_result import ReviewResult
from themis.rule_analysis.libs.text.sql_text import SqlText


class Themis(object):
    """
    规则解析类，负责初始化各种数据库句柄，包括mongo，mysql
    判断规则类型
    """

    def __init__(self,
                 instance_name,
                 username,
                 rule_type,
                 create_user,
                 start_date=None,
                 stop_date=None, ):
        try:
            self.instance_info = Instance.objects.get(instance_name=instance_name)
        except Exception:
            connection.close()
            self.instance_info = Instance.objects.get(instance_name=instance_name)
        self.username = username
        self.create_user = create_user
        self.rule_type = rule_type
        self.db_type = self.instance_info.db_type
        self.hostname = self.instance_info.host + ':' + str(self.instance_info.port)
        self.rule_status = 'ON'
        self.start_date = start_date
        self.stop_date = stop_date
        self.mongo_client = MongoOperat()
        self.review_result = ReviewResult(self.mongo_client, self.db_type,
                                          self.rule_type, self.username,
                                          self.rule_status)
        if self.db_type == "mysql" and self.rule_type == "OBJ":
            self.db_client = DbOperat(instance_name=instance_name, db_name=self.username)
        elif self.db_type == "mysql" and self.rule_type in ["SQLPLAN", "SQLSTAT"]:
            self.db_client = DbOperat(instance_name=instance_name, db_name=self.username)
            self.mys = MysqlPlanOrStat(self.db_client, self.mongo_client, self.rule_type)
        elif self.db_type == "mysql" and self.rule_type == "TEXT":
            self.sql_text = SqlText(self.mongo_client, self.start_date,
                                    self.stop_date, self.username,
                                    self.hostname)

    def m_rule_parse(self, key, rule_complexity, rule_cmd,
                     weight, max_score, input_parms, hostname, user, passwd):
        """
        mysql数据库的sqlplan和sqlstat的解析
        """
        result = self.mys.get_sql_info(
            self.start_date, self.stop_date, self.username, hostname)
        if not result:
            return False, 0
        # 回库查询获取执行计划
        self.mys.get_sql_plan(user, passwd)
        if rule_complexity == "simple":
            # 生成随机的collection名字
            tmp0, _ = self.review_result.gen_random_collection()
            self.mongo_client.drop(tmp0)
            # 替换掉自定义参数
            if input_parms:
                for parm in input_parms:
                    rule_cmd = rule_cmd.replace(
                        "@" + parm["parm_name"] + "@",
                        str(parm["parm_value"]))
            # 替换掉默认参数
            rule_cmd = rule_cmd.replace("@schema_name@", self.username). \
                replace("@tmp@", tmp0)
            self.mongo_client.command(rule_cmd)
            match_list, sql_text, sql_plan = self.mys.rule_match(tmp0)
            self.mongo_client.drop(tmp0)
            # 生成最终结果
            if match_list:
                temp = {}
                for data in match_list:
                    sql_id = str(data["checksum"]) + "#1#v"
                    temp_sql_plan = sql_plan[data["checksum"]]
                    temp_full_text = sql_text[data["checksum"]]
                    if len(temp_full_text) > 25:
                        temp_sql_text = temp_full_text[:25]
                    else:
                        temp_sql_text = ""
                    temp.update({
                        sql_id: {
                            "sql_id": data["checksum"],
                            "plan_hash_value": int(1),
                            "sql_text": temp_sql_text,
                            "sql_fulltext": temp_full_text,
                            "plan": temp_sql_plan,
                            "stat": data,
                            "obj_info": {},
                            "obj_name": None
                        }
                    })
                # 计算分数
                scores = len(temp.keys()) * float(weight)
                return temp, scores
            return None, None

    def text_parse(self, key, rule_complexity, rule_cmd,
                   weight, max_score, input_parms, sql_list):
        """
        mysql数据库的TEXT类规则
        """
        args = {}
        for parm in input_parms:
            args[parm["parm_name"]] = parm["parm_value"]
        score_list = []
        temp = {}
        for sql in sql_list:
            sql_id = sql["checksum"] + "#1#v"
            args["sql"] = sql["sqltext_form"]
            # 解析简单规则
            if rule_complexity == "simple":
                pat = re.compile(rule_cmd)
                if pat.search(args["sql"]):
                    score_list.append(sql["checksum"])
                    temp.update({
                        sql_id: {
                            "sql_id": sql["checksum"],
                            "sql_text": sql["sqltext_org"],
                            "obj_name": None,
                            "stat": sql["sqlstats"],
                            "plan": []
                        }
                    })
            # 解析复杂类规则
            elif rule_complexity == "complex":
                # 根据规则名称动态加载复杂规则
                module_name = ".".join(["themis.rule_analysis.rule", self.rule_type.lower(), key.lower()])
                module = __import__(module_name, globals(), locals(), "execute_rule")
                if module.execute_rule(**args):
                    score_list.append(sql["checksum"])
                    temp.update({
                        sql_id: {
                            "sql_id": sql["checksum"],
                            "sql_text": sql["sqltext_org"],
                            "obj_name": None,
                            "stat": sql["sqlstats"],
                            "plan": []
                        }
                    })
        scores = len(score_list) * float(weight)
        if scores > max_score:
            scores = max_score
        return temp, scores

    def obj_parse(self, key, rule_complexity, rule_cmd, weight,
                  max_score, input_parms):
        """
        解析mysql数据库的OBJ类规则
        """
        flag = True
        # 解析简单规则
        if rule_complexity == "simple":
            for parm in input_parms:
                rule_cmd = rule_cmd.replace(
                    "@" + parm["parm_name"] + "@",
                    str(parm["parm_value"]))
            rule_cmd = rule_cmd.replace("@username@", self.username)
            self.db_client.cursor.execute(rule_cmd)
            results = self.db_client.cursor.fetchall()
        # 解析复杂类规则
        elif rule_complexity == "complex":
            args = {
                "username": self.username,
                "weight": weight,
                "max_score": max_score,
                "db_cursor": self.db_client.cursor
            }
            [args.update({parm["parm_name"]: parm["parm_value"]})
             for parm in input_parms]
            # 根据规则名称动态加载规则模块
            module_name = ".".join(["themis.rule_analysis.rule", self.rule_type.lower(), key.lower()])
            module = __import__(module_name, globals(), locals(), "execute_rule")
            results, flag = module.execute_rule(**args)
        if isinstance(flag, bool):
            scores = len(results) * weight
            if scores > max_score:
                scores = max_score
        else:
            scores = flag
        return results, scores

    def run(self):
        job_record = {}
        if self.rule_type == "TEXT":
            sql_list = self.sql_text.get_text(self.db_type)
        for key, value in self.review_result.rule_info.items():
            job_record[key] = {}
            rule_complexity = value["rule_complexity"]
            rule_cmd = value["rule_cmd"]
            weight = value["weight"]
            max_score = value["max_score"]
            input_parms = value["input_parms"]
            if self.db_type == "mysql" and self.rule_type in ["SQLPLAN", "SQLSTAT"]:
                user = self.instance_info.user
                passwd = self.instance_info.raw_password
                result, scores = self.m_rule_parse(key, rule_complexity, rule_cmd,
                                                   weight, max_score, input_parms,
                                                   self.hostname, user, passwd)
                if result:
                    job_record[key].update(result)
                    job_record[key].update({"scores": scores})
            elif self.rule_type == "TEXT":
                result, scores = self.text_parse(key, rule_complexity,
                                                 rule_cmd, weight,
                                                 max_score, input_parms,
                                                 sql_list)
                if result:
                    job_record[key].update(result)
                    job_record[key].update({"scores": scores})
            elif self.db_type == "mysql" and self.rule_type == "OBJ":
                results, scores = self.obj_parse(key, rule_complexity,
                                                 rule_cmd, weight,
                                                 max_score, input_parms)
                job_record[key].update({"records": results, "scores": scores})
        return job_record

    def save_result(self, job_record):
        """
        """
        args = {
            "operator_user": self.create_user,
            "start_date": self.start_date,
            "stop_date": self.stop_date,
            "instance_name": self.username,
            "task_ip": self.instance_info.host,
            "task_port": self.instance_info.port
        }
        self.review_result.job_init(**args)
        job_record.update({"task_uuid": self.review_result.task_id})
        self.mongo_client.insert_one("results", job_record)
        sql = {"id": self.review_result.task_id}
        condition = {"$set": {"status": "1"}}
        self.mongo_client.update_one("job", sql, condition)
