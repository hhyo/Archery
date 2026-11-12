"""Object permissions for direct and unified workflow detail pages."""

import pytest
from django.contrib.auth.models import Group, Permission

from common.utils.const import WorkflowStatus, WorkflowType
from sql.models import ResourceGroup, WorkflowAudit


@pytest.fixture
def detail_records(sql_query_apply, archive_apply):
    review_group = Group.objects.create(name="detail_reviewers")
    records = {}
    for kind, record, workflow_type in (
        ("query", sql_query_apply, WorkflowType.QUERY),
        ("archive", archive_apply, WorkflowType.ARCHIVE),
    ):
        record.user_name = "test_user"
        record.save(update_fields=["user_name"])
        audit = WorkflowAudit.objects.create(
            group_id=1,
            group_name="group_name",
            workflow_id=record.pk,
            workflow_type=workflow_type,
            workflow_title="private detail regression",
            audit_auth_groups=str(review_group.pk),
            current_audit=str(review_group.pk),
            next_audit="-1",
            current_status=WorkflowStatus.WAITING,
            create_user="test_user",
        )
        direct = (
            f"/queryapplydetail/{record.pk}/"
            if kind == "query"
            else f"/archive/{record.pk}/"
        )
        records[kind] = (record, direct, f"/workflow/{audit.pk}/")
    return records


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("kind", ["query", "archive"])
@pytest.mark.parametrize("entry", [1, 2], ids=["direct", "unified"])
@pytest.mark.parametrize(
    "role,expected",
    [
        ("unrelated", 403),
        ("member", 403),
        ("owner", 200),
        ("owner_reviewer_outside_group", 200),
        ("reviewer_same_group", 200),
        ("reviewer_other_group", 403),
        ("reviewer_no_group", 403),
        ("wrong_reviewer", 403),
        ("auditor", 200),
        ("superuser", 200),
    ],
)
def test_detail_object_permissions(
    client, normal_user, detail_records, kind, entry, role, expected
):
    record, direct, unified = detail_records[kind]
    user = normal_user
    if role not in ("owner", "owner_reviewer_outside_group"):
        user.username = "other_user"
    user.is_superuser = role == "superuser"
    user.save()

    review = "query_review" if kind == "query" else "archive_review"
    if role == "wrong_reviewer":
        review = "archive_review" if kind == "query" else "query_review"
    if "reviewer" in role:
        user.user_permissions.add(
            Permission.objects.get(content_type__app_label="sql", codename=review)
        )
    if role == "auditor":
        user.user_permissions.add(
            Permission.objects.get(content_type__app_label="sql", codename="audit_user")
        )
    if role in ("member", "reviewer_same_group", "wrong_reviewer"):
        user.resource_group.add(ResourceGroup.objects.get(group_id=1))
    elif role in ("reviewer_other_group", "owner_reviewer_outside_group"):
        user.resource_group.add(ResourceGroup.objects.create(group_name="other"))

    client.force_login(user)
    response = client.get(direct if entry == 1 else unified)
    assert response.status_code == expected
    if expected == 200:
        key = "workflow_detail" if kind == "query" else "archive_config"
        assert response.context[key].pk == record.pk
        template = "queryapplydetail.html" if kind == "query" else "archivedetail.html"
        assert template in [t.name for t in response.templates]
    else:
        assert "private detail regression" not in response.content.decode()


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("kind", ["query", "archive"])
@pytest.mark.parametrize("entry", [1, 2], ids=["direct", "unified"])
def test_detail_requires_login(client, detail_records, kind, entry):
    response = client.get(detail_records[kind][entry])
    assert response.status_code == 302
    assert response.url == "/login/"
