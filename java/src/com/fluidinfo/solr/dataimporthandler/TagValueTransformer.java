package com.fluidinfo.solr.dataimporthandler;

import java.io.InputStream;
import java.io.ByteArrayInputStream;
import java.io.CharArrayReader;
import java.io.IOException;
import java.io.Reader;
import java.io.InputStreamReader;
import java.util.Map;
import java.util.LinkedList;
import java.util.List;
import java.util.Arrays;
import org.apache.noggit.JSONParser;
import java.sql.SQLException;
import org.postgresql.util.PGtokenizer;
import org.apache.commons.codec.binary.Hex;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;


public class TagValueTransformer {


    /**
     * Get a row from the database and turn it into appropiate key/value pairs
     * for our Solr schema.
     *
     * The value column is retrieved as a JSON blob and parsed using Noggit.
     * The field name is constructed from the tag path. For example, for
     * testuser/testtag:
     * - testuser/testtag_tag_raw_str for strings.
     * - testuser/testtag_tag_set_str for sets of strings.
     * - testuser/testtag_tag_fts Full-Text Search for strings and sets of
     *    strings. Its contents are not handled here, but automatically copied
     *    from the tag_raw_str and tag_set_str tags using the copyField
     *    directives in Solr's schema.xml.
     * - testuser/testtag_tag_number for numbers (both floats and integers).
     * - testuser/testtag_tag_bool for booleans.
     * - testuser/testtag_tag_null for empty tag values.
     */
    @SuppressWarnings("unchecked")
    public Object transformRow(Map<String, Object> row) throws Exception {
        Logger logger = LoggerFactory.getLogger(TagValueTransformer.class);
        String pathValuePair = (String)row.get("path_value_pair");
        logger.debug("path_value_pair: " + pathValuePair);
        row.remove("path_value_pair");

        if (pathValuePair != null) {

            // Remove the outer curly brackets and split the value into separate
            // elements.
            // We don't want the inner elements to be split yet, PGtokenizer is
            // smart enough not to do it.
            String[] tokenizedArray = PGtokenizer.remove(
                        pathValuePair, "{", "}").split("\",\"");

            // We'll add all the tag paths to expose them as a document field
            // later.
            List<String> paths = new LinkedList<String>();
            for (int i = 0; i < tokenizedArray.length; i++) {
                String pair = tokenizedArray[i];
                String pairWithoutQuotes = PGtokenizer.remove(pair, "\"", "\"");

                // Split string after the first comma.
                String[] tokenizedPair = PGtokenizer.removePara(
                                             pairWithoutQuotes).split(",", 2);

                if (tokenizedPair.length != 2) {
                    logger.error("Invalid value found in the database: " + pair);
                    throw new IOException("Invalid value found in the database: " +
                        pair);
                }

                if(tokenizedPair[0].length() == 0 && tokenizedPair[1].length() == 0) {
                    // The object doesn't have any values.
                    continue;
                }
                
                paths.add(tokenizedPair[0]);

                if(tokenizedPair[1].length() == 0) {
                    // This document should be a null JSON document, but it's empty.
                    // We'll produce a null tag field, though.
                    row.put(tokenizedPair[0] + "_tag_null", false);
                    continue;
                }

                String originalTagValue = tokenizedPair[1];
                String tagValue = decodePostgreSQL(originalTagValue);

                InputStream input = new ByteArrayInputStream(tagValue.getBytes());
                Reader rawTagValue = new InputStreamReader(input);
                JSONParser parser = new JSONParser(rawTagValue);

                try {
                int event = parser.nextEvent();
                boolean inStringSet = false;
                boolean inObject = false;
                List<String> stringSet = new LinkedList<String>();
                while (event != JSONParser.EOF) {
                    if (inObject) {
                        if (event == JSONParser.OBJECT_END) {
                            inObject = false;
                        }
                    } else {
                        switch (event) {
                        case JSONParser.STRING:
                            String rawValueString = parser.getString();
                            if (inStringSet) {
                                stringSet.add(rawValueString);
                            } else {
                                row.put(tokenizedPair[0] + "_tag_raw_str",
                                        rawValueString);
                            }
                            break;
                        case JSONParser.LONG:
                        case JSONParser.NUMBER:
                        case JSONParser.BIGNUMBER:
                            Double valueNumber = parser.getDouble();
                            row.put(tokenizedPair[0] + "_tag_number", valueNumber);
                            break;
                        case JSONParser.BOOLEAN:
                            Boolean valueBoolean = parser.getBoolean();
                            row.put(tokenizedPair[0] + "_tag_bool", valueBoolean);
                            break;
                        case JSONParser.ARRAY_START:
                            inStringSet = true;
                            break;
                        case JSONParser.ARRAY_END:
                            inStringSet = false;
                            List<String> newStringSet = new LinkedList<String>(
                                stringSet);
                            row.put(tokenizedPair[0] + "_tag_set_str", newStringSet);
                            stringSet.clear();
                            break;
                        case JSONParser.NULL:
                            row.put(tokenizedPair[0] + "_tag_null", false);
                            break;
                        case JSONParser.OBJECT_START:
                            inObject = true;
                            break;
                        }
                    }
                    event = parser.nextEvent();
                }
                } catch(Exception e) {
                    logger.error("Invalid payload (original): " + originalTagValue);
                    logger.error("Invalid payload (modified): " + tagValue);
                    throw e;
                }

            }
            // Expose the paths of all tag values as a document field.
            if (!paths.isEmpty()) {
                row.put("paths", paths);
            }
        }
        return row;
    }

    public static String decodePostgreSQL(String in) throws Exception {
	Logger logger = LoggerFactory.getLogger(TagValueTransformer.class);

	// Eliminates all the escaping chars and decode the HEX value.
	// Converts a string like this: 
        //    \"\\\\x225468652070617468206f662061206e616d6573706163652e22\" 
	// To something like this:
	// "The path of a namespace."
        char[] hex = in.substring(7, in.length() - 2).toCharArray();
	byte[] decodedHex = Hex.decodeHex(hex);
	logger.debug("decoded " + new String(decodedHex));
	return new String(decodedHex);
     }
}
