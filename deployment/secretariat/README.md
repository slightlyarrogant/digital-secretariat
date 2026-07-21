# Reference PostgreSQL deployment assets

These files describe the schema and least-privilege roles used by the 0.1 reference adapter.

Do not apply them directly to an unknown company database. Follow
[`docs/INSTALLATION.md`](../../docs/INSTALLATION.md) or the normative
[`docs/ai/INSTALLATION_CONTRACT.md`](../../docs/ai/INSTALLATION_CONTRACT.md): inspect the schema,
adapt the SQL, test it on a disposable clone, record hashes and evidence, then obtain the G2 human
approval for the exact production commands.

`deploy.sh` installs a reviewed, committed release and rendered systemd units. It deliberately does
not run migrations. Database changes and runtime deployment are separate approval and rollback
boundaries.
