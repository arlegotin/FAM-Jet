
import json, os, select, socket, sys, time
case,peer_path,deadline=sys.argv[1],sys.argv[2],float(sys.argv[3])
pid=os.getpid(); proof=None
while time.monotonic()<deadline:
    records=[]
    with open('monitor-evidence.jsonl') as stream:
        for line in stream:
            if line.endswith('\n'): records.append(json.loads(line))
    samples={row['sample_id']:row for row in records if row['kind']=='sample'}
    for row in records:
        if row['kind']!='resolution': continue
        native=row.get('identities',{}).get(str(pid),{})
        if native.get('image_evidence')!='kernel_image': continue
        sample=samples[row['sample_id']]
        own=[entry for entry in sample['processes'] if entry['pid']==pid]
        if len(own)==1 and own[0]['image']['status']=='ok': proof=own[0]; break
    if proof is not None: break
    time.sleep(min(.002,max(0,deadline-time.monotonic())))
if proof is None: raise SystemExit('no actual supervisor proof within original bound')
with open('monitor-events.jsonl','a') as stream:
    stream.write(json.dumps(dict(event='baseline',pid=pid,rss=proof['rss_bytes'],
        monotonic=time.monotonic(),boundary='post-import/pre-allocation'))+'\n'); stream.flush()
child=None
if case=='survivor':
    read,write=os.pipe(); child=os.fork()
    if child==0:
        os.close(read)
        peer=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
        peer.settimeout(max(0,deadline-time.monotonic()))
        peer.connect(peer_path)
        peer.sendall((json.dumps(dict(pid=os.getpid(),parent=os.getppid(),pgid=os.getpgrp()))+'\n').encode())
        peer.settimeout(None)
        os.write(write,b'R'); os.close(write)
        # Sole peer owner after parent exit. EOF from controller is fallback
        # lifecycle cleanup only, never a successful native SIGKILL control.
        peer.recv(1)
        os._exit(0)
    os.close(write)
    ready=select.select([read],[],[],max(0,deadline-time.monotonic()))[0]
    if not ready or os.read(read,1)!=b'R': raise SystemExit('survivor readiness failed')
    os.close(read)
print(json.dumps(dict(root_pid=pid,child_pid=child,root_pgid=os.getpgrp(),proof_sample_end=proof['sample_end'])),flush=True)
