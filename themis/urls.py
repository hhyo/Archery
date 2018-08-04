# -*- coding: UTF-8 -*-
from django.urls import path
from themis import views

urlpatterns = [
    path('', views.SqlReRuleSetIndex.as_view()),
    path('sqlreview/rule/simple/addition', views.RuleSimpleAdditoin.as_view()),
    path('sqlreview/rule/complex/addition', views.RuleComplexAddition.as_view()),
    path('sqlreview/rule/addition', views.RuleAddition.as_view()),
    path('new/version/sql/review/rule/info/index', views.SqlReRuleSetInfoIndex.as_view()),
    path('sqlreview/rule/upload', views.RuleUpload.as_view()),
    path('sqlreview/rule/info', views.SqlReviewRuleInfo.as_view()),
    path('new/version/sql/review/get/struct', views.SqlReviewGetStruct.as_view()),
    path('new/version/sql/review/task/index', views.SqlReviewTaskIndex.as_view()),
    path('new/version/sql/review/job/data', views.SqlReviewJobData.as_view()),
    path('new/version/sql/review/task/rule/info', views.SqlReviewTaskRuleInfo.as_view()),
    path('new/version/sql/review/task/rule/detail/info', views.SqlReviewTaskRuleDetailInfo.as_view()),
    path('new/version/sql/review/task/rule/plan/info', views.SqlReviewTaskRulePlanInfo.as_view()),
    path('new/version/sql/review/task/rule/text/info', views.SqlReviewTaskRuleTextInfo.as_view()),
    path('new/version/sql/review/task/publish', views.SqlReviewTaskPublish.as_view()),

]
