"""Optional asset maintenance: python scripts/build_typography_fonts.py SOURCES.

Requires fonttools (build-time only). Sources are original Google Fonts files
with each family's OFL.txt. Never downloads fonts during video production.
"""
import hashlib
import json
from pathlib import Path
import shutil
import sys
from fontTools import subset
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont

ROOT = Path(__file__).resolve().parents[1]
SOURCES = Path(sys.argv[1])
OUTPUT = ROOT / 'motion_engine/fonts'
families = ['inter','bevietnampro','montserrat','nunitosans','opensans','notosans','lora','notoserif','sourcesans3','barlowcondensed']
profiles = json.loads((ROOT/'skills/typography.json').read_text())['profiles']
manifest = []
for profile, family in zip(profiles, families):
    license_dir = OUTPUT/'licenses'/family
    license_dir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SOURCES/family/'OFL.txt', license_dir/'OFL.txt')
    for role in ('caption','heading'):
        if family == 'inter':
            source = OUTPUT/'Inter-Variable.ttf'
        elif family == 'barlowcondensed':
            source = OUTPUT/('BarlowCondensed-Bold.ttf' if role=='caption' else 'BarlowCondensed-ExtraBold.ttf')
        elif family == 'bevietnampro':
            source = SOURCES/family/('BeVietnamPro-SemiBold.ttf' if role=='caption' else 'BeVietnamPro-Bold.ttf')
        else:
            source = next((SOURCES/family).glob('*.ttf'))
        weight = profile[role+'_weight']
        font = TTFont(source)
        if 'fvar' in font:
            axes = {axis.axisTag: weight if axis.axisTag=='wght' else axis.defaultValue for axis in font['fvar'].axes}
            font = instantiateVariableFont(font, axes, inplace=True)
        options = subset.Options()
        options.name_IDs = ['*']; options.name_languages = ['*']; options.name_legacy = True
        sub = subset.Subsetter(options=options)
        # Vietnamese Latin, combining accents, common punctuation and symbols.
        sub.populate(unicodes=[c for lo, hi in [(0x20,0x24f),(0x300,0x36f),(0x1e00,0x1eff),(0x2000,0x206f),(0x20a0,0x20cf),(0x2100,0x214f)] for c in range(lo,hi+1)])
        sub.subset(font)
        # Renamed modified families respect OFL Reserved Font Names.
        family_name = profile['font_family']; style = {500:'Medium',600:'SemiBold',700:'Bold',800:'ExtraBold'}[weight]
        names = {1:family_name,2:style,3:family_name.replace(' ','')+'-'+style,4:family_name+' '+style,6:family_name.replace(' ','')+'-'+style,16:family_name,17:style}
        font['name'].names = [name for name in font['name'].names if name.nameID not in names]
        for name_id, value in names.items():
            font['name'].setName(value,name_id,3,1,0x409)
        font['OS/2'].usWeightClass = weight
        font['OS/2'].fsSelection &= ~((1<<5)|(1<<6))
        if weight>=700:font['OS/2'].fsSelection |= 1<<5
        font['head'].macStyle = 1 if weight>=700 else 0
        target = OUTPUT/profile[role+'_file']; font.save(target)
        manifest.append({'file':target.name,'original_family':profile['family'],'original_file':source.name,'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'license':'SIL OFL 1.1','source_url':'https://github.com/google/fonts/tree/main/ofl/'+family})
        print(target.name,target.stat().st_size,flush=True)
(OUTPUT/'typography-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
