"""
Modifies the get_objects function to support shards in Solr.
"""

STATEMENTS = [
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
        result INT;
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
    BEGIN
       IF clean THEN
           DELETE FROM objects;
           RETURN QUERY SELECT tag_values.object_id::uuid,
                            array_agg(ROW(tags.path, tag_values.value))::text
                        FROM tag_values, tags
                        WHERE tags.id = tag_values.tag_id AND
                              in_shard(tag_values.object_id, servers) = shard
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
