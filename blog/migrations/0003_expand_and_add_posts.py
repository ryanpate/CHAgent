"""Expand the two thin launch posts to full-length articles and add two new
posts targeting impression-generating queries from Search Console.

Search Console showed the launch posts (~250 words) as "discovered – currently
not indexed"; thin content does not get indexed on a low-authority domain. This
migration rewrites them with real depth and cross-links the blog into a mesh so
the previously-orphaned posts have internal links pointing at them.
"""
from django.db import migrations
from django.utils import timezone


POST1 = (
    "<p>Planning Center is where most worship teams keep their schedules, people, "
    "songs, and plans. It is excellent at storing that information. It is slower at "
    "<em>answering questions</em>. Finding out who is serving Sunday, when a song was "
    "last played, or who is blocked out on a date usually means opening several "
    "screens and cross-referencing them by hand.</p>"

    "<p>An AI assistant that connects to Planning Center changes that workflow. Instead "
    "of navigating menus, you ask a question in plain language and get the answer back "
    "from your live Planning Center data &mdash; no exporting, no spreadsheets, no "
    "duplicate database to maintain.</p>"

    "<h2>How an AI assistant connects to Planning Center</h2>"
    "<p>The assistant authenticates with your Planning Center account and reads your "
    "data through the official API. It does not copy your church into a separate system. "
    "When you ask a question, it pulls the current answer from Planning Center People and "
    "Services, formats it, and replies. Because it reads live data, the answer is always "
    "as current as Planning Center itself. If you have not connected an account yet, our "
    "<a href=\"https://aria.church/resources/planning-center-setup-guide/\">Planning Center "
    "setup guide</a> walks through it step by step.</p>"

    "<h2>What you can ask</h2>"
    "<p>The questions worship leaders ask most fall into a few categories:</p>"
    "<h3>Schedules and teams</h3>"
    "<ul>"
    "<li>Who is serving this Sunday, and what are their phone numbers?</li>"
    "<li>Who is on the vocal team next weekend?</li>"
    "<li>Who served on Easter last year?</li>"
    "</ul>"
    "<p>See <a href=\"https://aria.church/blog/who-is-serving-this-sunday-planning-center/\">"
    "how to instantly see who is serving this Sunday</a> for a worked example.</p>"
    "<h3>Songs and setlists</h3>"
    "<ul>"
    "<li>What songs did we play last Sunday?</li>"
    "<li>When did we last play a given song, and what key was it in?</li>"
    "<li>How often have we played a song in the last six months?</li>"
    "</ul>"
    "<h3>Availability and blockouts</h3>"
    "<ul>"
    "<li>Who is blocked out on a specific date?</li>"
    "<li>Is a particular volunteer available next Sunday?</li>"
    "<li>What are a volunteer&rsquo;s upcoming blockout dates?</li>"
    "</ul>"
    "<h3>Contact and care</h3>"
    "<ul>"
    "<li>What is a volunteer&rsquo;s email address?</li>"
    "<li>Give me the phone numbers for everyone serving this weekend.</li>"
    "<li>Who has not served in the last two months?</li>"
    "</ul>"

    "<h2>A typical week with an AI assistant</h2>"
    "<p>The value is clearest across a normal week. Early in the week you ask &ldquo;who is "
    "serving this Sunday, and who hasn&rsquo;t confirmed yet?&rdquo; and send a reminder to "
    "the people still outstanding. Midweek you check &ldquo;what songs did we play last "
    "Sunday&rdquo; so you don&rsquo;t repeat them, and &ldquo;what key was this song in last "
    "time&rdquo; while you build the set. When someone texts that they can&rsquo;t make it, "
    "you ask &ldquo;who plays bass and is available this Sunday&rdquo; and have a sub lined "
    "up in a minute. On Sunday you pull &ldquo;phone numbers for everyone on the team this "
    "morning&rdquo; in case you need to reach anyone. None of these is hard on its own &mdash; "
    "the point is that you stop opening five screens for each one.</p>"

    "<h2>Why it matters for worship leaders</h2>"
    "<p>Most worship leaders are volunteers or bi-vocational. The hours spent assembling "
    "schedules, chasing contact information, and checking availability are hours not spent "
    "leading worship or caring for the team. Pulling those answers in seconds gives that "
    "time back. It also lowers the mental load: you stop holding &ldquo;who is free, who "
    "is blocked out, who needs a follow-up&rdquo; in your head and start asking a question "
    "when you need the answer. Over a month that is the difference between admin running "
    "your week and you running the admin.</p>"

    "<h2>What about privacy?</h2>"
    "<p>Your church&rsquo;s data is sensitive. A good assistant reads Planning Center "
    "through a scoped connection, keeps each organization&rsquo;s data isolated, and does "
    "not use your information to train public models. If you evaluate tools in this space, "
    "ask exactly how your data is stored and who can see it &mdash; it is a fair question "
    "and the answer should be clear.</p>"

    "<h2>Common questions</h2>"
    "<p><strong>Does it replace Planning Center?</strong> No. It sits on top of Planning "
    "Center and reads from it. Planning Center stays your source of truth.</p>"
    "<p><strong>Do I have to re-enter my team?</strong> No. It reads the people, teams, and "
    "plans you already maintain in Planning Center.</p>"
    "<p><strong>What does it cost to try?</strong> You can start free. See "
    "<a href=\"https://aria.church/pricing/\">pricing</a> for plan details.</p>"

    "<h2>Getting started</h2>"
    "<p>Aria was built for exactly this: it connects to Planning Center and answers "
    "questions about your schedules, songs, blockouts, and volunteers in plain language, "
    "and helps you track follow-ups so no one falls through the cracks. "
    "<a href=\"https://aria.church/signup/\">Start a free trial</a> and connect your "
    "Planning Center account in a few minutes.</p>"
)


POST2 = (
    "<p>&ldquo;AI church software&rdquo; now covers everything from sermon-writing tools to "
    "donation analytics. For a worship team specifically, the features that actually save "
    "time are narrower than the marketing suggests. This is a practical guide to what to "
    "look for in 2026, written for worship leaders rather than IT directors.</p>"

    "<h2>What &ldquo;AI church software&rdquo; actually means</h2>"
    "<p>Most tools in this category do one of three things: generate content (sermons, "
    "social posts, graphics), analyze data (giving, attendance, engagement), or answer "
    "questions about information your church already stores. For worship teams, the third "
    "category is the one that removes weekly busywork, because your real bottleneck is "
    "usually finding answers inside Planning Center &mdash; not writing more content.</p>"

    "<h2>Five things to look for</h2>"
    "<ol>"
    "<li><strong>Planning Center integration.</strong> Your schedules, people, and songs "
    "already live in Planning Center. Good software reads that data directly instead of "
    "asking you to maintain a second copy. If a tool needs you to re-enter your team, that "
    "is a maintenance cost you will pay every week.</li>"
    "<li><strong>Plain-language answers.</strong> You should be able to ask &ldquo;who is "
    "serving Sunday&rdquo; or &ldquo;when did we last play this song&rdquo; and get an "
    "answer, without learning a query syntax.</li>"
    "<li><strong>Volunteer care.</strong> The best tools help you remember the human side: "
    "logging a conversation, surfacing who has not served recently, tracking prayer "
    "requests and follow-ups.</li>"
    "<li><strong>Clear data privacy.</strong> Church data is sensitive. Look for "
    "organization-level isolation, a clear statement that your data is not used to train "
    "public models, and transparent storage practices.</li>"
    "<li><strong>A price that fits a ministry budget.</strong> Per-month pricing that scales "
    "with team size beats enterprise contracts for most churches.</li>"
    "</ol>"

    "<h2>Questions to ask a vendor</h2>"
    "<ul>"
    "<li>Does it read my live Planning Center data, or do I maintain a separate database?</li>"
    "<li>What exactly can it answer about my team, songs, and schedule?</li>"
    "<li>How is my church&rsquo;s data stored, and who can access it?</li>"
    "<li>Is there a free trial so I can test it with my real data?</li>"
    "<li>What does support look like for a small volunteer team?</li>"
    "</ul>"

    "<h2>How worship-team needs differ from general church software</h2>"
    "<p>General church management software is built for the whole organization: membership, "
    "giving, groups, check-in, communication. It is broad by design. A worship leader&rsquo;s "
    "daily questions are narrow and specific &mdash; who is on which instrument this week, what "
    "songs are in rotation, who is blocked out, who needs a follow-up. A general platform can "
    "store all of that, but answering those questions still means navigating menus built for a "
    "different job. Worship-focused tooling optimizes for the handful of questions you ask most, "
    "which is why a narrow tool often saves more of your time than a broad one.</p>"

    "<h2>Read-live vs. duplicate-database: the key distinction</h2>"
    "<p>The single most important technical question is whether a tool reads your live Planning "
    "Center data or asks you to maintain a separate copy. A duplicate database looks fine in a "
    "demo and slowly rots in practice: every roster change, new volunteer, or song has to be "
    "entered twice, and the copy drifts out of date. A tool that reads Planning Center directly "
    "is always current and adds no maintenance. When you evaluate options, ask to see exactly "
    "where the data comes from.</p>"

    "<h2>Where the time savings come from</h2>"
    "<p>For a worship leader, the recurring weekly costs are scheduling logistics, contact "
    "lookups, availability checks, and song history. A tool that answers those in seconds "
    "&mdash; see our overview of <a href=\"https://aria.church/blog/ai-for-planning-center-"
    "worship-teams/\">AI for Planning Center worship teams</a> &mdash; pays for itself in "
    "the first month, because it converts repetitive lookups into a single question.</p>"

    "<h2>What to be skeptical of</h2>"
    "<p>Be wary of tools that promise to &ldquo;run your ministry&rdquo; or replace human "
    "judgment. AI is good at retrieving and summarizing information you already have. It is "
    "not a substitute for pastoral care or for knowing your people. The right framing is a "
    "fast assistant for the logistics, so you have more time for the relationships.</p>"

    "<h2>Putting it together</h2>"
    "<p>Aria was built around these criteria for worship arts teams: it connects to Planning "
    "Center, answers questions instantly, and helps you track relationships with volunteers, "
    "at a price built for churches. Compare the details on our "
    "<a href=\"https://aria.church/pricing/\">pricing page</a>, browse free "
    "<a href=\"https://aria.church/resources/\">worship team resources</a>, or "
    "<a href=\"https://aria.church/signup/\">try it free</a> with your own Planning Center "
    "account.</p>"
)


POST3 = (
    "<p>&ldquo;Who is serving this Sunday?&rdquo; is the question every worship leader asks "
    "most. In Planning Center the answer is there &mdash; but getting to it means opening the "
    "right plan, checking each team position, and then jumping to People if you also need "
    "phone numbers or emails. Here is how to get the whole answer in one step.</p>"

    "<h2>The manual way in Planning Center</h2>"
    "<p>Normally you would: open Services, find the correct service type, open this "
    "Sunday&rsquo;s plan, scroll the team section to see who is scheduled and who has "
    "accepted, and then &mdash; if you need to contact them &mdash; open each person in "
    "People to copy their phone or email. It works, but it is several screens for a question "
    "you ask every week.</p>"

    "<h2>The one-question way</h2>"
    "<p>With an AI assistant connected to Planning Center, you ask in plain language:</p>"
    "<ul>"
    "<li>&ldquo;Who is serving this Sunday?&rdquo;</li>"
    "<li>&ldquo;Who is on the team this weekend, with their phone numbers?&rdquo;</li>"
    "<li>&ldquo;Who is scheduled on vocals next Sunday?&rdquo;</li>"
    "</ul>"
    "<p>The assistant reads the current plan from Planning Center Services, matches each "
    "scheduled person to their contact details in People, and replies with the full list "
    "&mdash; positions and contact info together. What took several screens becomes one "
    "sentence.</p>"

    "<h2>Variations worship leaders ask</h2>"
    "<p>The same approach answers the follow-up questions that usually come next:</p>"
    "<ul>"
    "<li>&ldquo;Who has not confirmed yet?&rdquo; to chase outstanding responses.</li>"
    "<li>&ldquo;Who is blocked out this Sunday?&rdquo; before you finalize the plan.</li>"
    "<li>&ldquo;Give me emails for everyone serving this weekend&rdquo; to send one note.</li>"
    "<li>&ldquo;Who served last Easter?&rdquo; when you are planning a big service.</li>"
    "</ul>"

    "<h2>Working with multiple service types</h2>"
    "<p>Many churches run more than one service: a main morning service, plus high school or "
    "middle school ministry, or a weeknight gathering. In Planning Center these are separate "
    "service types, which is exactly where manual lookups get confusing. A good assistant lets "
    "you say which one you mean &mdash; &ldquo;who is on the high school ministry team this "
    "Sunday&rdquo; versus &ldquo;who is serving at the main service&rdquo; &mdash; and pulls "
    "from the right plan. That removes the most common source of &ldquo;wait, which service "
    "was that?&rdquo; mistakes.</p>"

    "<h2>Handling last-minute changes</h2>"
    "<p>The real stress test is Saturday night, when someone drops out. The manual version "
    "means re-opening the plan, finding the gap, and then digging through People to find who "
    "plays that instrument and whether they are free. Asked as a question &mdash; &ldquo;who "
    "plays drums and is available tomorrow?&rdquo; &mdash; the assistant checks the roster and "
    "blockouts together and gives you a short list to text. The faster you can fill a gap, the "
    "less a last-minute change derails your Sunday.</p>"

    "<h2>Why this matters</h2>"
    "<p>The point is not novelty &mdash; it is the cumulative time. A worship leader checks "
    "&ldquo;who is serving&rdquo; and &ldquo;how do I reach them&rdquo; dozens of times a "
    "month. Collapsing that into a single question removes a small friction you pay over and "
    "over, and it makes last-minute changes (a sub on Saturday night) far less stressful.</p>"

    "<h2>Setting it up</h2>"
    "<p>You need a Planning Center account and an assistant connected to it. Our "
    "<a href=\"https://aria.church/resources/planning-center-setup-guide/\">Planning Center "
    "setup guide</a> covers connecting your account, and the broader overview of "
    "<a href=\"https://aria.church/blog/ai-for-planning-center-worship-teams/\">AI for "
    "Planning Center worship teams</a> shows the other questions you can ask once you are "
    "connected.</p>"

    "<p>Aria answers exactly these questions from your live Planning Center data. "
    "<a href=\"https://aria.church/signup/\">Start a free trial</a> and ask &ldquo;who is "
    "serving this Sunday?&rdquo; in your first minute.</p>"
)


POST4 = (
    "<p>A clear volunteer application sets the tone for your whole worship team. It tells "
    "people you take the ministry seriously, it gathers the information you actually need, "
    "and it gives you a natural first conversation. Here is what to include &mdash; and a "
    "free template you can copy.</p>"

    "<p>If you just want the document, grab our free "
    "<a href=\"https://aria.church/resources/volunteer-application-template/\">church "
    "volunteer application template</a> and adapt it. If you want to understand what each "
    "section is for, read on.</p>"

    "<h2>1. Contact and basic information</h2>"
    "<p>Name, email, phone, and the best way to reach them. Keep it short; this is the part "
    "people expect. If you schedule through Planning Center, collecting an email up front "
    "makes it easy to add them later.</p>"

    "<h2>2. Areas of interest and experience</h2>"
    "<p>Ask which team they are interested in (vocals, band, tech, production, hospitality) "
    "and what experience they have. For musicians, ask about instruments and, if relevant, "
    "what they are comfortable playing. This is not an audition &mdash; it is so you can "
    "place people where they will thrive.</p>"

    "<h2>3. Availability</h2>"
    "<p>How often they hope to serve, which services or weekends, and any standing "
    "conflicts. Setting expectations here prevents the most common volunteer problem: a "
    "mismatch between how often you need them and how often they can actually come.</p>"

    "<h2>4. A short testimony or faith background</h2>"
    "<p>For a worship team, leading people in worship is a spiritual role, not only a "
    "musical one. A few sentences about their faith and why they want to serve gives you a "
    "starting point for a conversation with your pastor or team lead, without turning the "
    "form into an interrogation.</p>"

    "<h2>5. References and agreement</h2>"
    "<p>A reference or two and a simple acknowledgement of your team&rsquo;s commitments "
    "(rehearsal expectations, a code of conduct, background-check consent where required) "
    "protects everyone and keeps standards consistent.</p>"

    "<h2>How to deliver the application</h2>"
    "<p>Keep the format low-friction. A short online form gets far more completions than a PDF "
    "someone has to print, sign, and scan. Make it reachable from the places people already "
    "look &mdash; your church website, a QR code on a connect card, or a link you text after "
    "someone expresses interest. The easier it is to start, the more genuinely interested "
    "people you will hear from.</p>"

    "<h2>Common mistakes to avoid</h2>"
    "<ul>"
    "<li><strong>Too long.</strong> If the form takes more than a few minutes, good volunteers "
    "abandon it. Ask only what you will actually use.</li>"
    "<li><strong>No follow-up plan.</strong> Collecting applications you never respond to is "
    "worse than not asking. Decide in advance who reviews them and how fast.</li>"
    "<li><strong>Skipping expectations.</strong> Not stating rehearsal and commitment "
    "expectations up front leads to mismatches later.</li>"
    "<li><strong>One-and-done.</strong> An application is the first touch, not the whole "
    "onboarding. Plan the next two or three steps too.</li>"
    "</ul>"

    "<h2>What to do with the application</h2>"
    "<p>The form is the start, not the end. Follow up within a week &mdash; even a short "
    "&ldquo;thanks, let&rsquo;s grab coffee&rdquo; &mdash; because momentum matters when "
    "someone has just volunteered. Once they join, keep track of the relationship: how they "
    "are settling in, what they have shared, when they last served. Letting new volunteers "
    "drift is how teams lose people they worked hard to recruit.</p>"

    "<h2>Keep the human side organized</h2>"
    "<p>Recruiting is only worth it if you care for people after they join. Aria helps "
    "worship leaders log interactions, remember personal details, and track follow-ups so "
    "new volunteers do not fall through the cracks &mdash; alongside answering questions "
    "about your Planning Center schedule. Browse more free "
    "<a href=\"https://aria.church/resources/\">worship team resources</a> or "
    "<a href=\"https://aria.church/signup/\">start a free trial</a>.</p>"
)


UPDATES = {
    'ai-for-planning-center-worship-teams': {
        'title': 'AI for Planning Center: A Worship Team Guide',
        'excerpt': (
            'Connect AI to Planning Center to answer questions about schedules, '
            'volunteers, blockouts, and songs in plain language. Here is how it works '
            'and what you can ask.'
        ),
        'meta_title': 'AI for Planning Center: Worship Team Guide',
        'meta_description': (
            'How AI connects to Planning Center to answer questions about your worship '
            'team schedules, volunteers, songs, and blockouts instantly.'
        ),
        'focus_keyword': 'planning center ai',
        'content': POST1,
    },
    'best-ai-church-software-2026': {
        'title': 'The Best AI Church Software for Worship Teams in 2026',
        'excerpt': (
            'What to look for in AI church software in 2026: Planning Center '
            'integration, plain-language answers, volunteer care, and a ministry-friendly '
            'price.'
        ),
        'meta_title': 'Best AI Church Software for Worship Teams (2026)',
        'meta_description': (
            'A practical 2026 guide to AI church software for worship teams: Planning '
            'Center integration, volunteer care, privacy, and what to ask a vendor.'
        ),
        'focus_keyword': 'ai church software',
        'content': POST2,
    },
}


NEW_POSTS = [
    {
        'slug': 'who-is-serving-this-sunday-planning-center',
        'title': "How to Instantly See Who's Serving This Sunday in Planning Center",
        'excerpt': (
            'Stop clicking through screens. See exactly who is serving this Sunday in '
            'Planning Center — with their contact info — by asking one question.'
        ),
        'meta_title': "Who's Serving This Sunday? Planning Center Shortcut",
        'meta_description': (
            'How to instantly see who is serving this Sunday in Planning Center, with '
            'phone numbers and emails, by asking an AI assistant one plain-language question.'
        ),
        'focus_keyword': 'planning center who is serving',
        'content': POST3,
    },
    {
        'slug': 'church-volunteer-application-guide',
        'title': 'What to Include in a Church Volunteer Application (Worship Team Guide)',
        'excerpt': (
            'The sections every church volunteer application needs — contact info, '
            'interests, availability, testimony, and references — plus a free template.'
        ),
        'meta_title': 'Church Volunteer Application: What to Include',
        'meta_description': (
            'What to include in a church volunteer application for your worship team: '
            'contact info, experience, availability, testimony, references, and a free '
            'template.'
        ),
        'focus_keyword': 'church volunteer application',
        'content': POST4,
    },
]


def forwards(apps, schema_editor):
    BlogPost = apps.get_model('blog', 'BlogPost')
    now = timezone.now()
    for slug, fields in UPDATES.items():
        # .update() skips auto_now, so set updated_at explicitly for dateModified
        BlogPost.objects.filter(slug=slug).update(updated_at=now, **fields)
    for p in NEW_POSTS:
        BlogPost.objects.get_or_create(
            slug=p['slug'],
            defaults={
                **p,
                'status': 'published',
                'author_name': 'Aria Team',
                'published_at': now,
            },
        )


def backwards(apps, schema_editor):
    # New posts can be removed; expanded content is left in place (no clean restore).
    BlogPost = apps.get_model('blog', 'BlogPost')
    BlogPost.objects.filter(slug__in=[p['slug'] for p in NEW_POSTS]).delete()


class Migration(migrations.Migration):
    dependencies = [('blog', '0002_seed_launch_blog_posts')]
    operations = [migrations.RunPython(forwards, backwards)]
