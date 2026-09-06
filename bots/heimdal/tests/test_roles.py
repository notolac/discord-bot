from discord_core.interactions import Interaction, Member, User
from heimdal.roles import (
    ApprovalKey,
    clicker_is_staff,
    parse_approval_button,
    parse_request_modal_id,
    parse_role_request_value,
)
from heimdal.settings import Settings


def _settings(**kwargs: str) -> Settings:
    defaults = {
        "discord_app_id": "2002",
        "discord_public_key": "00",
        "discord_bot_token": "t",
        "heimdal_member_role_id": "777",
        "heimdal_interest_roles": "Academia:333,Startups:802,Gaming:111",
        "heimdal_approver_role_ids": "900,901",
        "heimdal_organizer_role_id": "800",
        "heimdal_speaker_role_id": "801",
        "heimdal_startups_role_id": "802",
        "heimdal_enterprises_role_id": "803",
        "heimdal_denied_role_ids": "900,901,902,903",
        "discord_prod_guild_id": "3003",
    }
    defaults.update(kwargs)
    return Settings(**defaults, _env_file=None)  # type: ignore[arg-type, call-arg]


def test_interest_roles_drop_approval_denied_and_member_ids():
    roles = _settings().interest_roles()
    assert [r.role_id for r in roles] == ["333", "111"]


def test_member_role_on_denylist_is_not_assignable():
    settings = _settings(heimdal_member_role_id="900")
    assert settings.assignable_member_role_id() is None


def test_approval_map_skips_denied_and_duplicate_ids():
    settings = _settings(heimdal_organizer_role_id="900", heimdal_speaker_role_id="800")
    mapping = settings.approval_role_map()
    assert ApprovalKey.ORGANIZER not in mapping
    assert mapping[ApprovalKey.SPEAKER] == "800"


def test_everyone_guild_id_is_denied():
    assert "3003" in _settings().denied_role_ids()


def test_parse_helpers_reject_forged_keys():
    assert parse_role_request_value("organizer") is ApprovalKey.ORGANIZER
    assert parse_role_request_value("org") is ApprovalKey.ORGANIZER
    assert parse_role_request_value("moderator") is None
    assert parse_role_request_value("900") is None
    assert parse_request_modal_id("role_req_org") is ApprovalKey.ORGANIZER
    assert parse_request_modal_id("role_req_adm") is None
    assert parse_approval_button("role_ok_org_12") == (True, ApprovalKey.ORGANIZER, "12")
    assert parse_approval_button("role_ok_org_abc") is None
    assert parse_approval_button("role_ok_org_12_999") is None
    assert parse_approval_button("role_no_stu_99") == (False, ApprovalKey.STARTUPS, "99")


def test_clicker_is_staff_requires_member_and_role_or_permission():
    settings = _settings()
    member = Member(user=User(id="1", username="a"), roles=["111"], permissions="0")
    staff_role = Member(user=User(id="1", username="a"), roles=["900"], permissions="0")
    manage = Member(user=User(id="1", username="a"), roles=[], permissions=str(1 << 5))
    no_member = Interaction.model_validate(
        {
            "id": "1",
            "application_id": "2",
            "type": 3,
            "token": "t",
            "user": {"id": "1", "username": "a"},
            "data": {"custom_id": "x", "component_type": 2},
        }
    )
    with_member = Interaction.model_validate(
        {
            "id": "1",
            "application_id": "2",
            "type": 3,
            "token": "t",
            "guild_id": "3003",
            "member": member.model_dump(),
            "data": {"custom_id": "x", "component_type": 2},
        }
    )
    assert clicker_is_staff(no_member, settings) is False
    assert clicker_is_staff(with_member, settings) is False
    with_member.member = staff_role
    assert clicker_is_staff(with_member, settings) is True
    with_member.member = manage
    assert clicker_is_staff(with_member, settings) is True
