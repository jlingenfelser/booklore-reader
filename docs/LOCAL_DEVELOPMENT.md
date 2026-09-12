# Local development / test deployment

The same repository can be tested on Pop!_OS or another Docker host before pushing to Linode.

## First local run

```bash
cp .env.example .env
```

Edit `.env` and set a writable local state directory, for example:

```bash
STATE_DIR=/home/YOUR_USER/booklore-reader-state
SITE_ADDRESS=:8080
```

If using a nonstandard HTTP port, also change the Compose gateway port mapping for local testing or use the production `:80` mapping on a machine where port 80 is available.

Generate safe DB passwords rather than leaving `CHANGE_ME`, or simply delete `.env` and run:

```bash
STATE_DIR="$HOME/booklore-reader-state" SITE_ADDRESS=:80 ./scripts/init-env.sh :80
```

Then:

```bash
./scripts/deploy.sh
```

## Rebuilding after customization changes

Edit only tracked source such as:

```text
customizations/apply-customizations.py
piper/
scripts/
docker-compose.yml
```

Then run:

```bash
./scripts/validate.sh
./scripts/deploy.sh
```

Do not edit `.build/booklore-src` as the source of truth. It is regenerated from the pinned upstream release.

## Inspect generated source

After `./scripts/prepare-source.sh`, the customized source is available at:

```text
.build/booklore-src
```

It is useful for inspecting the final Angular/Java code or diagnosing build errors, but any permanent fix should be made in `customizations/apply-customizations.py`.
