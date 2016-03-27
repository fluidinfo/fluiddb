# -*- coding: utf-8 -*-
"""
MiniToken: Generate encrypted signed tokens which contain key-value pairs
of anything that is JSON encodable.

Inspired by OpenToken, but offers fewer options, and is therefore much
smaller.  See http://tools.ietf.org/html/draft-smith-opentoken-02

+------------+----------+-------------------------+
| Byte Range | Length   | Description             |
+============+==========+=========================+
| 0..19      | 20       | SHA-1 HMAC              |
+------------+----------+-------------------------+
| 20..23     |  4       | Key info                |
+------------+----------+-------------------------+
| 24..39     | 16       | IV                      |
+------------+----------+-------------------------+
| 40..xx     | xx - 39  | Payload                 |
+------------+----------+-------------------------+
"""

from base64 import urlsafe_b64encode, urlsafe_b64decode
from Crypto.Random import atfork
from Crypto.Util import randpool
from Crypto.Cipher import AES
from cStringIO import StringIO
from hashlib import sha1
from json import dumps, loads
import logging
import traceback
from zlib import compress, decompress

AES_MODE = AES.MODE_CBC
AES_PAD = chr(1)


def dataToToken(key, data, keyInfo='main'):
    """Create a token string from data encrypted with a key.

    @param data: a C{dict} of JSON-encodable data.
    @param keyInfo: Length 4 C{str} information about the key.
    @raise: ValueError: if anything goes wrong.
    @return: the C{str} token.
    """
    try:
        iv = _createIV()
        payload = _encodeData(data)
        digest = _createDigest(keyInfo, iv, payload)
        encrypted = _encrypt(payload, key, iv)
        packed = _pack(digest, keyInfo, iv, encrypted)
        return _compress(packed)
    except Exception, e:
        logging.error(''.join(traceback.format_exc()))
        raise ValueError(str(e))


def tokenToData(key, token):
    """Return the data stored in this token.

    @param key: An AES Key.
    @param token: A token string.
    @raise: ValueError: if anything goes wrong.
    @return: the C{str} data from the token.
    """
    try:
        data = _decompress(token)
        digest, keyInfo, iv, payload = _unpack(data)
        payload = _decrypt(payload, key, iv).rstrip(AES_PAD)
        assert _checkDigest(digest, keyInfo, iv, payload)
        return _decodeData(payload)
    except Exception, e:
        logging.error(''.join(traceback.format_exc()))
        raise ValueError(str(e))


def createKey(keySize=32):
    """Create a random key.

    @param keySize: a positive C{int} key length.
    @return: a random string of length C{keySize}.
    """
    try:
        return randpool.RandomPool(512).get_bytes(keySize)
    except AssertionError:
        # An AssertionError can come from Crypto/Random/_UserFriendlyRNG.py,
        # which produces an error "PID check failed. RNG must be re-initialized
        # after fork(). Hint: Try Random.atfork()".  This seems to only happen
        # when running locally (in development mode).
        atfork()
        return randpool.RandomPool(512).get_bytes(keySize)


def _createIV():
    """Create a 16-byte initialization vector.

    @return: a C{str} initialization vector.
    """
    try:
        return randpool.RandomPool(512).get_bytes(16)
    except AssertionError:
        # An AssertionError can come from Crypto/Random/_UserFriendlyRNG.py,
        # which produces an error "PID check failed. RNG must be re-initialized
        # after fork(). Hint: Try Random.atfork()".  This seems to only happen
        # when running locally (in development mode).
        atfork()
        return randpool.RandomPool(512).get_bytes(16)


def _createDigest(keyInfo, iv, payload):
    """Create a hash digest.

    @param keyInfo: The C{str} key info of length 4.
    @param iv: The iv bytes.
    @param payload: The payload.
    """
    hash = sha1()
    hash.update(keyInfo)
    hash.update(iv)
    hash.update(payload)
    return hash.digest()


def _checkDigest(digest, keyInfo, iv, payload):
    """Check a digest against token parameters.

    @param digest: A string hash of a key, iv, and payload.
    @param keyInfo: The key info.
    @param iv: The iv bytes.
    @param payload: The payload.
    """
    return _createDigest(keyInfo, iv, payload) == digest


def _encodeData(data):
    """Return a JSON encoded dump of C{data}.

    @param data: The data to encode.
    """
    return dumps(data)


def _decodeData(payload):
    """Return (JSON) decode of C{payload}.

    @param payload: The payload to decode.
    """
    return loads(payload)


def _padded(s):
    """Pad a string to length zero mod 16.

    @param s: The C{str} to pad.
    @return: The padded string.
    """
    pad = 16 - len(s) % 16
    return s + pad * AES_PAD


def _encrypt(payload, key, iv):
    """Encrypt a string.

    @param payload: The C{str} payload to encrypt.
    @param key: The C{str} key to use in encryption.
    @param iv: The C{str} initialization vector.
    @return: an AES encryption object.
    """
    return AES.new(key, AES_MODE, iv).encrypt(_padded(payload))


def _decrypt(payload, key, iv):
    """Decrypt a string.

    @param payload: The C{str} payload to encrypt.
    @param key: The C{str} key to use in encryption.
    @param iv: The C{str} initialization vector.
    @return: the decrypted payload.
    """
    return AES.new(key, AES_MODE, iv).decrypt(payload)


def _compress(payload):
    """Compress a string.

    @param payload: The C{str} payload to compress.
    @return: a base-64 encoded C{str} version of the compressed payload.
    """
    zip = compress(payload)
    return urlsafe_b64encode(zip).replace('=', '*')


def _decompress(payload):
    """Decompress a payload string.

    @param payload: The C{str} payload to decompress.
    @return: the decompressed C{str} payload.
    """
    data = urlsafe_b64decode(payload.replace('*', '='))
    return decompress(data)


def _pack(digest, keyInfo, iv, payload):
    """Pack a digest, keyInfo, iv, and a payload.

    @param digest: The C{str} digest to pack.
    @param keyInfo: The C{str} key info to pack.
    @param iv: The C{str} initialization vector to pack.
    @param payload: The C{str} payload to pack.
    @return: the C{str} packed version.
    """
    return ''.join([digest, keyInfo, iv, payload])


def _unpack(bytes):
    """Unpack C{bytes} into a digest, keyInfo, iv, and a payload.

    @return: a 4-tuple of digest, keyInfo, iv, and payload.
    """
    buffer = StringIO(bytes)
    digest = buffer.read(20)
    keyInfo = buffer.read(4)
    iv = buffer.read(16)
    payload = buffer.read()
    return digest, keyInfo, iv, payload
