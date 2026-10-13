"""Project-scoped spelling and measured title layout; no invented transcript."""
import copy
import re
from difflib import SequenceMatcher
from pathlib import Path
from PIL import ImageFont


def name_rules(brand_name='', proper_names=''):
    rules=[]
    for line in proper_names.splitlines():
        parts=[p.strip() for p in line.split('|') if p.strip()]
        if parts:
            rules.append((parts[0],parts,False))
    # Only near spellings of an explicitly supplied brand token are inferred.
    first=brand_name.split()[0] if brand_name.split() else ''
    if re.fullmatch(r'[A-Za-z]{5,}',first):
        rules.append((first,[first],True))
    return rules


def normalize_names(text, brand_name='', proper_names=''):
    for canonical,aliases,fuzzy in name_rules(brand_name,proper_names):
        for alias in sorted(aliases,key=len,reverse=True):
            text=re.sub(r'(?<!\w)'+re.escape(alias)+r'(?!\w)',lambda m:canonical,text,flags=re.I)
        if fuzzy:
            def replace(m):
                word=m.group()
                return canonical if abs(len(word)-len(canonical))<=1 and SequenceMatcher(None,word.casefold(),canonical.casefold()).ratio()>=.84 else word
            text=re.sub(r'\b[A-Za-z]{5,}\b',replace,text)
    # A singular/plural suffix may be corrected only inside the full brand,
    # never every occurrence of a generic word such as 'solution'.
    tokens=brand_name.split()
    if len(tokens)>1:
        aliases=[brand_name]
        if tokens[-1].endswith('s') and len(tokens[-1])>4:
            aliases.append(' '.join(tokens[:-1]+[tokens[-1][:-1]]))
        for alias in aliases:
            text=re.sub(r'(?<!\w)'+re.escape(alias)+r'(?!\w)',lambda m:brand_name,text,flags=re.I)
    return text


def prepare_source(plan,brand_name='',proper_names=''):
    p=copy.deepcopy(plan)
    p['proper_names']=proper_names
    p.setdefault('recognition_subtitles',copy.deepcopy(p.get('subtitles',[])))
    if 'user_subtitles' in p:
        return p  # Reviewed sentences have precedence over spelling suggestions.
    from automatic_director import aligned_words
    for sub in p.get('subtitles',[]):
        corrected=normalize_names(sub['text'],brand_name,proper_names)
        if corrected!=sub['text']:
            sub['words']=aligned_words(sub.get('words',[]),corrected,sub['start'],sub['end'])
            sub['text']=corrected
    return p


def review_issues(subtitles):
    result=[]
    for i,s in enumerate(subtitles):
        reasons=[]
        confidence=[w.get('probability') for w in s.get('words',[]) if isinstance(w.get('probability'),(float,int))]
        if confidence and min(confidence)<.35:
            reasons.append('Nhận dạng có từ độ tin cậy thấp; cần nghe lại.')
        if re.search(r'\bchết cái\b',s.get('text',''),re.I):
            reasons.append('Cụm từ có thể chưa đúng ngữ cảnh; cần nghe lại, không tự thay từ.')
        if reasons:
            result.append({'subtitle_index':i,'start':s['start'],'end':s['end'],'reason':' '.join(reasons)})
    return result


def headline_layout(text,size=64,width=640,proper_names='',font_path=None):
    """Choose at most two balanced lines using the renderer's actual font."""
    text=' '.join(str(text).split())
    from project_paths import PROJECT_ROOT
    path=font_path or PROJECT_ROOT/'motion_engine/fonts/BarlowCondensed-Bold.ttf'
    tokens=text.split()
    protected=[line.split('|')[0].strip().casefold().split() for line in proper_names.splitlines()]
    protected=[name for name in protected if 1<len(name)<=4]
    def forbidden(boundary):
        return any([w.casefold() for w in tokens[start:start+len(name)]]==name and start<boundary<start+len(name)
                   for name in protected for start in range(max(0,boundary-len(name)+1),boundary))
    if not tokens:
        return '',size
    for font_size in range(size,17,-1):
        font=ImageFont.truetype(str(path),font_size)
        if font.getlength(text)<=width:
            return text,font_size
        candidates=[]
        for i in range(1,len(tokens)):
            if forbidden(i):continue
            left=' '.join(tokens[:i]);right=' '.join(tokens[i:])
            lengths=[font.getlength(left),font.getlength(right)]
            if max(lengths)<=width:
                penalty=abs(lengths[0]-lengths[1])+(width if min(i,len(tokens)-i)==1 and len(tokens)>3 else 0)
                candidates.append((penalty,left+'\n'+right))
        if candidates:
            return min(candidates)[1],font_size
    # Pathological unbroken text must still stay inside the title safe area.
    chars=list(text);middle=len(chars)//2
    return ''.join(chars[:middle])+'\n'+''.join(chars[middle:]),18
