Permissions
===========

Permissions in Fluidinfo are designed to be powerful and yet simple to
understand:

* Permissions are applied to namespaces and to tags.

* Applications attempt to carry out *actions* on these.

All possible actions are listed below.

Policies and their exceptions
-----------------------------

Permissions for each action are implemented as an overall policy (set to
either ``open`` or ``closed``), and a list of any exceptions to the
policy. A Fluidinfo API call is allowed to proceed if the permission for the
corresponding action has either

* an ``open`` policy, and the requesting user is not in the exceptions; or
* a ``closed`` policy, and the requesting user is in the exceptions.

Permissions are checked every time an application, on behalf of either a
user or itself, uses the Fluidinfo API to attempt to perform an action on a
namespace or tag.

Possible actions
----------------

The possible actions on namespaces and tags are as follows:

* Namespaces

 * **create** - create namespaces or tag names in a given namespace.
 * **update** - change the properties (e.g., description) of a namespace.
 * **delete** - delete the namespace, which must be empty.
 * **list** - see a list of contained namespaces and tag names.

* Tags (top-level actions)

 * **update** - change the overall properties of the tag, e.g., its description.
 * **delete** - delete the entire tag (and thus all its occurrences on objects).

* Tags (actions on tagged objects)

 * **write** - add a tag to an object, or change an exiting one.
 * **read** - read the value of a tag on an object.
 * **delete** - remove a tag from an object.

Setting permissions
-------------------

Finally, there is also a *control* action for every namespace and tag. Only
those users with control permission can change the policy or exception list
for other permissions (or for the control permission itself).

No permissions on objects
-------------------------

If you have not yet read :doc:`the description of Fluidinfo objects
<objects>`, you may be asking yourself about permissions on
objects. *Objects in Fluidinfo have no permissions.*
