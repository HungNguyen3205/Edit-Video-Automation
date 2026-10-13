"""Offline conceptual graphics in the approved white / teal / navy style."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

from project_paths import PROJECT_ROOT
ROOT = PROJECT_ROOT
TEAL, NAVY = '#0D9488', '#172D3B'


def draw_graphic(path, kind, title='', items=None):
    items = (items or [])[:5]
    im = Image.new('RGB', (600, 460), '#F1F7F7')
    d = ImageDraw.Draw(im)
    font_path = ROOT / 'motion_engine/fonts/Inter-Variable.ttf'
    def text(x, y, value, size=22, color=NAVY, center=False, max_width=450):
        value = str(value)
        f = ImageFont.truetype(str(font_path), size)
        while f.getlength(value) > max_width and size > 12:
            size -= 1
            f = ImageFont.truetype(str(font_path), size)
        d.text((x, y), value, font=f, fill=color, anchor='mm' if center else 'lt')
    if kind == 'chat':
        d.rounded_rectangle((70, 20, 530, 440), radius=30, fill=NAVY)
        d.ellipse((98, 48, 148, 98), fill=TEAL)
        text(123, 73, (title or 'AI')[0].upper(), 27, 'white', True)
        text(166, 55, title or 'TRỢ LÝ AI', 26, 'white', max_width=325)
        text(166, 88, 'Minh họa hội thoại', 15, '#98D8D1')
        for idx, value in enumerate(items[:3]):
            y = 137 + idx * 87
            x = 95 if idx % 2 == 0 else 150
            d.rounded_rectangle((x, y, 505, y + 67), radius=18, fill='white' if idx % 2 == 0 else TEAL)
            text(x + 18, y + 22, value, 23, NAVY if idx % 2 == 0 else 'white', max_width=480-x-18)
        text(300, 412, 'ĐỒ HỌA MINH HỌA', 14, '#98D8D1', True)
    elif kind == 'process':
        d.ellipse((224, 35, 376, 187), fill=TEAL)
        text(300, 111, title or 'Ý TƯỞNG', 35, 'white', True, max_width=140)
        labels = items[:3]
        for idx, value in enumerate(labels):
            cx = 100 + idx * 200 if len(labels) == 3 else 180 + idx * 240 if len(labels) == 2 else 300
            d.line((300, 187, cx, 270), fill='#94CFC9', width=4)
            d.rounded_rectangle((cx-85, 270, cx+85, 355), radius=18, fill='white')
            text(cx, 311, value, 20, NAVY, True, max_width=150)
        text(300, 414, 'SƠ ĐỒ MINH HỌA', 14, '#526673', True)
    else:
        points = [(110, 85), (475, 85), (90, 320), (490, 320), (300, 405)]
        for idx, (x,y) in enumerate(points[:len(items) or 5]):
            d.line((300, 220, x, y), fill='#93CFC8', width=4)
            d.ellipse((x-32,y-32,x+32,y+32),fill='white',outline='#CCE5E2',width=2)
            d.ellipse((x-9,y-17,x+9,y+1),fill=TEAL)
            d.rounded_rectangle((x-17,y+5,x+17,y+18),radius=8,fill=TEAL)
            if items:
                text(x,y+48,items[idx],17,NAVY,True,max_width=160)
        d.rounded_rectangle((195,170,405,270),radius=24,fill=NAVY)
        text(300,220,title or 'THÔNG ĐIỆP',25,'white',True,max_width=180)
    path = Path(path)
    im.save(path)
    return path
