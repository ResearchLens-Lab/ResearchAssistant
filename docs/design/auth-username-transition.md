# Authentication username transition

Migration `0002_usernames` adds a nullable `users.username` field and a unique index. Existing users keep their records, password hashes, and email login; their username remains null until a future account profile flow allows them to choose one. The migration does not derive usernames from email addresses.

New registrations require a 3–24 character username. The API lowercases it before persistence, rejects spaces, leading/trailing punctuation, and the reserved names `admin`, `support`, and `root`. The database unique index is the final concurrency-safe check. The 12-character password policy applies to new registrations; existing password hashes remain valid and existing email/password login remains supported.

Username availability is not checked separately. Registration itself reports a username conflict without exposing the associated email. Password recovery and server-side rate limiting are not implemented in the current backend; the login screen states the recovery limitation directly.

To apply the migration to a configured database, run `alembic -c backend/alembic.ini upgrade head` from the repository root after setting the database environment variables.
