from pathlib import Path
from django.conf import settings

def test_social_images_exist_with_correct_dimensions():
    from PIL import Image
    base = Path(settings.BASE_DIR) / 'static'
    og = base / 'og-image.png'
    tw = base / 'twitter-card.png'
    assert og.exists() and tw.exists(), "social images missing"
    assert Image.open(og).size == (1200, 630)
    assert Image.open(tw).size == (1200, 600)
