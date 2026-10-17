def compare_static(before,after):
    left={k:v for k,v in before.items() if k not in ('objects','owned_python_and_array_storage_bytes')}
    right={k:v for k,v in after.items() if k not in ('objects','owned_python_and_array_storage_bytes')}
    assert left==right,'numeric/export/config ownership changed'
    a={x['path']:x for x in before['objects']};b={x['path']:x for x in after['objects']};assert a.keys()==b.keys(),'owned object set changed'
    changes=[]
    for path,x in a.items():
        y=b[path]
        assert {k:v for k,v in x.items() if k!='python_getsizeof_bytes'}=={k:v for k,v in y.items() if k!='python_getsizeof_bytes'},path
        if x['python_getsizeof_bytes']!=y['python_getsizeof_bytes']:
            assert x['type']=='dict','non-dictionary static allocation changed'
            changes.append({'path':path,'before_bytes':x['python_getsizeof_bytes'],'after_bytes':y['python_getsizeof_bytes']})
    return {'semantic_owned_objects_equal':True,'tensor_storage_export_config_equal':True,'owned_object_count':len(a),'dictionary_allocation_changes':changes,'before_total_bytes':before['owned_python_and_array_storage_bytes'],'after_total_bytes':after['owned_python_and_array_storage_bytes'],'scope':'observed dictionary Python allocation sizes may vary; all owned paths/types/values/numeric storage/export/config exact; no new owned state allowed'}
