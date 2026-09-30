#!/bin/sh

set -eu
umask 077

if [ -z "${PGUSER:-}" ] || [ -z "${PGDATABASE:-}" ] || [ -z "${CCL_DATABASE_USER:-}" ]; then
    echo "Database administrator, database, and application role must be configured." >&2
    exit 2
fi
if [ "$PGUSER" = "$CCL_DATABASE_USER" ]; then
    echo "The application database role must differ from the PostgreSQL administrator." >&2
    exit 2
fi

password_file="${CCL_DATABASE_PASSWORD_FILE:-/run/ccl-db-credentials/password}"
password_directory="$(dirname -- "$password_file")"
if [ -L "$password_file" ] || [ ! -d "$password_directory" ]; then
    echo "The application database credential directory is unavailable or unsafe." >&2
    exit 1
fi
chmod 0700 -- "$password_directory"

temporary_password=""
cleanup() {
    if [ -n "$temporary_password" ]; then
        rm -f -- "$temporary_password"
    fi
}
trap cleanup EXIT HUP INT TERM

if [ ! -e "$password_file" ]; then
    temporary_password="${password_file}.partial.$$"
    if [ -e "$temporary_password" ] || [ -L "$temporary_password" ]; then
        echo "A temporary credential path already exists; refusing to overwrite it." >&2
        exit 1
    fi
    dd if=/dev/urandom bs=32 count=1 2>/dev/null | od -An -tx1 | tr -d ' \n' >"$temporary_password"
    chmod 0600 -- "$temporary_password"
    mv -n -- "$temporary_password" "$password_file"
fi

if [ -L "$password_file" ] || [ ! -f "$password_file" ]; then
    echo "The application database credential must be a regular file." >&2
    exit 1
fi
chmod 0600 -- "$password_file"
app_password="$(cat -- "$password_file")"
case "$app_password" in
    ''|*[!0-9a-f]*)
        echo "The application database credential is empty or malformed." >&2
        exit 1
        ;;
esac
if [ "${#app_password}" -ne 64 ]; then
    echo "The application database credential has an unexpected length." >&2
    exit 1
fi

{
    # Keep the password out of process arguments; its validated hex alphabet
    # is safe as a single psql variable value on this input stream.
    printf '\\set app_password %s\n' "$app_password"
    cat <<'SQL'
SELECT format('CREATE ROLE %I LOGIN PASSWORD %L', :'app_role', :'app_password')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'app_role')
\gexec

ALTER ROLE :"app_role" WITH LOGIN PASSWORD :'app_password'
    NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS NOINHERIT;
GRANT CONNECT ON DATABASE :"database" TO :"app_role";
GRANT USAGE, CREATE ON SCHEMA public TO :"app_role";
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO :"app_role";
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO :"app_role";
ALTER DEFAULT PRIVILEGES FOR ROLE :"admin_role" IN SCHEMA public
    GRANT ALL PRIVILEGES ON TABLES TO :"app_role";
ALTER DEFAULT PRIVILEGES FOR ROLE :"admin_role" IN SCHEMA public
    GRANT ALL PRIVILEGES ON SEQUENCES TO :"app_role";

SELECT format('ALTER TABLE %I.%I OWNER TO %I', schemaname, tablename, :'app_role')
FROM pg_tables
WHERE schemaname = 'public' AND tableowner = current_user
\gexec

SELECT format('ALTER SEQUENCE %I.%I OWNER TO %I', namespace.nspname, relation.relname, :'app_role')
FROM pg_class AS relation
JOIN pg_namespace AS namespace ON namespace.oid = relation.relnamespace
WHERE namespace.nspname = 'public'
  AND relation.relkind = 'S'
  AND pg_get_userbyid(relation.relowner) = current_user
\gexec

SELECT format('REVOKE %I FROM %I', granted.rolname, member.rolname)
FROM pg_auth_members AS membership
JOIN pg_roles AS granted ON granted.oid = membership.roleid
JOIN pg_roles AS member ON member.oid = membership.member
WHERE member.rolname = :'app_role'
\gexec
SQL
} | psql --no-psqlrc --set=ON_ERROR_STOP=1 \
    --set=admin_role="$PGUSER" \
    --set=app_role="$CCL_DATABASE_USER" \
    --set=database="$PGDATABASE"

unset app_password
echo "Application database role configured with least-privilege attributes."
