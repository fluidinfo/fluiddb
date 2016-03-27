"""
Creates a new objects table with an indexed flag. Additionally, it creates a
plpgsql stored procedure use to get the updated objects from the Data Import
Handler.
"""

STATEMENTS = [
    """
    CREATE TABLE objects_temp (
        object_id UUID PRIMARY KEY,
        indexed BOOLEAN NOT NULL DEFAULT FALSE)
    """,
    """
    INSERT INTO objects_temp(object_id)
    SELECT object_id
    FROM objects
    WHERE update_time > (now() - '1 hour'::INTERVAL) at time zone 'UTC'
    """,
    """
    DROP INDEX objects_update_time_idx
    """,
    """
    DROP TABLE objects
    """,
    """
    ALTER TABLE objects_temp RENAME TO objects
    """,
    """
    CREATE LANGUAGE plpgsql
    """,
    """
    CREATE FUNCTION get_objects(clean BOOLEAN, object_id OUT UUID,
                                path_value_pair OUT TEXT)
    RETURNS SETOF RECORD
    AS $$
    BEGIN
       IF clean THEN
           DELETE FROM objects;
           RETURN QUERY SELECT tag_values.object_id::uuid,
                            array_agg(ROW(tags.path, tag_values.value))::text
                        FROM tag_values, tags
                        WHERE tags.id = tag_values.tag_id
                        GROUP BY tag_values.object_id;
       ELSE
           DELETE FROM objects WHERE indexed;
           UPDATE objects SET indexed=TRUE;
           RETURN QUERY SELECT objects.object_id::uuid,
                            array_agg(ROW(tags.path, tag_values.value))::text
                        FROM tag_values
                             RIGHT OUTER JOIN objects
                             ON objects.object_id = tag_values.object_id
                             LEFT OUTER JOIN tags
                             ON tags.id = tag_values.tag_id
                        WHERE objects.indexed
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
