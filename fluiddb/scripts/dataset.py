"""Logic to batch import datasets directly into Fluidinfo."""

import logging
from time import time

import transaction

from fluiddb.data.exceptions import UnknownUserError
from fluiddb.model.user import getUser
from fluiddb.security.comment import SecureCommentAPI
from fluiddb.security.object import SecureObjectAPI
from fluiddb.security.value import SecureTagValueAPI


class DatasetImporter(object):
    """Upload object data to Fluidinfo."""

    def __init__(self, batchSize):
        self._batchSize = batchSize

    def upload(self, username, objects, message=None):
        """Upload batch object data directly into Fluidinfo.

        The data to be uploaded must be provided in the following format::

            [{'about': <about-tag-value>,
              'values': {<tag-path>: <tag-value>, ...}},
             ...]

        @param username: The name of the L{User} to import data on behalf of.
        @param objects: A C{list} of C{dict}s representing tags and values,
            organized as objects, to upload to Fluidinfo.
        @param message: An optional C{unicode} message used to make logging
            output less generic.
        """
        message = (u'%s: ' % message) if message else u''
        nObjects = len(objects)
        nImported = 0
        logging.info('%sImporting %d new objects.', message, nObjects)
        startTime = time()

        start, end = 0, min(len(objects), self._batchSize)
        if end:
            while start < len(objects):
                # NOTE: Be careful here.  An obvious refactoring, at first
                # glance, is to move the logic to get the user and create the
                # tag value API out of the loop, but doing so will cause the
                # user object to be used across transaction boundaries, which
                # we don't want to do.  It's important that the database
                # interactions for each batch processed here are managed in a
                # single transaction.
                try:
                    user = getUser(username)
                    if user is None:
                        raise UnknownUserError([username])
                    data = self._getObjectData(user, objects[start:end])
                    SecureTagValueAPI(user).set(data)
                    transaction.commit()
                    nImported += (end - start)
                    logging.info('%sImported %d/%d new objects.', message,
                                 nImported, nObjects)
                except:
                    transaction.abort()
                    logging.info('%sImport failed. Aborting.', message)
                    raise
                start, end = end, min(len(objects), end + self._batchSize)

            elapsed = time() - startTime
            logging.info('%sImported %d objects in %s seconds, %.3f '
                         'objects/second.', message, nObjects, elapsed,
                         float(nObjects) / elapsed)

    def _getObjectData(self, user, objects):
        """Reformat the data to directly import it into Fluidinfo.

        @param user: The L{User} to use when preparing data to import.
        @param objects: The C{list} of objects to convert into the
            L{TagValueAPI.set} format.
        @return: A C{dict} with object information that can be used to make a
            L{TagValueAPI.set} call.
        """
        api = SecureObjectAPI(user)
        data = {}
        for objectData in objects:
            # FIXME We could reduce the number of queries here by making
            # ObjectAPI.create take a 'skipExistanceCheck' parameter and using
            # ObjectAPI.get to prefetch object IDs for all existing about
            # values.
            objectID = api.create(objectData['about'])
            data[objectID] = objectData['values']
        return data


class CommentImporter(object):
    """Upload comment data to Fluidinfo."""

    def __init__(self, batchSize):
        self._batchSize = batchSize

    def upload(self, comments, message=None):
        """Upload batch comment data directly into Fluidinfo.

        @param comments: A C{list} of comment C{dict}s, each with keys:
            about: (Optional) A C{list} of C{unicode} values the comment is
                about.
            importer: The C{unicode} name of the importer application.
            text: The C{unicode} text of the comment.
            timestamp: A C{datetime.datetime} instance or C{None} if the
                current time should be used.
            url: A C{str} URL where the comment took place, or C{None}.
            username: The user's C{unicode} name in Fluidinfo. Note that the
                user might not officially exist in Fluidinfo yet. For example,
                we could be importing the tweets of someone who is followed by
                an actual Fluidinfo user.
        @param message: An optional C{unicode} message used to make logging
            output less generic.
        """
        message = (u'%s: ' % message) if message else u''
        nComments = len(comments)
        nImported = 0
        logging.info('%sImporting %d new comments.', message, nComments)
        startTime = time()

        while comments:
            # NOTE: Be careful here.  An obvious refactoring, at first
            # glance, is to move the logic to get the user and create the
            # comment API outside the loop, but doing so will cause the
            # user object to be used across transaction boundaries, which
            # we don't want to do.  It's important that the database
            # interactions for each batch processed here are managed in a
            # single transaction.
            thisBatch = comments[0:min(len(comments), self._batchSize)]
            try:
                user = getUser(u'fluidinfo.com')
                if user is None:
                    raise UnknownUserError([u'fluidinfo.com'])
                for comment in thisBatch:
                    SecureCommentAPI(user).create(
                        comment['text'], comment['username'],
                        importer=comment['importer'], url=comment['url'],
                        about=comment.get('about'), when=comment['timestamp'])
                transaction.commit()
                nImported += len(thisBatch)
                logging.info('%sImported %d/%d new comments.', message,
                             nImported, nComments)
            except:
                transaction.abort()
                logging.info('%sImport failed. Aborting.', message)
                raise
            else:
                comments = comments[len(thisBatch):]
        elapsed = time() - startTime
        logging.info('%sImported %d comments in %s seconds, %.3f '
                     'comments/second.', message, nComments, elapsed,
                     float(nComments) / elapsed)
