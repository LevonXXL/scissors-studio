# Scissors production layout

The live tree is under `/home/scissors`. Git releases are stored in
`/home/scissors/releases/<commit>` and `/home/scissors/current` selects the
active release. Media, collected static files, and upload temporary files are
separate directories under `/home/scissors`. Legacy `/opt/scissors-*` and
`/srv/scissors/*` paths are symlinks for rollback compatibility.

`scissors-backend` and `scissors-frontend` run as separate system users. Both
can read the active release but cannot change its code. Django can write to
media, static, and its temporary directory. The SSR process has no writable
application path. systemd uses a private `/home` view and binds only the active
release and the backend data directories into each service. Python and Node
stdout/stderr go to the journal; Gunicorn captures Python tracebacks.

Secrets are root-owned in `/etc/scissors/`. The backend and VAPID environment
files are readable by the backend service group. The GitHub deploy private key
is `root:scissors`, mode `0440`; only the `scissors` deployment user can read
it. `scissors` cannot read backend or VAPID secrets. Its sudoers entry permits
only restarting `scissors-backend.service` and `scissors-frontend.service`.

Angie reads static and media files through per-user ACLs. Angie can traverse
the required directories and read files, but cannot write or execute files in
either tree. Directory execute permission is required for traversal; regular
files have no execute bits. Angie configuration is limited to Scissors
virtual hosts. Other sites and services are not changed.

## Git deployment

The Makefiles upload the small deployment helper, then the server fetches the
GitHub `main` branch using `/etc/scissors/github_deploy_key`. Add the matching
public key to the private repository as a read-only deploy key before the first
Git deployment. The helper builds a new release, switches `current` atomically,
restarts both services, checks health, and restores the previous release if
startup fails. It refuses to deploy until the current Telegram bot, page
breadcrumb, Google Maps, upload-security, analytics, and frontend breadcrumb
sources are present in the remote commit. The current production snapshot
remains available until a Git release is deployed.

The new canonical origins are `https://studio.scissors.group`,
`https://api.studio.scissors.group`, and
`https://studio.static.scissors.group`. The apex site uses a temporary 302
redirect to the studio subdomain. The active SSR bundle still requests the
former static hostname, which now redirects and serves no files; the CSP
bridge allows both hosts during this transition. The next Git-built SSR
release uses the new static host directly, after which that compatibility
redirect and the temporary CSP allowance can be removed.

## Scheduled sitemap

To install it, open `sudo crontab -u scissors-backend -e` and add the entries
from `ops/deploy/sitemap.crontab.example`. It runs at 03:15 Moscow time and
writes directly to `/home/scissors/static/sitemap.xml`, which Angie serves.
It sources both protected environment files and sends output to syslog. A
systemd timer is preferable if journald logging and the service sandbox should
also apply.

## Checks

- `angie -t`, then reload Angie after a config change.
- `systemd-analyze verify` for the three Scissors units.
- Confirm both app services are active and inspect tracebacks with
  `journalctl -u scissors-backend.service`.
- Check the 302 from `scissors.group`, HTTPS 200 from the studio host, and
  static/media delivery from the static host.
- Before deployment, confirm there is enough free disk space for a new Git
  release and its Node dependencies.
