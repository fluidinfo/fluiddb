from datetime import datetime
from uuid import uuid4

from storm.exceptions import IntegrityError
from fluiddb.data.comment import (
    Comment, CommentObjectLink, createComment, deleteComment)
from fluiddb.data.value import createAboutTagValue
from fluiddb.testing.basic import FluidinfoTestCase
from fluiddb.testing.resources import DatabaseResource


class CommentSchemaTest(FluidinfoTestCase):

    resources = [('store', DatabaseResource())]

    def testUniqueObjectID(self):
        """
        An C{IntegrityError} is raised if a L{Comment} with duplicate
        L{Comment.objectID} is added to the database.
        """
        objectID = uuid4()
        self.store.add(Comment(objectID, u'username', datetime.now()))
        self.store.add(Comment(objectID, u'otheruser', datetime.now()))
        self.assertRaises(IntegrityError, self.store.flush)
        self.store.rollback()


class CommentObjectRelationSchemaTest(FluidinfoTestCase):

    resources = [('store', DatabaseResource())]

    def testUniqueObjectIDAndCommentID(self):
        """
        An C{IntegrityError} is raised if a L{CommentObjectLink} with
        duplicate L{Comment.objectID} and L{AboutTagValue.objectID} is added to
        the database.
        """
        objectID = uuid4()
        commentID = uuid4()
        self.store.add(CommentObjectLink(commentID, objectID))
        self.store.add(CommentObjectLink(commentID, objectID))
        self.assertRaises(IntegrityError, self.store.flush)
        self.store.rollback()


class CreateCommentTest(FluidinfoTestCase):

    resources = [('store', DatabaseResource())]

    def testCreateComment(self):
        """
        L{createComment} creates a L{Comment} object and the related
        L{CommentObjectLink} objects.
        """
        commentID = uuid4()
        target1 = uuid4()
        target2 = uuid4()
        createAboutTagValue(target1, u'target1')
        createAboutTagValue(target2, u'target2')
        timestamp = datetime.now()
        createComment(commentID, [target1, target2], u'username', timestamp)

        result = self.store.find(Comment, Comment.objectID == commentID)
        comment = result.one()
        self.assertNotIdentical(None, comment)
        self.assertEqual(u'username', comment.username)
        self.assertEqual(timestamp, comment.creationTime)

        result = self.store.find(CommentObjectLink,
                                 CommentObjectLink.commentID == commentID)
        targets = [relation.objectID for relation in result]
        self.assertEqual(sorted([target1, target2]), sorted(targets))

        comments = [relation.commentID for relation in result]
        self.assertEqual([commentID, commentID], comments)

    def testCreateExistingComment(self):
        """
        L{createComment} with an existent comment ID will remove the old
        comment and relations before creating a new one.
        """
        commentID = uuid4()
        target1 = uuid4()
        target2 = uuid4()
        createAboutTagValue(target1, u'target1')
        createAboutTagValue(target2, u'target2')
        timestamp = datetime.now()
        createComment(commentID, [target1], u'username', timestamp)
        createComment(commentID, [target2], u'otheruser', timestamp)

        result = self.store.find(Comment, Comment.objectID == commentID)
        comment = result.one()
        self.assertNotIdentical(None, comment)
        self.assertEqual(u'otheruser', comment.username)
        self.assertEqual(timestamp, comment.creationTime)

        result = self.store.find(CommentObjectLink,
                                 CommentObjectLink.commentID == commentID)
        self.assertEqual([target2], [relation.objectID for relation in result])
        comments = [relation.commentID for relation in result]
        self.assertEqual([commentID], comments)

    def testCreateCommentWithoutTimestamp(self):
        """
        L{createComment} uses C{now} if no default creation time is provided.
        """
        commentID = uuid4()
        target1 = uuid4()
        target2 = uuid4()
        createAboutTagValue(target1, u'target1')
        createAboutTagValue(target2, u'target2')
        createComment(commentID, [target1, target2], u'username')

        result = self.store.find(Comment, Comment.objectID == commentID)
        comment = result.one()
        self.assertNotIdentical(None, comment)
        self.assertEqual(u'username', comment.username)
        self.assertNotIdentical(None, comment.creationTime)


class DeleteCommentTest(FluidinfoTestCase):

    resources = [('store', DatabaseResource())]

    def testDeleteComment(self):
        """
        L{deleteComment} removes a L{Comment} object and its related
        L{CommentObjectLink} objects.
        """
        commentID = uuid4()
        target1 = uuid4()
        target2 = uuid4()
        createAboutTagValue(target1, u'target1')
        createAboutTagValue(target2, u'target2')
        timestamp = datetime.now()
        createComment(commentID, [target1, target2], u'username', timestamp)

        self.assertEqual(1, deleteComment(commentID))

        # The entry in the comments table must be gone.
        result = self.store.find(Comment, Comment.objectID == commentID)
        self.assertTrue(result.is_empty())

        # The entries in the comment object link table must be gone.
        result = self.store.find(CommentObjectLink,
                                 CommentObjectLink.commentID == commentID)
        self.assertTrue(result.is_empty())

    def testDeleteNonexistentComment(self):
        """
        L{deleteComment} must return C{0} when asked to remove a L{Comment}
        that does not exist.
        """
        commentID = uuid4()
        self.assertEqual(0, deleteComment(commentID))
