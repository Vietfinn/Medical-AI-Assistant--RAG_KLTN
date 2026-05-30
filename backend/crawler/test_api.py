import json, re, urllib.request

data = json.loads(open('test_lc.json', encoding='utf-8').read())
def find_keys(obj, target):
    if isinstance(obj, dict):
        if target in obj: print(f"Found {target}:", obj[target])
        for k, v in obj.items(): find_keys(v, target)
    elif isinstance(obj, list):
        for item in obj: find_keys(item, target)

# search for "api.nhathuoclongchau.com.vn" in strings
def find_api_urls(obj):
    res = set()
    if isinstance(obj, str):
        if 'api.nhathuoclongchau.com.vn' in obj:
            res.add(obj)
    elif isinstance(obj, dict):
        for k, v in obj.items():
            res.update(find_api_urls(v))
    elif isinstance(obj, list):
        for v in obj:
            res.update(find_api_urls(v))
    return res

print(find_api_urls(data))
