from tw_alpha_scraper.permissions import AccessPolicy


def test_access_policy_allows_admin_channel():
    policy = AccessPolicy(admin_channel_id=10, admin_role_ids=(20,))
    assert policy.is_allowed(channel_id=10, role_ids=[], manage_guild=False) is True


def test_access_policy_allows_admin_role():
    policy = AccessPolicy(admin_channel_id=None, admin_role_ids=(20,))
    assert policy.is_allowed(channel_id=11, role_ids=[19, 20], manage_guild=False) is True


def test_access_policy_falls_back_to_manage_guild():
    policy = AccessPolicy()
    assert policy.is_allowed(channel_id=11, role_ids=[], manage_guild=True) is True
    assert policy.is_allowed(channel_id=11, role_ids=[], manage_guild=False) is False
