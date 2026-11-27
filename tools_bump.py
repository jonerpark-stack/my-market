"""화면을 고친 뒤 실행: 휴대폰이 새 버전을 자동으로 받도록 버전 번호를 올린다."""
import re, time, pathlib
d = pathlib.Path(__file__).parent / "docs"
v = str(int(time.time()))
p = d / "index.html"; s = p.read_text(encoding="utf-8")
p.write_text(re.sub(r'const APP_VERSION = "\d+";', f'const APP_VERSION = "{v}";', s), encoding="utf-8")
(d / "version.json").write_text('{"v":"%s"}' % v)
print("version", v)
