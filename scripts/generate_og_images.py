"""Generate Aria social-share images. Run: python3 scripts/generate_og_images.py"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

BG = (15, 15, 15)        # #0f0f0f
GOLD = (201, 162, 39)    # #c9a227
WHITE = (245, 245, 245)
OUT = Path(__file__).resolve().parent.parent / 'static'

def _font(size):
    for p in [OUT / 'fonts' / 'Inter-Bold.ttf', OUT / 'fonts' / 'Inter.ttf']:
        if p.exists():
            try:
                return ImageFont.truetype(str(p), size)
            except Exception:
                pass
    for sys_font in ['/System/Library/Fonts/Supplemental/Arial Bold.ttf',
                     '/Library/Fonts/Arial Bold.ttf',
                     '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf']:
        try:
            return ImageFont.truetype(sys_font, size)
        except Exception:
            continue
    return ImageFont.load_default()

def _center_text(draw, text, font, y, w, fill):
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    draw.text(((w - tw) / 2, y), text, font=font, fill=fill)

def make(width, height, path):
    img = Image.new('RGB', (width, height), BG)
    d = ImageDraw.Draw(img)
    _center_text(d, 'ARIA', _font(140), height // 2 - 130, width, GOLD)
    _center_text(d, 'AI Worship Team Management', _font(48), height // 2 + 30, width, WHITE)
    _center_text(d, 'Planning Center integration · aria.church', _font(30), height // 2 + 110, width, (160, 160, 160))
    img.save(path)
    print(f'wrote {path} ({width}x{height})')

if __name__ == '__main__':
    OUT.mkdir(parents=True, exist_ok=True)
    make(1200, 630, OUT / 'og-image.png')
    make(1200, 600, OUT / 'twitter-card.png')
