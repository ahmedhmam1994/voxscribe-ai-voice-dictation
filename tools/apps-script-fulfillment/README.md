# VoxScribe Pro fulfillment (Google Apps Script)

Emails a Pro license key to the buyer within seconds of a Gumroad sale. It runs in your
own Google account, for free. It is separate from the website and from `scripts/fulfill_sales.py`.

## How it works

1. Gumroad's "Ping" calls the script's web address on every sale.
2. The script checks the secret in the address, then asks Gumroad's API about that sale.
   A faked ping for a sale that does not exist is ignored.
3. For a paid, not refunded VoxScribe Pro sale it signs a key and emails it from your Gmail
   (a copy goes to `OWNER_EMAIL`). Each sale is recorded, so a repeated ping sends nothing.
4. If the email fails, the key is kept and a timer retries every 10 minutes with the same key.

The signing code is in `Ed25519.gs` (about 250 lines, plain numbers, no third-party library) and is tested
against the RFC 8032 test vector, Node's own Ed25519, and the Python verifier the Windows
app uses. Run the tests from the repo root with `python -m pytest tests/test_apps_script_fulfillment.py`.

## Setup (once, about 15 minutes)

1. **Gumroad token.** Gumroad, Settings, Advanced, Applications: create an application, then
   generate an access token. Keep it to paste in step 3.
2. **New project.** Go to https://script.google.com, choose New project, and name it
   "VoxScribe fulfillment". Add two script files and paste in the contents of `Code.gs` and
   `Ed25519.gs` from this folder.
3. **Script properties.** Project Settings, Script Properties, add:
   - `GUMROAD_ACCESS_TOKEN`: the token from step 1.
   - `PING_SECRET`: a long random string. Make one with
     `python -c "import secrets; print(secrets.token_urlsafe(32))"`.
   - `SIGNING_SEED_B64`: run `python scripts\copy_signing_key.py`, then paste. It copies the
     key to the clipboard without showing it. Copy something else afterwards to clear it.
   - `OWNER_EMAIL`: your Gmail address, for a copy of every email and as the reply address.
4. **Run `setup`.** In the editor choose the `setup` function and press Run. Google asks you to
   allow sending email and reaching other services. It shows an "unverified app" warning
   because it is your own script: choose Advanced, then continue. `setup` checks the
   properties, starts the retry timer and runs a signing self test.
5. **Deploy.** Deploy, New deployment, type Web app, Execute as Me, Who has access Anyone
   (Gumroad has to be able to call it). Copy the Web app URL ending in `/exec`.
6. **Gumroad ping.** Gumroad, Settings, Advanced, Ping. Set the URL to
   `<web app URL>?s=<PING_SECRET>` and save.
7. **Try it for real.** Make a 100 percent off discount code for Pro and buy it yourself. The key
   should arrive in seconds. In Apps Script, Executions shows each run and any error.

Do not leave the old local tool running too. After the first real sale works, run
`python scripts\fulfill_sales.py --mark-existing` so it cannot hand out a second key.

## Changing the code later

Edit the files, then Deploy, Manage deployments, edit the deployment and pick a new version.
The URL stays the same.

## Things to know

- **Free limits:** about 100 emails a day from a personal Gmail account, which is far more than
  the sales volume.
- **Where the record is:** the BCC copy in your inbox, and each sale's entry in Script
  Properties (`sale:<id>`). `sold_keys.csv` is not updated by this tool.
- **Reissuing on purpose:** delete the `sale:<id>` property and send the ping again.
- **Gumroad may show the ping as a redirect (302).** The script has already run by then, and a
  repeated ping is harmless.
- **The signing key is now in your Google account.** Keep 2-step verification on. A leaked key
  would let someone make keys, so treat the Google account like the key itself.
