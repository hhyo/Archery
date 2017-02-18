# -*- coding: UTF-8 -*- 

class Const(object):
    workflowStatus = {
                        'finish': '已正常结束', 
                        'abort': '人工终止流程',
                        'autoreviewing': '自动审核中',
                        'manreviewing': '等待审核人审核',
                        'executing': '执行中',
                        'autoreviewwrong': '自动审核不通过',
                        'exception': '执行有异常',
                     }
