# CHAgent Development Skill

This skill provides guidance for developing the Cherry Hills Worship Arts Team Portal (Aria).

## Quick Reference

| Task | Key Files |
|------|-----------|
| Add AI query type | `core/agent.py` |
| New model | `core/models.py` |
| New view | `core/views.py`, `core/urls.py` |
| Multi-tenant decorator | `core/middleware.py` |
| Planning Center API | `core/planning_center.py` |
| Templates | `templates/core/` |

---

## Multi-Tenant Development

**CRITICAL**: All data must be scoped to an organization. Every tenant-aware model must have:

```python
organization = models.ForeignKey(
    'Organization',
    on_delete=models.CASCADE,
    related_name='model_names'
)
```

### View Pattern (Function-Based)

```python
from django.contrib.auth.decorators import login_required
from core.middleware import require_organization, require_permission

@login_required
@require_organization
def my_view(request):
    # Always filter by organization
    items = MyModel.objects.filter(organization=request.organization)
    return render(request, 'template.html', {'items': items})
```

### View Pattern (Class-Based)

```python
from core.middleware import OrganizationContextMixin

class MyView(OrganizationContextMixin, ListView):
    model = MyModel
    # get_queryset() automatically filters by organization
```

### Permission Decorators

```python
@require_permission('can_manage_users')  # Check specific permission
@require_role('owner', 'admin')          # Check role membership
```

### Common Mistake - NEVER do this:

```python
# WRONG - returns ALL organizations' data
items = MyModel.objects.all()

# CORRECT - scoped to current organization
items = MyModel.objects.filter(organization=request.organization)
```

---

## Adding New AI Query Types to Aria

Location: `core/agent.py`

### Step 1: Add Detection Function

Create a detection function following this pattern:

```python
def is_my_new_query(message: str) -> Tuple[bool, str]:
    """
    Detect if message is asking about [topic].

    Returns:
        Tuple of (is_match, query_subtype)
    """
    message_lower = message.lower().strip()

    patterns = {
        'subtype_a': [
            r'pattern\s+one',
            r'pattern\s+two',
        ],
        'subtype_b': [
            r'another\s+pattern',
        ],
    }

    for subtype, pattern_list in patterns.items():
        for pattern in pattern_list:
            if re.search(pattern, message_lower):
                logger.info(f"Query pattern matched: '{subtype}' for: '{message[:50]}...'")
                return True, subtype

    return False, None
```

### Step 2: Add Handler in query_agent()

In the `query_agent()` function, add handling logic:

```python
# Check for new query type
is_my_query, query_subtype = is_my_new_query(message)
if is_my_query:
    result = handle_my_query(message, query_subtype, organization)
    return format_my_query_response(result)
```

### Step 3: Add Formatter (if needed)

```python
def format_my_query_response(data: dict) -> str:
    """Format the query response for display."""
    if not data:
        return "I couldn't find that information."

    lines = []
    lines.append(f"**{data['title']}**\n")
    # ... format the rest
    return '\n'.join(lines)
```

### Existing Query Types for Reference

| Function | Detects |
|----------|---------|
| `is_aggregate_question()` | Team-wide queries (food, hobbies, prayer, etc.) |
| `is_analytics_query()` | Analytics/reporting requests |
| `is_pco_data_query()` | Contact info, birthdays, teams |
| `is_song_or_setlist_query()` | Songs, setlists, chord charts, lyrics |
| `is_blockout_query()` | Availability and blockout dates |
| `check_ambiguous_song_or_person()` | Disambiguation needed |

---

## Creating New Models

### Standard Tenant-Scoped Model

```python
class MyNewModel(models.Model):
    """Description of the model."""

    # REQUIRED: Organization scope
    organization = models.ForeignKey(
        'Organization',
        on_delete=models.CASCADE,
        related_name='my_new_models'
    )

    # Common fields
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_my_new_models'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Your fields
    name = models.CharField(max_length=200)
    # ...

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'My New Model'
        verbose_name_plural = 'My New Models'

    def __str__(self):
        return self.name
```

### After Creating Model

```bash
# Create migration
python manage.py makemigrations

# Review migration file in core/migrations/

# Apply migration
python manage.py migrate

# Register in admin (optional)
# Add to core/admin.py:
# @admin.register(MyNewModel)
# class MyNewModelAdmin(admin.ModelAdmin):
#     list_display = ['name', 'organization', 'created_at']
#     list_filter = ['organization']
```

---

## Planning Center API Integration

Location: `core/planning_center.py`

### Adding New PCO Endpoints

Two API classes exist:
- `PlanningCenterAPI` - People data
- `PlanningCenterServicesAPI` - Services, songs, schedules

```python
def get_new_resource(self, resource_id: str) -> dict:
    """
    Fetch [resource] from Planning Center.

    Args:
        resource_id: The PCO resource ID

    Returns:
        Resource data dict or None
    """
    try:
        response = self._request(
            'GET',
            f'/services/v2/new_resource/{resource_id}'
        )
        return response.get('data', {})
    except Exception as e:
        logger.error(f"Error fetching resource {resource_id}: {e}")
        return None
```

### PCO Rate Limiting

- Add 0.5s delay every 20 requests for bulk operations
- Scope queries to team members when possible (vs all 517+ people)
- Use caching for frequently accessed data

---

## Conversation Context

Location: `core/models.py` - `ConversationContext`

The context tracks state across messages:

| Field | Purpose |
|-------|---------|
| `shown_interaction_ids` | Deduplication - don't show same interaction twice |
| `discussed_volunteer_ids` | Track who's being discussed |
| `pending_song_suggestions` | Song selection in progress |
| `pending_disambiguation` | Waiting for user to clarify (song vs person) |
| `pending_followup` | Follow-up creation in progress |
| `pending_date_lookup` | Date confirmation needed |
| `message_count` | Triggers summarization at 15+ messages |

### Using Context in Agent

```python
def get_or_create_context(session_id: str) -> ConversationContext:
    context, created = ConversationContext.objects.get_or_create(
        session_id=session_id,
        defaults={'shown_interaction_ids': [], 'discussed_volunteer_ids': []}
    )
    return context

# Mark interactions as shown
context.shown_interaction_ids.append(interaction.id)
context.save()
```

---

## Common Development Commands

```bash
# Run development server
python manage.py runserver

# Create migrations
python manage.py makemigrations

# Apply migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Django shell
python manage.py shell

# Check for issues
python manage.py check

# Collect static files (for production)
python manage.py collectstatic --noinput
```

---

## Push Notifications

Location: `core/notifications.py`

### Sending Notifications

```python
from core.notifications import send_notification_to_user, notify_task_assignment

# Generic notification
send_notification_to_user(
    user=user,
    notification_type='custom',
    title='Title Here',
    body='Message body',
    url='/path/to/resource/',
    priority='normal'  # or 'high'
)

# Use pre-built helpers when available
notify_task_assignment(task, user)
notify_new_dm(message)
notify_channel_message(message, mentioned_users)
```

### Notification Types

`announcement`, `dm`, `channel`, `care`, `followup`, `project`, `task`

---

## Template Patterns

### HTMX Partial Updates

```html
<!-- Trigger HTMX request -->
<button hx-post="{% url 'action_url' %}"
        hx-target="#target-div"
        hx-swap="innerHTML">
    Action
</button>

<!-- Target for updates -->
<div id="target-div">
    {% include 'core/partials/content.html' %}
</div>
```

### Organization Context in Templates

```html
<!-- Available via context processor -->
{{ organization.name }}
{{ organization.ai_assistant_name }}  <!-- Usually "Aria" -->
{{ membership.role }}
{{ membership.can_manage_users }}
```

---

## Testing Checklist

When adding new features:

- [ ] Model has `organization` ForeignKey
- [ ] Views filter by `request.organization`
- [ ] Views use `@require_organization` decorator
- [ ] Queries don't leak data across tenants
- [ ] PCO queries scoped to avoid rate limits
- [ ] Logging added for debugging (`logger.info/warning/error`)
- [ ] Templates handle empty states gracefully
