# -*- coding: utf-8 -*-

import os
import sys


class Rule(object):

    def __init__(self, client, rule_dir=None):
        if not rule_dir:
            self.dir = ["obj", "plan_stat", "text"]
        else:
            self.dir = rule_dir
        self.client = client

    def rule_init(self):
        for directory in self.dir:
            rule_insert(directory)

    def rule_append(self):
        pass

    def rule_reset(self):
        self.rule_init()

    def rule_insert(self, directory):
        file = os.walk(directory)
        for filename in file[2]:
            name = filename.split(".")
            if name[1] == "py":
                func = self.import_module(directory, name[0])
                if hasattr(func, "rule"):
                    rule = func.rule
                    record = self.client.get_collection("rule").find(
                        {"rule_name": rule["rule_name"]})
                    if not record:
                        self.client.get_collection("rule").insert_one(rule)

    def import_module(self, module_name, func_name):
        if not sys.modules.get(module_name):
            module = __import__(module_name)
        return getattr(module, func_name)

    def rule_exec(self, rule_type, rule_list, **kwargs):
        extend_rule_list = get_filename("extend_rule")
        if rule_type in ["sqlplan", "sqlstat"]:
            file_list = get_filename("sqlplan")
        elif rule_type in ["obj", "text"]:
            file_list = get_filename(rule_type)

        for rule in rule_list:
            if rule in file_list:
                func_exec = import_module(rule_type, "execute_rule")
            elif rule in extend_rule_list:
                func_exec = import_module("extend_rule", "execute_rule")
        func_exec(**kwargs)

    def list_file(self, path):
        try:
            name_list = os.walk(path)
            return name_list.next()[2]
        except StopIteration:
            pass

    def get_filename(self, path):
        file_list = self.list_file(path)
        filename_list = []
        for name in file_list:
            if "." in name:
                name_split = name.split(".")
                if name_split[1] == "py":
                    filename_list.append(name_split[0])
        return filename_list
