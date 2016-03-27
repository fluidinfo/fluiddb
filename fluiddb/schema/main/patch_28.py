"""
Fix for garbled patch 27. Restores get_objects() with sharding.
"""

STATEMENTS = [
    """
    CREATE OR REPLACE FUNCTION get_objects(clean boolean, servers integer,
        shard integer, OUT object_id uuid, OUT path_value_pair TEXT)
    RETURNS SETOF RECORD AS
    $body$
        DECLARE
            last_object INTEGER;
        BEGIN
            IF clean THEN
                RETURN QUERY SELECT tag_values.object_id::UUID,
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
                SET last_indexed = (
                    SELECT COALESCE(MAX(id), 0)
                    FROM dirty_objects
                )
                WHERE shard_id = shard;

                RETURN QUERY SELECT tag_values.object_id::uuid,
                        array_agg(ROW(tags.path, tag_values.value))::TEXT
                    FROM tag_values JOIN tags
                        ON tags.id = tag_values.tag_id
                    WHERE tag_values.object_id IN (
                        SELECT DISTINCT dirty_objects.object_id
                        FROM dirty_objects
                        WHERE in_shard(dirty_objects.object_id,
                            servers) = shard
                        AND dirty_objects.id > last_object)
                    GROUP BY tag_values.object_id;
            END IF;
        END
    $body$ LANGUAGE plpgsql;
    """
]


def apply(store):
    print __doc__
    for statement in STATEMENTS:
        store.execute(statement)
