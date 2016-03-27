from datetime import datetime

from storm.locals import Storm, DateTime, Unicode, UUID

from fluiddb.data.store import getMainStore


class Comment(Storm):
    """A reference to a comment object.

    @param objectID: The objectID of the comment object.
    @param username: The username of the creator of the comment.
    @creationTime: The timestamp when the comment was created.
    """

    __storm_table__ = 'comments'

    objectID = UUID('object_id', primary=True, allow_none=False)
    username = Unicode('username', allow_none=False)
    creationTime = DateTime('creation_time', allow_none=False)

    def __init__(self, objectID, username, creationTime):
        self.objectID = objectID
        self.username = username
        self.creationTime = creationTime


class CommentObjectLink(Storm):
    """A representation of object-comment many-to-many relation.

    @param: commentID: The objectID of the comment object.
    @param: objectID: The objectID of the object the comment is targeting.
    """

    __storm_table__ = 'comment_object_link'
    __storm_primary__ = 'commentID', 'objectID'

    commentID = UUID('comment_id', allow_none=False)
    objectID = UUID('object_id', allow_none=False)

    def __init__(self, commentID, objectID):
        self.commentID = commentID
        self.objectID = objectID


def createComment(objectID, targetObjectIDs, username, creationTime=None):
    """Creates a new L{Comment}.

    @param objectID: The objectID of the new comment.
    @param targetObjectIDs: A list with all the target objectIDs
    @param username: The username of the creator of the comment.
    @param creationTime: Optionally a timestamp for the comment.
    """
    store = getMainStore()
    store.find(Comment, Comment.objectID == objectID).remove()
    creationTime = creationTime or datetime.utcnow()
    comment = Comment(objectID, username, creationTime)
    store.add(comment)
    for targetID in targetObjectIDs:
        store.add(CommentObjectLink(objectID, targetID))
    return comment


def deleteComment(objectID):
    """Deletes a L{Comment}.

    @param objectID: The object ID of the comment.
    @return: An C{int} count of the number of comments removed.
    """
    store = getMainStore()
    return store.find(Comment, Comment.objectID == objectID).remove()
