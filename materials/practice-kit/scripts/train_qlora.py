"""Реальный 4bit NF4 + LoRA; assistant-only loss без TRL-обёртки."""
import argparse
import importlib.metadata
import json
import random
import time
from pathlib import Path
import torch
from transformers import AutoModelForCausalLM,AutoTokenizer,BitsAndBytesConfig
from peft import LoraConfig,get_peft_model,prepare_model_for_kbit_training
from common import WORK,checksum,write_json

parser=argparse.ArgumentParser()
parser.add_argument('--model',default='/models/chat-small')
parser.add_argument('--steps',type=int,default=40)
parser.add_argument('--length',type=int,default=256)
parser.add_argument('--out',type=Path,default=WORK/'adapter')
args=parser.parse_args()
if not torch.cuda.is_available() or args.steps<1:
    raise RuntimeError('CUDA and positive steps required')
random.seed(17)
torch.manual_seed(17)
torch.cuda.manual_seed_all(17)
torch.set_num_threads(2)
tok=AutoTokenizer.from_pretrained(args.model,local_files_only=True,trust_remote_code=False)
q=BitsAndBytesConfig(load_in_4bit=True,bnb_4bit_quant_type='nf4',bnb_4bit_use_double_quant=True,bnb_4bit_compute_dtype=torch.float16)
base=AutoModelForCausalLM.from_pretrained(args.model,local_files_only=True,trust_remote_code=False,quantization_config=q,device_map={'':0},torch_dtype=torch.float16)
base=prepare_model_for_kbit_training(base,use_gradient_checkpointing=True)
base.config.use_cache=False
lora=LoraConfig(task_type='CAUSAL_LM',r=8,lora_alpha=16,lora_dropout=.05,target_modules=['q_proj','v_proj'],bias='none')
model=get_peft_model(base,lora)
model.train()
data=WORK/'training-data/train.jsonl'
dev=WORK/'training-data/dev.jsonl'


def encode(path):
    result=[]
    for line in path.read_text(encoding='utf-8').splitlines():
        row=json.loads(line)
        full=tok.apply_chat_template(row['messages'],tokenize=True,add_generation_prompt=False)
        prefix=tok.apply_chat_template(row['messages'][:-1],tokenize=True,add_generation_prompt=True)
        if full[:len(prefix)]!=prefix:
            raise ValueError('template prefix mismatch; inspect loss mask')
        if len(full)>args.length or len(full)<=len(prefix):
            raise ValueError('would truncate or lose assistant target')
        labels=[-100]*len(prefix)+full[len(prefix):]
        result.append({'input_ids':torch.tensor([full],device='cuda'),'attention_mask':torch.ones((1,len(full)),device='cuda',dtype=torch.long),'labels':torch.tensor([labels],device='cuda')})
    if not result:
        raise ValueError('empty dataset')
    return result


train_rows=encode(data)
dev_rows=encode(dev)
optimizer=torch.optim.AdamW([p for p in model.parameters() if p.requires_grad],lr=2e-4)
torch.cuda.reset_peak_memory_stats()
start=time.perf_counter()
losses=[]
for step in range(args.steps):
    optimizer.zero_grad()
    # effective batch=2: два отдельных microbatch по одному примеру.
    step_loss=0
    for offset in range(2):
        batch=train_rows[(step*2+offset)%len(train_rows)]
        loss=model(**batch).loss/2
        if not torch.isfinite(loss):
            raise RuntimeError('nonfinite loss')
        loss.backward()
        step_loss+=float(loss.detach())
    torch.nn.utils.clip_grad_norm_(model.parameters(),1.0)
    optimizer.step()
    losses.append(step_loss)
model.eval()
with torch.no_grad():
    dev_loss=sum(float(model(**b).loss) for b in dev_rows)/len(dev_rows)
args.out.mkdir(parents=True,exist_ok=True)
model.save_pretrained(args.out)
tok.save_pretrained(args.out)
write_json(args.out/'run.json',{'base':args.model,'base_source':json.loads((Path(args.model)/'course-source.json').read_text()) if (Path(args.model)/'course-source.json').exists() else None,'train_sha256':checksum(data),'dev_sha256':checksum(dev),'steps':args.steps,'microbatch':1,'accumulation':2,'length':args.length,'seed':17,'lr':2e-4,'loss_mask':'assistant-only incl template ending','losses':losses,'dev_loss':dev_loss,'elapsed_seconds':time.perf_counter()-start,'peak_allocated_bytes':torch.cuda.max_memory_allocated(),'peak_reserved_bytes':torch.cuda.max_memory_reserved(),'gpu':torch.cuda.get_device_name(0),'versions':{p:importlib.metadata.version(p) for p in ['torch','transformers','peft','bitsandbytes','accelerate']},'cuda':torch.version.cuda,'trainable_parameters':sum(p.numel() for p in model.parameters() if p.requires_grad),'template':tok.chat_template})
print(json.dumps({'dev_loss':dev_loss,'peak_allocated_bytes':torch.cuda.max_memory_allocated(),'adapter':str(args.out)}))
