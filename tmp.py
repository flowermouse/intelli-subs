import json

with open('output/segments.jsonl', 'r') as file:
    segments = [json.loads(line) for line in file]

for segment in segments:
    segment['audio'] = './output/' + segment['audio']

with open('data.jsonl', 'w') as file:
    for segment in segments:
        file.write(json.dumps(segment) + '\n')
print(f"Processed {len(segments)} segments and saved to data.jsonl")