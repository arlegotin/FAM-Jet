"""Finite trusted-source generation joins, not continuous executable identity.

Callers validate family vectors/phase/reader requests and retain the actual
Popen launch/end paths. This registry owns cross-family uniqueness, ordered
completion and sampled image/lifetime consistency. It never grants a baseline.
"""
from copy import deepcopy
import errno
import math


def instant(value):
    return type(value) in (int,float) and math.isfinite(value)


class SourceLifecycles:
    def __init__(self,failed=None):
        self.failed=failed if failed is not None else set()
        self.generations={}; self.ids={}; self.ends={}

    def reject(self,pid,message):
        self.failed.add(pid)
        raise ValueError(message)

    def declare(self,entry,family,source=None):
        pid=entry['pid']; identifier=entry.get('launch_id')
        if (type(pid) is not int or pid<=0 or not isinstance(identifier,str) or not identifier or
                pid in self.generations or identifier in self.ids or pid in self.failed):
            if identifier in self.ids: self.failed.add(self.ids[identifier])
            self.reject(pid,'duplicate/reused source launch generation')
        if (family not in ('owned_root','reader','ps','cleanup_ps','git') or
                type(entry.get('parent')) is not int or entry['parent']<0 or
                not instant(entry.get('launch_start')) or
                ('completion_end' not in entry and entry.get('reaped') is not False)):
            self.reject(pid,'invalid source generation')
        record=dict(entry=deepcopy(entry),original=entry,family=family,source=source,peak_bytes=None,
                    latest_sample_start=float('-inf'),last_image_end=float('-inf'))
        self.generations[pid]=record; self.ids[identifier]=pid
        if pid in self.ends: self._end(record,self.ends[pid])
        elif 'completion_end' in entry: self.complete(entry)
        return record

    def complete(self,event):
        pid=event['pid']
        if pid in self.ends: self.reject(pid,'duplicate source completion')
        self.ends[pid]=dict(event)
        if pid in self.generations: self._end(self.generations[pid],event)

    def _end(self,record,event):
        entry=record['entry']; end=event.get('completion_end')
        if (event.get('launch_id')!=entry['launch_id'] or event.get('parent')!=entry['parent'] or
                event.get('reaped') is not True or type(event.get('returncode')) is not int or
                not instant(end) or ('monotonic' in event and (not instant(event['monotonic']) or event['monotonic']<end)) or end<entry['launch_start'] or end<record['latest_sample_start'] or
                end<=record['last_image_end']):
            self.reject(entry['pid'],'invalid source completion lifetime')
        entry.update(completion_end=end,reaped=True,returncode=event['returncode'])

    def image_evidence(self,pid,image,start,end,*,numeric=False):
        record=self.generations[pid]; entry=record['entry']
        low=image.get('lookup_start'); high=image.get('lookup_end')
        artifact=entry.get('expected_image') if record['family']=='reader' else entry.get('artifact')
        kernel=(image.get('status')=='ok' and image.get('method')=='macos.proc_pidpath' and
                artifact is not None and all(image.get(k)==artifact.get(k) for k in ('path','sha256')))
        exited=(image.get('status')=='error' and image.get('method')=='macos.proc_pidpath' and
                image.get('reason')=='native_lookup_failed' and image.get('errno')==errno.ESRCH)
        ordered=(all(instant(v) for v in (start,end,low,high)) and start<=end and low<=high and
                 (entry['launch_start']<=low<=high<=end if numeric else end<=low))
        if (not ordered or not (kernel or exited) or end<entry['launch_start'] or
                start>entry.get('completion_end',float('inf')) or
                (kernel and (low<entry['launch_start'] or high>=entry.get('completion_end',float('inf'))))):
            self.failed.add(pid); return None
        return 'kernel_image' if kernel else 'image_unavailable'

    def attribute(self,row,*,numeric=False):
        pid=row['pid']; record=self.generations.get(pid)
        if pid in self.failed: return 'unaccounted'
        if record is None: return 'pending_source_lifecycle'
        entry=record['entry']; image=row.get('image') or {}
        start=row.get('sample_start'); end=row.get('sample_end')
        artifact=entry.get('expected_image') if record['family']=='reader' else entry.get('artifact')
        evidence=self.image_evidence(pid,image,start,end,numeric=numeric)
        if (row.get('ambiguous') or row.get('parent')!=entry['parent'] or
                type(row.get('rss_bytes')) is not int or row['rss_bytes']<0 or evidence is None):
            self.failed.add(pid); return 'unaccounted'
        record['peak_bytes']=max(record['peak_bytes'] or 0,row['rss_bytes'])
        record['latest_sample_start']=max(record['latest_sample_start'],start)
        if evidence=='kernel_image': record['last_image_end']=max(record['last_image_end'],image['lookup_end'])
        # A source-owned helper needs actual matching completion even if sampled live.
        if pid not in self.ends: return 'pending_source_lifecycle'
        self._end(record,self.ends[pid])
        row.setdefault('identity',{}).update(image_evidence=evidence,
            launch_evidence='source_owned_lifecycle',family=record['family'],launch_id=entry['launch_id'],
            expected_image=artifact,completion=self.ends[pid],source=record['source'],
            ownership_observability='directly_observed_owner' if record['source'] and
                record['source'].get('kind')=='owned_supervisor' else 'parent_reported')
        return 'attributed'

    def unsettled(self):
        return set(self.ends)-set(self.generations) or any(
            pid not in self.ends for pid,record in self.generations.items() if record['family']!='owned_root')
