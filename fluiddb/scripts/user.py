import transaction

from fluiddb.model.user import UserAPI


def createUser(username, password, fullname, email, role):
    """Create a new L{User}.

    @param username: A C{unicode} username for the user.
    @param password: A C{unicode} password in plain text for the user. The
        password will be hashed before being stored.
    @param fullname: A C{unicode} name for the user.
    @param email: The C{unicode} email address for the user.
    @param role: The L{Role} for the user.
    @return: A C{list} of C{(objectID, username)} 2-tuples for the new
        L{User}s.
    """
    username = username.lower()
    users = UserAPI()
    result = users.create([(username, password, fullname, email)])
    # Set the role with an update to ensure that the 'fluiddb/users/role' tag
    # value is set correctly.
    users.set([(username, None, None, None, role)])
    try:
        transaction.commit()
    except:
        transaction.abort()
        raise
    return result


def deleteUser(username):
    """Delete a L{User}.

    @param username: A C{unicode} username for the user.
    """
    result = UserAPI().delete([username])
    try:
        transaction.commit()
    except:
        transaction.abort()
        raise
    return result


def updateUser(username, password, fullname, email, role):
    """Updates a L{User}.

    @param username: A C{unicode} username for the user.
    @param password: A C{unicode} password in plain text for the user. The
        password will be hashed before being stored.
    @param fullname: A C{unicode} name for the user.
    @param email: The C{unicode} email address for the user.
    @param role: The L{Role} for the user.
    @return: @return: A C{(objectID, username)} 2-tuple representing the
        L{User} that was updated.
    """
    try:
        result = UserAPI().set([(username, password, fullname, email, role)])
        transaction.commit()
    except:
        transaction.abort()
        raise
    return result
