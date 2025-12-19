import json

# 建议增加 encoding='utf-8' 以确保在不同系统环境下都能正确读取中文
with open('output/segments.jsonl', 'r', encoding='utf-8') as file:
    segments = [json.loads(line) for line in file]

for segment in segments:
    segment['audio'] = './output/' + segment['audio']

print(max(segment['duration'] for segment in segments))

# 增加 encoding='utf-8' 并设置 ensure_ascii=False
with open('data.jsonl', 'w', encoding='utf-8') as file:
    for segment in segments:
        # ensure_ascii=False 会让中文以原样字符保存，而不是 \uXXXX 格式
        file.write(json.dumps(segment, ensure_ascii=False) + '\n')
print(f"Processed {len(segments)} segments and saved to data.jsonl")