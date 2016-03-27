#!/bin/sh -e
# This script periodically cleans the dirty_objects table removing objects 
# already indexed.
echo 'DELETE FROM dirty_objects WHERE id <= (SELECT MIN(last_indexed) FROM last_indexed_objects);' | psql -q fluidinfo
