# Platform Admin Dashboard

The Platform Admin Dashboard provides superadmins with comprehensive tools to monitor and manage all organizations, users, subscriptions, and usage metrics across the entire Aria platform.

## Quick Start

### 1. Run Migrations

First, apply the database migration to add the `is_superadmin` field:

```bash
python3 manage.py migrate
```

### 2. Create a Superadmin User

Promote an existing user to superadmin:

```bash
# Using username
python3 manage.py make_superadmin admin

# Using email
python3 manage.py make_superadmin admin@example.com

# Or specify explicitly
python3 manage.py make_superadmin --username admin
python3 manage.py make_superadmin --email admin@example.com
```

### 3. List Current Superadmins

```bash
python3 manage.py make_superadmin --list
```

### 4. Remove Superadmin Status

```bash
python3 manage.py make_superadmin --remove admin
```

### 5. Access the Dashboard

Navigate to: **`/platform-admin/`**

Only users with `is_superadmin=True` can access this section.

---

## Features

### 📊 Overview Dashboard (`/platform-admin/`)

**Key Metrics:**
- Total organizations (active, trial, past due, cancelled)
- Monthly Recurring Revenue (MRR) & Annual Recurring Revenue (ARR)
- Total users and active users (30 days)
- AI query usage across all organizations

**Displays:**
- Subscription plan distribution chart
- Recent signups (last 30 days)

### 🏢 Organizations List (`/platform-admin/organizations/`)

**Features:**
- View all organizations with usage metrics
- Filter by subscription status (active, trial, past_due, cancelled, suspended)
- Filter by subscription plan
- Search by name, slug, or email
- Sort by creation date

**Metrics Shown:**
- Member count
- Volunteer count
- Interaction count
- Subscription plan and status

**Quick Actions:**
- View organization details
- Impersonate organization (for support)

### 🔍 Organization Detail (`/platform-admin/organizations/<id>/`)

**Information Displayed:**
- Basic info (slug, email, phone, timezone, created date)
- Subscription details (plan, status, trial dates, Stripe IDs)
- AI query usage
- Usage statistics (volunteers, interactions, chat messages, follow-ups, announcements, channels, projects, tasks)
- Recent activity (last 30 days)
- Team members with roles and last login

**Admin Actions:**
- Update subscription status
- Impersonate organization

### 👥 Organization Impersonation

**Purpose:** Support debugging and customer support

**How it Works:**
1. Click "Impersonate" on any organization
2. Session switches to that organization's context
3. View the platform as if you're a member of that organization
4. Yellow "Exit Impersonation" button appears in admin nav
5. Click to return to admin dashboard

**Security:** Only superadmins can impersonate. Session is clearly marked.

### 💰 Revenue Analytics (`/platform-admin/revenue/`)

**Metrics:**
- MRR (Monthly Recurring Revenue)
- ARR (Annual Recurring Revenue)
- Average revenue per organization
- Active subscription count

**Growth Metrics:**
- New subscriptions (last 30 days)
- Churned organizations (last 30 days)
- Monthly churn rate

**Revenue Breakdown:**
- Revenue by subscription plan
- Percentage of total MRR per plan

### 📈 Usage Analytics (`/platform-admin/usage/`)

**User Activity:**
- Total users (all time)
- Active users (7 days)
- Active users (30 days)

**AI Usage:**
- Total AI queries this month
- Top organizations by AI usage

**Feature Adoption:**
- Percentage of organizations using each feature:
  - Volunteers
  - Interactions
  - Follow-ups
  - Channels
  - Projects

### 👤 Users List (`/platform-admin/users/`)

**Features:**
- List all platform users
- Search by username, email, or display name
- View organization count per user
- See last login and join date
- Identify superadmins

---

## URL Structure

| URL | View | Purpose |
|-----|------|---------|
| `/platform-admin/` | Overview Dashboard | Key platform metrics |
| `/platform-admin/organizations/` | Organizations List | Browse all orgs with filters |
| `/platform-admin/organizations/<id>/` | Organization Detail | Detailed org view |
| `/platform-admin/organizations/<id>/impersonate/` | Impersonate | Support tool |
| `/platform-admin/organizations/<id>/update-status/` | Update Status | Change subscription status |
| `/platform-admin/exit-impersonation/` | Exit Impersonation | Return to admin |
| `/platform-admin/revenue/` | Revenue Analytics | Financial metrics |
| `/platform-admin/usage/` | Usage Analytics | Feature adoption & usage |
| `/platform-admin/users/` | Users List | All platform users |

---

## Security

### Access Control

- **Decorator:** `@require_superadmin` on all admin views
- **Middleware:** `/platform-admin/` URLs excluded from organization context requirements
- **Permission Check:** Only `user.is_superadmin == True` can access

### Impersonation Safety

- Impersonation status stored in session with clear flag
- Yellow banner shows when impersonating
- Easy one-click exit
- Never sent to external systems (Stripe, PCO, etc.)

---

## Database Schema

### User Model Addition

```python
class User(AbstractUser):
    is_superadmin = models.BooleanField(
        default=False,
        help_text="Platform administrator with access to all organizations"
    )
```

### Migration

File: `accounts/migrations/0003_add_is_superadmin.py`

---

## Common Tasks

### Make the First Superadmin

```bash
# Create a user if needed
python3 manage.py createsuperuser

# Promote to platform superadmin
python3 manage.py make_superadmin <username>
```

### Monitor Revenue

1. Go to `/platform-admin/revenue/`
2. Review MRR, ARR, and churn rate
3. Check revenue by plan distribution

### Support a Customer

1. Go to `/platform-admin/organizations/`
2. Search for the organization
3. Click "View" to see details
4. Click "Impersonate" to see their view
5. Debug the issue
6. Click "Exit Impersonation"

### Check Platform Health

1. Go to `/platform-admin/`
2. Review active organizations count
3. Check AI query usage
4. Look at recent signups

### Find a User

1. Go to `/platform-admin/users/`
2. Search by username, email, or name
3. View their organization memberships

### Update Organization Status

1. Go to organization detail page
2. Use the status dropdown
3. Click "Update"
4. Status changes immediately

---

## Troubleshooting

### Cannot Access Admin Dashboard

**Error:** "Authentication required" or "Platform administrator access required"

**Solution:**
```bash
python3 manage.py make_superadmin <your_username>
```

### Stuck in Impersonation Mode

**Solution:** Navigate to `/platform-admin/exit-impersonation/` or click the yellow "Exit Impersonation" button

### Revenue Numbers Look Wrong

**Check:**
- Organizations with `subscription_status` in ['active', 'past_due'] are counted
- `subscription_plan.price_monthly_cents` is used (stored in cents)
- Divided by 100 to show dollars

### Feature Adoption Shows 0%

**Likely Cause:** No active organizations yet, or all organizations are in trial/cancelled status

**Check:** Only orgs with `subscription_status` in ['active', 'trial'] are counted

---

## Future Enhancements

Potential improvements for the admin dashboard:

- [ ] Revenue trend charts (monthly growth)
- [ ] Cohort analysis (retention by signup month)
- [ ] Customer health score
- [ ] Support ticket integration
- [ ] Automated alerts (churn risk, payment failures)
- [ ] Bulk organization operations
- [ ] Export data to CSV/Excel
- [ ] Advanced search with multiple filters
- [ ] Organization notes/tags
- [ ] Customer success metrics

---

## Technical Details

### Views Location

`core/admin_views.py` - All admin view functions

### Templates Location

`templates/core/admin/` - All admin templates
- `base.html` - Admin base template with navigation
- `dashboard.html` - Overview dashboard
- `organizations_list.html` - Organizations table with filters
- `organization_detail.html` - Detailed org view
- `revenue_analytics.html` - Revenue metrics
- `usage_analytics.html` - Usage metrics
- `users_list.html` - Users table

### URL Configuration

`core/urls.py` - Admin routes under `/platform-admin/`

### Middleware Configuration

`core/middleware.py` - `/platform-admin/` excluded from tenant context

### Management Command

`accounts/management/commands/make_superadmin.py` - Promote users to superadmin

---

## Support

For issues or questions about the admin dashboard:
1. Check the troubleshooting section above
2. Review the code in `core/admin_views.py`
3. Verify migrations are applied
4. Check user has `is_superadmin=True` in database

---

**Last Updated:** December 19, 2025
