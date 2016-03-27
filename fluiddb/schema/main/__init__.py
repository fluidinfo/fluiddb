from storm.zope.schema import ZSchema


def createSchema():
    """Create the L{Schema} instance for the main database."""
    from fluiddb.schema import main as patches

    return ZSchema(CREATE, DROP, DELETE, patches)


CREATE = [
    """
    GRANT SELECT
        ON TABLE patch TO fluidinfo
    """,

    # FIXME Ideally user.namespace_id should declare 'REFERENCES namespace' but
    # circular dependencies make this awkward.  Could we wire this up with an
    # ALTER TABLE statement or would the circular dependency cause problems
    # when inserting rows...?
    """
    CREATE TABLE users (
        id SERIAL NOT NULL PRIMARY KEY,
        object_id UUID NOT NULL UNIQUE,
        role INTEGER NOT NULL,
        username TEXT NOT NULL UNIQUE,
        password_hash BYTEA NOT NULL,
        fullname TEXT NOT NULL,
        email TEXT,
        namespace_id INTEGER,
        creation_time TIMESTAMP NOT NULL DEFAULT (now() AT TIME ZONE 'UTC'))
    """,
    """
    GRANT SELECT, UPDATE, INSERT, DELETE
        ON TABLE users TO fluidinfo
    """,

    """
    CREATE TABLE twitter_users (
        user_id INTEGER NOT NULL PRIMARY KEY REFERENCES users
            ON DELETE CASCADE,
        uid INTEGER NOT NULL UNIQUE,
        creation_time TIMESTAMP NOT NULL DEFAULT (now() AT TIME ZONE 'UTC'))
    """,
    """
    GRANT SELECT, UPDATE, INSERT, DELETE
        ON TABLE twitter_users TO fluidinfo
    """,

    """
    CREATE TABLE oauth_consumers (
        user_id INTEGER NOT NULL PRIMARY KEY REFERENCES users
            ON DELETE CASCADE,
        secret BYTEA NOT NULL,
        creation_time TIMESTAMP NOT NULL DEFAULT (now() AT TIME ZONE 'UTC'))
    """,
    """
    GRANT SELECT, UPDATE, INSERT, DELETE
        ON TABLE oauth_consumers TO fluidinfo
    """,


    """
    CREATE TABLE namespaces (
        id SERIAL NOT NULL PRIMARY KEY,
        object_id UUID NOT NULL UNIQUE,
        parent_id INTEGER REFERENCES namespaces ON DELETE CASCADE,
        creator_id INTEGER NOT NULL REFERENCES users ON DELETE CASCADE,
        path TEXT NOT NULL UNIQUE,
        name TEXT NOT NULL,
        creation_time TIMESTAMP NOT NULL DEFAULT (now() AT TIME ZONE 'UTC'))
    """,
    """
    GRANT SELECT, UPDATE, INSERT, DELETE
        ON TABLE namespaces TO fluidinfo
    """,

    """
    CREATE TABLE namespace_permissions (
        namespace_id INTEGER NOT NULL PRIMARY KEY
            REFERENCES namespaces ON DELETE CASCADE,
        create_policy BOOLEAN NOT NULL,
        create_exceptions INTEGER[] NOT NULL,
        update_policy BOOLEAN NOT NULL,
        update_exceptions INTEGER[] NOT NULL,
        delete_policy BOOLEAN NOT NULL,
        delete_exceptions INTEGER[] NOT NULL,
        list_policy BOOLEAN NOT NULL,
        list_exceptions INTEGER[] NOT NULL,
        control_policy BOOLEAN NOT NULL,
        control_exceptions INTEGER[] NOT NULL)
    """,
    """
    GRANT SELECT, UPDATE, INSERT, DELETE
        ON TABLE namespace_permissions TO fluidinfo
    """,

    """
    CREATE TABLE tags (
        id SERIAL NOT NULL PRIMARY KEY,
        object_id UUID NOT NULL UNIQUE,
        namespace_id INTEGER NOT NULL REFERENCES namespaces ON DELETE CASCADE,
        creator_id INTEGER NOT NULL REFERENCES users ON DELETE CASCADE,
        path TEXT NOT NULL UNIQUE,
        name TEXT NOT NULL,
        creation_time TIMESTAMP NOT NULL DEFAULT (now() AT TIME ZONE 'UTC'))
    """,
    """
    GRANT SELECT, UPDATE, INSERT, DELETE
        ON TABLE tags TO fluidinfo
    """,

    """
    CREATE TABLE tag_permissions (
        tag_id INTEGER NOT NULL PRIMARY KEY REFERENCES tags ON DELETE CASCADE,
        update_policy BOOLEAN NOT NULL,
        update_exceptions INTEGER[] NOT NULL,
        delete_policy BOOLEAN NOT NULL,
        delete_exceptions INTEGER[] NOT NULL,
        control_policy BOOLEAN NOT NULL,
        control_exceptions INTEGER[] NOT NULL,
        write_value_policy BOOLEAN NOT NULL,
        write_value_exceptions INTEGER[] NOT NULL,
        read_value_policy BOOLEAN NOT NULL,
        read_value_exceptions INTEGER[] NOT NULL,
        delete_value_policy BOOLEAN NOT NULL,
        delete_value_exceptions INTEGER[] NOT NULL,
        control_value_policy BOOLEAN NOT NULL,
        control_value_exceptions INTEGER[] NOT NULL)
    """,
    """
    GRANT SELECT, UPDATE, INSERT, DELETE
        ON TABLE tag_permissions TO fluidinfo
    """,

    """
    CREATE TABLE tag_values (
        id SERIAL NOT NULL PRIMARY KEY,
        creator_id INTEGER NOT NULL REFERENCES users ON DELETE CASCADE,
        tag_id INTEGER NOT NULL REFERENCES tags ON DELETE CASCADE,
        object_id UUID NOT NULL,
        creation_time TIMESTAMP NOT NULL DEFAULT (now() AT TIME ZONE 'UTC'),
        value BYTEA,
        UNIQUE(tag_id, object_id))
    """,

    # Use 3000 rows as a sample for the table analyzer to provide more
    # information to the query planner, this makes queries for the object_id
    # column in the tag_values table (such as the one in the DIH) use the index
    # instead of a sequential scan, and thus much faster.
    """
    ALTER TABLE tag_values ALTER COLUMN object_id SET STATISTICS 3000
    """,

    """
    GRANT SELECT, UPDATE, INSERT, DELETE
        ON TABLE tag_values TO fluidinfo
    """,
    """
    CREATE INDEX tag_values_object_id_idx ON tag_values (object_id)
    """,
    """
    CREATE INDEX tag_values_creator_id_idx ON tag_values (creator_id)
    """,
    """
    CREATE INDEX tag_values_creation_time_idx
        ON tag_values (creation_time DESC)
    """,
    """
    CREATE INDEX tag_values_creator_creation_idx
        ON tag_values (creator_id, creation_time DESC)
    """,

    """
    CREATE TABLE opaque_values (
        file_id BYTEA NOT NULL PRIMARY KEY,
        content BYTEA NOT NULL)
    """,

    """
    CREATE TABLE opaque_value_link (
        value_id INTEGER NOT NULL REFERENCES tag_values ON DELETE CASCADE,
        file_id BYTEA NOT NULL REFERENCES opaque_values ON DELETE RESTRICT,
        PRIMARY KEY (value_id, file_id))
    """,

    """
    CREATE TABLE about_tag_values (
        object_id UUID PRIMARY KEY,
        value TEXT UNIQUE)
    """,
    """
    GRANT SELECT, UPDATE, INSERT, DELETE
        ON TABLE about_tag_values TO fluidinfo
    """,

    """
    CREATE TABLE comments (
        object_id UUID NOT NULL PRIMARY KEY,
        username TEXT NOT NULL,
        creation_time TIMESTAMP NOT NULL DEFAULT (now() AT TIME ZONE 'UTC'))
    """,
    """
    GRANT SELECT, UPDATE, INSERT, DELETE
        ON TABLE comments TO fluidinfo
    """,

    """
    CREATE TABLE comment_object_link (
        comment_id UUID NOT NULL REFERENCES comments ON DELETE CASCADE,
        object_id UUID NOT NULL REFERENCES about_tag_values ON DELETE CASCADE,
        PRIMARY KEY (comment_id, object_id))
    """,
    """
    CREATE INDEX comment_object_link_object_id_idx
        ON comment_object_link (object_id)
    """,
    """
    CREATE INDEX comment_object_link_comment_id_idx
        ON comment_object_link (comment_id)
    """,
    """
    GRANT SELECT, UPDATE, INSERT, DELETE
        ON TABLE comment_object_link TO fluidinfo
    """,

    """
    CREATE TABLE dirty_objects (
        id SERIAL NOT NULL PRIMARY KEY,
        object_id UUID NOT NULL,
        update_time TIMESTAMP NOT NULL DEFAULT (now() AT TIME ZONE 'UTC'))
    """,
    """
    GRANT SELECT, UPDATE, INSERT, DELETE
        ON TABLE dirty_objects TO fluidinfo
    """,

    """
    CREATE TABLE last_indexed_objects (
        shard_id SERIAL NOT NULL PRIMARY KEY,
        last_indexed INTEGER)
    """,
    """
    GRANT SELECT, UPDATE, INSERT, DELETE
        ON TABLE last_indexed_objects TO fluidinfo
    """,

    # FIXME The following three expressions are used to ensure that 'plpgsql'
    # always exists.  In the case of PostgreSQL 9.1 this is already the case,
    # so we need to do some checks before running 'CREATE LANGUAGE plpgsql' or
    # bad things happen.  It's not already the case in PostgreSQL 8.4, so we
    # need to call it in that situation.  They should all be removed when
    # everyone is off PostgreSQL 8.4. -jkakar
    """
    CREATE OR REPLACE FUNCTION make_plpgsql() RETURNS VOID
    LANGUAGE SQL
    AS $$
        CREATE LANGUAGE plpgsql;
    $$
    """,
    """
    SELECT
        CASE
        WHEN EXISTS(
            SELECT 1
            FROM pg_catalog.pg_language
            WHERE lanname='plpgsql'
        )
        THEN NULL
        ELSE make_plpgsql() END
    """,
    """
    DROP FUNCTION make_plpgsql()
    """,
    # Turn an hexadecimal integer in a VARCHAR into a valid INTEGER. There's no
    # from_hex built-in function in PostgreSQL. It first concatenates x with
    # the incoming hexadecimal VARCHAR and casts the result as an INTEGER.
    # Since concatenating the 'x' string would produce 'xHEXVALUE', we have to
    # put this into a SELECT statement.
    """
    CREATE OR REPLACE FUNCTION hex_to_int(hexval VARCHAR) RETURNS INTEGER AS $$
    DECLARE
        result INT;
    BEGIN
        EXECUTE 'SELECT x''' || hexval || '''::INT' INTO result;
        RETURN result;
    END
    $$ LANGUAGE 'plpgsql' IMMUTABLE STRICT;
    """,
    # Find the shard an objectID would belong to by returning the modulo of the
    # second section of a UUID ('e29b' in '550e8400-e29b-
    # 41d4-a716-446655440000') with the number of Solr shards.
    """
    CREATE OR REPLACE FUNCTION in_shard(object_id UUID, servers INTEGER)
    RETURNS INTEGER
    AS $$
    DECLARE
        result INTEGER;
        object_id_section VARCHAR;
    BEGIN
        object_id_section = SUBSTRING(object_id::VARCHAR, 10, 4);
        result = hex_to_int(object_id_section) % servers;
        RETURN result;
    END
    $$ LANGUAGE 'plpgsql' IMMUTABLE STRICT;
    """,
    """
    CREATE OR REPLACE FUNCTION get_objects(clean BOOLEAN, servers INTEGER,
                                           shard INTEGER, object_id OUT UUID,
                                           path_value_pair OUT TEXT)
    RETURNS SETOF RECORD
    AS $$
    DECLARE
        last_object INTEGER;
    BEGIN
        IF clean THEN
            RETURN QUERY SELECT tag_values.object_id::uuid,
                    array_agg(ROW(tags.path, tag_values.value))::TEXT
                FROM tag_values, tags
                WHERE tags.id = tag_values.tag_id AND
                    in_shard(tag_values.object_id, servers) = shard
                GROUP BY tag_values.object_id;
        ELSE
            SELECT last_indexed INTO last_object
            FROM last_indexed_objects
            WHERE shard_id = shard;
            IF NOT FOUND THEN
                last_object := 0;
                INSERT INTO last_indexed_objects (shard_id, last_indexed)
                VALUES (shard, last_object);
            END IF;

            UPDATE last_indexed_objects
            SET last_indexed = (SELECT COALESCE(MAX(id), 0) FROM dirty_objects)
            WHERE shard_id = shard;

            RETURN QUERY SELECT tag_values.object_id::uuid,
                    array_agg(ROW(tags.path, tag_values.value))::TEXT
                FROM tag_values JOIN tags
                    ON tags.id = tag_values.tag_id
                WHERE tag_values.object_id IN (
                    SELECT DISTINCT dirty_objects.object_id
                    FROM dirty_objects
                    WHERE in_shard(dirty_objects.object_id, servers) = shard
                    AND dirty_objects.id > last_object)
                GROUP BY tag_values.object_id;
        END IF;
    END
    $$ LANGUAGE plpgsql;
    """
]


DROP = [
    'DROP TABLE dirty_objects',
    'DROP TABLE about_tag_values',
    'DROP TABLE tag_values',
    'DROP TABLE tag_permissions',
    'DROP TABLE tags',
    'DROP TABLE namespace_permissions',
    'DROP TABLE namespaces',
    'DROP TABLE oauth_consumers',
    'DROP TABLE twitter_users',
    'DROP TABLE users',
    'DROP TABLE comments',
    'DROP TABLE comment_object_link',
]


DELETE = [
    # All tables aren't listed here because we rely on ON CASCADE DELETE to
    # clean up everything.
    'DELETE FROM dirty_objects',
    'DELETE FROM last_indexed_objects',
    'DELETE FROM about_tag_values',
    'DELETE FROM users',
    'DELETE FROM comments',
]
