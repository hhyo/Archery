from pytest_django.asserts import assertTemplateUsed, assertContains

from sql.utils.workflow_audit import AuditV2


def test_get_sql_workflow(
    sql_workflow,
    fake_generate_audit_setting,
    super_user,
    admin_client,
    create_auth_group,
):
    sql_workflow, _ = sql_workflow
    audit = AuditV2(workflow=sql_workflow)
    audit.create_audit()
    audit.workflow.status = "workflow_manreviewing"
    audit.workflow.save()
    response = admin_client.get(f"/detail/{sql_workflow.id}/")
    assert response.status_code == 200
    assertTemplateUsed(response, "detail.html")
    # 展示审批人用户名
    assert (
        response.context["current_audit_auth_group"]
        == f"{create_auth_group.name}: {super_user.username}"
    )
