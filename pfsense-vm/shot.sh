#!/bin/bash
cd "$(dirname "$0")"
(printf 'screendump /tmp/pf.ppm\n'; sleep 1.5) | nc -w3 127.0.0.1 4556 >/dev/null
python3 - <<'PY'
try:
    from PIL import Image
    Image.open('/tmp/pf.ppm').save('/private/tmp/claude-501/-Users-ginye-Documents-nexus-work/ce31299c-dff3-4e66-b701-bab1ab4976fa/scratchpad/pf.png')
    print("ok")
except Exception as e: print("ERR",e)
PY
