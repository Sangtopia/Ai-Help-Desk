import pytest

from helpdesk import tools
from helpdesk.seed import build_database

DANA = "dana.whitfield@brightline.example"
TOM = "tom.becker@brightline.example"
AISHA = "aisha.khan@brightline.example"


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    path = tmp_path / "helpdesk.db"
    monkeypatch.setenv("HELPDESK_DB", str(path))
    build_database(path)


def test_lookup_user_returns_account_mailbox_and_devices():
    result = tools.lookup_user(DANA)
    assert result["ok"]
    assert result["user"]["is_vip"]
    assert result["account"]["status"] == "active"
    assert result["devices"] == ["BL-LT-0101"]


def test_lookup_user_is_case_insensitive_and_trims():
    assert tools.lookup_user("  Tom.Becker@Brightline.Example ")["user"]["user_id"] == 4


def test_lookup_unknown_user():
    assert not tools.lookup_user("nobody@brightline.example")["ok"]


def test_lookup_reports_nearly_full_mailbox():
    assert tools.lookup_user("mei.chen@brightline.example")["mailbox"]["percent_used"] > 99


def test_reset_password_on_locked_account_warns_to_unlock():
    result = tools.reset_password(4)
    assert result["ok"]
    assert result["must_change_password"]
    assert len(result["temporary_password"]) == 14
    assert "unlock_account" in result["note"]
    assert tools.lookup_user(TOM)["account"]["must_change_password"]


def test_reset_password_refuses_disabled_account():
    result = tools.reset_password(10)
    assert not result["ok"]
    assert "disabled" in result["error"]


def test_unlock_account():
    assert tools.unlock_account(4)["account_status"] == "active"
    account = tools.lookup_user(TOM)["account"]
    assert account["status"] == "active"
    assert account["failed_login_count"] == 0


def test_unlock_already_active_account_is_a_noop():
    assert tools.unlock_account(1)["note"] == "Account was not locked"


def test_unlock_refuses_disabled_account():
    assert not tools.unlock_account(10)["ok"]


def test_check_spam_quarantine_lists_newest_first_with_releasable_flag():
    messages = tools.check_spam_quarantine(AISHA)["messages"]
    assert [m["message_id"] for m in messages] == ["Q-1001", "Q-1003", "Q-1002"]
    assert {m["message_id"]: m["releasable"] for m in messages} == {"Q-1001": True, "Q-1003": False, "Q-1002": True}


def test_release_email_removes_it_from_quarantine():
    assert tools.release_email("Q-1001")["ok"]
    remaining = [m["message_id"] for m in tools.check_spam_quarantine(AISHA)["messages"]]
    assert "Q-1001" not in remaining
    assert not tools.release_email("Q-1001")["ok"]


@pytest.mark.parametrize("message_id", ["Q-1003", "Q-1005"])
def test_release_email_refuses_phishing_and_malware(message_id):
    result = tools.release_email(message_id)
    assert not result["ok"]
    assert "security team" in result["error"]


def test_device_with_low_disk():
    result = tools.check_device_status("bl-lt-0106")
    assert result["online"]
    assert result["assigned_to"] == "leo.martins@brightline.example"
    assert any("Low disk" in w for w in result["warnings"])


def test_device_with_stale_checkin():
    result = tools.check_device_status("BL-LT-0107")
    assert not result["online"]
    assert any("No check-in for 12 days" in w for w in result["warnings"])


def test_printer_has_no_disk_info():
    result = tools.check_device_status("BL-PR-FL2")
    assert result["kind"] == "printer"
    assert not result["online"]
    assert "disk" not in result
    assert result["warnings"] == []


def test_unknown_device():
    assert not tools.check_device_status("BL-LT-9999")["ok"]


def test_escalate_to_tier2():
    result = tools.escalate_to_tier2("T-42", "VPN fails after reset; logs attached")
    assert result["ok"]
    assert result["escalation_id"] == 1


def test_escalate_requires_summary():
    assert not tools.escalate_to_tier2("T-42", "   ")["ok"]


def test_normal_signins_are_inside_usual_hours():
    result = tools.check_signin_logs(1)
    assert result["summary"]["locations"] == ["New York, US"]
    assert not any(s["outside_usual_hours_home"] for s in result["signins"])


def test_early_shift_worker_is_not_flagged():
    signins = tools.check_signin_logs(8)["signins"]
    assert signins and all(s["home_time"].endswith("06:16") for s in signins)
    assert not any(s["outside_usual_hours_home"] for s in signins)


def test_travelling_user_is_odd_at_home_but_normal_where_they_are():
    lisbon = [s for s in tools.check_signin_logs(6)["signins"] if s["location"] == "Lisbon, PT"]
    assert len(lisbon) == 3
    assert all(s["outside_usual_hours_home"] and not s["outside_usual_hours_location"] for s in lisbon)
    assert all(s["result"] == "success" and s["network"] == "residential" for s in lisbon)


def test_compromised_user_shows_denied_pushes_from_hosting_network():
    result = tools.check_signin_logs(2)
    assert result["summary"]["mfa_denied"] == 3
    assert result["summary"]["hosting_network_signins"] == 4
    latest = result["signins"][0]
    assert latest["location"] == "Singapore, SG"
    assert latest["home_time"].endswith("04:14")
    assert latest["result"] == "success"


def test_locked_user_has_recent_failed_passwords():
    assert tools.check_signin_logs(4)["summary"]["failed_password"] == 5


def test_signin_logs_unknown_user():
    assert not tools.check_signin_logs(999)["ok"]


def test_mfa_status():
    assert tools.check_mfa_status(1)["enrolled"]
    assert not tools.check_mfa_status(12)["enrolled"]
    assert not tools.check_mfa_status(999)["ok"]


def test_block_sign_in_also_removes_vpn_access():
    assert tools.block_sign_in(2, "4 AM sign-in from Singapore after denied Duo pushes")["ok"]
    account = tools.lookup_user("marcus.reyes@brightline.example")["account"]
    assert account["sign_in_blocked"] and not account["vpn_access"]
    assert tools.block_sign_in(2, "again")["note"] == "Sign-in was already blocked"


def test_block_sign_in_requires_reason_and_active_account():
    assert not tools.block_sign_in(2, " ")["ok"]
    assert not tools.block_sign_in(10, "probing")["ok"]
