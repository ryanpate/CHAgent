"""SEO Tier 3 growth content.

Deepens the AI-for-Planning-Center post (ranks pos ~15 for "ai planning center",
29 impressions) with worked use-cases, a manual-vs-AI comparison, and an
expanded FAQ, and adds two posts targeting an open cluster with GSC impressions
but no dedicated page ("ai tools for churches", "church volunteer management").
"ai church software" is intentionally NOT targeted here — best-ai-church-software-2026
already owns it.

Content is HTML (rendered via {{ post.content|safe }}).
"""
from django.db import migrations
from django.utils import timezone


POST_AI = (
    "<p>Planning Center is where most worship teams keep their schedules, people, "
    "songs, and plans. It is excellent at storing that information. It is slower at "
    "<em>answering questions</em>. Finding out who is serving Sunday, when a song was "
    "last played, or who is blocked out on a date usually means opening several "
    "screens and cross-referencing them by hand.</p>"

    "<p>AI for Planning Center changes that workflow. Instead of navigating menus, you "
    "ask a question in plain language and get the answer back from your live Planning "
    "Center data &mdash; no exporting, no spreadsheets, no duplicate database to "
    "maintain. This guide explains how Planning Center AI works, what you can ask, and "
    "where it saves the most time.</p>"

    "<h2>How AI connects to Planning Center</h2>"
    "<p>An AI assistant authenticates with your Planning Center account and reads your "
    "data through the official API. It does not copy your church into a separate system. "
    "When you ask a question, it pulls the current answer from Planning Center People and "
    "Services, formats it, and replies. Because it reads live data, the answer is always "
    "as current as Planning Center itself. If you have not connected an account yet, our "
    "<a href=\"https://aria.church/resources/planning-center-setup-guide/\">Planning Center "
    "setup guide</a> walks through the setup step by step, and the "
    "<a href=\"https://aria.church/integrations/\">Planning Center integration</a> page "
    "explains exactly what data the assistant can read.</p>"

    "<h2>What you can ask Planning Center AI</h2>"
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

    "<h2>Three ways worship teams use Planning Center AI every week</h2>"
    "<h3>1. Building and confirming the Sunday schedule</h3>"
    "<p>Before you finalize a plan, you need to know who is actually available. Instead of "
    "opening each volunteer&rsquo;s blockout calendar, you ask &ldquo;who is blocked out next "
    "Sunday?&rdquo; and &ldquo;who has not served in three weeks?&rdquo; in one place. The "
    "assistant reads the same blockout data your team already enters in Planning Center, so "
    "you schedule around real availability the first time instead of reshuffling on Saturday "
    "night.</p>"
    "<h3>2. Caring for volunteers, not just scheduling them</h3>"
    "<p>Healthy teams are built on relationships, not rotations. Because the assistant can "
    "surface who has drifted off the schedule or who you last spoke with, it becomes a prompt "
    "to reach out &mdash; &ldquo;who on the team has a birthday this month?&rdquo; or &ldquo;who "
    "have I not checked in with lately?&rdquo; The scheduling data you already keep becomes a "
    "care tool, not just a logistics one.</p>"
    "<h3>3. Answering song and setlist questions instantly</h3>"
    "<p>&ldquo;What key is Goodness of God in, and when did we last play it?&rdquo; is a two-minute "
    "hunt through your song library and past plans. With Planning Center AI it is one question. "
    "That matters most in the moment &mdash; during rehearsal, in a planning meeting, or when a "
    "vocalist asks for a different key.</p>"

    "<h2>AI vs. doing it by hand</h2>"
    "<p>None of these questions are impossible in Planning Center today &mdash; that is the point. "
    "Every answer already lives in your account. The difference is the time and friction between "
    "the question and the answer:</p>"
    "<ul>"
    "<li><strong>By hand:</strong> open Services, find the plan, cross-reference the team list, "
    "then open each person&rsquo;s profile for contact info or blockouts. A few minutes per "
    "question, several times a week.</li>"
    "<li><strong>With AI:</strong> ask once, in plain language, and get the formatted answer from "
    "the same live data. Seconds, from any device.</li>"
    "</ul>"
    "<p>Over a month of weekly services, that friction is the real cost &mdash; and it is exactly "
    "the busywork that pulls worship leaders away from leading.</p>"

    "<h2>Is my Planning Center data safe?</h2>"
    "<p>A good assistant reads your data through Planning Center&rsquo;s official OAuth "
    "authorization, never stores your login, and only accesses the People and Services data you "
    "authorize. It reads live rather than copying your church into another database, so there is "
    "no second copy to secure or keep in sync.</p>"

    "<h2>Frequently asked questions</h2>"
    "<h3>What is Planning Center AI?</h3>"
    "<p>It is an AI assistant that connects to your Planning Center account and answers questions "
    "about your schedules, volunteers, songs, and blockouts in plain language, reading your live "
    "data instead of making you navigate menus.</p>"
    "<h3>Does it work with the free Planning Center plan?</h3>"
    "<p>Yes. It reads through the standard Planning Center API, which works across plan tiers. If "
    "you are just getting started, follow the "
    "<a href=\"https://aria.church/resources/planning-center-setup-guide/\">setup guide</a> first.</p>"
    "<h3>Do I have to move my data out of Planning Center?</h3>"
    "<p>No. The assistant reads your existing Planning Center data live. Planning Center stays your "
    "system of record; the AI is just a faster way to ask it questions.</p>"

    "<p><a href=\"https://aria.church/\">Aria</a> is an AI assistant built for worship teams on "
    "Planning Center. <a href=\"https://aria.church/signup/\">Start a free 14-day trial</a> "
    "&mdash; no credit card required &mdash; and ask your first question in minutes.</p>"
)


POST_TOOLS = (
    "<p>Churches are adopting AI faster than most software categories expected, and for a "
    "practical reason: ministry teams are small, and the administrative load is not. The right "
    "AI tools remove weekly busywork so staff and volunteers can spend more time with people. "
    "This is a practical guide to the categories of AI tools for churches, what each is good "
    "at, and how to choose without wasting a budget on novelty.</p>"

    "<h2>The four categories of AI tools for churches</h2>"
    "<p>Almost every AI tool a church will consider falls into one of four buckets. Knowing which "
    "problem you are actually trying to solve keeps you from buying a content generator when your "
    "real bottleneck is scheduling.</p>"

    "<h3>1. Worship and scheduling</h3>"
    "<p>These tools connect to the software you already use to schedule volunteers and plan "
    "services &mdash; most often Planning Center &mdash; and let you ask questions in plain "
    "language: who is serving Sunday, who is blocked out, when you last played a song. This is the "
    "category that removes the most <em>recurring</em> work, because service planning happens every "
    "single week. If your team lives in Planning Center, this is usually the highest-ROI place to "
    "start; see <a href=\"https://aria.church/blog/ai-for-planning-center-worship-teams/\">how AI "
    "works with Planning Center</a> for a detailed look.</p>"

    "<h3>2. Communication and congregation care</h3>"
    "<p>AI tools here help draft announcements, emails, and follow-up messages, and can help track "
    "who needs a check-in. Used well, they make small teams feel more responsive; used carelessly, "
    "they make communication feel generic. The rule of thumb: let AI draft, but keep a human voice "
    "on anything pastoral.</p>"

    "<h3>3. Sermon and content preparation</h3>"
    "<p>Research assistants, outline generators, and study tools fall here. They are genuinely "
    "useful for surfacing cross-references and speeding up prep, but they are assistants, not "
    "authors &mdash; the theology and the pastoral judgment stay with your team.</p>"

    "<h3>4. Administration and operations</h3>"
    "<p>Giving analysis, attendance trends, and general office automation. These tools quietly save "
    "hours for whoever keeps the lights on, and they are often the easiest to justify because the "
    "time savings are measurable.</p>"

    "<h2>How to choose AI tools for your church</h2>"
    "<ul>"
    "<li><strong>Start with your biggest recurring task.</strong> The best AI tool is the one that "
    "removes work you do every week, not the one with the most features.</li>"
    "<li><strong>Prefer tools that connect to what you already use.</strong> An assistant that reads "
    "your existing Planning Center or church database beats one that asks you to maintain a second "
    "copy of your data.</li>"
    "<li><strong>Check how it handles your data.</strong> Ask whether it reads live through an "
    "official API, whether it stores your data, and what it does with member information.</li>"
    "<li><strong>Keep a human on anything pastoral.</strong> AI is excellent at logistics and "
    "drafts; care and teaching stay with people.</li>"
    "</ul>"

    "<h2>Where to start</h2>"
    "<p>If your team schedules and plans services in Planning Center, worship and scheduling is the "
    "category with the fastest payback, because it touches every week. "
    "<a href=\"https://aria.church/\">Aria</a> is an AI assistant built specifically for worship "
    "teams on Planning Center &mdash; it answers questions about schedules, volunteers, and songs, "
    "and helps you care for your team. <a href=\"https://aria.church/signup/\">Start a free 14-day "
    "trial</a>, no credit card required, or read the "
    "<a href=\"https://aria.church/resources/planning-center-setup-guide/\">Planning Center setup "
    "guide</a> if you are still getting your data in place.</p>"

    "<h2>Frequently asked questions</h2>"
    "<h3>What are the best AI tools for churches?</h3>"
    "<p>It depends on your biggest recurring task. For worship teams, an assistant that connects to "
    "Planning Center saves the most weekly time; for office staff, admin and giving tools pay off "
    "fastest. Start with the work you repeat every week.</p>"
    "<h3>Are AI tools for churches expensive?</h3>"
    "<p>Most are subscription tools priced per month, and many offer free trials. The real cost to "
    "watch is not the price &mdash; it is whether the tool removes enough recurring work to be worth "
    "a place in your workflow.</p>"
    "<h3>Is it appropriate for churches to use AI?</h3>"
    "<p>For logistics &mdash; scheduling, drafting, admin &mdash; AI simply gives small teams more "
    "time for ministry. The guidance most leaders land on is to use AI for busywork and keep human "
    "judgment on anything pastoral or theological.</p>"
)


POST_VOL = (
    "<p>Volunteers are the engine of nearly every ministry, and coordinating them is one of the "
    "most time-consuming jobs on a church staff. Recruiting, scheduling, reminding, thanking, and "
    "&mdash; most importantly &mdash; genuinely caring for a team of volunteers is a lot to hold in "
    "your head. This is where AI for church volunteer management earns its place: not by replacing "
    "the relationship, but by removing the busywork that gets in the way of it.</p>"

    "<h2>What church volunteer management actually involves</h2>"
    "<p>Good volunteer management is more than filling slots on a schedule. It is a cycle:</p>"
    "<ul>"
    "<li><strong>Recruiting</strong> the right people into the right roles.</li>"
    "<li><strong>Onboarding</strong> them with clear expectations and the information they need.</li>"
    "<li><strong>Scheduling</strong> fairly, around real availability.</li>"
    "<li><strong>Communicating</strong> reminders and changes without nagging.</li>"
    "<li><strong>Caring</strong> &mdash; noticing prayer requests, milestones, and the volunteer who "
    "has quietly stopped showing up.</li>"
    "<li><strong>Retaining</strong> people by making them feel known, not just used.</li>"
    "</ul>"
    "<p>Most tools handle the middle of that list &mdash; scheduling and reminders &mdash; well. The "
    "recruiting and, especially, the <em>caring</em> are where coordinators run out of hours.</p>"

    "<h2>Where AI helps a volunteer coordinator</h2>"
    "<h3>Surfacing who needs attention</h3>"
    "<p>The hardest part of care is simply noticing. An AI assistant that reads your team data can "
    "answer &ldquo;who has not served in the last two months?&rdquo; or &ldquo;whose prayer request "
    "did I say I would follow up on?&rdquo; &mdash; turning information you already have into a prompt "
    "to reach out before someone drifts away for good.</p>"
    "<h3>Remembering the details that build relationship</h3>"
    "<p>You cannot personally remember every volunteer&rsquo;s spouse&rsquo;s name, new job, or "
    "surgery date &mdash; but a coordinator who does is a coordinator people want to serve under. "
    "Logging those details and having them resurface at the right moment is exactly the kind of "
    "memory work AI is good at.</p>"
    "<h3>Cutting the scheduling and reminder overhead</h3>"
    "<p>Answering &ldquo;who is available next Sunday?&rdquo; and &ldquo;who is already blocked "
    "out?&rdquo; in seconds means you build a workable schedule the first time. Less time on "
    "logistics is more time for people.</p>"

    "<h2>Start with the basics, then add intelligence</h2>"
    "<p>You do not need AI to manage volunteers well &mdash; you need a clear application, a fair "
    "schedule, and consistent follow-up. Get those right first: our free "
    "<a href=\"https://aria.church/resources/volunteer-application-template/\">volunteer application "
    "template</a> and <a href=\"https://aria.church/resources/worship-schedule-template/\">worship "
    "schedule template</a> give you a starting point. Once the basics are in place, an AI assistant "
    "removes the repetitive parts so you can focus on the relationships.</p>"

    "<h2>How Aria helps worship volunteer coordinators</h2>"
    "<p><a href=\"https://aria.church/\">Aria</a> connects to your Planning Center data and helps you "
    "both schedule <em>and</em> care for your team &mdash; tracking interactions, follow-ups, and the "
    "personal details that make volunteers feel known. <a href=\"https://aria.church/signup/\">Start a "
    "free 14-day trial</a>, no credit card required, and see how much of the busywork it takes off "
    "your plate.</p>"

    "<h2>Frequently asked questions</h2>"
    "<h3>What is the best way to manage church volunteers?</h3>"
    "<p>Combine a clear application and role expectations, a fair rotation built around real "
    "availability, consistent communication, and intentional care &mdash; noticing who needs a "
    "check-in. Software helps with the logistics; the care is what retains people.</p>"
    "<h3>Can AI help with volunteer retention?</h3>"
    "<p>Indirectly but meaningfully. AI cannot build a relationship for you, but by surfacing who is "
    "drifting and remembering personal details, it prompts the human follow-up that keeps volunteers "
    "engaged.</p>"
    "<h3>Do I need special software to manage volunteers?</h3>"
    "<p>No &mdash; many teams start with a spreadsheet and a template. Dedicated tools and AI "
    "assistants become worth it as your team grows and the coordination load outpaces what you can "
    "hold in your head.</p>"
)


UPDATES = {
    'ai-for-planning-center-worship-teams': {
        'title': 'AI for Planning Center: A Worship Team Guide',
        'excerpt': (
            'How AI for Planning Center works, what you can ask, and the three '
            'places it saves worship teams the most time each week.'
        ),
        'meta_title': 'AI for Planning Center: Worship Team Guide',
        'meta_description': (
            'How Planning Center AI works for worship teams: ask who is serving '
            'Sunday, track volunteer care, and look up songs from your live data.'
        ),
        'focus_keyword': 'ai planning center',
        'content': POST_AI,
    },
}


NEW_POSTS = [
    {
        'slug': 'ai-tools-for-churches',
        'title': 'AI Tools for Churches: A Practical Guide',
        'excerpt': (
            'The four categories of AI tools for churches, what each is good at, '
            'and how to choose without wasting your budget on novelty.'
        ),
        'meta_title': 'AI Tools for Churches: A Practical Guide',
        'meta_description': (
            'A practical guide to AI tools for churches: worship and scheduling, '
            'communication, sermon prep, and admin — and how to choose.'
        ),
        'focus_keyword': 'ai tools for churches',
        'content': POST_TOOLS,
    },
    {
        'slug': 'ai-church-volunteer-management',
        'title': 'AI for Church Volunteer Management',
        'excerpt': (
            'How AI helps volunteer coordinators recruit, schedule, and — most '
            'importantly — care for the people on their teams.'
        ),
        'meta_title': 'AI for Church Volunteer Management',
        'meta_description': (
            'How AI for church volunteer management helps coordinators schedule '
            'fairly, follow up, and care for volunteers so they stay engaged.'
        ),
        'focus_keyword': 'church volunteer management',
        'content': POST_VOL,
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
    dependencies = [('blog', '0003_expand_and_add_posts')]
    operations = [migrations.RunPython(forwards, backwards)]
