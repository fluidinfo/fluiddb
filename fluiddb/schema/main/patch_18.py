"""
Fixes a bug where get_objects deletes all the items in the objects table when
called from a shard.
"""

STATEMENTS = [
    """
    CREATE OR REPLACE FUNCTION get_objects(clean BOOLEAN, servers INTEGER,
                                           shard INTEGER, object_id OUT UUID,
                                           path_value_pair OUT TEXT)
    RETURNS SETOF RECORD
    AS $$
    BEGIN
       IF clean THEN
           DELETE FROM objects
               WHERE in_shard(objects.object_id, servers) = shard;
           RETURN QUERY SELECT tag_values.object_id::uuid,
                   array_agg(ROW(tags.path, tag_values.value))::text
               FROM tag_values, tags
               WHERE tags.id = tag_values.tag_id AND
                   in_shard(tag_values.object_id, servers) = shard
               GROUP BY tag_values.object_id;
       ELSE
           DELETE FROM objects
               WHERE indexed AND
                   in_shard(objects.object_id, servers) = shard;
           UPDATE objects SET indexed=TRUE
               WHERE in_shard(objects.object_id, servers) = shard;
           RETURN QUERY SELECT objects.object_id::uuid,
                   array_agg(ROW(tags.path, tag_values.value))::text
               FROM tag_values
                   RIGHT OUTER JOIN objects
                   ON objects.object_id = tag_values.object_id
                   LEFT OUTER JOIN tags
                   ON tags.id = tag_values.tag_id
               WHERE objects.indexed AND
                   in_shard(tag_values.object_id, servers) = shard
               GROUP BY objects.object_id;
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
