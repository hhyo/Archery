# -*- coding: UTF-8 -*-

import wtforms_json
import re

from wtforms import IntegerField, StringField, FloatField
from wtforms import TextAreaField, BooleanField, FieldList
from wtforms import FormField, FieldList
from wtforms.validators import ValidationError, Length, DataRequired
from wtforms import Form

"""
基于wtforms的验证类
"""


class BaseParms(Form):
    parm_desc = StringField("parm_desc")
    parm_name = StringField("parm_name")


class InputParms(BaseParms):
    parm_unit = StringField("parm_unit")
    parm_value = FloatField("parm_value")

    def validate_parm_value(form, field):
        if not field.data:
            raise ValidationError(u"输入参数值不正确")
        try:
            float(field.data)
        except ValueError:
            raise ValidationError(u"输入参数值不正确")


class BaseForm(Form):
    db_type = StringField("dbtype", [DataRequired()])
    max_score = FloatField("maxscore", [DataRequired(message=u"分值不正确")])
    rule_desc = TextAreaField(
        "rule_desc", [DataRequired(message=u"规则描述不正确"), Length(max=255)])
    rule_name = StringField(
        "rule_name", [DataRequired(message=u"规则名称不正确"), Length(max=50)])
    rule_summary = StringField("rule_summary",
                               [DataRequired(), Length(max=255)])
    rule_type = StringField("rule_type", [DataRequired()])
    weight = FloatField("rule_weight", [DataRequired()])
    rule_status = StringField("rule_status", [DataRequired()])
    rule_solution = TextAreaField(
        "solution", [DataRequired(message=u"解决方案必须有")])
    rule_complexity = StringField("rule_complexity", [DataRequired()])
    input_parms = FieldList(FormField(InputParms))
    output_parms = FieldList(FormField(BaseParms))
    exclude_obj_type = StringField("exclude_obj_type")

    def validate_db_type(form, field):
        if field.data not in ["O", "mysql"]:
            raise ValidationError(u"数据库类型不正确")

    def validate_max_score(form, field):
        if not field.data:
            raise ValidationError(u"分数不正确")
        try:
            float(field.data)
        except ValueError:
            raise ValidationError(u"分数不正确")

    def validate_weight(form, field):
        try:
            float(field.data)
        except ValueError:
            raise ValidationError(u"权重类型不正确")

    def validate_rule_type(form, field):
        if field.data not in ["OBJ", "TEXT", "SQLPLAN", "SQLSTAT"]:
            raise ValidationError(u"规则类型不正确")

    def validate_rule_status(form, field):
        if field.data not in ["ON", "OFF"]:
            raise ValidationError(u"规则状态不正确")

    def validate_rule_complexity(form, field):
        if field.data not in ["simple", "complex"]:
            raise ValidationError(u"规则复杂度不正确")


class SimpleForm(BaseForm):
    rule_cmd = StringField(
        "rule_cmd", [DataRequired(message=u"命令不能为空")])

    def validate_rule_cmd(form, field):
        db_key = ("\b(exec|execute|insert|select|delete|update|alter|create|"
                  "drop|count|chr|char|asc|mid|substring|master|truncate|"
                  "declare|xp_cmdshell|restore|backup|net)\b")
        mongo_key = r"""\b(update|delete|drop|remove|killcursors|dropdatabase
                        |dropindex|reindex|lock|unlock|fsync|setprofilingLevel
                        |repairDatabase|removeUser|shutdownServer|killOp|eval
                        |copyDatabase|cloneDatabase|addUser|setSlaveOk)\b"""
        regex = re.compile(mongo_key, re.I)
        m = regex.search(field.data)
        if m:
            raise ValidationError(u"有违法字符")


class ComplexForm(BaseForm):
    rule_cmd = StringField("rule_cmd", [DataRequired(message=u"命令不能为空")])

    def validate_rule_cmd(form, field):
        if field.data not in ["default"]:
            raise ValidationError(u"规则数据不正确")


if __name__ == "__main__":
    wtforms_json.init()
    data = {
        "db_type": "O",
        "rule_status": "ON",
        "max_score": 10,
        "rule_desc": u"测试",
        "rule_name": "test_rule",
        "rule_type": "OBJ",
        "rule_summary": "test",
        "rule_cmd": "delet",
        "rule_weight": 2,
        # "solution": "test xxxx",
        "rule_complexity": "simple",
        "rule_solution": "xxxxx",
        # "xxx": "test",
        "input_parms": [{
            "parm_desc": "test",
            "parm_name": "ddd",
            "parm_unit": "GB",
            "parm_value": "xxx"
        }],
        "output_parms": [{"parm_desc": "test", "parm_name": "ttt"}]
    }
    # form = ComplexForm.from_json(data)
    try:
        form = SimpleForm.from_json(data, skip_unknown_keys=False)
        print(form.data)
        print(form.validate())
        if not form.validate():
            print(form.errors)
    except wtforms_json.InvalidData as e:
        print(str(e))
