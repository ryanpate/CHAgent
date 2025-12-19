# Railway Deployment Checklist - Admin Dashboard

## ✅ Pre-Deployment Verification

### Code Changes Pushed
- ✅ Committed to GitHub: 17 files changed, 2757 insertions
- ✅ Pushed to `origin/main`
- ✅ Commit hash: `8465910`

### Database Migrations
- ✅ Migration created: `accounts/migrations/0003_add_is_superadmin.py`
- ✅ Adds `User.is_superadmin` BooleanField (default=False)
- ✅ Migration tested locally and passed

### Railway Configuration
- ✅ `railway.toml` configured with automatic migrations
- ✅ Start command includes: `python manage.py migrate --noinput`
- ✅ No new environment variables required
- ✅ No new dependencies added (all standard Django)

### URL Routes
- ✅ All admin routes under `/platform-admin/` namespace
- ✅ Protected by `@require_superadmin` decorator
- ✅ Excluded from organization context middleware

### Templates
- ✅ 7 new templates in `templates/core/admin/`
- ✅ Uses existing Tailwind CSS (no new assets)
- ✅ No static file changes needed

---

## 🚀 Railway Deployment Process

Railway will automatically:

1. **Detect Push** - GitHub webhook triggers deployment
2. **Build Image** - Using nixpacks builder
3. **Run Migrations** - Execute: `python manage.py migrate --noinput`
   - Will apply `accounts.0003_add_is_superadmin`
   - Adds `is_superadmin` column to `accounts_user` table
4. **Health Check** - Verify `/health/` endpoint
5. **Start Application** - Gunicorn serves Django app
6. **Deploy Complete** - New version live at https://aria.church

**Expected Duration**: 2-3 minutes

---

## ✅ Post-Deployment Steps

### 1. Verify Deployment Success

**Check Railway Dashboard:**
- Deployment status should show "Success"
- Build logs should show migration applied
- Health check should pass

**Check Application:**
```bash
curl https://aria.church/health/
# Should return: {"status": "ok"}
```

### 2. Verify Migration Applied

**In Railway Dashboard > Database:**
```sql
-- Check if column exists
SELECT column_name, data_type, column_default
FROM information_schema.columns
WHERE table_name = 'accounts_user'
AND column_name = 'is_superadmin';

-- Expected result:
-- column_name  | data_type | column_default
-- is_superadmin| boolean   | false
```

### 3. Make Yourself a Superadmin

**Option A: Railway Dashboard Shell**
```bash
# In Railway project > Database > Query
UPDATE accounts_user
SET is_superadmin = true
WHERE username = 'ryanpate';
```

**Option B: Django Shell (via Railway)**
```bash
# In Railway project > Your Service > Shell
python manage.py shell

# Then in Python shell:
from accounts.models import User
user = User.objects.get(username='ryanpate')
user.is_superadmin = True
user.save()
exit()
```

**Option C: Management Command (if Railway console access)**
```bash
python manage.py make_superadmin ryanpate
```

### 4. Verify Admin Dashboard Access

Navigate to: **https://aria.church/platform-admin/**

**Expected:**
- Should load without errors
- Shows overview dashboard with metrics
- Navigation bar shows: Overview, Organizations, Revenue, Usage, Users

**If access denied:**
- Verify `is_superadmin = true` in database
- Clear browser cache/cookies
- Try logging out and back in

### 5. Test Core Features

**Test Checklist:**
- [ ] Overview dashboard loads with metrics
- [ ] Organizations list shows Cherry Hills Church
- [ ] Can view organization detail page
- [ ] Revenue analytics displays correctly
- [ ] Usage analytics shows data
- [ ] Users list appears
- [ ] Impersonate feature works (test with caution)
- [ ] Exit impersonation returns to admin panel

---

## 🔍 Monitoring & Verification

### Check Railway Logs

**Look for successful migration:**
```
Running migrations:
  Applying accounts.0003_add_is_superadmin... OK
```

**Look for any errors:**
```bash
# Should NOT see:
- "No such table: accounts_user"
- "column is_superadmin does not exist"
- "permission denied"
```

### Database Verification Query

```sql
-- Count superadmins (should be at least 1 after you promote yourself)
SELECT COUNT(*) FROM accounts_user WHERE is_superadmin = true;

-- List all superadmins
SELECT id, username, email, is_superadmin, is_active
FROM accounts_user
WHERE is_superadmin = true;
```

---

## ⚠️ Potential Issues & Solutions

### Issue 1: Migration Fails
**Symptom:** Deployment fails with migration error

**Check:**
```bash
# Railway logs should show specific error
```

**Solution:**
- Migration is simple and should not fail
- If it does, check database connection
- Verify PostgreSQL version compatibility (should be fine)

### Issue 2: Cannot Access /platform-admin/
**Symptom:** 403 Forbidden or redirect

**Check:**
1. Is user logged in?
2. Is `is_superadmin = true` in database?
3. Check Railway logs for errors

**Solution:**
```sql
-- Verify in database
SELECT username, is_superadmin FROM accounts_user WHERE username = 'ryanpate';

-- If false, update:
UPDATE accounts_user SET is_superadmin = true WHERE username = 'ryanpate';
```

### Issue 3: Template Not Found
**Symptom:** TemplateDoesNotExist error

**Check:**
- Verify templates deployed: `templates/core/admin/*.html`
- Check Railway build logs for file copy issues

**Solution:**
- Templates are tracked in git, should auto-deploy
- Force rebuild if needed

### Issue 4: CSS Not Loading
**Symptom:** Admin dashboard has no styling

**Check:**
- Admin templates use Tailwind CDN (no local files needed)
- Check browser console for CDN errors

**Solution:**
- Should work automatically (uses CDN)
- Verify CDN accessible: https://cdn.tailwindcss.com

---

## 🔐 Security Verification

### Post-Deployment Security Checks

1. **Verify superadmin protection:**
   ```bash
   # Try accessing as non-superadmin (should be denied)
   curl -I https://aria.church/platform-admin/
   ```

2. **Check impersonation safety:**
   - Impersonate a test organization
   - Verify yellow "Exit Impersonation" button appears
   - Exit and verify back in admin panel

3. **Verify organization data isolation:**
   - Admin should see ALL organizations
   - Impersonated view should see ONLY that org's data

---

## 📊 Expected Metrics (Post-Deployment)

After successful deployment, admin dashboard should show:

**Overview Dashboard:**
- Total Organizations: 1 (Cherry Hills Church)
- MRR: $0 (trial/no paid plan yet)
- Total Users: 2 (ryanpate, rryanpate)
- AI Queries: <current month's usage>

**Organizations List:**
- 1 organization listed
- Status: Trial or Active
- Member count: 2
- Volunteer/Interaction counts based on existing data

---

## 🎯 Success Criteria

Deployment is successful when:

- ✅ Railway deployment shows "Success"
- ✅ Migration applied without errors
- ✅ `/health/` endpoint returns 200 OK
- ✅ Main site (https://aria.church) works normally
- ✅ At least one superadmin exists
- ✅ `/platform-admin/` loads and displays metrics
- ✅ All admin views (Organizations, Revenue, Usage, Users) accessible
- ✅ No console errors in browser
- ✅ Impersonation feature works correctly

---

## 📞 Rollback Plan (If Needed)

If deployment causes issues:

### Option 1: Revert Git Commit
```bash
git revert 8465910
git push origin main
# Railway will auto-deploy previous version
```

### Option 2: Rollback in Railway Dashboard
1. Go to Railway project
2. Click on deployment
3. Select "Redeploy" on previous successful deployment

### Option 3: Fix Forward
- Migration is additive (adds column with default)
- Safe to keep - no data loss risk
- Fix any code issues and push new commit

---

## 📝 Notes

- **Zero Downtime**: Migration adds a column with default value, should not cause downtime
- **Backwards Compatible**: Existing code continues to work
- **Database Impact**: Minimal - adds one boolean column to users table
- **Performance Impact**: None - simple boolean field with index
- **Rollback Safety**: Column can be ignored if needed (default=False)

---

## ✅ Final Verification Commands

After deployment, run these to verify:

```bash
# 1. Check site is up
curl -I https://aria.church/
# Expected: 200 OK

# 2. Check health endpoint
curl https://aria.church/health/
# Expected: {"status": "ok"}

# 3. Check admin accessible (after making yourself superadmin)
curl -I https://aria.church/platform-admin/
# Expected: 200 OK (if logged in as superadmin)
```

---

**Deployment Ready**: ✅ All checks passed, safe to deploy!

**Deployed At**: <Will be filled after Railway deployment completes>

**Deployed By**: Railway (automatic from GitHub push)
