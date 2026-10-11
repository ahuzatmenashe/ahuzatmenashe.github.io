#!/usr/bin/env python3
"""Build and validate a real Wallet pass locally with Python stdlib + OpenSSL.

Compatible with Alpine/iSH. No signing material is uploaded or logged.
The template intentionally omits Team ID; the signing certificate supplies it.
"""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import urllib.request
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PASS_TYPE = "pass.com.ahuzatmenashe.businesscard"
FINAL_URL = "https://ahuzatmenashe.github.io/"
WWDR_URL = "https://www.apple.com/certificateauthority/AppleWWDRCAG4.cer"
ROOT_URL = "https://www.apple.com/appleca/AppleIncRootCertificate.cer"
WWDR_SHA256 = "ea4757885538dd8cb59ff4556f676087d83c85e70902c122e42c0808b5bce14c"
ROOT_SHA256 = "b0b1730ecbc7ff4505142c49f1295e6eda6bcaed7e2c68c5be91b5a11001f024"
SIZES = {"icon": (29, 29), "logo": (160, 50), "thumbnail": (90, 90)}
ASSETS = {name + ("" if scale == 1 else "@%dx" % scale) + ".png":
          (size[0] * scale, size[1] * scale)
          for name, size in SIZES.items() for scale in (1, 2, 3)}
PAYLOAD = set(ASSETS) | {"pass.json"}
ARCHIVE_FILES = PAYLOAD | {"manifest.json", "signature"}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def openssl(*args, data=None):
    executable = os.environ.get("OPENSSL", "openssl")
    result = subprocess.run([executable, *map(str, args)], input=data,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    # Never dump subprocess output: it can contain signing material.
    require(result.returncode == 0,
            "OpenSSL %s failed. Check certificate validity, chain, paths and device clock."
            % args[0])
    return result.stdout


def cert_to_pem(path, destination):
    raw = Path(path).read_bytes()
    fmt = "PEM" if raw.startswith(b"-----BEGIN CERTIFICATE-----") else "DER"
    pem = openssl("x509", "-inform", fmt, "-in", path, "-outform", "PEM")
    destination.write_bytes(pem)
    return pem


def cert_identity(path):
    subject = openssl("x509", "-in", path, "-noout", "-subject",
                      "-nameopt", "RFC2253").decode("utf-8")
    subject = subject.removeprefix("subject=").strip()
    team = re.search(r"(?:^|,)OU=([A-Z0-9]{10})(?:,|$)", subject)
    uid = re.search(r"(?:^|,)UID=([^,]+)(?:,|$)", subject)
    require(team is not None, "No valid 10-character Team ID in signing certificate OU.")
    require(uid is not None and uid.group(1) == PASS_TYPE,
            "Signing certificate UID does not match the registered Pass Type ID.")
    openssl("x509", "-in", path, "-noout", "-checkend", "0")
    return team.group(1)


def fetch(url):
    request = urllib.request.Request(url, headers={"User-Agent": "Ahuzat-Menashe-Wallet/1.0"})
    with urllib.request.urlopen(request, timeout=45) as response:
        require(response.status == 200, "HTTPS download did not return HTTP 200.")
        require(response.url.startswith("https://"), "HTTPS download redirected to HTTP.")
        return response.read(), response.url


def verify_website(url):
    require(url == FINAL_URL, "Only the requested final URL is approved for this kit.")
    html, resolved = fetch(url)
    require(resolved == url, "Final website redirected to a different URL.")
    require(hashlib.sha256(html).digest() == hashlib.sha256((ROOT / "index.html").read_bytes()).digest(),
            "Final website does not exactly match this kit's index.html. Publish it first, or download the latest kit.")
    return {"url": resolved, "sha256": hashlib.sha256(html).hexdigest()}


def prepare_chain(work, wwdr=None, apple_root=None):
    for provided, url, name, expected in (
            (wwdr, WWDR_URL, "wwdr.pem", WWDR_SHA256),
            (apple_root, ROOT_URL, "apple-root.pem", ROOT_SHA256)):
        path = Path(provided) if provided else work / (name + ".cer")
        if not provided:
            path.write_bytes(fetch(url)[0])
        cert_to_pem(path, work / name)
        der = openssl("x509", "-in", work / name, "-outform", "DER")
        require(hashlib.sha256(der).hexdigest() == expected,
                "Apple CA fingerprint differs from the verified official certificate.")
    openssl("verify", "-CAfile", work / "apple-root.pem", work / "wwdr.pem")


def validate_payload(directory, team):
    spec = json.loads((directory / "pass.json").read_text(encoding="utf-8"))
    require(spec.get("formatVersion") == 1, "Invalid pass format version.")
    require(spec.get("passTypeIdentifier") == PASS_TYPE, "Wrong Pass Type ID.")
    require(spec.get("teamIdentifier") == team, "Wrong Team ID.")
    require(bool(spec.get("serialNumber")) and bool(spec.get("organizationName"))
            and bool(spec.get("description")), "Required pass identity missing.")
    require("generic" in spec and not any(k in spec for k in ("boardingPass", "coupon", "storeCard", "eventTicket")),
            "Pass must use the generic style.")
    keys = []
    for section in ("headerFields", "primaryFields", "secondaryFields", "auxiliaryFields", "backFields"):
        for field in spec["generic"].get(section, []):
            require(isinstance(field.get("value"), (str, int, float)), "Invalid field value.")
            keys.append(field["key"])
    require(len(keys) == len(set(keys)), "Duplicate Wallet field key.")
    require(len(spec["generic"].get("primaryFields", [])) <= 1, "Too many primary fields.")
    require(sum(len(spec["generic"].get(k, [])) for k in ("secondaryFields", "auxiliaryFields")) <= 4,
            "Too many fields for a generic pass with QR.")
    barcodes = spec.get("barcodes", [])
    require(len(barcodes) == 1 and barcodes[0] == {
        "format": "PKBarcodeFormatQR", "message": FINAL_URL, "messageEncoding": "iso-8859-1"},
        "QR payload does not point to the approved final URL.")
    website = next(f["value"] for f in spec["generic"]["backFields"] if f["key"] == "website")
    require(website == FINAL_URL, "Back-field website and QR differ.")
    for name, size in ASSETS.items():
        data = (directory / name).read_bytes()
        require(data[:8] == b"\x89PNG\r\n\x1a\n", "Invalid PNG: " + name)
        require(struct.unpack(">II", data[16:24]) == size, "Wrong asset dimensions: " + name)
    return spec


def write_manifest(directory):
    manifest = {name: hashlib.sha1((directory / name).read_bytes()).hexdigest()
                for name in sorted(PAYLOAD)}
    (directory / "manifest.json").write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def validate_archive(archive, certificate, work):
    directory = work / "validate"
    directory.mkdir()
    with zipfile.ZipFile(archive) as z:
        names = z.namelist()
        require(len(names) == len(set(names)) and set(names) == ARCHIVE_FILES,
                "Archive contains missing, duplicated, nested or unapproved files.")
        require(all(i.file_size < 2_000_000 for i in z.infolist()), "Unexpected archive size.")
        require(z.testzip() is None, "Archive CRC validation failed.")
        for name in names:
            (directory / name).write_bytes(z.read(name))
    team = cert_identity(certificate)
    validate_payload(directory, team)
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    require(set(manifest) == PAYLOAD, "Manifest file set is invalid.")
    for name, digest in manifest.items():
        require(digest == hashlib.sha1((directory / name).read_bytes()).hexdigest(),
                "Manifest hash mismatch: " + name)
    cms = openssl("cms", "-cmsout", "-print", "-inform", "DER", "-in", directory / "signature").decode()
    require("eContent: <ABSENT>" in cms and "signingTime" in cms,
            "Signature must be detached and include a signing time.")
    verified = openssl("smime", "-verify", "-binary", "-inform", "DER",
                       "-in", directory / "signature", "-content", directory / "manifest.json",
                       "-CAfile", work / "apple-root.pem", "-purpose", "any",
                       "-signer", work / "actual-signer.pem")
    require(verified == (directory / "manifest.json").read_bytes(), "Signed content mismatch.")
    expected = openssl("x509", "-in", certificate, "-outform", "DER")
    actual = openssl("x509", "-in", work / "actual-signer.pem", "-outform", "DER")
    require(actual == expected, "Signature was not created by the supplied Pass Type certificate.")
    # Verify the intermediate is embedded (Wallet requires it), not supplied externally.
    chain = openssl("pkcs7", "-inform", "DER", "-in", directory / "signature", "-print_certs")
    embedded = re.findall(rb"-----BEGIN CERTIFICATE-----.*?-----END CERTIFICATE-----", chain, re.S)
    require(any(openssl("x509", "-outform", "DER", data=pem) ==
                openssl("x509", "-in", work / "wwdr.pem", "-outform", "DER") for pem in embedded),
            "Signature does not embed the WWDR G4 certificate.")
    return {"teamIdentifier": team, "passTypeIdentifier": PASS_TYPE,
            "files": len(names), "sha256": hashlib.sha256(Path(archive).read_bytes()).hexdigest()}


def build(args):
    key = Path(args.key).expanduser().resolve()
    require(key.is_file(), "Signing key file not found.")
    require(ROOT not in key.parents, "Keep the private key outside the public source directory.")
    output = Path(args.output).expanduser().resolve()
    require(output.parent.is_dir(), "Output folder does not exist; check the iSH Files mount.")
    require(output.name == "Ahuzat-Menashe.pkpass", "Use the required Ahuzat-Menashe.pkpass filename.")
    website = verify_website(args.url)
    with tempfile.TemporaryDirectory(prefix="ahuzat-wallet-") as temporary:
        work = Path(temporary)
        certificate = work / "pass-cert.pem"
        cert_to_pem(args.cert, certificate)
        team = cert_identity(certificate)
        prepare_chain(work, args.wwdr, args.apple_root)
        openssl("verify", "-CAfile", work / "apple-root.pem", "-untrusted", work / "wwdr.pem", "-purpose", "any", certificate)
        cert_public = openssl("x509", "-in", certificate, "-pubkey", "-noout")
        cert_der = openssl("pkey", "-pubin", "-outform", "DER", data=cert_public)
        key_der = openssl("pkey", "-in", key, "-pubout", "-outform", "DER")
        require(hashlib.sha256(cert_der).digest() == hashlib.sha256(key_der).digest(),
                "Private key does not match the certificate.")
        package = work / "package"
        package.mkdir()
        spec = copy.deepcopy(json.loads((HERE / "pass.template.json").read_text(encoding="utf-8")))
        spec["teamIdentifier"] = team
        (package / "pass.json").write_text(json.dumps(spec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        for name in ASSETS:
            shutil.copyfile(HERE / "assets" / name, package / name)
        validate_payload(package, team)
        write_manifest(package)
        openssl("smime", "-sign", "-binary", "-in", package / "manifest.json",
                "-signer", certificate, "-inkey", key, "-certfile", work / "wwdr.pem",
                "-outform", "DER", "-md", "sha256", "-out", package / "signature")
        archive = work / "Ahuzat-Menashe.pkpass"
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as z:
            for name in sorted(ARCHIVE_FILES):
                z.write(package / name, name)
        report = validate_archive(archive, certificate, work)
        report["website"] = website
        # Only write the final deliverable after every check passes.
        shutil.copyfile(archive, output)
        output.with_suffix(".validation.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print("Verified signed pass saved to: " + str(output))
        print("Pass Type ID: " + PASS_TYPE + "; certificate Team ID: " + team)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cert", required=True, help="Existing public pass.cer (DER or PEM)")
    parser.add_argument("--key", help="Existing private.key, outside this repository")
    parser.add_argument("--url", default=FINAL_URL)
    parser.add_argument("--output", default="/mnt/walletshare/Downloads/Ahuzat-Menashe.pkpass")
    parser.add_argument("--wwdr", help="Optional locally downloaded official WWDR G4 certificate")
    parser.add_argument("--apple-root", help="Optional locally downloaded official Apple Root CA")
    parser.add_argument("--validate", metavar="PKPASS", help="Validate an existing signed archive instead of building")
    args = parser.parse_args()
    try:
        if args.validate:
            with tempfile.TemporaryDirectory(prefix="ahuzat-validate-") as temporary:
                work = Path(temporary)
                certificate = work / "pass-cert.pem"
                cert_to_pem(args.cert, certificate)
                prepare_chain(work, args.wwdr, args.apple_root)
                report = validate_archive(Path(args.validate), certificate, work)
                report["website"] = verify_website(args.url)
                print(json.dumps(report, indent=2))
        else:
            require(args.key is not None, "--key is required when signing.")
            build(args)
    except (ValueError, OSError, KeyError, StopIteration, zipfile.BadZipFile) as error:
        print("Build stopped: " + str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
