#!/usr/bin/env python3
"""Package only reviewed public source files; never include arbitrary directories."""
from pathlib import Path
import hashlib
import zipfile

ROOT = Path(__file__).resolve().parents[1]
FILES = ["index.html", "README.md", ".gitignore", ".gitattributes", ".nojekyll",
         ".pages.yml", "content/site.json", "assets/card.mjs", "admin/index.html",
         "wallet/build.sh", "wallet/build_pass.py", "wallet/pass.template.json",
         "tools/test_wallet.py", "tools/test_content.mjs", "tools/pack_wallet_kit.py"]
FILES += [p.relative_to(ROOT).as_posix() for p in sorted((ROOT / "media/images").glob("*.jpg"))]
FILES += ["wallet/assets/" + stem + suffix + ".png"
          for stem in ("icon", "logo", "thumbnail") for suffix in ("", "@2x", "@3x")]

if __name__ == "__main__":
    archive = ROOT / "Ahuzat-Wallet-Kit.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as z:
        for name in sorted(FILES):
            data = (ROOT / name).read_bytes()
            if any(b"-----BEGIN " + marker + b"PRIVATE KEY-----" in data
                   for marker in (b"", b"RSA ", b"EC ", b"ENCRYPTED ")):
                raise ValueError("Refusing to package private signing material: " + name)
            info = zipfile.ZipInfo("Ahuzat-Wallet-Kit/" + name, date_time=(2026, 10, 11, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (0o100755 if name.endswith(".sh") else 0o100644) << 16
            z.writestr(info, data)
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        assert len(z.namelist()) == len(FILES)
    print(str(archive))
    print("SHA256: " + hashlib.sha256(archive.read_bytes()).hexdigest())
