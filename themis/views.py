# -*- coding: utf-8 -*-
import simplejson as json
import time
import json
import sqlparse
import wtforms_json
import os

from django.contrib.auth.mixins import PermissionRequiredMixin, LoginRequiredMixin
from django.shortcuts import render
from django_q.tasks import async_task
from pymongo import DESCENDING
from django.views import View
from themis.utils.jsonres import temRes
from themis.utils.raiseerr import APIError
from themis.utils.wtform_models import SimpleForm, ComplexForm
from themis.themis import Themis
from themis.rule_analysis.db.mongo_operat import MongoOperat
from sql.models import Instance

import logging

logger = logging.getLogger('default')
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class BaseHandler(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'sql.menu_themis'
    raise_exception = True

    @property
    def mongo_client(self):
        return MongoOperat()


class SqlReRuleSetIndex(BaseHandler):

    def get(self, request):
        return render(request, "rule_set.html")


class RuleSimpleAdditoin(BaseHandler):

    def get(self, request):
        return render(request, "rule_simple_add.html")


class RuleComplexAddition(BaseHandler):

    def get(self, request):
        return render(request, "rule_complex_add.html")


class RuleAddition(BaseHandler):

    @temRes
    def post(self, request):
        """
        规则增加功能
        """
        argument = json.loads(request.body)
        wtforms_json.init()
        try:
            if argument["rule_complexity"] == "simple":
                form = SimpleForm.from_json(argument, skip_unknown_keys=False)
            elif argument["rule_complexity"] == "complex":
                form = ComplexForm.from_json(argument, skip_unknown_keys=False)
            if not form.validate():
                message = list(form.errors.values())[0][0]
                return {"errcode": 30061, "message": message}
            if argument["rule_complexity"] == "complex":
                filename = argument["rule_name"].lower() + ".py"
                if not os.path.exists(
                        "../rule_analysis/rule/extend/" + filename):
                    return {"errcode": 30063, "message": u"需要先上传脚本"}
            record = self.mongo_client.get_collection("rule").find_one({
                "rule_name": argument["rule_name"].upper(),
                "db_type": argument["db_type"]})
            if record:
                return {"errcode": 30062, "message": u"规则已经存在"}
            argument["rule_name"] = argument["rule_name"].upper()
            argument["solution"] = argument["rule_solution"].split("\n")
            argument["max_score"] = float(argument["max_score"])
            argument["weight"] = float(argument["weight"])
            if argument["input_parms"]:
                for index, value in enumerate(argument["input_parms"]):
                    argument["input_parms"][index]["parm_value"] = \
                        float(value["parm_value"])
            self.mongo_client.get_collection("rule").insert_one(argument)
            return {"errcode": 80061, "message": u"增加规则成功"}
        except wtforms_json.InvalidData as e:
            return {"errcode": 30060, "message": str(e)}


class RuleUpload(BaseHandler):

    @temRes
    def post(self, request):
        """
        复杂规则增加之代码文件上传
        """
        f = request.FILES["pyfile"]
        filename = f.name
        if "." in filename:
            if filename.split(".")[1] != "py":
                return {"errcode": 30062, "message": u"文件类型不正确"}
        else:
            return {"errcode": 30062, "message": u"文件类型不正确"}
        with open(BASE_DIR + "/themis/rule_analysis/rule/extend/" + filename.lower(), "wb+") as file:
            for chunk in f.chunks():
                file.write(chunk)
        context = {
            "files": [{"name": "success", "mimetype": "text"}],
            "errcode": 80070,
            "message": "success"
        }
        return context


class SqlReRuleSetInfoIndex(BaseHandler):

    def get(self, request):
        """
        api: /new/version/sql/review/rule/info/index
        任务发布界面之ip地址显示
        """
        # 获取实例列表
        instances = Instance.objects.filter(type='master', db_type='mysql')
        return render(request, "rule_set_info.html", {'instances': instances})


class SqlReviewTaskIndex(BaseHandler):

    def get(self, request):
        return render(request, "task_info.html")


class SqlReviewRuleInfo(BaseHandler):

    @temRes
    def get(self, request):
        """
        api: /sqlreview/rule/info
        规则展示界面
        """
        results = self.mongo_client.get_collection("rule").find({})
        data = []
        for value in results:
            parms = [0, 0, 0, 0, 0]
            for index, temp in enumerate(value["input_parms"]):
                parms[index] = temp.get("parm_value", 0)
            data.append([
                value["rule_name"],
                value["rule_summary"],
                value["rule_status"],
                value["weight"],
                value["max_score"],
                value["rule_type"],
                "Oracle" if value["db_type"] == "O" else "Mysql",
                parms[0],
                parms[1],
                parms[2],
                value["rule_cmd"],
                value.get("exclude_obj_type", "无"),
            ])
        return {"errcode": 80013, "message": u"查询成功", "data": data}

    @temRes
    def post(self, request):
        rule_name = request.POST.get("id")
        db_type = request.POST.get("dbtype")
        flag = request.POST.get("flag")
        oldvalue = request.POST.get("value", None)
        value = request.POST.get("value", None)
        if db_type == "Oracle":
            dbtype = "O"
        elif db_type == "Mysql":
            dbtype = "mysql"
        else:
            raise APIError(u"db类型不正确", 30055)
        if not rule_name:
            raise APIError(u"规则名称不正确", 30057)

        rule_name = rule_name.split("$")[0]
        record = self.mongo_client.get_collection("rule"). \
            find_one({"rule_name": rule_name, "db_type": dbtype})
        if not record:
            raise APIError(u"没有相关规则", 30055)
        if flag == "maxscore":
            self.mongo_client.get_collection("rule").update_one(
                {"rule_name": rule_name, "db_type": dbtype},
                {"$set": {"max_score": str(value)}}
            )
        elif flag == "status":
            if value not in ["ON", "OFF"] or oldvalue not in ["ON", "OFF"]:
                raise APIError(u"状态不正确", 30054)
            self.mongo_client.get_collection("rule").update_one(
                {"rule_name": rule_name, "db_type": dbtype},
                {"$set": {"rule_status": value}}
            )
        elif flag == "weight":
            try:
                value = float(value)
            except Exception:
                raise APIError(u"设置错误", 30059)
            self.mongo_client.get_collection("rule").update_one(
                {"rule_name": rule_name, "db_type": dbtype},
                {"$set": {"weight": value}}
            )
        elif flag in ["parm1", "parm2", "parm3", "parm4", "parm5"]:
            num = int(flag[-1]) - 1
            edit_parm = "input_parms." + str(num) + ".parm_value"
            if len(record['input_parms']) < int(flag[-1]):
                raise APIError(u"设置错误", 30055)
            try:
                value = float(value)
            except Exception:
                raise APIError(u"设置错误", 30059)
            self.mongo_client.get_collection("rule").update_one(
                {"rule_name": rule_name, "db_type": dbtype},
                {"$set": {edit_parm: value}}
            )
        elif flag == "rule_cmd":
            self.mongo_client.get_collection("rule").update_one(
                {"rule_name": rule_name, "db_type": dbtype},
                {"$set": {'rule_cmd': value}}
            )
        context = {
            "message": u"规则设置成功",
            "errcode": 80025,
            "data": value,
            "olddata": oldvalue
        }
        return context


class SqlReviewGetStruct(BaseHandler):

    @temRes
    def get(self, request):
        """
        api: /new/version/sql/review/get/struct
        根据实例名获取规则信息
        """
        flag = request.GET.get("flag")
        instance_name = request.GET.get("instance_name")
        db_type = Instance.objects.get(instance_name=instance_name).db_type
        if flag.upper() not in ["OBJ", "SQLPLAN", "SQLSTAT", "TEXT"]:
            raise APIError(u"规则类型不正确", 30058)
        records = self.mongo_client.get_collection("rule").find(
            {"rule_type": flag.upper(), "db_type": db_type}
        )
        temp = []
        for value in records:
            temp.append([
                value["rule_name"],
                value["rule_summary"],
                value["rule_status"],
                value["weight"],
                value["max_score"],
                value["rule_type"],
                value["db_type"],
                value.get("exclude_obj_type", "无")
            ])
        context = {"message": u"查询成功", "errcode": 80050, "data": temp}
        return context


class SqlReviewJobData(BaseHandler):

    @temRes
    def get(self, request):
        """
        api: /new/version/sql/review/job/data
        获取任务详情列表
        """
        sEcho = request.GET.get("sEcho", None)
        start = request.GET.get("start", None)
        username = request.GET.get("username", None)
        operuser = request.GET.get("operuser", None)
        status = request.GET.get("status", None)
        if status:
            if status not in ["0", "1", "2"]:
                raise APIError(u"状态不正确", 30060)
        starttime = request.GET.get("starttime", None)
        endtime = request.GET.get("endtime", None)
        if starttime and endtime:
            try:
                starttime = time.strftime(
                    "%Y-%m-%d %H:%M:%S", time.strptime(starttime, '%Y-%m-%d'))
                endtime = time.strftime(
                    "%Y-%m-%d %H:%M:%S", time.strptime(endtime, '%Y-%m-%d'))
            except Exception:
                raise APIError(u"时间戳不正确", 30062)
        sql = {}
        if username:
            sql.update({"name": {"$regex": username}})
        if operuser:
            sql.update({"operator_user": {"$regex": operuser}})
        if status:
            sql.update({"status": status})
        if starttime:
            sql.update({"create_time": {"$gt": starttime}})
        if endtime:
            sql.update({"end_time": {"$lt": endtime}})
        records = self.mongo_client.get_collection("job").find(sql). \
            sort("create_time", DESCENDING).skip(int(start)).limit(10)
        number = self.mongo_client.get_collection("job").find(sql).count()
        result = []
        for value in records:
            temp = {}
            if value["status"] == "1":
                task_status = "成功"
            elif value["status"] == "0":
                task_status = "失败"
            else:
                task_status = "正在运行"
            temp.update({
                "operuser": value["operator_user"],
                "username": value["name"].split("#")[0],
                "create_time": value["create_time"],
                "status": task_status,
                "task_type": value["name"].split("#")[1],
                "capture_start_time": value["desc"]["capture_time_s"],
                "capture_stop_time": value["desc"]["capture_time_e"],
                "id": value["id"]
            })
            result.append(temp)
            temp = {}
        res_data = {
            "sEcho": sEcho,
            "iTotalRecords": number,
            "iTotalDisplayRecords": number,
            "aaData": result
        }
        return res_data


class SqlReviewTaskRuleInfo(BaseHandler):

    @temRes
    def post(self, request):
        """
        api:/new/version/sql/review/task/rule/info
        根据任务id获取任务详情
        """
        flag = request.POST.get("flag", None)
        if flag == "1":
            task_uuid = request.POST.get("task_uuid", None)
        else:
            task_uuid = request.POST.get("task_uuid", None)
            if len(task_uuid) > 10:
                raise APIError(u"选择任务过多", 30063)
        if not task_uuid:
            raise APIError(u"请选择相应任务", 30064)
        rule_type = request.POST.get("rule_type", None)
        if not rule_type:
            raise APIError(u"任务类型不能为空", 30065)
        results = self.mongo_client.get_collection("results").find_one(
            {"task_uuid": task_uuid}
        )
        rule_info = self.mongo_client.get_collection("rule").find(
            {"rule_type": rule_type.upper()}
        )
        if not rule_info:
            raise APIError(u"任务类型不正确", 30066)
        job_info = self.mongo_client.get_collection("job").find_one({"id": task_uuid})
        rule_summary = {}
        for value in rule_info:
            rule_summary.update({
                value["rule_name"]: [
                    value["rule_summary"],
                    value["exclude_obj_type"]
                ],
            })
        search_temp = {}
        # mysql数据库的任务
        port = job_info["desc"]["port"]
        search_temp.update({
            "DB_IP": job_info["desc"]["db_ip"],
            "OWNER": job_info["desc"]["owner"]
        })
        mysql_score = []
        [mysql_score.append(float(data["max_score"]))
         for data in self.mongo_client.get_collection("rule").find(
            {"db_type": "mysql", "rule_type": rule_type.upper()}
        )]
        total_score = sum(mysql_score)
        rules = []
        rule_flag = ""
        # 根据规则类型分类，响应不同结果
        if rule_type.upper() == "OBJ":
            for key, value in results.items():
                if value and isinstance(results[key], dict):
                    if value["records"]:
                        temp_set = []
                        # compute records value
                        [temp_set.append(temp[0]) for temp in value["records"]]
                        search_temp.update(
                            {"OBJECT_TYPE": rule_summary[key][1]}
                        )
                        # prevent object
                        prevent_obj = self.mongo_client. \
                            get_collection("exclude_obj_info"). \
                            find(search_temp)
                        prevent_temp = []
                        [prevent_temp.append(data["OBJECT_NAME"])
                         for data in prevent_obj]
                        final_set = list(set(temp_set) - set(prevent_temp))
                        score = value["scores"]
                        rules.append(
                            [key, rule_summary[key][0], len(final_set), score]
                        )
            rule_flag = rule_type.upper()
        elif rule_type.upper() in ["SQLPLAN", "SQLSTAT", "TEXT"]:
            for key, value in results.items():
                if value and isinstance(results[key], dict):
                    num = 0
                    for temp in results[key].keys():
                        if "#" in temp:
                            num += 1
                    rules.append(
                        [key, rule_summary[key][0], num, value["scores"]])
            rule_flag = rule_type.upper()
        context = {
            "task_uuid": task_uuid,
            "ip": search_temp["DB_IP"],
            "port": port,
            "schema": search_temp["OWNER"],
            "rules": rules,
            "rule_flag": rule_flag,
            "total_score": total_score,
            "message": u"查询成功",
            "errcode": 80050
        }
        return context


class SqlReviewTaskRuleDetailInfo(BaseHandler):

    @temRes
    def post(self, request):
        """
        根据任务id和规则名称获取规则违反的具体信息
        """
        task_uuid = request.POST.get("task_uuid", None)
        rule_name = request.POST.get("rule_name", None)
        if not task_uuid:
            raise APIError(u"任务id不正确", 30063)
        results = self.mongo_client.get_collection("results").find_one(
            {"task_uuid": task_uuid}, {rule_name: 1})
        rule_info = self.mongo_client.get_collection("rule").find_one(
            {"rule_name": rule_name})
        job_info = self.mongo_client.get_collection("job").find_one(
            {"id": task_uuid})
        search_temp = {}
        if job_info["desc"]["port"] == "1521":
            search_temp.update({
                "DB_IP": job_info["desc"]["db_ip"],
                "OWNER": job_info["desc"]["owner"],
                "INSTANCE_NAME": job_info["desc"]["instance_name"].upper()})
        table_title = []
        title = []
        records = []
        flag = ""
        # 根据规则类型走不通分支
        if rule_info["rule_type"] == "OBJ":
            if results[rule_name]["records"]:
                for data in rule_info["output_parms"]:
                    table_title.append(data["parm_desc"])
                for data in rule_info["input_parms"]:
                    title.append([data["parm_value"], data["parm_desc"]])
                for data in results[rule_name]["records"]:
                    if data not in records:
                        records.append(data)
            flag = rule_info["rule_type"]
        elif rule_info["rule_type"] in ["SQLPLAN", "SQLSTAT"]:
            for key in results[rule_name].keys():
                if "#" in key:
                    if results[rule_name][key]["obj_name"]:
                        obj_name = results[rule_name][key]["obj_name"]
                    else:
                        obj_name = u"空"
                    cost = results[rule_name][key].get("cost", None) \
                        if results[rule_name][key].get("cost", None) else "空"
                    if results[rule_name][key].get("stat"):
                        count = results[rule_name][key].get("stat").get("ts_cnt", u"空")
                    else:
                        count = "空"
                    records.append([
                        key.split("#")[0],
                        results[rule_name][key]["sql_text"],
                        key.split("#")[1],
                        key.split("#")[2],
                        obj_name,
                        cost,
                        count
                    ])
            flag = rule_info["rule_type"]
            title = rule_name
            table_title = ""
        elif rule_info["rule_type"] == "TEXT":
            for key in results[rule_name].keys():
                if "#" in key:
                    if len(results[rule_name][key]["sql_text"]) > 40:
                        sqltext = results[rule_name][key]["sql_text"][:40]
                    else:
                        sqltext = results[rule_name][key]["sql_text"]
                    records.append([key.split("#")[0], sqltext])
            flag = rule_info["rule_type"]
            title = rule_name
            table_title = ""
        solution = "<br>".join(rule_info["solution"])
        context = {
            "task_uuid": task_uuid,
            "title": title,
            "table_title": table_title,
            "rule_name": rule_name,
            "records": records,
            "flag": flag,
            "solution": solution,
            "message": u"查询成功",
            "errcode": 80051
        }
        return context


class SqlReviewTaskRulePlanInfo(BaseHandler):

    @temRes
    def post(self, request):
        """
        根据任务id，规则名称，hash_value获取统计信息和文本
        """
        argument = json.loads(request.body)
        task_uuid = argument.get("task_uuid", None)
        sql_id_hash = argument.get("sql_id_hash", None)
        rule_name = argument.get("rule_name", None)
        if not task_uuid:
            raise APIError(u"任务id不正确", 30063)
        plan = []
        sql_id = argument.get("id", None)
        if sql_id == "v":
            search_key = rule_name + "." + sql_id_hash + "#v"
            keyword = sql_id_hash + "#v"
        else:
            search_key = rule_name + "." + sql_id_hash + "#" + sql_id
            keyword = sql_id_hash + "#" + sql_id
        record = self.mongo_client.get_collection("results").find_one(
            {"task_uuid": str(task_uuid)}, {str(search_key): 1}
        )
        task_info = self.mongo_client.get_collection("job").find_one(
            {"id": str(task_uuid)}
        )
        stat_title = []
        stat_data = []
        obj_title = []
        obj_data = []
        if record[rule_name][keyword]["stat"]:
            temp = record[rule_name][keyword]["stat"]
            stat_title = temp.keys()
            stat_data = temp.values()
        sql_fulltext = sqlparse.format(
            record[rule_name][keyword]["sql_fulltext"], reindent=True
        )
        if int(task_info["desc"]["port"]) == 1521:
            flag = "O"
            if record[rule_name][keyword]["obj_info"]:
                temp = record[rule_name][keyword]["obj_info"]
                obj_title = temp.keys()
                [obj_data.append(str(data)) for data in temp.values()]
            plan = record[rule_name][keyword]["plan"]
            # 将执行计划根据id进行排序
            plan.sort(key=lambda x: x['ID'])
        else:
            obj_title = []
            obj_data = []
            flag = "mysql"
            plan = record[rule_name][keyword]["plan"]
        context = {
            "sql_fulltext": sql_fulltext,
            "plan": plan,
            "obj_title": obj_title,
            "obj_data": [obj_data],
            "stat_title": list(stat_title),
            "stat_data": [list(stat_data)],
            "flag": flag,
            "message": u"查询成功",
            "errcode": 80054
        }
        return context


class SqlReviewTaskRuleTextInfo(BaseHandler):

    @temRes
    def post(self, request):
        """
        获取文本类规则的详细信息
        """
        argument = json.loads(request.body)
        task_uuid = argument.get("task_uuid", None)
        sql_id_hash = argument.get("sql_id_hash", None)
        rule_name = argument.get("rule_name", None)
        if not task_uuid:
            raise APIError(u"任务id不正确", 30063)
        sql_id = sql_id_hash + "#v"
        search_key = rule_name + "." + sql_id
        record = self.mongo_client.get_collection("results"). \
            find_one(
            {"task_uuid": str(task_uuid)},
            {str(search_key): 1}
        )
        sqltext = sqlparse.format(
            record[rule_name][sql_id]["sql_text"], reindent=True
        )
        sqlstat = record[rule_name][sql_id]["stat"]
        stat_title = []
        stat_list = []
        for index, value in enumerate(sqlstat):
            if index == 0:
                stat_title = value.keys()
            temp = []
            [temp.append(str(data)) for data in value.values()]
            stat_list.append(temp)
        context = {
            "message": u"查询成功",
            "errcode": 80055,
            "sqltext": sqltext,
            "stat_title": list(stat_title),
            "stat_list": stat_list,
            "sql_id": sql_id.split("#")[0]
        }
        return context


class SqlReviewPreventObject(BaseHandler):

    @temRes
    def get(self, request):
        records = self.mongo_client.get_collection("exclude_obj_info").find({})
        temp = []
        if records:
            for value in records:
                if value["DB_TYPE"] == "O":
                    db_type = "oracle"
                else:
                    db_type = "mysql"
                if value.get("INSTANCE_NAME", None):
                    port_or_name = value["INSTANCE_NAME"]
                else:
                    port_or_name = value["port"]
                temp.append([
                    value["OWNER"],
                    value["OBJECT_NAME"],
                    value["OBJECT_TYPE"],
                    db_type, value["DB_IP"],
                    port_or_name, value["OBJECT_NAME"]
                ])
        context = {"message": u"查询成功", "errcode": 80052, "data": temp}
        return context

    def post(self, request):
        pass


class SqlReviewTaskPublish(BaseHandler):

    @staticmethod
    def run(**kwargs):
        """
        执行任务
        :return:
        """
        kwargs = kwargs.get('kwargs')
        themis = Themis(instance_name=kwargs.get('instance_name'),
                        username=kwargs.get('username'),
                        rule_type=kwargs.get('rule_type').upper(),
                        start_date=kwargs.get('start_date'),
                        stop_date=kwargs.get('stop_date'),
                        create_user=kwargs.get('create_user'))
        job_record = themis.run()
        themis.save_result(job_record)

    @temRes
    def post(self, request):
        kwargs = {
            'instance_name': request.POST.get('instance_name'),
            'username': request.POST.get('db_name'),
            'rule_type': request.POST.get('rule_type'),
            'start_date': request.POST.get('start_date'),
            'stop_date': request.POST.get('stop_date'),
            'create_user': request.user.display
        }

        # 非对象类型必须选择起止日期
        if kwargs['rule_type'] != 'obj':
            if not (kwargs['start_date'] and kwargs['stop_date']):
                context = {
                    "errcode": 80058,
                    "message": u"请分析选择起止日期"
                }
                return context

        async_task(self.run, kwargs=kwargs)

        context = {
            "errcode": 80058,
            "message": u"任务发布成功"
        }
        return context
