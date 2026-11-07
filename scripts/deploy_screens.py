import os

handoff_file = r"d:\AI\Aman Jain - Master\.agents\teamwork\explorer_m11_2\handoff.md"
with open(handoff_file, "r", encoding="utf-8") as f:
    text = f.read()

cur = 0
count = 0
while True:
    header_idx = text.find("### 4.", cur)
    if header_idx == -1:
        break
    line_end = text.find("\n", header_idx)
    header_line = text[header_idx:line_end]

    q1 = header_line.find("`")
    if q1 != -1:
        q2 = header_line.find("`", q1 + 1)
        rel_path = header_line[q1 + 1:q2]

        dart_idx = text.find("```dart", line_end)
        if dart_idx != -1:
            code_start = text.find("\n", dart_idx) + 1
            code_end = text.find("```", code_start)
            code = text[code_start:code_end].strip()

            target_path = os.path.normpath(os.path.join(r"d:\AI\Aman Jain - Master", rel_path))
            os.makedirs(os.path.dirname(target_path), exist_ok=True)
            with open(target_path, "w", encoding="utf-8") as out:
                out.write(code + "\n")
            print(f"Deployed: {rel_path} ({len(code)} bytes)")
            count += 1
            cur = code_end + 3
            continue
    cur = line_end + 1

print(f"All done: {count} files deployed.")
