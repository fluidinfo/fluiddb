"""
Added a LIMIT to the get_objects main query to trick postgres planner to use an
index scan instead of a seq scan.
"""

STATEMENTS = [
    """
    CREATE OR REPLACE FUNCTION get_objects(clean BOOLEAN, object_id OUT UUID,
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
           UPDATE objects SET indexed=TRUE WHERE NOT indexed;
           RETURN QUERY SELECT objects.object_id::uuid,
                            array_agg(ROW(tags.path, tag_values.value))::text
                        FROM tag_values
                             RIGHT OUTER JOIN objects
                             ON objects.object_id = tag_values.object_id
                             LEFT OUTER JOIN tags
                             ON tags.id = tag_values.tag_id
                        GROUP BY objects.object_id
                        LIMIT 10000;
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
