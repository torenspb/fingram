# Fingram

A single-user Telegram bot that appends expenses to Google Sheets.
Send `12.50 lunch` in your private chat with the bot. Negative amounts (refunds)
and decimal commas are accepted; descriptions are limited to 500 characters.
Columns A–C contain date (displayed as `dd.mm.yyyy`), numeric amount and literal description.
Formulas in descriptions are stored as text. Use a dedicated contiguous table on
the first worksheet, optionally with a header row; keep unrelated tables elsewhere.
New expenses are appended after the last populated row of that worksheet.

## Configuration

Create a Telegram bot through BotFather and a dedicated Google service account.
Enable the Sheets API, download its JSON key, and share only your expense sheet
with the service account as an editor. No project-wide Editor role or domain-wide
delegation is needed. Disable group invitations through BotFather as an extra precaution.

```sh
cp vars/variables.example.json vars/variables.local.json
chmod 700 vars
chmod 600 vars/variables.local.json
```

Copy the Google key to `vars/service_acc_secret.json` and `chmod 600` that file.
Edit `variables.local.json`: set your numeric Telegram user ID, sheet URL, token
and optionally timezone (defaults to `Europe/Tallinn`, Estonia). Exactly one user is supported. The key filename is relative to the
configuration directory. The old tracked `vars/variables.json` is now an example
file; migrate real settings to `variables.local.json`. Never commit credentials.
Rotate credentials if they have previously been published.

## Docker Compose (Intel Linux or 64-bit Raspberry Pi OS)

Install Docker Engine with the Compose and Buildx plugins. The same Dockerfile
uses Python 3.15.2 and supports `linux/amd64` and `linux/arm64`; Compose builds for
the host architecture automatically. No inbound ports or router forwarding are needed.

Run the container with your unprivileged Linux user's UID/GID so it can read the
private credential files you own (do not run these commands from a root login):

```sh
printf 'FINGRAM_UID=%s\nFINGRAM_GID=%s\n' "$(id -u)" "$(id -g)" > .env
docker compose up -d --build
docker compose logs --tail=50 bot
```

Alternatively, keep the default container UID/GID 10001 and make that account the
owner of the credential directory and its files. Compose mounts credentials
read-only, uses a read-only root filesystem, drops capabilities and rotates logs.
Run only one instance per Telegram token.

To build both architectures into a registry image (requires a Buildx builder with
both architectures available, through native nodes or QEMU):

```sh
docker buildx create --name fingram-builder --driver docker-container --use
docker buildx build --platform linux/amd64,linux/arm64 -t YOUR_REGISTRY/fingram:VERSION --push .
```

To deploy that image on either machine, set `FINGRAM_IMAGE=YOUR_REGISTRY/fingram:VERSION`
in `.env`, then run `docker compose pull && docker compose up -d --no-build`.
Use a version tag or manifest digest you control. Rebuild periodically with
`docker compose build --pull` and recreate with `docker compose up -d` for base
image security updates; review pinned Python/dependency upgrades periodically.

## Local execution and remote provisioning

Use a supported Python (the container uses 3.15.2):

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python bot.py
```

Run from the repository directory, or set `FINGRAM_CONFIG` to an absolute config
path. `provision.yml` copies the reviewed source, sets private credential
permissions, and builds on the remote host. It requires Docker and Compose there.
Set `FINGRAM_LOCAL_VARS` and `FINGRAM_ACC_SECRET` to your local files, then run
`ansible-playbook -i 'YOUR_PI_ADDRESS,' provision.yml`. For this playbook, configure
`service_secret` as `service_acc_secret.json`.

## Failure behavior and tests

Writes are server-side appends and handlers run sequentially. Failed writes are
not automatically retried: a timeout can occur after Google committed a row.
If told to check the sheet, inspect it before resending. A failed Telegram
confirmation does not repeat the spreadsheet write. Polling reconnects after
errors; logs contain operation names and exception types, not exception bodies.
This does not provide exactly-once delivery across crashes/restarts.

```sh
.venv/bin/python -m unittest discover -s tests -v
```
