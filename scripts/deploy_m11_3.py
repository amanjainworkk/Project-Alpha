import os
import sys

sys.path.insert(0, r"d:\AI\Aman Jain - Master\.agents\teamwork\explorer_m11_3")

source_file = r"d:\AI\Aman Jain - Master\.agents\teamwork\explorer_m11_3\test_proposed_code.py"
with open(source_file, "r", encoding="utf-8") as f:
    code_text = f.read()

# Execute in isolated namespace to extract the blueprints dict
ns = {}
exec(code_text, ns)
blueprints = ns.get("blueprints", {})

print(f"Loaded {len(blueprints)} blueprints from explorer_m11_3")

file_mapping = {
    "audio_service.dart": r"d:\AI\Aman Jain - Master\Alpha\apk\lib\services\audio_service.dart",
    "widgets.dart": r"d:\AI\Aman Jain - Master\Alpha\apk\lib\widgets\widgets.dart",
    "screens.dart": r"d:\AI\Aman Jain - Master\Alpha\apk\lib\screens\screens.dart",
    "services.dart": r"d:\AI\Aman Jain - Master\Alpha\apk\lib\services\services.dart",
    "screens_test.dart": r"d:\AI\Aman Jain - Master\Alpha\apk\test\widget\screens_test.dart",
}

for name, target in file_mapping.items():
    if name in blueprints:
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "w", encoding="utf-8") as out:
            out.write(blueprints[name].strip() + "\n")
        print(f"Deployed: {name} -> {target} ({len(blueprints[name])} bytes)")
    else:
        print(f"WARNING: {name} not found in blueprints!")
