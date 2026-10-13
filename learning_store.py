"""Local style feedback memory; stores no speech, names, assets or timestamps."""
import hashlib
import json
import os
from pathlib import Path
from statistics import median
from datetime import datetime, timezone

RULES=[
    'Preserve source speech and duration; use only facts and names in the current video/request.',
    'Prefer camera opening and ending, with a few relevant interior illustrations.',
    'Use short clear headlines; keep explicit multiword names together.',
    'Use gentle purposeful camera zoom and quiet effects; respect the current request.',
    'Uploaded photos are preferred when relevant; conceptual graphics must not imply a real product screenshot.'
]



def editor_skills(path=None):
    """Load bounded project instructions; a broken file cannot break rendering."""
    try:
        pack=json.loads(Path(path or Path(__file__).parent/'editing_skills.json').read_text(encoding='utf-8'))
        if not isinstance(pack,dict):raise ValueError('Invalid skill pack')
        skills=pack.get('skills')
        if pack.get('schema_version')!=1 or not isinstance(skills,list) or not 1<=len(skills)<=8:
            raise ValueError('Invalid skill pack')
        ids=set();active=[]
        for skill in skills:
            if not isinstance(skill,dict) or not isinstance(skill.get('id'),str) or not 1<=len(skill['id'])<=40 or skill['id'] in ids or not isinstance(skill.get('enabled'),bool) or not isinstance(skill.get('rule'),str) or not 1<=len(skill['rule'])<=400:
                raise ValueError('Invalid skill')
            ids.add(skill['id'])
            if skill['enabled']:active.append({'id':skill['id'],'rule':skill['rule']})
        if sum(len(skill['rule']) for skill in active)>1800:
            raise ValueError('Skill instructions are too long')
        return active
    except (OSError,ValueError,TypeError):
        return []


def visual_summary(plan):
    scenes=plan.get('storyboard',[])
    types=[s.get('scene_type','talking_head') for s in scenes]
    return {'scene_types':types[:12],'scene_count':len(scenes),
        'illustration_fraction':round(sum(t!='talking_head' for t in types)/max(1,len(types)),2),
        'headline_words_median':round(median([len(s.get('headline','').split()) for s in scenes])) if scenes else 0}


class LearningStore:
    def __init__(self,data_dir):
        self.root=Path(data_dir)/'learning';self.root.mkdir(parents=True,exist_ok=True)

    def records(self):
        result=[]
        for path in self.root.glob('*.json'):
            try:
                record=json.loads(path.read_text(encoding='utf-8'))
                if record.get('schema_version')==1 and record.get('decision') in ('approve_style','needs_changes') and isinstance(record.get('note'),str) and isinstance(record.get('visual_style'),dict):result.append(record)
            except (ValueError,OSError):continue
        return sorted(result,key=lambda r:r.get('updated_at',''),reverse=True)

    def save(self,project,decision,note,captions_checked=False):
        identifier=hashlib.sha256((project['id']+project['output_path']+str(project['revision'])).encode()).hexdigest()
        record={'schema_version':1,'id':identifier,'project_id':project['id'],
            'output_path':project['output_path'],'revision':project['revision'],
            'decision':decision,'note':note.strip()[:800],'captions_checked':captions_checked,
            'visual_style':visual_summary(project['edit_plan']),
            'planning_mode':(project.get('job') or {}).get('planning_mode','unknown'),
            'updated_at':datetime.now(timezone.utc).isoformat()}
        path=self.root/(identifier+'.json');temporary=path.with_suffix('.tmp')
        temporary.write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8');os.replace(temporary,path)
        return record

    def context(self):
        approved=[r for r in self.records() if r['decision']=='approve_style'][:3]
        # Bounded summaries support new content; never replay a previous script.
        baseline=json.loads((Path(__file__).parent/'style_reference.json').read_text(encoding='utf-8'))
        changes=[r['note'][:250] for r in self.records() if r['decision']=='needs_changes' and r.get('note')][:2]
        skills=editor_skills()
        return {'schema_version':1,'active_skills':[s['id'] for s in skills],'rules':RULES+[s['rule'] for s in skills],'initial_visual_reference':baseline['visual_style'],'requested_changes':changes,'approved_style_examples':[
            {'visual_style':r['visual_style'],'user_note':r['note'][:250]} for r in approved]}

    def status(self):
        records=self.records()
        return {'mode':'style_memory','model_weights_trained':False,
                'initial_visual_references':1,'approved_styles':sum(r['decision']=='approve_style' for r in records),
                'needs_changes':sum(r['decision']=='needs_changes' for r in records),
                'reference_limit':3,'active_skills':[s['id'] for s in editor_skills()]}

    def export(self):
        # Export style supervision only; no private transcript/brand/asset paths.
        return '\n'.join(json.dumps({'schema_version':1,'decision':r['decision'],
            'note':r['note'],'captions_checked':r['captions_checked'],
            'visual_style':r['visual_style'],'planning_mode':r['planning_mode']},ensure_ascii=False)
            for r in self.records() if r['decision']=='approve_style')
