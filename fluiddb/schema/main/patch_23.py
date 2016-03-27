"""
Rename the 'objects' table to 'dirty_objects' and make object_id not unique.
"""

STATEMENTS = [
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

    """
    INSERT INTO dirty_objects (object_id)
    SELECT object_id FROM objects;
    """,

    """
    DROP TABLE objects;
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
                   array_agg(ROW(tags.path, tag_values.value))::text
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

           RETURN QUERY SELECT dirty_objects.object_id::uuid,
                   array_agg(ROW(tags.path, tag_values.value))::text
               FROM tag_values
                   RIGHT OUTER JOIN dirty_objects
                   ON dirty_objects.object_id = tag_values.object_id
                   LEFT OUTER JOIN tags
                   ON tags.id = tag_values.tag_id
               WHERE in_shard(dirty_objects.object_id, servers) = shard
                   AND dirty_objects.id > last_object
               GROUP BY dirty_objects.object_id;
       END IF;
    END
    $$ LANGUAGE plpgsql;
    """
]


def apply(store):
    print __doc__
    for statement in STATEMENTS:
        print statement
        store.execute(statement)
