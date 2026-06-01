from django.db import migrations
from django.utils import timezone

POSTS = [
    {
        'slug': 'ai-for-planning-center-worship-teams',
        'title': 'How AI Helps Worship Teams Get More from Planning Center',
        'excerpt': 'Connect AI to Planning Center to answer questions about schedules, volunteers, blockouts, and songs in plain language.',
        'meta_title': 'AI for Planning Center: Worship Team Guide',
        'meta_description': 'How AI connects to Planning Center to answer questions about your worship team schedules, volunteers, and songs instantly.',
        'focus_keyword': 'planning center ai',
        'content': (
            "<p>Planning Center is where most worship teams keep their schedules, people, and songs. "
            "But finding a specific answer — who is serving Sunday, when a song was last played, who is "
            "blocked out — usually means clicking through several screens.</p>"
            "<p>An AI assistant that connects to Planning Center changes that. Instead of navigating menus, "
            "you ask a question in plain language and get the answer from your live PCO data.</p>"
            "<h2>What you can ask</h2>"
            "<ul>"
            "<li>Who is serving this Sunday, and what are their phone numbers?</li>"
            "<li>When did we last play a given song, and what key was it in?</li>"
            "<li>Who is blocked out on a specific date?</li>"
            "</ul>"
            "<h2>Why it matters</h2>"
            "<p>Worship leaders spend hours each month on logistics. Answering these questions instantly frees "
            "that time for actually caring for the team. Aria connects to Planning Center and does exactly this. "
            "<a href=\"https://aria.church/signup/\">Start a free trial</a>.</p>"
        ),
    },
    {
        'slug': 'best-ai-church-software-2026',
        'title': 'The Best AI Church Software for Worship Teams in 2026',
        'excerpt': 'What to look for in AI church software — Planning Center integration, volunteer care, and instant answers.',
        'meta_title': 'Best AI Church Software for Worship Teams (2026)',
        'meta_description': 'A practical look at AI church software for worship teams in 2026: Planning Center integration, volunteer care, and instant answers.',
        'focus_keyword': 'ai church software',
        'content': (
            "<p>“AI church software” covers a lot of tools. For worship teams specifically, the features that "
            "actually save time are narrower than the marketing suggests.</p>"
            "<h2>What to look for</h2>"
            "<ol>"
            "<li><strong>Planning Center integration.</strong> Your data already lives there; the software should read it, not duplicate it.</li>"
            "<li><strong>Plain-language answers.</strong> Schedules, songs, blockouts, and contact info on demand.</li>"
            "<li><strong>Volunteer care.</strong> Logging interactions and surfacing who needs follow-up.</li>"
            "</ol>"
            "<h2>Putting it together</h2>"
            "<p>Aria was built around these three things for worship arts teams. It connects to Planning Center, "
            "answers questions instantly, and helps you track relationships with volunteers. "
            "<a href=\"https://aria.church/signup/\">Try it free</a>.</p>"
        ),
    },
]

def seed(apps, schema_editor):
    BlogPost = apps.get_model('blog', 'BlogPost')
    now = timezone.now()
    for p in POSTS:
        BlogPost.objects.get_or_create(
            slug=p['slug'],
            defaults={**p, 'status': 'published', 'author_name': 'Aria Team', 'published_at': now},
        )

def unseed(apps, schema_editor):
    BlogPost = apps.get_model('blog', 'BlogPost')
    BlogPost.objects.filter(slug__in=[p['slug'] for p in POSTS]).delete()

class Migration(migrations.Migration):
    dependencies = [('blog', '0001_initial')]
    operations = [migrations.RunPython(seed, unseed)]
