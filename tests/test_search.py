from django.utils.safestring import SafeString
from core.search import snippet


def test_snippet_highlights_match_case_insensitive():
    out = snippet("We moved the Easter set to G", "easter")
    assert '<mark>Easter</mark>' in out
    assert isinstance(out, SafeString)


def test_snippet_escapes_html():
    out = snippet("<script>alert(1)</script> easter", "easter")
    assert '<script>' not in out
    assert '&lt;script&gt;' in out
    assert '<mark>easter</mark>' in out


def test_snippet_windows_long_text():
    text = "x" * 500 + " easter " + "y" * 500
    out = snippet(text, "easter")
    assert 'easter' in out.lower()
    assert len(out) < 500
    assert '…' in out


import pytest
from django.urls import reverse
from accounts.models import User
from core.models import (Organization, SubscriptionPlan, OrganizationMembership, Project, Task,
                         TaskComment, Channel, ChannelMessage, DirectMessage, Announcement,
                         ProjectDiscussion, ProjectDiscussionMessage)
from core.search import unified_search


@pytest.fixture
def world(db):
    plan = SubscriptionPlan.objects.create(slug='s-search', name='S', tier='team')
    org = Organization.objects.create(name='Org', email='o@x.org', slug='org-search',
                                      subscription_plan=plan, subscription_status='active')
    other_org = Organization.objects.create(name='Other', email='o2@x.org', slug='other-search',
                                            subscription_plan=plan, subscription_status='active')
    alice = User.objects.create_user(username='alice@x.org', email='alice@x.org', password='supersecret1')
    bob = User.objects.create_user(username='bob@x.org', email='bob@x.org', password='supersecret1')
    for u in (alice, bob):
        OrganizationMembership.objects.create(user=u, organization=org, role='member')
        u.default_organization = org; u.save()
    return dict(org=org, other_org=other_org, alice=alice, bob=bob)


@pytest.mark.django_db
def test_finds_matches_across_surfaces_for_member(world):
    org, alice = world['org'], world['alice']
    proj = Project.objects.create(organization=org, name='Easter project', owner=alice)
    proj.members.add(alice)
    task = Task.objects.create(organization=org, project=proj, title='Easter worship set', created_by=alice)
    TaskComment.objects.create(task=task, author=alice, content='moved easter set to G')
    chan = Channel.objects.create(organization=org, name='production', slug='production', is_private=False)
    ChannelMessage.objects.create(channel=chan, author=alice, content='easter set list ready?')
    Announcement.objects.create(organization=org, title='Easter service', content='plan')
    disc = ProjectDiscussion.objects.create(organization=org, project=proj, title='Easter service plan', created_by=alice)
    ProjectDiscussionMessage.objects.create(discussion=disc, author=alice, content='easter logistics')

    res = unified_search(org, alice, 'easter')
    assert len(res['projects']) == 1
    assert len(res['tasks']) == 1
    assert len(res['task_comments']) == 1
    assert len(res['channel_messages']) == 1
    assert len(res['announcements']) == 1
    assert len(res['discussions']) >= 1
    # result shape + deep link
    assert res['tasks'][0]['url'] == reverse('task_detail', args=[proj.id, task.id])
    assert res['channel_messages'][0]['url'] == reverse('channel_detail', args=[chan.slug])


@pytest.mark.django_db
def test_short_query_and_org_isolation(world):
    org, other_org, alice = world['org'], world['other_org'], world['alice']
    Announcement.objects.create(organization=other_org, title='Easter elsewhere', content='x')
    assert unified_search(org, alice, 'e') == {k: [] for k in unified_search(org, alice, 'e')}  # <2 chars -> empty
    res = unified_search(org, alice, 'easter')
    assert res['announcements'] == []  # other org's announcement not visible


@pytest.mark.django_db
def test_private_channel_not_leaked(world):
    org, alice, bob = world['org'], world['alice'], world['bob']
    priv = Channel.objects.create(organization=org, name='leaders', slug='leaders', is_private=True)
    priv.members.add(alice)  # bob is NOT a member
    ChannelMessage.objects.create(channel=priv, author=alice, content='easter secret')
    assert len(unified_search(org, alice, 'easter')['channel_messages']) == 1
    assert unified_search(org, bob, 'easter')['channel_messages'] == []


@pytest.mark.django_db
def test_dm_only_for_participants(world):
    org, alice, bob = world['org'], world['alice'], world['bob']
    carol = User.objects.create_user(username='carol@x.org', email='carol@x.org', password='supersecret1')
    OrganizationMembership.objects.create(user=carol, organization=org, role='member')
    DirectMessage.objects.create(sender=alice, recipient=bob, content='easter plan')
    assert len(unified_search(org, alice, 'easter')['direct_messages']) == 1
    assert len(unified_search(org, bob, 'easter')['direct_messages']) == 1
    assert unified_search(org, carol, 'easter')['direct_messages'] == []  # not a participant


@pytest.mark.django_db
def test_project_content_not_leaked_to_non_member(world):
    org, alice, bob = world['org'], world['alice'], world['bob']
    proj = Project.objects.create(organization=org, name='Private plan', owner=alice)
    proj.members.add(alice)  # bob not a member
    task = Task.objects.create(organization=org, project=proj, title='Easter rehearsal', created_by=alice)
    TaskComment.objects.create(task=task, author=alice, content='easter notes')
    a = unified_search(org, alice, 'easter')
    assert len(a['tasks']) == 1 and len(a['task_comments']) == 1
    b = unified_search(org, bob, 'easter')
    assert b['tasks'] == [] and b['task_comments'] == []
