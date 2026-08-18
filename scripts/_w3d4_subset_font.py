"""GB2312 + CJK 标点 全字符子集 → woff2"""
from fontTools.subset import Subsetter
from fontTools.ttLib import TTFont
import os

SRC = r'C:\Windows\Fonts\Noto Sans SC (TrueType).otf'
DST = r'D:\hermes-dev-team\nsp-im\docs\preview\fonts\NotoSansSC-gb2312.woff2'

# 策略：GB2312 一级 3755 字 + ASCII + CJK 标点 = 3800 字左右
# 这是"中文最常用 99% 覆盖"，woff2 后约 1.5-2 MB
chars = set()
for cp in range(0x4E00, 0x9FA6):
    chars.add(chr(cp))
for cp in range(0x20, 0x7F):
    chars.add(chr(cp))
for cp in [0x3001,0x3002,0x3003,0x3005,0x3008,0x3009,0x300A,0x300B,0x300C,0x300D,
          0x300E,0x300F,0x3010,0x3011,0x3014,0x3015,0x3016,0x3017,0x2014,0x2018,
          0x2019,0x201C,0x201D,0x2026,0xFF0C,0xFF1A,0xFF1B,0xFF1F,0xFF01,
          0xFF08,0xFF09,0xFF0E,0xFFE5,0x00A0,0x00B7]:
    chars.add(chr(cp))

print(f'目标字符数: {len(chars)}')

font = TTFont(SRC)
subsetter = Subsetter()
subsetter.populate(text=''.join(chars))
subsetter.subset(font)
font.flavor = 'woff2'
font.save(DST)
size_kb = os.path.getsize(DST)/1024
print(f'OK {DST} -> {size_kb:.1f} KB')