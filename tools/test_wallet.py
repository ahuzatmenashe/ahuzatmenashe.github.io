#!/usr/bin/env python3
"""Exercise real PKCS#7 signing using disposable QA certificates, never Apple keys.

No test credentials enter the checkout. Synthetic root pins and HTTPS response
are patched in memory for this test only; the production CLI has no bypass flag.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import zipfile

module_spec = importlib.util.spec_from_file_location("wallet", Path(__file__).resolve().parents[1] / "wallet/build_pass.py")
wallet = importlib.util.module_from_spec(module_spec)
module_spec.loader.exec_module(wallet)


def expect_failure(label, operation):
    try:
        operation()
    except (ValueError, OSError):
        print("PASS: rejects " + label)
        return
    raise AssertionError("Did not reject " + label)


def main():
    with tempfile.TemporaryDirectory(prefix="ahuzat-wallet-test-") as temporary:
        d = Path(temporary)
        ca_ext = d / "ca.ext"
        ca_ext.write_text("basicConstraints=critical,CA:TRUE\nkeyUsage=critical,keyCertSign,cRLSign\nsubjectKeyIdentifier=hash\nauthorityKeyIdentifier=keyid,issuer\n")
        leaf_ext = d / "leaf.ext"
        leaf_ext.write_text("basicConstraints=critical,CA:FALSE\nkeyUsage=critical,digitalSignature\nsubjectKeyIdentifier=hash\nauthorityKeyIdentifier=keyid,issuer\n")
        wallet.openssl("req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "2", "-subj", "/CN=Disposable QA Root", "-keyout", d / "root.key", "-out", d / "root.pem")
        for name, subject, parent, extension in (
                ("intermediate", "/CN=Disposable QA Intermediate", "root", ca_ext),
                ("leaf", "/UID=" + wallet.PASS_TYPE + "/OU=TESTTEAM01/CN=Disposable QA Signer", "intermediate", leaf_ext)):
            wallet.openssl("req", "-new", "-newkey", "rsa:2048", "-nodes", "-subj", subject,
                           "-keyout", d / (name + ".key"), "-out", d / (name + ".csr"))
            wallet.openssl("x509", "-req", "-in", d / (name + ".csr"), "-CA", d / (parent + ".pem"),
                           "-CAkey", d / (parent + ".key"), "-CAcreateserial", "-days", "2",
                           "-extfile", extension, "-out", d / (name + ".pem"))
        wallet.WWDR_SHA256 = hashlib.sha256(wallet.openssl("x509", "-in", d / "intermediate.pem", "-outform", "DER")).hexdigest()
        wallet.ROOT_SHA256 = hashlib.sha256(wallet.openssl("x509", "-in", d / "root.pem", "-outform", "DER")).hexdigest()
        actual_html = (wallet.ROOT / "index.html").read_bytes()
        wallet.fetch = lambda url: (actual_html, url)
        args = argparse.Namespace(cert=str(d / "leaf.pem"), key=str(d / "leaf.key"),
                                  output=str(d / "Ahuzat-Menashe.pkpass"), url=wallet.FINAL_URL,
                                  wwdr=str(d / "intermediate.pem"), apple_root=str(d / "root.pem"))
        wallet.build(args)
        print("PASS: real detached PKCS#7 sign/verify, embedded intermediate, extracted Team ID, exact manifest, ZIP and final URL")
        archive = Path(args.output)
        with zipfile.ZipFile(archive) as z:
            original = {name: z.read(name) for name in z.namelist()}
        manifest_path = d / "manifest.json"
        manifest_path.write_bytes(original["manifest.json"])
        no_intermediate = d / "signature-without-intermediate"
        wallet.openssl("smime", "-sign", "-binary", "-in", manifest_path,
                       "-signer", d / "leaf.pem", "-inkey", d / "leaf.key",
                       "-outform", "DER", "-out", no_intermediate)
        payload = d / "payload"
        payload.mkdir()
        for name in wallet.PAYLOAD:
            (payload / name).write_bytes(original[name])
        spec = json.loads(original["pass.json"])
        spec["teamIdentifier"] = "WRONGTEAM1"
        (payload / "pass.json").write_text(json.dumps(spec), encoding="utf-8")
        expect_failure("wrong Team ID", lambda: wallet.validate_payload(payload, "TESTTEAM01"))
        spec["teamIdentifier"] = "TESTTEAM01"
        spec["barcodes"][0]["message"] = "https://example.com/"
        (payload / "pass.json").write_text(json.dumps(spec), encoding="utf-8")
        expect_failure("outdated QR URL", lambda: wallet.validate_payload(payload, "TESTTEAM01"))
        for label, modifications in (
                ("tampered manifest payload", {"logo.png": original["logo.png"] + b"tamper"}),
                ("unexpected private-key archive entry", {"private.key": b"fake test marker"}),
                ("broken signature", {"signature": b"invalid"}),
                ("missing embedded intermediate", {"signature": no_intermediate.read_bytes()})):
            damaged = d / (label.replace(" ", "-") + ".pkpass")
            with zipfile.ZipFile(damaged, "w") as z:
                for name, data in {**original, **modifications}.items():
                    z.writestr(name, data)
            validation = d / label.replace(" ", "-")
            validation.mkdir()
            (validation / "apple-root.pem").write_bytes((d / "root.pem").read_bytes())
            (validation / "wwdr.pem").write_bytes((d / "intermediate.pem").read_bytes())
            expect_failure(label, lambda: wallet.validate_archive(damaged, d / "leaf.pem", validation))
        args.key = str(d / "root.key")
        expect_failure("mismatched private key", lambda: wallet.build(args))
        wallet.fetch = lambda url: (b"<html>different site</html>", url)
        expect_failure("wrong website content", lambda: wallet.verify_website(wallet.FINAL_URL))
        expect_failure("unapproved URL", lambda: wallet.verify_website("https://example.com/"))
        print("All Wallet build checks passed using disposable QA credentials. No production pass was signed.")


if __name__ == "__main__":
    main()
