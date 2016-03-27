# The admin username is the name of the top-level namespace that will contain
# all the system namespaces and tags. This can be set per-instance
# via create-fluiddb.py. adminPassword is specified with create-fluiddb.py
adminUsername = 'fluiddb'
adminName = 'FluidDB administrator'
adminEmail = 'fluidDB@example.com'
bugsEmail = 'bugs@example.com'

# The anonymous user.
anonUsername = 'anon'
anonPassword = 'anon'
anonName = 'FluidDB anonymous user'

# Additional username information is in fluiddb/common/users.py

# Namespace and tag permission defaults can be found in
# fluiddb/common/permissions.py

# The various top-level system namespaces that hold information about
# namespaces, tags and the sets of tag values.
namespaceCategoryName = 'namespaces'
tagCategoryName = 'tags'
tagInstanceSetCategoryName = 'tag-values'

categories = (namespaceCategoryName,
              tagCategoryName,
              tagInstanceSetCategoryName)

adminUserNamespaceName = 'users'
aboutTagName = 'about'
pathTagName = 'path'
descriptionTagName = 'description'
usernameTagName = 'username'
nameTagName = 'name'
passwordTagName = 'password'
emailTagName = 'email'
defaultNamespaceName = 'default'

# Separator used between namespace and tag names.
sep = '/'

# Top-level HTTP API categories.
httpNamespaceCategoryName = namespaceCategoryName
httpTagCategoryName = tagCategoryName
httpTagInstanceSetCategoryName = tagInstanceSetCategoryName
httpObjectCategoryName = 'objects'
httpUserCategoryName = 'users'
httpPermissionCategoryName = 'permissions'
httpPolicyCategoryName = 'policies'
httpAboutCategoryName = 'about'
httpValueCategoryName = 'values'
httpCrossdomainName = 'crossdomain.xml'

keyValueStoreType = 'thriftlocal'
keyValueStoreAddress = 'localhost'
keyValueStorePort = 8002

wsfePort = 8880
wsfeDomain = 'example.com'

# Note that in (at least in some cases) the username in dbURI needs to be
# present as a user on the system where the database will be used. In the
# case of using EC2 on Ubuntu, the username is present in the
# fluiddb/admin/ec2/bin/ec2ubuntu-build-ami-fluidinfo-script so if you
# change the username here, you'll have to change it there too.
dbURI = 'postgres://fluiddb:fluiddb@localhost:5432/fluiddb'

# Note that if you change coordinatorPort, you will also need to also
# change the firewall rules on the machines running FluidDB.
coordinatorPort = 8001

# Various things need to know the name of services.
tagsServiceName = 'fluiddb_service_tags'
brokerRabbitmqServiceName = 'fluiddb_service_broker_rabbitmq'
coordinatorServiceName = 'fluiddb_service_coordinator'
databasePostgresServiceName = 'fluiddb_service_database_postgres'
facadeServiceName = 'fluiddb_service_facade'
namespacesServiceName = 'fluiddb_service_namespaces'
objectsServiceName = 'fluiddb_service_objects'
uniqueTagsServiceName = 'fluiddb_service_uniquetags'
setopsServiceName = 'fluiddb_service_setops'
wsfeServiceName = 'fluiddb_service_wsfe'

# The specification file can be relative to the FluidDB resources
# directory on the machine FluidDB is running on.
AMQPSpecFile = 'specs/amqp0-8.stripped.xml'
AMQPVhost = 'localhost'
AMQPEncoding = 'PLAIN'
AMQPLocale = 'EN_us'

messageBroker = 'rabbitmq'
brokerUsername = 'fluiddb'
brokerPassword = 'fluiddb'
brokerPort = 5672

# Path components (tags, namespaces) accept colons, dots, hyphens,
# underscores and any other alphanumeric character defined in the Unicode
# standard (activated by using re.UNICODE).  Note that pathComponentRegex
# ensures path names are not empty.
# Since comma (,) is used to join the object id and the path in Solr to form
# the unique id (primary key) of the document, we won't support commas in
# tag paths
pathAllowedChars = r'[\:\.\-\w]'
pathComponentRegex = r'%s+' % pathAllowedChars

# Default charset
charset = "utf-8"

# Types for PUT/GET of primitive values.
# Note: this must be lower case (we compare lowercased incoming
# content-type headers against this string).
contentTypeForPrimitiveJSON = 'application/vnd.fluiddb.value+json'

# All the content types we're able to return for a FluidDB primitive value.
contentTypesForPrimitiveValue = (contentTypeForPrimitiveJSON,)

# How often (in seconds) we loop to dump dirty tags, namespaces, and
# the object table to the key-value store.
dumpInterval = 1800

# The host name of the machine offering the fluidDB API. This will offer
# a variety of APIs (HTTP, HTTPS, XMPP, facade via Thrift, etc).
#
# If you change this value, you also need to change the documentation
# in docs/example.com/sphinx/fluidDB/api/http.rst
fluidDBHost = 'fluiddb.example.com'

# Endpoint options for use with command line utils that use txFluidDB's
# endpoint class.
fluidDBEndpoint = 'http://%s/' % fluidDBHost
localEndpoint = 'http://localhost:%d/' % wsfePort

# Tag names the user creator uses to mark users' objects.
activationTokenTagName = u'activation-token'
createdAtTagName = u'created-at'
