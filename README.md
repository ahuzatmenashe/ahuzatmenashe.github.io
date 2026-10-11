# Ahuzat Menashe — digital business card and Apple Wallet

The website retains the original Hebrew RTL content, villa images, dark/gold
design and all six business links. No framework or server is required.

Approved final address: **https://ahuzatmenashe.github.io/**.
Repository: **https://github.com/ahuzatmenashe/ahuzatmenashe.github.io**.
The owner approved the existing organization `ahuzatmenashe` instead of the
originally proposed `ahuzatmenashecard`. The original personal repository is
preserved at https://github.com/bar987789-oss/ahuzat-menashe-card.

The production pass has been signed locally with the owner's existing Apple
certificate and matching private key. Download it at
**https://ahuzatmenashe.github.io/Ahuzat-Menashe.pkpass**. Its certificate-derived
Team ID is `CABL4XGRQ7`; the Pass Type ID is
`pass.com.ahuzatmenashe.businesscard`. The detached signature, certificate chain,
embedded WWDR G4, manifest hashes, allowed archive files and final live QR URL
have passed verification. See `wallet/production.validation.json` for the
public validation result. Actual iPhone installation remains to be confirmed.

The private key is stored outside this checkout at
`C:\Users\bar98\Ahuzat-Wallet-Private\private.key` and is never published.

## Wallet source

`wallet/pass.template.json` is source, not an installable pass. It deliberately
has no Team ID: `wallet/build_pass.py` extracts the actual Team ID from the OU
of the existing Apple certificate and checks its UID against
`pass.com.ahuzatmenashe.businesscard`. No identity is guessed.

The generic pass uses the website's colors, a matching typeset logo, the actual
villa photo as a thumbnail, Hebrew fields with right alignment, contact links
on the back, and Wallet's native QR renderer pointing to the approved live URL.
PNG assets are supplied at 1x/2x/3x: icon 29x29, logo 160x50, thumbnail 90x90
points. Wallet controls the final field layout and text direction; confirm it
on the target iPhone.

## Build on the iPad in iSH

Keep the existing files **outside** the downloaded kit:

- `/root/wallet/private.key` — stays on the iPad; never upload or paste its contents.
- `/root/wallet/pass.cer` — existing Apple-issued certificate.
- `/root/wallet/certificate.csr` — already used; no new CSR/certificate needed.

Once GitHub Pages is live, paste this block into iSH:

```sh
set -eu
apk add python3 openssl ca-certificates curl unzip
cd /root/wallet
test -f private.key
test -f pass.cer
test -d /mnt/walletshare/Downloads
curl --fail --location --proto '=https' --tlsv1.2 \
  https://ahuzatmenashe.github.io/Ahuzat-Wallet-Kit.zip \
  -o /mnt/walletshare/Downloads/Ahuzat-Wallet-Kit.zip
unzip -o /mnt/walletshare/Downloads/Ahuzat-Wallet-Kit.zip -d /root/wallet
sh /root/wallet/Ahuzat-Wallet-Kit/wallet/build.sh \
  --cert /root/wallet/pass.cer \
  --key /root/wallet/private.key \
  --output /mnt/walletshare/Downloads/Ahuzat-Menashe.pkpass
```

Installing Python/OpenSSL adds no Python packages. The script works with
OpenSSL 1.1.1 and 3.x. An encrypted key can prompt for its password locally.
The mounted Downloads directory must already exist. If a command fails, stop
and report the error text; do not paste any private-key or password contents.

The build downloads the current Pass Type ID intermediate **WWDR G4** and
Apple Root CA from official Apple HTTPS endpoints. It checks their SHA-256
certificate fingerprints and the complete certificate chain, validity and
public-key match. A certificate using a different issuer is rejected for
inspection rather than replaced. Apple can rotate its certificates; update
the pinned public fingerprints only after reviewing Apple's official PKI.

Before signing, the script verifies the final URL returns HTTP 200 without
changing address and that its HTML exactly matches this kit's `index.html`.
It then generates the real `pass.json`, SHA-1 `manifest.json` required by
PassKit, a detached PKCS#7 signature with signing time and embedded WWDR, and
the ZIP archive **Ahuzat-Menashe.pkpass**. It validates the manifest, signature,
signer identity and archive before copying the output into Downloads.
Only approved pass files enter the archive. No key, certificate, CSR, HTML or
build script is packaged in the pass itself.

A public-data validation report is saved alongside it as
`Ahuzat-Menashe.validation.json`. To check the pass again:

```sh
python3 /root/wallet/Ahuzat-Wallet-Kit/wallet/build_pass.py \
  --cert /root/wallet/pass.cer \
  --validate /mnt/walletshare/Downloads/Ahuzat-Menashe.pkpass
```

## Build locally on Windows

With Python 3.9+ and OpenSSL on PATH, run from this repository:

```powershell
python wallet/build_pass.py --cert .\pass.cer --key ..\Ahuzat-Wallet-Private\private.key --output .\Ahuzat-Menashe.pkpass
```

If OpenSSL is supplied by Git for Windows, set its location before running:

```powershell
$env:OPENSSL = 'C:\Program Files\Git\usr\bin\openssl.exe'
```

The certificate remains an ignored local file. The private key must remain
outside the source checkout. The same live-site, identity and signature checks
apply on Windows and iSH.

## Add to Apple Wallet on an iPhone

Open **https://ahuzatmenashe.github.io/Ahuzat-Menashe.pkpass** in Safari on the
iPhone and tap **Add** when the pass preview appears. If Safari downloads the
file instead, open it from Files on the iPhone.

In the iPad Files app, open the mounted Downloads folder and share
`Ahuzat-Menashe.pkpass` to the iPhone with AirDrop, or save it in iCloud Drive
and open it from Files on the iPhone. Open the pass and tap **Add**. Verify
the Hebrew text, photo, phone number and back links. Scan the QR using another
device and confirm it opens https://ahuzatmenashe.github.io/.

iPad does not provide the iPhone Wallet installation flow. A successful build
does not prove installation: record actual iPhone confirmation before declaring
completion. The signed production file is available; device acceptance has not
yet been confirmed.

For a public website download button, first confirm the actual iPhone download
and installation flow for the signed pass, then add the button to the website.
The public kit is a source download, not an Add to Wallet link.

## Reproduce checks and package

```sh
python3 tools/test_wallet.py
python3 tools/pack_wallet_kit.py
```

The signing test generates disposable synthetic certificates in the operating
system temporary directory and deletes them when finished. Test-only certificate
fingerprints and the website response are substituted in memory; there is no
production option to bypass HTTPS, certificate verification or signing checks.
It verifies real detached signing and rejects wrong Team IDs, incorrect QR
URLs, tampering, unexpected key entries, corrupt signatures and mismatched keys.
It does not sign an Apple pass or prove iPhone acceptance.

`Ahuzat-Wallet-Kit.zip` contains an explicit allowlist of public sources and
assets. The packager excludes Git history, environment files, output passes,
credentials and QA artifacts, and rejects private-key PEM markers. The ZIP is
ignored by default; explicitly add the reviewed ZIP when publishing it:
`git add -f Ahuzat-Wallet-Kit.zip`.

GitHub Pages uses `main` at `/` with HTTPS enabled. `.nojekyll` serves the static
files directly. No CI signing workflow or cloud secret storage is used.

## Specifications

- [Apple pass design and creation](https://developer.apple.com/library/archive/documentation/UserExperience/Conceptual/PassKit_PG/Creating.html)
- [Apple WWDR intermediate certificates](https://developer.apple.com/help/account/certificates/wwdr-intermediate-certificates/)
- [Apple official PKI](https://www.apple.com/certificateauthority/)
- [GitHub Pages documentation](https://docs.github.com/en/pages/quickstart)
