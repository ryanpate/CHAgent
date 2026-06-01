# Unified Communication Search — Design Spec

**Date:** 2026-06-01
**Status:** Approved (design), pending implementation plan
**Author:** Ryan Pate + Claude

## Goal

Let team members find any past conversation or work item from one search box — across task
comments, project discussions, channel messages, direct messages, announcements, plus task
and project titles. This directly attacks the team's #1 Todoist pain point: in-project
communication getting lost because there's no way to search across surfaces (today only
Aria-chat-history search and member search exist).

## Decisions (locked)

| Decision | Choice |
|---|---|
| Scope | Communication surfaces (task comments, project discussions, channel messages, DMs, announcements) **plus** task titles/descriptions and project names |
| Entry point | A search input in the top nav on every authenticated page → GET `/search/?q=` results page |
| Results UX | Grouped by type with counts + filter tabs (`?type=`); each row deep-links to the source with a highlighted snippet |
| Search tech | Case-insensitive `icontains` (portable across the SQLite test DB and Postgres prod); recency-ordered, capped per type. **Not** Postgres FTS (would break the SQLite test suite) |
| Access control | Mirror the existing per-surface list-view visibility exactly — search never reveals anything the user can't already see |

## Out of Scope (YAGNI)

- No volunteers / songs / Planning Center / Knowledge-Base search (different data, some via embeddings).
- No command palette / as-you-type overlay.
- No full-text ranking, stemming, or fuzzy matching.
- No saved searches or search history.

## Context (verified)

Existing per-surface visibility (from the current list views — search MUST reuse these):
- **Projects** (`project_list`): `Q(owner=user) | Q(members=user)`, org-scoped.
- **Channels** (`channel_list`): `Q(is_private=False) | Q(members=user)`, org-scoped.
- **Direct messages**: `DirectMessage` has `sender` and `recipient` FKs → user sees rows where `sender=user OR recipient=user`.
- **Announcements**: org-wide (all members).

Models: `Task` (FK `project`), `TaskComment` (FK `task`, text `content`), `ProjectDiscussion`
(FK `project`, `title`) + `ProjectDiscussionMessage`, `ChannelMessage` (FK `channel`, text
`content`), `DirectMessage` (text `content`), `Announcement` (`title` + `content`), `Project`
(`name`, `description`), `Channel` (`is_private`, `members`).

Deep-link URL names: `task_detail(project_pk, pk)`, `channel_detail(slug)`,
`dm_conversation(user_id)`, `announcement_detail(pk)`, `project_detail(pk)`. The project-
discussion detail URL must be confirmed during implementation (link to the discussion view,
or `project_detail` with an anchor if no dedicated route exists).

---

## A. Search service — `core/search.py`

A single focused module, kept out of the view for isolated testing.

```
unified_search(organization, user, query, type=None, limit_per_type=20) -> SearchResults
```

- Returns results grouped by surface key: `projects`, `tasks`, `task_comments`,
  `discussions`, `channel_messages`, `direct_messages`, `announcements`. Each item is a
  normalized dict: `{type, title, snippet, url, author, when}` so the template renders all
  result types uniformly.
- Each surface is queried independently with `icontains` on its text field(s), filtered by
  `organization` AND the access rule in §B, ordered by `-created_at`, sliced to
  `limit_per_type`. When `type` is provided, only that surface is queried (used by the
  "view all" filter tabs, which may use a higher/uncapped limit with simple pagination).
- A `snippet(text, query)` helper extracts a ~160-char window around the first match and
  highlights the matched term. It must HTML-escape the source text first, then wrap matches
  in `<mark>` (return a safe string) so no user content can inject markup.
- Query shorter than 2 characters returns empty results (the view shows a prompt).

Each surface should `select_related`/`values` the fields needed for title/author/url to
avoid N+1 queries when building results.

## B. Access control (security-critical)

Reuse the exact visibility filters from the list views:

| Surface | Filter |
|---|---|
| Projects | `organization=org AND (owner=user OR members=user)` |
| Tasks, TaskComments | belongs to a project the user owns or is a member of (join via `task.project`), org-scoped |
| Project discussions + messages | project the user owns or is a member of, org-scoped |
| Channels, ChannelMessages | `organization=org AND (channel.is_private=False OR channel.members=user)` |
| Direct messages | `sender=user OR recipient=user` |
| Announcements | `organization=org` |

A user must never see a private channel's messages they aren't a member of, a DM they aren't
party to, or tasks/comments/discussions in a project they aren't on. Use `.distinct()` where
`members` joins can duplicate rows.

## C. View + UX

- **View** `search` at `/search/?q=<query>&type=<surface>`: `@login_required`, requires
  organization (`request.organization`). Reads `q`; if `len(q.strip()) < 2`, renders the page
  with a "type at least 2 characters" prompt and no results. Otherwise calls `unified_search`
  (passing `type` when a filter tab is active) and renders `search_results.html`.
- **Header input**: add a search `<form method="get" action="{% url 'search' %}">` with a text
  input named `q` to the top nav in `base.html`, shown on authenticated pages. Respects the
  existing mobile/app-mode nav patterns.
- **Results page** `templates/core/search_results.html`:
  - Shows the query and a total count.
  - Filter tabs: All / Tasks / Comments / Discussions / Channels / Messages / Announcements,
    each linking to `?q=<query>&type=<surface>` (All omits `type`). Active tab highlighted.
  - Grouped sections (in "All" view) each with a heading + count and up to `limit_per_type`
    rows; if a surface has more, a "View all N" link sets `?type=`.
  - Each row: title (deep link to source), highlighted snippet, author, relative date.
  - Empty state when no matches; prompt state when query too short.
  - Dark-theme styling consistent with the app.

## D. Tech

- `icontains` matching; portable across SQLite (tests) and Postgres (prod).
- Order each surface by `-created_at`; cap at `limit_per_type` (default 20) in grouped view.
- The `type`-filtered view uses a higher cap (100) and shows a "showing first 100" note if
  truncated. No pagination in v1 (YAGNI).
- Rationale for not using Postgres full-text search: the test suite runs on SQLite, where
  `SearchVector`/`__search`/`pg_trgm` are unavailable; `icontains` is adequate at a worship
  team's data scale.

## Testing / Success Criteria

- **Service unit tests:** a matching term is found in each surface (task comment, project
  discussion message, channel message, DM, announcement, task title, project name); results
  carry correct `url`/`title`/`author`; org isolation (no cross-org matches); `<2`-char query
  returns empty; snippet highlights and escapes.
- **Access-control tests (the security core):**
  - User not a member/owner of a project gets none of its tasks, task comments, or discussions.
  - User not a member of a private channel gets none of its messages; public-channel messages
    are returned for any org member.
  - User not party to a DM never sees it; both participants do.
  - Announcements returned for any org member.
- **View tests:** grouped rendering with counts; `?type=` filter narrows to one surface;
  min-length prompt; empty state; the nav search input is present on an authenticated page.
- Full existing suite stays green (currently 831 passing).

## User Actions

None.
