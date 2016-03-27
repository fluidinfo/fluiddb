package com.fluidinfo.solr.dataimporthandler;

import java.util.Collections;
import java.util.Map;
import java.util.HashMap;
import java.util.List;
import java.util.LinkedList;
import java.io.IOException;
import org.junit.Test;
import org.junit.Before;
import junit.framework.JUnit4TestAdapter;
import static org.junit.Assert.*;
import java.sql.SQLException;


public class TestTagValueTransformer {

    private TagValueTransformer _transformer;

    @Before
    public void setUp() {
        this._transformer = new TagValueTransformer();
    }

    /**
     * Test that a boolean value generates a TAG/PATH_tag_bool field.
     */
    @Test
    public void testBoolean() throws Exception {
        Map<String, Object> row = new HashMap<String, Object>();
        String objectId = "6600cb04-f0a0-48c5-b0a2-b249dec4a16b";
        row.put("object_id", objectId);
        String path_value_pair = "{\"(foo/bar,true)\"}";
        row.put("path_value_pair", path_value_pair);
        Map<String, Object> outputRow = (Map<String, Object>)this._transformer.transformRow(row);
        assertNull(outputRow.get("path_value_pair"));
        assertEquals(true, outputRow.get("foo/bar_tag_bool"));
        assertEquals(objectId, row.get("object_id"));
    }

    /**
     * Test that a null tag value generates a TAG/PATH_tag_null field and its
     * value is false.
     */
    @Test
    public void testNull() throws Exception {
        Map<String, Object> row = new HashMap<String, Object>();
        String objectId = "6600cb04-f0a0-48c5-b0a2-b249dec4a16b";
        row.put("object_id", objectId);
        String path_value_pair = "{\"(foo/bar,null)\"}";
        row.put("path_value_pair", path_value_pair);
        Map<String, Object> outputRow = (Map<String, Object>)this._transformer.transformRow(row);
        assertNull(outputRow.get("path_value_pair"));
        assertEquals(false, outputRow.get("foo/bar_tag_null"));
        assertEquals(objectId, row.get("object_id"));
    }

    /**
     * Test that a set of strings value generates a TAG/PATH_tag_set_str field
     * and its value is a list of strings.
     */
    @Test
    public void testSet() throws Exception {
        Map<String, Object> row = new HashMap<String, Object>();

        String objectId = "6600cb04-f0a0-48c5-b0a2-b249dec4a16b";
        row.put("object_id", objectId);
        String path_value_pair = "{\"(foo/bar,\\\"[\\\"\\\"one\\\"\\\", \\\"\\\"two\\\"\\\"]\\\")\"}";
        row.put("path_value_pair", path_value_pair);
        Map<String, Object> outputRow = (Map<String, Object>)this._transformer.transformRow(row);
        assertNull(outputRow.get("path_value_pair"));

        List<String> expected = new LinkedList<String>();
        expected.add("one");
        expected.add("two");
        Collections.sort(expected);

        List<String> result1 = (List<String>)outputRow.get("foo/bar_tag_set_str");
        Collections.sort(result1);

        assertEquals(expected, result1);
        assertEquals(objectId, row.get("object_id"));
    }

    /**
     * Test that a string value generates a TAG/PATH_tag_raw_str field
     * and its value is a string.
     */
    @Test
    public void testString() throws Exception {
        Map<String, Object> row = new HashMap<String, Object>();
        String objectId = "6600cb04-f0a0-48c5-b0a2-b249dec4a16b";
        row.put("object_id", objectId);
        String path_value_pair = "{\"(foo/bar,\\\"\\\"\\\"fubar\\\"\\\"\\\")\"}";
        row.put("path_value_pair", path_value_pair);
        Map<String, Object> outputRow = (Map<String, Object>)this._transformer.transformRow(row);
        assertNull(outputRow.get("path_value_pair"));
        assertEquals("fubar", outputRow.get("foo/bar_tag_raw_str"));
        assertEquals(objectId, row.get("object_id"));
    }
    
    /**
     * Test that an empty string value generates a TAG/PATH_tag_raw_str field
     * and its value is a string.
     */
    @Test
    public void testStringEmpty() throws Exception {
        Map<String, Object> row = new HashMap<String, Object>();
        String objectId = "6600cb04-f0a0-48c5-b0a2-b249dec4a16b";
        row.put("object_id", objectId);
        String path_value_pair = "{\"(foo/bar,\\\"\\\"\\\"\\\"\\\"\\\")\"}";
        row.put("path_value_pair", path_value_pair);
        Map<String, Object> outputRow = (Map<String, Object>)this._transformer.transformRow(row);
        assertNull(outputRow.get("path_value_pair"));
        assertEquals("", outputRow.get("foo/bar_tag_raw_str"));
        assertEquals(objectId, row.get("object_id"));
    }

    /**
     * Test that a string value with parens and commas generates a
     * TAG/PATH_tag_raw_str field and its value is a string.
     */
    @Test
    public void testStringParensCommas() throws Exception {
        Map<String, Object> row = new HashMap<String, Object>();
        String objectId = "6600cb04-f0a0-48c5-b0a2-b249dec4a16b";
        row.put("object_id", objectId);
        String path_value_pair = "{\"(foo/bar,\\\"\\\"\\\"),\\\"\\\"\\\")\"}";
        row.put("path_value_pair", path_value_pair);
        Map<String, Object> outputRow = (Map<String, Object>)this._transformer.transformRow(row);
        assertNull(outputRow.get("path_value_pair"));
        assertEquals("),", outputRow.get("foo/bar_tag_raw_str"));
        assertEquals(objectId, row.get("object_id"));
    }

    /**
     * Test that an integer value generates a TAG/PATH_tag_number field.
     */
    @Test
    public void testInteger() throws Exception {
        Map<String, Object> row = new HashMap<String, Object>();
        String objectId = "6600cb04-f0a0-48c5-b0a2-b249dec4a16b";
        row.put("object_id", objectId);
        String path_value_pair = "{\"(foo/bar,4)\"}";
        row.put("path_value_pair", path_value_pair);
        Map<String, Object> outputRow = (Map<String, Object>)this._transformer.transformRow(row);
        assertNull(outputRow.get("path_value_pair"));
        assertEquals(4.0, outputRow.get("foo/bar_tag_number"));
        assertEquals(objectId, row.get("object_id"));
    }

    /**
     * Test that an integer value generates a TAG/PATH_tag_number field.
     */
    @Test
    public void testIntegerWithSixDigit() throws Exception {
        Map<String, Object> row = new HashMap<String, Object>();
        String objectId = "6600cb04-f0a0-48c5-b0a2-b249dec4a16b";
        row.put("object_id", objectId);
        String path_value_pair = "{\"(foo/bar,123456)\"}";
        row.put("path_value_pair", path_value_pair);
        Map<String, Object> outputRow = (Map<String, Object>)this._transformer.transformRow(row);
        assertNull(outputRow.get("path_value_pair"));
        assertEquals(123456.0, outputRow.get("foo/bar_tag_number"));
        assertEquals(objectId, row.get("object_id"));
    }

    /**
     * Test that a float value generates a TAG/PATH_tag_number field.
     */
    @Test
    public void testFloat() throws Exception {
        Map<String, Object> row = new HashMap<String, Object>();
        String objectId = "6600cb04-f0a0-48c5-b0a2-b249dec4a16b";
        row.put("object_id", objectId);
        String path_value_pair = "{\"(foo/bar,4.3)\"}";
        row.put("path_value_pair", path_value_pair);
        Map<String, Object> outputRow = (Map<String, Object>)this._transformer.transformRow(row);
        assertNull(outputRow.get("path_value_pair"));
        assertEquals(4.3, outputRow.get("foo/bar_tag_number"));
        assertEquals(objectId, row.get("object_id"));
    }

    /**
     * Test that an object with more than one tag value is properly processed.
     */
    @Test
    public void testMoreThanOneTagValue() throws Exception {
        Map<String, Object> row = new HashMap<String, Object>();
        String objectId = "6600cb04-f0a0-48c5-b0a2-b249dec4a16b";
        row.put("object_id", objectId);
        String path_value_pair = "{\"(foo/bar,4.3)\"," +
            "\"(test/tag,\\\"\\\"\\\"hello\\\"\\\"\\\")\"}";
        row.put("path_value_pair", path_value_pair);
        Map<String, Object> outputRow = (Map<String, Object>)this._transformer.transformRow(row);
        assertNull(outputRow.get("path_value_pair"));
        assertEquals(4.3, outputRow.get("foo/bar_tag_number"));
        assertEquals("hello", outputRow.get("test/tag_tag_raw_str"));
        assertEquals(objectId, row.get("object_id"));

        List<String> expected = new LinkedList<String>();
        expected.add("foo/bar");
        expected.add("test/tag");
        Collections.sort(expected);

        List<String> paths = (List<String>)outputRow.get("paths");
        Collections.sort(paths);

        assertEquals(expected, paths);
    }

    /**
     * Test that an object with no tag values is properly processed.
     */
    @Test
    public void testNoTagValues() throws Exception {
        Map<String, Object> row = new HashMap<String, Object>();
        String objectId = "6600cb04-f0a0-48c5-b0a2-b249dec4a16b";
        row.put("object_id", objectId);
        String path_value_pair = "{\"(,)\"}";
        row.put("path_value_pair", path_value_pair);
        Map<String, Object> outputRow = (Map<String, Object>)this._transformer.transformRow(row);
        assertNull(outputRow.get("path_value_pair"));
        assertEquals(objectId, row.get("object_id"));
        assertNull(row.get("paths"));
    }

    /**
     * Test that binary values (as dictionaries) are not inserted in Solr.
     */
    @Test
    public void testBinaryValue() throws Exception {
        Map<String, Object> row = new HashMap<String, Object>();
        String objectId = "6600cb04-f0a0-48c5-b0a2-b249dec4a16b";
        row.put("object_id", objectId);
        String path_value_pair = "{\"(foo/bar,\\\"{\\\"\\\"file-id\\\"\\\": \\\"\\\"222b0bd51fcef7e65c2e62db2ed65457013bab56be6fafeb19ee11d453153c80\\\"\\\", \\\"\\\"mime-type\\\"\\\": \\\"\\\"image/jpeg\\\"\\\", \\\"\\\"size\\\"\\\": 4}\\\")\"}";
        row.put("path_value_pair", path_value_pair);
        Map<String, Object> outputRow = (Map<String, Object>)this._transformer.transformRow(row);
        assertNull(outputRow.get("path_value_pair"));
        assertEquals(objectId, row.get("object_id"));

        // Test that none of the fields are set.
        assertNull(row.get("foo/bar_tag_number"));
        assertNull(row.get("foo/bar_tag_raw_str"));
        assertNull(row.get("foo/bar_tag_set_str"));
        assertNull(row.get("foo/bar_tag_bool"));
        assertNull(row.get("foo/bar_tag_null"));

        List<String> expected = new LinkedList<String>();
        expected.add("foo/bar");
        Collections.sort(expected);

        List<String> paths = (List<String>)outputRow.get("paths");
        Collections.sort(paths);

        assertEquals(expected, paths);
    }

    /**
     * Test that an empty tag value generates a TAG/PATH_tag_null field and its
     * value is false.
     */
    @Test
    public void testEmpty() throws Exception {
        Map<String, Object> row = new HashMap<String, Object>();
        String objectId = "6600cb04-f0a0-48c5-b0a2-b249dec4a16b";
        row.put("object_id", objectId);
        String path_value_pair = "{\"(foo/bar,)\"}";
        row.put("path_value_pair", path_value_pair);
        Map<String, Object> outputRow = (Map<String, Object>)this._transformer.transformRow(row);
        assertNull(outputRow.get("path_value_pair"));
        assertEquals(false, outputRow.get("foo/bar_tag_null"));
        assertEquals(objectId, row.get("object_id"));
    }

    /**
     * Test that an invalid tag value raises an IOException.
     */
    @Test(expected=IOException.class)
    public void testInvalidTagValue() throws Exception {
        Map<String, Object> row = new HashMap<String, Object>();
        String objectId = "6600cb04-f0a0-48c5-b0a2-b249dec4a16b";
        row.put("object_id", objectId);
        String path_value_pair = "{\"(bogus-value)\"}";
        row.put("path_value_pair", path_value_pair);
        Map<String, Object> outputRow = (Map<String, Object>)this._transformer.transformRow(row);
        assertNull(outputRow.get("path_value_pair"));
        assertEquals(false, outputRow.get("foo/bar_tag_null"));
    }

    /**
     * Test that unicode strings are inserted into Solr properly.
     */
    @Test
    public void testStringUnicode() throws Exception {
        Map<String, Object> row = new HashMap<String, Object>();
        String objectId = "6600cb04-f0a0-48c5-b0a2-b249dec4a16b";
        row.put("object_id", objectId);
        String path_value_pair = "{\"(foo/bar,\\\"\\\"\\\"\\\\\\\\\\\\\\\\u00f1and\\\\\\\\\\\\\\\\u00fa\\\"\\\"\\\")\"}";
        row.put("path_value_pair", path_value_pair);
        Map<String, Object> outputRow = (Map<String, Object>)this._transformer.transformRow(row);
        assertNull(outputRow.get("path_value_pair"));
        assertEquals("\u00f1and\u00fa", outputRow.get("foo/bar_tag_raw_str"));
        assertEquals(objectId, row.get("object_id"));
    }
}
