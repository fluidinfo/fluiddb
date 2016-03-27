from datetime import datetime

from storm.schema.patch import PatchApplier
import transaction

from fluiddb.data.permission import Operation, Policy
from fluiddb.data.system import createSystemData
from fluiddb.data.user import Role
from fluiddb.model.object import ObjectAPI
from fluiddb.model.permission import PermissionAPI
from fluiddb.model.value import TagValueAPI
from fluiddb.model.tag import TagAPI
from fluiddb.model.user import UserAPI, getUser
from fluiddb.model.oauth import OAuthConsumerAPI


def bootstrapSystemData(store):
    """Create system data in a database.

    @param store: The C{Store} for the database.
    """
    try:
        createSystemData()
    except:
        transaction.abort()
        raise
    else:
        transaction.commit()


def bootstrapWebAdminData():
    """Create system data in a database."""
    try:
        superuser = getUser(u'fluiddb')
        UserAPI().create([((u'fluidinfo.com',
                            u'secret',
                            u'Fluidinfo website',
                            u'fluidinfo@example.com'))])
        webuser = getUser(u'fluidinfo.com')
        webuser.role = Role.USER_MANAGER
        TagAPI(superuser).create([(u'fluiddb/users/activation-token',
                                   u'Activation token for the user')])
        PermissionAPI(superuser).set([(u'fluiddb/users/activation-token',
                                       Operation.WRITE_TAG_VALUE,
                                       Policy.CLOSED, [u'fluidinfo.com'])])
        anonuser = getUser(u'anon')
        OAuthConsumerAPI.register(anonuser)
    except:
        transaction.abort()
        raise
    else:
        transaction.commit()


def setVersionTag(version):
    """Updates the fluiddb/version tag.

    @param version: The new version string.
    """
    user = getUser(u'fluiddb')
    objectID = ObjectAPI(user).create(u'fluidinfo')
    releaseDate = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
    values = {objectID: {
        u'fluiddb/api-version': {
            'mime-type': 'text/plain',
            'contents': version},
        u'fluiddb/release-date': {
            'mime-type': 'text/plain',
            'contents': releaseDate + '\n'}}}
    TagValueAPI(user).set(values)
    PermissionAPI(user).set([
        (u'fluiddb/api-version', Operation.READ_TAG_VALUE, Policy.OPEN, []),
        (u'fluiddb/release-date', Operation.READ_TAG_VALUE, Policy.OPEN, [])])

    try:
        transaction.commit()
    except:
        transaction.abort()
        raise


def patchDatabase(store, schema):
    """Create a schema or apply databases patches to a database.

    @param store: The C{Store} for the database.
    @param schema: The Storm C{Schema} for the database.
    """
    try:
        schema.upgrade(store)
    except:
        transaction.abort()
        raise
    else:
        transaction.commit()


class PatchStatus(object):
    """Information about the patch state of a database.

    @ivar unappliedPatches: A list of unapplied patch versions.
    @ivar unknownPatches: A list of unknown patch versions.
    """

    def __init__(self, unappliedPatches, unknownPatches):
        self.unappliedPatches = unappliedPatches
        self.unknownPatches = unknownPatches


def getPatchStatus(store, schema):
    """Get the patch status for a database.

    @param store: The C{Store} for the database.
    @param schema: The Storm C{Schema} for the database.
    @return: A L{PatchStatus} instance with information about the patch level
        of the database.
    """
    # FIXME It's a bit unfortunate that we're accessing private attributes and
    # methods of Schema and PatchApplier in this code, but there's no way to
    # get the information we need with the public API.  This is really a bug
    # in Storm, see bug #754468 for more details about it.
    patchApplier = PatchApplier(store, schema._patch_package)
    unappliedPatches = sorted(patchApplier._get_unapplied_versions())
    unknownPatches = sorted(patchApplier.get_unknown_patch_versions())
    return PatchStatus(unappliedPatches, unknownPatches)
