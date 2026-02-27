# ARIA - App Store Listing

## App Name
ARIA

## Subtitle (App Store) / Short Description (Play Store)
AI Worship Team Management

## Description

ARIA is the AI-powered platform built for worship arts teams. Chat with Aria, your intelligent assistant, to instantly access volunteer information, schedules, songs, and team insights — all from your phone.

**Key Features:**

- **AI Assistant (Aria)** — Ask questions about volunteers, schedules, songs, chord charts, and lyrics. Aria understands natural language and learns from your team's interactions.

- **Planning Center Integration** — Direct access to your PCO data for people, schedules, blockouts, and service plans. No more switching apps.

- **Volunteer Care** — Log interactions, track personal details, and follow up on prayer requests. Build genuine relationships with your team.

- **Follow-up Management** — Create and track action items, prayer requests, and reminders. Never let a follow-up slip through the cracks.

- **Team Communication** — Announcements, channels, and direct messages keep your team connected. @mention teammates in conversations and task comments.

- **Knowledge Base** — Upload documents and images for Aria to reference. Get instant answers about procedures, guidelines, and resources.

- **Analytics Dashboard** — Track engagement, care metrics, interaction trends, and AI performance at a glance.

- **Push Notifications** — Real-time alerts for messages, announcements, task assignments, and care alerts.

ARIA is designed exclusively for worship arts teams and church volunteer management. Your data is encrypted, isolated per organization, and never used to train AI models.

Currently in closed beta. Request access at https://aria.church

## Keywords
worship, church, volunteer, team management, planning center, worship arts, church management, volunteer scheduling, worship team, church app

## Category
- **App Store**: Productivity
- **Play Store**: Productivity

## Privacy Policy URL
https://aria.church/privacy/

## Support URL
https://aria.church/security/

## Marketing URL
https://aria.church

## Copyright
2026 ARIA

## Age Rating
4+ (App Store) / Everyone (Play Store)

## Screenshots Needed

### iPhone 6.7" (iPhone 15 Pro Max) — Required
1. Chat with Aria (AI assistant conversation)
2. Volunteer list view
3. Follow-up management
4. Team communication hub
5. Analytics dashboard

### iPhone 5.5" (iPhone 8 Plus) — Required
Same 5 screenshots at smaller resolution.

### iPad Pro 12.9" — Recommended
Same 5 screenshots at iPad resolution.

### Android Phone — Required
Same 5 screenshots, captured on Pixel emulator.

## App Store Submission Checklist

### Step 1: Create Distribution Certificate
- [ ] Go to developer.apple.com → Certificates, Identifiers & Profiles → Certificates
- [ ] Click + → Select "Apple Distribution"
- [ ] Create CSR from Keychain Access (Certificate Assistant → Request a Certificate from a Certificate Authority → Save to disk)
- [ ] Upload CSR, download .cer file, double-click to install

### Step 2: Create App Store Provisioning Profile
- [ ] Go to Profiles → Click +
- [ ] Select "App Store Connect" (under Distribution)
- [ ] Select App ID: church.aria.app
- [ ] Select Distribution certificate
- [ ] Name it "ARIA App Store", download, double-click to install

### Step 3: Register App in App Store Connect
- [ ] Go to appstoreconnect.apple.com → My Apps → + → New App
- [ ] Platform: iOS
- [ ] Name: ARIA
- [ ] Primary Language: English (U.S.)
- [ ] Bundle ID: church.aria.app
- [ ] SKU: aria-church

### Step 4: Fill in App Store Listing
- [ ] Subtitle: AI Worship Team Management
- [ ] Category: Productivity
- [ ] Privacy Policy URL: https://aria.church/privacy/
- [ ] Support URL: https://aria.church
- [ ] Description: Copy from this file's Description section above
- [ ] Keywords: worship, church, volunteer, team management, planning center, worship arts, church management, volunteer scheduling, worship team, church app
- [ ] Marketing URL: https://aria.church
- [ ] Copyright: 2026 ARIA
- [ ] Age Rating: Fill out questionnaire (answer No to everything → 4+)

### Step 5: Take Screenshots
- [ ] 6.7" iPhone (iPhone 15 Pro Max) — required
- [ ] 5.5" iPhone (iPhone 8 Plus) — required if supporting older devices

Capture these 5 screens:
1. Chat with Aria (showing a conversation)
2. Volunteer list
3. Follow-up management
4. Communication hub
5. Analytics dashboard

### Step 6: Set Up App Review Demo Account
- [ ] Run: `python3 manage.py create_demo_account` on production
- [ ] In App Store Connect → App Review Information:
  - Sign-in required: Yes
  - Username: demo@aria.church
  - Password: AppReview2026!
  - Notes: "This app requires a server connection. The demo account has sample data pre-loaded."

### Step 7: Archive and Upload
- [ ] Open project in Xcode: `open mobile/ios/App/App.xcodeproj`
- [ ] Select "Any iOS Device" as build destination
- [ ] Set signing to Distribution profile under Signing & Capabilities
- [ ] Product → Archive
- [ ] In Organizer: Select archive → Distribute App → App Store Connect → Upload

### Step 8: Submit for Review
- [ ] Wait for build to appear in App Store Connect (5-15 minutes)
- [ ] Select the build under version 1.0
- [ ] Review all listing details
- [ ] Click "Submit for Review"
- [ ] Apple review typically takes 24-48 hours
