"""Контрольные суммы разрешённого комплекта без секретов и пользовательских результатов."""
import argparse
from pathlib import Path
from common import ROOT,WORK,checksum,write_json

parser=argparse.ArgumentParser()
parser.add_argument('--id',default='training-r1')
args=parser.parse_args()
paths=[]
for directory in ['scripts','data','sql','dotnet']:
    paths.extend(p for p in (ROOT/directory).rglob('*') if p.is_file() and not any(x in p.parts for x in ['__pycache__','bin','obj']))
paths.extend(ROOT/p for p in ['compose.yaml','Dockerfile','Dockerfile.gpu','requirements.txt','requirements-gpu.txt'])
files={str(p.relative_to(ROOT)).replace('\\','/'):checksum(p) for p in sorted(paths)}
models={p.parent.name:checksum(p) for p in (ROOT/'models').glob('*/course-source.json')}
manifest={'release_id':args.id,'files':files,'model_source_manifest_sha256':models,'images':'record docker image inspect IDs/RepoDigests in release-images.txt','adapter':'record adapter checksums if used; otherwise null','index':'exact corpus + configured encoder; no persisted ANN in reference','policy':'training-A-v1; overlay current revocations on restore','secrets':'excluded; provision separately','evaluation':'attach manually reviewed reports before release','status':'candidate, not automatically approved'}
write_json(WORK/f'manifest-{args.id}.json',manifest)
print('candidate manifest created; image IDs, adapter, review and current rights remain explicit release inputs')
